import json
import urllib.error
from datetime import date

import pytest

from trader import prices
from trader.prices import PriceCache, PriceError


def _chart_payload(day: date, close: float) -> bytes:
    ts = int(__import__("datetime").datetime(day.year, day.month, day.day).timestamp())
    return json.dumps({
        "chart": {"result": [{
            "timestamp": [ts],
            "indicators": {"quote": [{"close": [close]}]},
        }]}
    }).encode()


class _Resp:
    def __init__(self, body: bytes):
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_fetch_reintenta_y_cae_a_otro_host(monkeypatch, tmp_path):
    """Un 400 transitorio no debe abortar: se reintenta y acaba funcionando."""
    calls = []

    def fake_urlopen(req, timeout=0):
        calls.append(req.full_url)
        if len(calls) == 1:  # primer intento falla con 400
            raise urllib.error.HTTPError(req.full_url, 400, "Bad Request", {}, None)
        return _Resp(_chart_payload(date(2026, 7, 14), 100.0))

    monkeypatch.setattr(prices.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(prices.time, "sleep", lambda s: None)

    cache = PriceCache(cache_dir=str(tmp_path))
    cache.ensure_range("MU", date(2026, 7, 14), date(2026, 7, 14))

    assert len(calls) == 2
    assert "query1" in calls[0] and "query2" in calls[1]  # alterna de host
    assert cache.close_on("MU", date(2026, 7, 14)) == 100.0


def test_fetch_falla_tras_agotar_reintentos(monkeypatch, tmp_path):
    def always_400(req, timeout=0):
        raise urllib.error.HTTPError(req.full_url, 400, "Bad Request", {}, None)

    monkeypatch.setattr(prices.urllib.request, "urlopen", always_400)
    monkeypatch.setattr(prices.time, "sleep", lambda s: None)

    cache = PriceCache(cache_dir=str(tmp_path))
    with pytest.raises(PriceError):
        cache.ensure_range("MU", date(2026, 7, 14), date(2026, 7, 14))


def test_refresh_fallido_usa_la_cache_si_cubre_el_rango(monkeypatch, tmp_path):
    """Con --refresh, si Yahoo falla pero la caché ya cubre el rango, se sigue."""
    (tmp_path / "WDC.csv").write_text("date,close\n2026-07-14,50.0\n")

    def always_400(req, timeout=0):
        raise urllib.error.HTTPError(req.full_url, 400, "Bad Request", {}, None)

    monkeypatch.setattr(prices.urllib.request, "urlopen", always_400)
    monkeypatch.setattr(prices.time, "sleep", lambda s: None)

    cache = PriceCache(cache_dir=str(tmp_path), refresh=True)
    # No lanza pese al fallo de red: la caché cubre el día pedido.
    cache.ensure_range("WDC", date(2026, 7, 14), date(2026, 7, 14))
    assert cache.close_on("WDC", date(2026, 7, 14)) == 50.0
