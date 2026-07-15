import os
from datetime import date

import pytest

from trader import revolut
from trader.portfolio import compute_daily_series, holdings_value, provisional_today
from trader.prices import PriceCache

DATA = os.path.join(os.path.dirname(__file__), "data")


class FakePrices(PriceCache):
    """Precios fijos, sin red y sin disco."""

    def __init__(self, table):
        super().__init__(cache_dir="/nonexistent", offline=True)
        self.table = table

    def ensure_range(self, ticker, start, end):
        pass

    def close_on(self, ticker, day):
        return self.table[ticker]


PRICES = FakePrices({"AAPL": 205.0, "MSFT": 310.0})


def _series():
    events, _ = revolut.parse_file(os.path.join(DATA, "sample.csv"))
    return compute_daily_series(events, PRICES, until=date(2026, 7, 4))


def test_day_one_topup_is_not_profit():
    day1 = _series()[0]
    # 1000 ingresados, 400 en AAPL que cierra a 205 => 600 cash + 410 = 1010
    assert day1.external_flow == 1000.0
    assert day1.end_value == pytest.approx(1010.0)
    assert day1.pnl == pytest.approx(10.0)
    # Dietz: 10 / (0 + 1000/2 * ... ) -> denom = 0 + 500
    assert day1.daily_return == pytest.approx(10.0 / 500.0)


def test_day_two_buy_moves_no_flow():
    day2 = _series()[1]
    # Compra de MSFT a 300 que cierra a 310: +10 de P&L, sin flujo externo
    assert day2.external_flow == 0.0
    assert day2.pnl == pytest.approx(10.0)
    assert day2.daily_return == pytest.approx(10.0 / 1010.0)


def test_day_three_sell_and_dividend():
    day3 = _series()[2]
    # Vende 1 AAPL a 210 (cierre 205: +5 sobre valoración) y cobra 5 de dividendo
    assert day3.external_flow == 0.0
    assert day3.pnl == pytest.approx(10.0)


def test_day_four_fee_and_topup():
    day4 = _series()[3]
    # Comisión de 1 => P&L -1; el ingreso de 500 no cuenta como ganancia
    assert day4.external_flow == 500.0
    assert day4.pnl == pytest.approx(-1.0)
    assert day4.daily_return < 0


def test_cumulative_is_geometric():
    series = _series()
    acc = 1.0
    for row in series:
        acc *= 1 + row.daily_return
    assert series[-1].cumulative_return == pytest.approx(acc - 1.0)


def test_empty_events():
    assert compute_daily_series([], PRICES) == []


def test_holdings_value_prices_open_positions():
    events, _ = revolut.parse_file(os.path.join(DATA, "sample.csv"))
    values = holdings_value(events, PRICES, until=date(2026, 7, 4))
    # Solo posiciones abiertas, valoradas al cierre; sin efectivo ni importes.
    assert set(values) <= {"AAPL", "MSFT"}
    assert all(v > 0 for v in values.values())


def test_holdings_value_empty():
    assert holdings_value([], PRICES) == {}


def test_provisional_today_uses_live_prices():
    events, _ = revolut.parse_file(os.path.join(DATA, "sample.csv"))
    series = compute_daily_series(events, PRICES, until=date(2026, 7, 4))
    # Cotización en vivo por encima del cierre cacheado (205/310) => mejor cum.
    live = {"AAPL": 250.0, "MSFT": 400.0}
    prov = provisional_today(events, series, PRICES, lambda t: live.get(t))
    assert prov is not None
    assert prov["cum"] > round(series[-1].cumulative_return * 100, 4)


def test_provisional_none_without_live_quotes():
    events, _ = revolut.parse_file(os.path.join(DATA, "sample.csv"))
    series = compute_daily_series(events, PRICES, until=date(2026, 7, 4))
    # Sin ninguna cotización en vivo no hay indicador provisional.
    assert provisional_today(events, series, PRICES, lambda t: None) is None


def test_provisional_none_without_positions():
    assert provisional_today([], [], PRICES, lambda t: 100.0) is None


def test_live_price_offline_returns_none():
    assert PRICES.live_price("AAPL") is None
