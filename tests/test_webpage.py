"""La página embebe solo los últimos 30 días, pero conserva inicio y acumulado."""

from datetime import date, timedelta

from trader import webpage
from trader.players import Player
from trader.portfolio import DayResult


def _series(n_days: int) -> list[DayResult]:
    start = date(2026, 1, 1)
    out = []
    cum = 0.0
    for i in range(n_days):
        cum += 0.01  # +1% cada día, acumulado desde el inicio
        out.append(DayResult(
            day=start + timedelta(days=i),
            start_value=100.0, end_value=101.0, external_flow=0.0, pnl=1.0,
            daily_return=0.01, cumulative_return=cum,
        ))
    return out


def test_payload_limits_to_last_30_days():
    player = Player(player_id="fede", display_name="Fede")
    series = _series(45)
    payload = webpage.build_payload([(player, series)])
    p = payload["players"][0]

    # Solo los últimos 30 días en la ventana visible.
    assert len(p["days"]) == 30
    assert p["days"][0]["date"] == "2026-01-16"   # día 45-30+1
    assert p["days"][-1]["date"] == "2026-02-14"  # día 45

    # Pero la fecha de inicio real y el acumulado se conservan.
    assert p["since"] == "2026-01-01"
    assert p["days"][-1]["cum"] == round(45 * 1.0, 4)  # 45% acumulado desde el inicio


def test_payload_keeps_all_when_shorter_than_window():
    player = Player(player_id="ana", display_name="Ana")
    payload = webpage.build_payload([(player, _series(10))])
    p = payload["players"][0]
    assert len(p["days"]) == 10
    assert p["since"] == "2026-01-01"


def test_custom_window():
    player = Player(player_id="fede", display_name="Fede")
    payload = webpage.build_payload([(player, _series(45))], last_days=7)
    assert len(payload["players"][0]["days"]) == 7


def test_pending_in_payload():
    player = Player(player_id="fede", display_name="Fede")
    pending = [{"id": "ana", "name": "Ana"}]
    payload = webpage.build_payload([(player, _series(5))], pending=pending)
    assert payload["pending"] == pending


def test_pending_defaults_empty():
    player = Player(player_id="fede", display_name="Fede")
    payload = webpage.build_payload([(player, _series(5))])
    assert payload["pending"] == []
