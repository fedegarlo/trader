import os
from datetime import date

from trader import revolut

DATA = os.path.join(os.path.dirname(__file__), "data")


def _sample_events():
    events, warnings = revolut.parse_file(os.path.join(DATA, "sample.csv"))
    assert warnings == []
    return events


def test_parses_all_rows():
    events = _sample_events()
    assert len(events) == 7
    kinds = [ev.kind for ev in events]
    assert kinds == [
        revolut.TOPUP, revolut.BUY, revolut.BUY, revolut.SELL,
        revolut.DIVIDEND, revolut.FEE, revolut.TOPUP,
    ]


def test_money_and_dates():
    events = _sample_events()
    topup = events[0]
    assert topup.day == date(2026, 7, 1)
    assert topup.total == 1000.0
    buy = events[1]
    assert buy.ticker == "AAPL"
    assert buy.quantity == 2
    assert buy.total == 400.0


def test_parse_money_formats():
    assert revolut._parse_money("$1,234.56") == 1234.56
    assert revolut._parse_money("1.234,56 €") == 1234.56
    assert revolut._parse_money("-US$12.30") == -12.30
    assert revolut._parse_money("") == 0.0


def test_commission_classified_as_fee():
    # La comisión de una operación (confirmación de Revolut) debe restar
    # efectivo como FEE, no ignorarse: penaliza la rentabilidad.
    for raw in ("COMMISSION", "TRADING FEE", "STAMP DUTY"):
        assert revolut.classify(raw) == revolut.FEE
    csv_text = (
        "Date,Ticker,Type,Quantity,Price per share,Total Amount,Currency,FX Rate\n"
        "2026-07-21T13:52:41.000000Z,,COMMISSION,,,USD 1.49,USD,1.15\n"
    )
    events, warnings = revolut.parse_csv(csv_text)
    assert warnings == []
    assert len(events) == 1
    assert events[0].kind == revolut.FEE
    assert events[0].total == 1.49


def test_unknown_type_warns():
    csv_text = (
        "Date,Ticker,Type,Quantity,Price per share,Total Amount,Currency,FX Rate\n"
        "2026-07-01T09:00:00.000000Z,,SOMETHING WEIRD,,,$10.00,USD,1.00\n"
    )
    events, warnings = revolut.parse_csv(csv_text)
    assert events == []
    assert len(warnings) == 1
