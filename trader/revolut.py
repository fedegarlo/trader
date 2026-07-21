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
from datetime import date, datetime


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


def _parse_money(raw: str) -> float:
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


def _parse_date(raw: str) -> date:
    raw = raw.strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z",
                "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw.replace("Z", "+0000"), fmt).date()
        except ValueError:
            continue
    # ISO genérico como último recurso
    return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()


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
            day = _parse_date(col(row, "date"))
        except ValueError:
            warnings.append(f"Línea {lineno}: fecha no válida '{col(row, 'date')}', ignorada")
            continue
        events.append(Event(
            day=day,
            kind=kind,
            ticker=(col(row, "ticker") or None),
            quantity=_parse_money(col(row, "quantity")),
            total=abs(_parse_money(col(row, "total amount", "total"))),
            currency=col(row, "currency") or "USD",
        ))

    events.sort(key=lambda ev: ev.day)
    return events, warnings


def parse_file(path: str) -> tuple[list[Event], list[str]]:
    with open(path, encoding="utf-8-sig") as fh:
        return parse_csv(fh.read())
