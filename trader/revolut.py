"""Parser del extracto de operaciones de Revolut (CSV).

Revolut exporta desde la app (Inversiones -> Extractos) un CSV con columnas:

    Date,Ticker,Type,Quantity,Price per share,Total Amount,Currency,FX Rate

Los tipos de operación observados en los extractos de Revolut incluyen:
BUY - MARKET, BUY - LIMIT, SELL - MARKET, SELL - LIMIT, SELL - STOP,
CASH TOP-UP, CASH WITHDRAWAL, DIVIDEND, CUSTODY FEE, COMMISSION,
STOCK SPLIT, TRANSFER FROM/TO... El parser es tolerante: normaliza cada
tipo a una de las categorías internas y avisa de las que no reconoce. Las
comisiones de operación (COMMISSION) se tratan como FEE: restan efectivo y
penalizan la rentabilidad (no son un flujo externo neutralizado).
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone


# Categorías internas de evento
BUY = "BUY"
SELL = "SELL"
TOPUP = "TOPUP"          # entrada de dinero externo (no cuenta como rentabilidad)
WITHDRAWAL = "WITHDRAWAL"  # salida de dinero externo
DIVIDEND = "DIVIDEND"
FEE = "FEE"
SPLIT = "SPLIT"


@dataclass(frozen=True)
class Event:
    """Una fila del extracto ya normalizada."""

    day: date
    kind: str
    ticker: str | None
    quantity: float
    total: float  # importe en la divisa del extracto, siempre >= 0
    currency: str
    # Instante exacto (UTC, sin tzinfo) si el extracto trae hora. El CSV de la
    # app la trae ("2026-08-05T13:35:16.400Z"); el PDF de cuenta, no. Solo se
    # usa para ordenar operaciones del mismo día: el cálculo diario no depende
    # de la hora.
    at: datetime | None = None


_TYPE_MAP = [
    (re.compile(r"^BUY\b"), BUY),
    (re.compile(r"^SELL\b"), SELL),
    (re.compile(r"^CASH TOP-?UP"), TOPUP),
    (re.compile(r"^(CASH WITHDRAWAL|WITHDRAWAL)"), WITHDRAWAL),
    (re.compile(r"^DIVIDEND"), DIVIDEND),
    (re.compile(r"^(CUSTODY FEE|SERVICE FEE|COMMISSION|TRADING FEE|STAMP DUTY|FEE)"), FEE),
    (re.compile(r"^STOCK SPLIT"), SPLIT),
    (re.compile(r"^TRANSFER FROM"), TOPUP),
    (re.compile(r"^TRANSFER TO"), WITHDRAWAL),
]

_MONEY_RE = re.compile(r"[^0-9.\-]")


def parse_money(raw: str) -> float:
    """Convierte '$1,234.56' / '-US$12.30' / '1.234,56 €' a float."""
    raw = (raw or "").strip()
    if not raw:
        return 0.0
    # Formato europeo "1.234,56": coma decimal (puede ir seguida del símbolo)
    if re.search(r",\d{1,2}\s*\D*$", raw) and not re.search(r"\.\d{1,2}\s*\D*$", raw):
        raw = raw.replace(".", "").replace(",", ".")
    else:
        raw = raw.replace(",", "")
    cleaned = _MONEY_RE.sub("", raw)
    return float(cleaned) if cleaned not in ("", "-", ".") else 0.0


_DATE_FORMATS = (
    # (formato, ¿trae hora?)
    ("%Y-%m-%dT%H:%M:%S.%f%z", True), ("%Y-%m-%dT%H:%M:%S%z", True),
    ("%Y-%m-%d %H:%M:%S", True), ("%Y-%m-%d", False),
    ("%d/%m/%Y %H:%M:%S", True), ("%d/%m/%Y", False),
)


def _to_utc(moment: datetime) -> datetime:
    """Instante en UTC y sin tzinfo, para poder comparar filas entre sí."""
    if moment.tzinfo is None:
        return moment
    return moment.astimezone(timezone.utc).replace(tzinfo=None)


def parse_moment(raw: str) -> tuple[date, datetime | None]:
    """``(día, instante)`` de la fecha de una fila del extracto.

    El instante es ``None`` cuando la fila solo trae el día (el PDF de cuenta,
    por ejemplo). Sirve para ordenar dos operaciones del mismo día.
    """
    raw = raw.strip()
    for fmt, has_time in _DATE_FORMATS:
        try:
            moment = datetime.strptime(raw.replace("Z", "+0000"), fmt)
        except ValueError:
            continue
        return moment.date(), _to_utc(moment) if has_time else None
    # ISO genérico como último recurso
    moment = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    return moment.date(), _to_utc(moment) if ":" in raw else None


def _parse_date(raw: str) -> date:
    return parse_moment(raw)[0]


def classify(raw_type: str) -> str | None:
    upper = raw_type.strip().upper()
    for pattern, kind in _TYPE_MAP:
        if pattern.search(upper):
            return kind
    return None


def parse_csv(text: str) -> tuple[list[Event], list[str]]:
    """Parsea el contenido de un extracto. Devuelve (eventos, avisos)."""
    events: list[Event] = []
    warnings: list[str] = []
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        return [], ["CSV vacío"]

    fields = {name.strip().lower(): name for name in reader.fieldnames}

    def col(row: dict, *names: str) -> str:
        for name in names:
            key = fields.get(name)
            if key is not None and row.get(key):
                return row[key]
        return ""

    for lineno, row in enumerate(reader, start=2):
        raw_type = col(row, "type")
        if not raw_type:
            continue
        kind = classify(raw_type)
        if kind is None:
            warnings.append(f"Línea {lineno}: tipo no reconocido '{raw_type}', ignorada")
            continue
        try:
            day, at = parse_moment(col(row, "date"))
        except ValueError:
            warnings.append(f"Línea {lineno}: fecha no válida '{col(row, 'date')}', ignorada")
            continue
        events.append(Event(
            day=day,
            kind=kind,
            ticker=(col(row, "ticker") or None),
            quantity=parse_money(col(row, "quantity")),
            total=abs(parse_money(col(row, "total amount", "total"))),
            currency=col(row, "currency") or "USD",
            at=at,
        ))

    events.sort(key=lambda ev: ev.day)
    return events, warnings


def parse_file(path: str) -> tuple[list[Event], list[str]]:
    with open(path, encoding="utf-8-sig") as fh:
        return parse_csv(fh.read())
