from trader.tickers import ticker_meta


def test_known_ticker_has_name_domain_and_peers():
    meta = ticker_meta("AAPL")
    assert meta["name"] == "Apple"
    assert meta["domain"] == "apple.com"
    assert isinstance(meta["peers"], list) and meta["peers"]  # tiene relacionados


def test_lookup_is_case_insensitive():
    assert ticker_meta("msft")["name"] == "Microsoft"
    assert ticker_meta("msft")["peers"] == ticker_meta("MSFT")["peers"]


def test_unknown_ticker_falls_back_to_symbol():
    meta = ticker_meta("ZZZZ")
    assert meta == {"name": "ZZZZ", "domain": "", "peers": []}
