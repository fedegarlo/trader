import pytest

from pdfbuild import make_pdf
from trader import revolut, revolut_pdf

# Extracto de cuenta de Revolut ("Account Statement"), con el mismo formato que
# el PDF que llega por correo pero con datos inventados.
STATEMENT = [
    "Account Statement",
    "Generated on the 05 Aug 2026",
    "Jugadora de Prueba",
    "Calle Falsa 123",
    "Madrid",
    "ES",
    "Period 01 Jul 2026 - 05 Aug 2026",
    "Account name Jugadora de Prueba",
    "Account number XX00XX00XX00",
    "USD Account summary",
    "Starting Ending",
    "Positions Value US$0 US$1,113.79",
    "Cash value* US$15 US$594.79",
    "Total US$15 US$1,708.58",
    "USD Portfolio breakdown",
    "Symbol Company ISIN Quantity Price Value % of Portfolio",
    "NVDA NVIDIA US67066G1040 2.39789948 US$211.94 US$508.21 45.63%",
    "SAP SAP US8030542042 3 US$201.86 US$605.58 54.37%",
    "Positions Value US$1,113.79 65.19%",
    "Cash value US$594.79 34.81%",
    "Total US$1,708.58",
    "USD Transactions",
    "Date Symbol Type Quantity Price Side Value Fees Commission",
    "13 Jul 2026 14:28:11 GMT Cash top-up US$500 US$0 US$0",
    "13 Jul 2026 14:28:12 GMT NVDA Trade - Market 2.39789948 US$208.52 Buy US$500 US$0 US$0",
    "15 Jul 2026 22:11:43 GMT Cash withdrawal -US$17.66 US$0 US$0",
    "21 Jul 2026 13:52:40 GMT Cash top-up US$1,142.85 US$0 US$0",
    "21 Jul 2026 13:52:41 GMT SAP Trade - Limit 6 US$190 Buy US$1,142.85 US$0 US$2.85",
    "04 Aug 2026 15:37:16 GMT SAP Trade - Market 3 US$199.90 Sell US$597.15 US$0.03 US$2.52",
    "05 Aug 2026 09:00:00 GMT NVDA Dividend US$0.30 US$0 US$0",
    "EUR Account summary",
    "Starting Ending",
    "Positions Value €0 €0",
    "Cash value* €0 €0",
    "EUR Transactions",
    "Date Symbol Type Quantity Price Side Value Fees Commission",
    "Glossary",
    "Transactions",
    "A chronological list of all financial activity within a specific period.",
]


def _events(lines=None):
    csv_text, warnings = revolut_pdf.pdf_to_csv(make_pdf(lines or STATEMENT))
    events, csv_warnings = revolut.parse_csv(csv_text)
    assert csv_warnings == []          # el CSV generado se parsea sin quejas
    return events, warnings


# ----- conversión a CSV -----

def test_pdf_to_csv_produces_canonical_header():
    csv_text, _ = revolut_pdf.pdf_to_csv(make_pdf(STATEMENT))
    assert csv_text.splitlines()[0] == ",".join(revolut_pdf.CSV_HEADER)


def test_trades_keep_side_ticker_quantity_and_cash_value():
    events, _ = _events()
    buys = [ev for ev in events if ev.kind == revolut.BUY]
    assert [ev.ticker for ev in buys] == ["NVDA", "SAP"]
    assert buys[0].quantity == pytest.approx(2.39789948)
    assert buys[0].total == pytest.approx(500)          # columna Value
    # En una compra, Value ya incluye la comisión (6 × 190 + 2.85).
    assert buys[1].total == pytest.approx(1142.85)

    sell = next(ev for ev in events if ev.kind == revolut.SELL)
    assert sell.ticker == "SAP" and sell.quantity == pytest.approx(3)
    assert sell.total == pytest.approx(597.15)          # neto de fees y comisión


def test_cash_movements_and_dividend():
    events, _ = _events()
    kinds = [ev.kind for ev in events]
    assert kinds.count(revolut.TOPUP) == 3              # dos del extracto + saldo inicial
    withdrawal = next(ev for ev in events if ev.kind == revolut.WITHDRAWAL)
    assert withdrawal.total == pytest.approx(17.66)     # el signo no importa
    dividend = next(ev for ev in events if ev.kind == revolut.DIVIDEND)
    assert dividend.total == pytest.approx(0.30) and dividend.ticker == "NVDA"


def test_opening_cash_balance_reconciles_with_statement():
    from trader.portfolio import _positions_at

    events, warnings = _events()
    positions, cash = _positions_at(events, max(ev.day for ev in events))
    assert warnings == []
    # El extracto empieza con US$15 en efectivo: sin esa fila de apertura el
    # efectivo reconstruido no cuadraría con el US$594.79 final del PDF.
    assert cash == pytest.approx(594.79)
    assert positions == {"NVDA": pytest.approx(2.39789948), "SAP": pytest.approx(3)}


def test_warns_when_statement_starts_with_open_positions():
    lines = [l.replace("Positions Value US$0 US$1,113.79",
                       "Positions Value US$900 US$1,113.79") for l in STATEMENT]
    events, warnings = _events(lines)
    assert any("empieza con acciones" in w for w in warnings)
    # No se inventa efectivo de apertura: la cartera de partida es desconocida.
    assert sum(1 for ev in events if ev.kind == revolut.TOPUP) == 2


def test_currency_comes_from_each_section():
    events, _ = _events()
    assert {ev.currency for ev in events} == {"USD"}    # la sección EUR va vacía


def test_dates_do_not_depend_on_locale():
    events, _ = _events()
    assert min(ev.day for ev in events).isoformat() == "2026-07-01"   # inicio del periodo
    assert max(ev.day for ev in events).isoformat() == "2026-08-05"


def test_glossary_and_page_furniture_are_ignored():
    events, warnings = _events()
    assert len(events) == 8 and warnings == []


# ----- errores -----

def test_rejects_pdf_without_transactions_table():
    with pytest.raises(revolut_pdf.PdfError):
        revolut_pdf.pdf_to_csv(make_pdf(["Factura de la luz", "Total 42,00 €"]))


def test_rejects_unreadable_pdf():
    with pytest.raises(revolut_pdf.PdfError):
        revolut_pdf.pdf_to_csv(b"%PDF-1.4 esto no es un PDF")


def test_cli_encrypt_converts_pdf_before_encrypting(tmp_path):
    from trader import secretbox
    from trader.__main__ import main

    src = tmp_path / "extracto.pdf"
    src.write_bytes(make_pdf(STATEMENT))
    out = tmp_path / "trades.csv.enc"
    main(["encrypt", str(src), "--out", str(out), "--key", "clave-liga"])
    stored = secretbox.decrypt_file(str(out), "clave-liga").decode()
    assert stored.startswith("Date,Ticker,Type,") and "BUY - MARKET" in stored


def test_looks_like_pdf():
    assert revolut_pdf.looks_like_pdf(make_pdf(["x"]))
    assert not revolut_pdf.looks_like_pdf(b"Date,Ticker,Type\n")
