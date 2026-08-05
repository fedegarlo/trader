"""Lectura del extracto **PDF** de Revolut ("Account Statement").

Además del CSV de la app (Inversiones -> Extractos), Revolut envía por correo
un PDF de cuenta con una tabla de movimientos por divisa::

    USD Transactions
    Date Symbol Type Quantity Price Side Value Fees Commission
    13 Jul 2026 14:28:11 GMT Cash top-up US$500 US$0 US$0
    13 Jul 2026 14:28:12 GMT NVDA Trade - Market 2.39789948 US$208.52 Buy US$500 US$0 US$0
    15 Jul 2026 22:11:43 GMT Cash withdrawal -US$17.66 US$0 US$0

Este módulo extrae ese texto y lo convierte al **mismo CSV** que exporta la
app, de modo que el resto del sistema (parser, cartera, ranking) no cambia y
lo que se guarda cifrado en ``players/<id>/trades.csv.enc`` sigue siendo un
CSV legible.

Sobre las columnas de dinero del PDF: ``Value`` es el efectivo que realmente
se mueve, ya con las comisiones aplicadas (en una compra, ``cantidad × precio
+ comisión``; en una venta, el neto después de ``Fees`` y ``Commission``). Por
eso se vuelca ``Value`` como ``Total Amount`` y **no** se generan filas de
comisión aparte: contarlas otra vez duplicaría el gasto.

El PDF cubre un periodo, no toda la historia de la cuenta, así que el
"Account summary" trae un saldo de partida. Si la cuenta empezaba el periodo
sin acciones, ese efectivo inicial se añade como un ingreso el primer día
(un flujo externo, que no puntúa) y el efectivo reconstruido cuadra con el
del extracto. Si empezaba **con** acciones, el PDF no dice cuáles, así que se
avisa: hace falta un extracto que cubra desde el principio.
"""

from __future__ import annotations

import csv
import io
import re

from .revolut import parse_money

CSV_HEADER = ["Date", "Ticker", "Type", "Quantity", "Price per share",
              "Total Amount", "Currency", "FX Rate"]


class PdfError(Exception):
    """El PDF no se puede leer o no es un extracto de Revolut."""


# Cabeceras de sección: "USD Transactions", "USD Account summary"…
_SECTION_RE = re.compile(
    r"^(?:(?P<currency>[A-Z]{3})\s+)?"
    r"(?P<name>Transactions|Account summary|Portfolio breakdown|Glossary)\s*$",
    re.IGNORECASE)
_TABLE_HEADER_RE = re.compile(r"^Date\s+Symbol\s+Type\b", re.IGNORECASE)

# "Positions Value US$0 US$4,402.62" / "Cash value* US$15 US$0.02" (inicio y fin)
_BALANCE_RE = re.compile(
    r"^(?P<what>Positions Value|Cash value)\*?\s+(?P<start>\S+)\s+\S+\s*$",
    re.IGNORECASE)
# "Period 01 Jul 2026 - 05 Aug 2026"
_PERIOD_RE = re.compile(
    r"^Period\s+(?P<day>\d{1,2})\s+(?P<month>[A-Za-z]{3,9})\.?\s+(?P<year>\d{4})\s*[-–]")

_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun",
     "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}

# "13 Jul 2026 14:28:11 GMT resto de la fila…" (la hora y la zona son opcionales)
_ROW_RE = re.compile(
    r"^(?P<day>\d{1,2})\s+(?P<month>[A-Za-z]{3,9})\.?\s+(?P<year>\d{4})"
    r"(?:\s+(?P<time>\d{1,2}:\d{2}(?::\d{2})?))?"
    r"(?:\s+[A-Z]{2,5})?"
    r"\s+(?P<rest>\S.*)$")

# Importe con símbolo delante: US$1,234.56 / -US$17.66 / €0 / £12.30 / 1.234,56
_MONEY_RE = re.compile(
    r"^-?(?:US\$|A\$|C\$|S\$|HK\$|R\$|NZ\$|\$|€|£|₺|zł|Kč|CHF|SEK|NOK|DKK|PLN|RON)?"
    r"-?\d[\d.,]*$")
# Símbolo de cotización: 1-8 caracteres en mayúsculas (BRK.B, RDS-A…)
_TICKER_RE = re.compile(r"^[A-Z][A-Z0-9]*(?:[.\-][A-Z0-9]+)*$")
_SIDES = {"buy": "BUY", "sell": "SELL"}


def looks_like_pdf(data: bytes) -> bool:
    """¿Los primeros bytes son los de un PDF?"""
    return data[:1024].lstrip()[:5].startswith(b"%PDF")


def extract_text(data: bytes) -> str:
    """Texto de todas las páginas del PDF, en orden."""
    try:
        from pypdf import PdfReader
    except ImportError as exc:                                # pragma: no cover
        raise PdfError("falta la dependencia 'pypdf' para leer extractos PDF") from exc

    try:
        reader = PdfReader(io.BytesIO(data))
        if getattr(reader, "is_encrypted", False):
            # Los extractos de Revolut van sin contraseña; algunos PDF traen
            # cifrado "vacío" que se abre con la contraseña en blanco.
            try:
                reader.decrypt("")
            except Exception as exc:
                raise PdfError("el PDF está protegido con contraseña") from exc
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    except PdfError:
        raise
    except Exception as exc:
        raise PdfError(f"no se puede leer el PDF ({exc})") from exc


def _parse_day(day: str, month: str, year: str) -> str | None:
    """'13', 'Jul', '2026' -> '2026-07-13' (o ``None`` si el mes no existe)."""
    number = _MONTHS.get(month[:3].lower())
    if number is None:
        return None
    return f"{int(year):04d}-{number:02d}-{int(day):02d}"


def _split_row(rest: str) -> tuple[str | None, str, str, str, str] | None:
    """Descompone la parte de la fila que sigue a la fecha.

    Devuelve ``(ticker, tipo, cantidad, precio, importe)`` o ``None`` si la
    línea no tiene la forma de un movimiento.
    """
    tokens = rest.split()
    if not tokens:
        return None

    side_at = next((i for i, tok in enumerate(tokens) if tok.lower() in _SIDES), None)
    if side_at is not None:
        # SÍMBOLO Tipo… Cantidad Precio Lado Importe [Fees] [Commission]
        head, tail = tokens[:side_at], tokens[side_at + 1:]
        if len(head) < 3 or not tail or not _MONEY_RE.match(tail[0]):
            return None
        quantity, price = head[-2], head[-1]
        type_tokens = head[:-2]
        total = tail[0]
        side = _SIDES[tokens[side_at].lower()]
    else:
        # [SÍMBOLO] Tipo… Importe [Fees] [Commission]
        money_at = len(tokens)
        while money_at > 0 and _MONEY_RE.match(tokens[money_at - 1]) and \
                len(tokens) - money_at < 3:
            money_at -= 1
        if money_at == 0 or money_at == len(tokens):
            return None
        type_tokens = tokens[:money_at]
        quantity = price = ""
        total = tokens[money_at]
        side = None

    ticker = None
    if type_tokens and _TICKER_RE.match(type_tokens[0]) and len(type_tokens) > 1:
        ticker, type_tokens = type_tokens[0], type_tokens[1:]
    if not type_tokens:
        return None

    kind = " ".join(type_tokens).upper()
    if side:
        # "Trade - Market" + Buy -> "BUY - MARKET" (lo que emite el CSV).
        order = kind.replace("TRADE", "", 1).strip(" -") or "MARKET"
        kind = f"{side} - {order}"
    return ticker, kind, quantity, price, total


def _opening_rows(balances: dict[str, dict[str, float]], period_start: str | None,
                  rows: list[list[str]], warnings: list[str]) -> list[list[str]]:
    """Filas de apertura con el efectivo con el que arranca el extracto."""
    opening: list[list[str]] = []
    for currency, balance in balances.items():
        cash = balance.get("cash value", 0.0)
        positions = balance.get("positions value", 0.0)
        if positions > 0.005:
            warnings.append(
                f"El extracto {currency} empieza con acciones ya compradas "
                f"({currency} {positions:,.2f}): manda un extracto que cubra "
                "desde tu primera operación o la cartera saldrá incompleta.")
            continue
        if abs(cash) < 0.005:
            continue
        first = next((row[0] for row in rows if row[6] == currency), None)
        day = period_start or (first.split(" ", 1)[0] if first else None)
        if day is None:
            continue
        kind = "CASH TOP-UP" if cash > 0 else "CASH WITHDRAWAL"
        opening.append([day, "", kind, "", "", f"{cash:.2f}", currency, ""])
    return opening


def statement_to_csv(text: str) -> tuple[str, list[str]]:
    """Convierte el texto de un extracto PDF al CSV que exporta la app.

    Devuelve ``(csv, avisos)``. Lanza :class:`PdfError` si el texto no tiene
    ninguna tabla de movimientos (es decir, no es un extracto de Revolut).
    """
    rows: list[list[str]] = []
    warnings: list[str] = []
    balances: dict[str, dict[str, float]] = {}
    period_start: str | None = None
    section = currency = None
    tables = 0

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue

        header = _SECTION_RE.match(line)
        if header:
            section = header.group("name").lower()
            currency = (header.group("currency") or "").upper() or None
            if section == "transactions" and currency:
                tables += 1
            continue

        if period_start is None:
            period = _PERIOD_RE.match(line)
            if period:
                period_start = _parse_day(period.group("day"), period.group("month"),
                                          period.group("year"))
                continue

        if section == "account summary" and currency:
            balance = _BALANCE_RE.match(line)
            if balance:
                balances.setdefault(currency, {})[balance.group("what").lower()] = \
                    parse_money(balance.group("start"))
            continue

        if section != "transactions" or not currency or _TABLE_HEADER_RE.match(line):
            continue

        row = _ROW_RE.match(line)
        if not row:
            continue                      # cabeceras, pies de página, direcciones…
        day = _parse_day(row.group("day"), row.group("month"), row.group("year"))
        if day is None:
            continue
        parts = _split_row(row.group("rest"))
        if parts is None:
            warnings.append(f"Movimiento no interpretable: {line}")
            continue
        ticker, kind, quantity, price, total = parts
        stamp = f"{day} {row.group('time')}" if row.group("time") else day
        rows.append([stamp, ticker or "", kind, quantity, price, total, currency, ""])

    if not tables:
        raise PdfError("el PDF no parece un extracto de Revolut "
                       "(no tiene tabla de movimientos)")

    # Solo tiene sentido arrastrar el saldo inicial de las divisas con actividad.
    used = {row[6] for row in rows}
    rows = _opening_rows({c: b for c, b in balances.items() if c in used},
                         period_start, rows, warnings) + rows

    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(CSV_HEADER)
    writer.writerows(rows)
    return out.getvalue(), warnings


def pdf_to_csv(data: bytes) -> tuple[str, list[str]]:
    """Extracto PDF (bytes) -> CSV equivalente al de la app y avisos."""
    return statement_to_csv(extract_text(data))
