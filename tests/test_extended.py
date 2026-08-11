"""Cotización fuera de horario (pre-market / after-hours) de Yahoo."""

from trader.extended import STALE_SECONDS, parse_quote

NOW = 1_800_000_000.0


def _payload(price):
    return {"quoteSummary": {"result": [{"price": price}]}}


def test_post_market_percent_is_computed_against_the_regular_close():
    q = parse_quote(_payload({
        "marketState": "POST",
        "regularMarketPrice": 200.0,
        "regularMarketPreviousClose": 190.0,
        "postMarketPrice": 202.0,
        "postMarketTime": NOW - 60,
        "currency": "USD",
    }), now=NOW)
    assert q["session"] == "post"
    assert q["price"] == 202.0
    assert q["pct"] == 1.0          # 202 / 200 - 1
    assert q["regular"] == 200.0
    assert q["regularPct"] == 5.26  # 200 / 190 - 1, la sesión regular del día
    assert q["currency"] == "USD"


def test_pre_market_uses_the_previous_close_as_reference():
    # Antes de abrir, ``regularMarketPrice`` sigue siendo el cierre de ayer:
    # es exactamente la referencia contra la que se lee un pre-market.
    q = parse_quote(_payload({
        "marketState": "PRE",
        "regularMarketPrice": 100.0,
        "preMarketPrice": 98.5,
        "preMarketTime": NOW - 300,
    }), now=NOW)
    assert q["session"] == "pre"
    assert q["pct"] == -1.5


def test_yahoo_raw_wrapper_is_accepted():
    q = parse_quote(_payload({
        "marketState": "POST",
        "regularMarketPrice": {"raw": 50.0, "fmt": "50.00"},
        "postMarketPrice": {"raw": 51.0, "fmt": "51.00"},
        "postMarketTime": {"raw": NOW},
    }), now=NOW)
    assert q["pct"] == 2.0


def test_regular_session_has_no_extended_data():
    q = parse_quote(_payload({
        "marketState": "REGULAR",
        "regularMarketPrice": 100.0,
        "postMarketPrice": 120.0,   # resto de la sesión anterior: se ignora
        "postMarketTime": NOW,
    }), now=NOW)
    assert q["session"] is None
    assert "price" not in q and "pct" not in q
    assert q["regular"] == 100.0


def test_closed_market_has_no_extended_data():
    # CLOSED es la noche cerrada / el fin de semana: no hay sesión extendida en
    # curso, así que no se enseña nada aunque Yahoo arrastre un postMarketPrice.
    q = parse_quote(_payload({
        "marketState": "CLOSED",
        "regularMarketPrice": 100.0,
        "postMarketPrice": 101.0,
        "postMarketTime": NOW,
    }), now=NOW)
    assert q["session"] is None


def test_stale_quote_is_dropped():
    q = parse_quote(_payload({
        "marketState": "POST",
        "regularMarketPrice": 100.0,
        "postMarketPrice": 101.0,
        "postMarketTime": NOW - STALE_SECONDS - 1,
    }), now=NOW)
    assert q["session"] is None
    assert q["regular"] == 100.0


def test_percent_falls_back_to_yahoo_when_no_regular_price():
    # Sin precio regular no se puede calcular el %: se usa el de Yahoo, que
    # llega en tanto por uno.
    q = parse_quote(_payload({
        "marketState": "PRE",
        "preMarketPrice": 12.0,
        "preMarketChangePercent": 0.0325,
        "preMarketTime": NOW,
    }), now=NOW)
    assert q["session"] == "pre"
    assert q["pct"] == 3.25


def test_returns_none_when_there_is_nothing_to_show():
    assert parse_quote(_payload({"marketState": "REGULAR"}), now=NOW) is None
    assert parse_quote({"quoteSummary": {"result": []}}) is None
    assert parse_quote({}) is None
