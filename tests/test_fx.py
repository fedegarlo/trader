"""Cambio a euros del módulo del objetivo (trader/fx.py).

Todo con caché en disco: no se toca la red en los tests, igual que el resto
del proyecto.
"""

from datetime import date

from trader import fx
from trader.prices import PriceCache


def _cache(tmp_path, symbol, rows):
    (tmp_path / f"{symbol}.csv").write_text(
        "date,close\n" + "".join(f"{d},{c}\n" for d, c in rows), encoding="utf-8")
    return PriceCache(cache_dir=str(tmp_path), offline=True)


def test_symbol_is_the_yahoo_pair_against_the_euro():
    assert fx.symbol_for("USD") == "EURUSD=X"
    assert fx.symbol_for("gbp") == "EURGBP=X"


def test_euro_needs_no_conversion():
    prices = PriceCache(cache_dir="/nonexistent", offline=True)
    assert fx.rate_to_eur(prices, "EUR", date(2026, 8, 13)) == 1.0
    assert fx.rate_to_eur(prices, "eur", date(2026, 8, 13)) == 1.0
    # sin divisa declarada se asume euro (no se inventa un cambio)
    assert fx.rate_to_eur(prices, "", date(2026, 8, 13)) == 1.0


def test_rate_is_the_inverse_of_the_yahoo_pair(tmp_path):
    # Yahoo publica EURUSD=X como «1 EUR = 1,1791 USD»; queremos euros por dólar.
    prices = _cache(tmp_path, "EURUSD=X", [("2026-08-13", "1.1791")])
    rate = fx.rate_to_eur(prices, "USD", date(2026, 8, 13))
    assert round(rate, 6) == round(1 / 1.1791, 6)
    assert round(5895.4 * rate) == 5000        # el caso que motivó todo esto


def test_rate_falls_back_to_the_last_close(tmp_path):
    # Fin de semana: vale el cierre anterior, como con cualquier precio.
    prices = _cache(tmp_path, "EURUSD=X", [("2026-08-13", "1.1791")])
    assert fx.rate_to_eur(prices, "USD", date(2026, 8, 15)) is not None


def test_no_rate_returns_none_instead_of_guessing(tmp_path):
    prices = PriceCache(cache_dir=str(tmp_path), offline=True)
    assert fx.rate_to_eur(prices, "USD", date(2026, 8, 13)) is None


def test_zero_or_broken_rate_is_discarded(tmp_path):
    prices = _cache(tmp_path, "EURUSD=X", [("2026-08-13", "0")])
    assert fx.rate_to_eur(prices, "USD", date(2026, 8, 13)) is None


def test_rates_to_eur_skips_what_it_cannot_resolve(tmp_path):
    prices = _cache(tmp_path, "EURUSD=X", [("2026-08-13", "1.1791")])
    rates = fx.rates_to_eur(prices, ["USD", "EUR", "GBP", "usd"], date(2026, 8, 13))
    assert set(rates) == {"USD", "EUR"}        # de GBP no hay caché
    assert rates["EUR"] == 1.0
