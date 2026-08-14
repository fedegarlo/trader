"""Titulares por ticker: normalización, caché y tolerancia a fallos de la API."""

import json
from datetime import date

import pytest

from trader import news as news_mod
from trader.news import NewsCache, normalize_item, normalize_items, parse_response


def _item(title="Apple presenta resultados", link="https://finance.yahoo.com/news/a",
          **extra):
    return {"title": title, "link": link, **extra}


def _response(*results, invalid=None, error=None):
    return {
        "success": error is None,
        "provider": "yahoo",
        "timezone": "Europe/Madrid",
        "totalNews": sum(len(r.get("news") or []) for r in results),
        "results": list(results),
        "invalidTickers": invalid or [],
        "error": error,
    }


def _result(ticker, news, error=None):
    return {"ticker": ticker, "count": len(news), "cached": False,
            "stale": False, "error": error, "news": news}


# ---- normalización ---------------------------------------------------------

def test_normalize_keeps_the_useful_fields():
    item = normalize_item(_item(
        description="La compañía supera las previsiones.",
        publishedAt="2026-08-14T13:05:00.000Z", source="Yahoo Finance"))
    assert item == {
        "title": "Apple presenta resultados",
        "link": "https://finance.yahoo.com/news/a",
        "source": "Yahoo Finance",
        "at": "2026-08-14T13:05:00.000Z",
        "desc": "La compañía supera las previsiones.",
    }


def test_normalize_needs_title_and_link():
    assert normalize_item(_item(title="  ")) is None
    assert normalize_item({"title": "Sin enlace"}) is None
    assert normalize_item("no soy un dict") is None


def test_normalize_rejects_non_http_links():
    # La página abre estos enlaces tal cual: solo http(s), nunca javascript:.
    assert normalize_item(_item(link="javascript:alert(1)")) is None
    assert normalize_item(_item(link="data:text/html,<script>")) is None
    assert normalize_item(_item(link="http://example.com/x"))["link"] == "http://example.com/x"


def test_normalize_trims_long_texts_and_collapses_spaces():
    item = normalize_item(_item(title="A" * 500, description="hola\n\n  mundo"))
    assert len(item["title"]) == news_mod.MAX_TITLE and item["title"].endswith("…")
    assert item["desc"] == "hola mundo"


def test_normalize_drops_description_equal_to_the_title():
    item = normalize_item(_item(description="Apple presenta resultados"))
    assert "desc" not in item


def test_normalize_items_dedupes_and_sorts_newest_first():
    items = normalize_items([
        _item(title="vieja", link="https://x/1", publishedAt="2026-08-10T09:00:00Z"),
        _item(title="nueva", link="https://x/2", publishedAt="2026-08-14T09:00:00Z"),
        _item(title="repetida", link="https://x/1", publishedAt="2026-08-12T09:00:00Z"),
        _item(title="sin fecha", link="https://x/3"),
    ])
    assert [i["title"] for i in items] == ["nueva", "vieja", "sin fecha"]


def test_normalize_items_honours_the_limit():
    raws = [_item(link=f"https://x/{i}") for i in range(10)]
    assert len(normalize_items(raws, limit=3)) == 3


# ---- respuesta de la API ---------------------------------------------------

def test_parse_response_groups_by_ticker():
    payload = _response(
        _result("AAPL", [_item(link="https://x/1"), _item(link="https://x/2")]),
        _result("TSLA", [_item(link="https://x/3")]))
    news, warnings = parse_response(payload)
    assert list(news) == ["AAPL", "TSLA"]
    assert len(news["AAPL"]) == 2 and news["TSLA"][0]["link"] == "https://x/3"
    assert warnings == []


def test_parse_response_reports_errors_without_losing_the_rest():
    payload = _response(
        _result("AAPL", [_item(link="https://x/1")]),
        _result("ZZZZ", [], error="ticker desconocido"),
        invalid=["no-existe"])
    news, warnings = parse_response(payload)
    assert list(news) == ["AAPL"]  # el ticker sin noticias no aparece
    assert any("ZZZZ" in w for w in warnings)
    assert any("no-existe" in w for w in warnings)


def test_parse_response_survives_garbage():
    assert parse_response(None) == ({}, ["respuesta de la API de noticias que no "
                                         "es un objeto JSON"])
    news, warnings = parse_response({"success": False, "error": "boom"})
    assert news == {} and warnings and "boom" in warnings[0]


# ---- caché y descarga ------------------------------------------------------

class _Api:
    """API de noticias de mentira: registra los lotes que se le piden."""

    def __init__(self, news_by_ticker=None, fail=False):
        self.news_by_ticker = news_by_ticker or {}
        self.fail = fail
        self.calls = []

    def __call__(self, tickers):
        self.calls.append(list(tickers))
        if self.fail:
            raise OSError("sin red")
        return _response(*[_result(t, self.news_by_ticker.get(t, []))
                           for t in tickers])


def _cache(tmp_path, api, **kw):
    cache = NewsCache(cache_dir=str(tmp_path / "news"),
                      today=date(2026, 8, 14), **kw)
    cache._post = api
    return cache


def test_fetch_all_downloads_and_caches(tmp_path):
    api = _Api({"AAPL": [_item(link="https://x/1")]})
    cache = _cache(tmp_path, api)
    news = cache.fetch_all(["AAPL", "TSLA"])

    assert api.calls == [["AAPL", "TSLA"]]  # una sola petición en lote
    assert list(news) == ["AAPL"]           # TSLA no tenía titulares
    saved = json.loads((tmp_path / "news" / "AAPL.json").read_text("utf-8"))
    assert saved["asOf"] == "2026-08-14"
    assert saved["items"][0]["link"] == "https://x/1"


def test_cache_of_the_day_avoids_a_second_request(tmp_path):
    api = _Api({"AAPL": [_item(link="https://x/1")]})
    _cache(tmp_path, api).fetch_all(["AAPL"])

    again = _Api({"AAPL": [_item(link="https://x/2")]})
    news = _cache(tmp_path, again).fetch_all(["AAPL"])
    assert again.calls == []
    assert news["AAPL"][0]["link"] == "https://x/1"


def test_stale_cache_is_refetched(tmp_path):
    api = _Api({"AAPL": [_item(link="https://x/1")]})
    _cache(tmp_path, api).fetch_all(["AAPL"])

    # Al día siguiente los titulares de ayer ya no valen: se vuelven a pedir.
    tomorrow = NewsCache(cache_dir=str(tmp_path / "news"), today=date(2026, 8, 15))
    tomorrow._post = _Api({"AAPL": [_item(link="https://x/2")]})
    assert tomorrow.fetch_all(["AAPL"])["AAPL"][0]["link"] == "https://x/2"


def test_refresh_forces_a_new_request(tmp_path):
    _cache(tmp_path, _Api({"AAPL": [_item(link="https://x/1")]})).fetch_all(["AAPL"])
    api = _Api({"AAPL": [_item(link="https://x/2")]})
    news = _cache(tmp_path, api, refresh=True).fetch_all(["AAPL"])
    assert api.calls == [["AAPL"]]
    assert news["AAPL"][0]["link"] == "https://x/2"


def test_api_failure_falls_back_to_the_cache(tmp_path, capsys):
    _cache(tmp_path, _Api({"AAPL": [_item(link="https://x/1")]})).fetch_all(["AAPL"])
    cache = _cache(tmp_path, _Api(fail=True), refresh=True)
    news = cache.fetch_all(["AAPL"])
    assert news["AAPL"][0]["link"] == "https://x/1"     # se sirve la caché
    assert "AVISO" in capsys.readouterr().err           # y se avisa


def test_api_failure_without_cache_is_not_fatal(tmp_path):
    assert _cache(tmp_path, _Api(fail=True)).fetch_all(["AAPL"]) == {}


def test_offline_never_touches_the_network(tmp_path):
    api = _Api({"AAPL": [_item(link="https://x/1")]})
    assert _cache(tmp_path, api, offline=True).fetch_all(["AAPL"]) == {}
    assert api.calls == []


def test_offline_still_serves_the_cache(tmp_path):
    _cache(tmp_path, _Api({"AAPL": [_item(link="https://x/1")]})).fetch_all(["AAPL"])
    api = _Api(fail=True)
    news = _cache(tmp_path, api, offline=True).fetch_all(["AAPL"])
    assert news["AAPL"][0]["link"] == "https://x/1" and api.calls == []


def test_invalid_symbols_are_not_sent(tmp_path, capsys):
    api = _Api({"AAPL": [_item(link="https://x/1")]})
    _cache(tmp_path, api).fetch_all(["AAPL", "aapl us", ""])
    assert api.calls == [["AAPL"]]
    assert "aapl us" in capsys.readouterr().err


@pytest.mark.parametrize("ticker", ["AAPL", "BRK.B", "^GSPC", "BTC-USD"])
def test_accepted_ticker_formats(ticker, tmp_path):
    api = _Api()
    _cache(tmp_path, api).fetch_all([ticker])
    assert api.calls == [[ticker]]


def test_requests_are_batched(tmp_path):
    api = _Api()
    tickers = [f"T{i:03d}" for i in range(45)]
    _cache(tmp_path, api).fetch_all(tickers)
    assert [len(c) for c in api.calls] == [news_mod.BATCH, news_mod.BATCH, 5]


def test_limit_zero_disables_the_news(tmp_path):
    api = _Api({"AAPL": [_item(link="https://x/1")]})
    assert _cache(tmp_path, api, limit=0).fetch_all(["AAPL"]) == {}
    assert api.calls == []


def test_limit_caps_what_reaches_the_page(tmp_path):
    api = _Api({"AAPL": [_item(link=f"https://x/{i}") for i in range(8)]})
    news = _cache(tmp_path, api, limit=3).fetch_all(["AAPL"])
    assert len(news["AAPL"]) == 3


def test_request_body_carries_tickers_limit_and_timezone(tmp_path, monkeypatch):
    sent = {}

    class _Resp:
        def read(self):
            return json.dumps(_response(_result("AAPL", []))).encode()

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def fake_urlopen(req, timeout=None):
        sent["url"] = req.full_url
        sent["method"] = req.get_method()
        sent["body"] = json.loads(req.data.decode("utf-8"))
        sent["type"] = req.get_header("Content-type")
        return _Resp()

    monkeypatch.setattr(news_mod.urllib.request, "urlopen", fake_urlopen)
    NewsCache(cache_dir=str(tmp_path / "news"), endpoint="http://api.test/news",
              limit=5).fetch_all(["AAPL"])

    assert sent["url"] == "http://api.test/news" and sent["method"] == "POST"
    assert sent["type"] == "application/json"
    assert sent["body"] == {"tickers": ["AAPL"], "limit": 5,
                            "timezone": "Europe/Madrid"}


def test_endpoint_comes_from_the_environment(monkeypatch):
    monkeypatch.setenv("TRADER_NEWS_API", "http://otro/news")
    assert NewsCache().endpoint == "http://otro/news"
    monkeypatch.delenv("TRADER_NEWS_API")
    assert NewsCache().endpoint == news_mod.DEFAULT_ENDPOINT
