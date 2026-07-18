from trader.tickers import ticker_meta


def test_known_ticker_has_name_and_domain():
    meta = ticker_meta("AAPL")
    assert meta == {"name": "Apple", "domain": "apple.com"}


def test_lookup_is_case_insensitive():
    assert ticker_meta("msft")["name"] == "Microsoft"


def test_unknown_ticker_falls_back_to_symbol():
    meta = ticker_meta("ZZZZ")
    assert meta == {"name": "ZZZZ", "domain": ""}
