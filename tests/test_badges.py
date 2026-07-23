"""Insignias acumulativas: detección de logros y récord persistente.

El histórico no se recalcula desde cero en cada ejecución: se comprueba que las
insignias se **añaden** (sin duplicar) y que el récord de «mayor subida de un
valor en un día» solo se reescribe cuando se supera, conservando el anterior.
"""

from datetime import date, timedelta

from trader import badges
from trader.players import Player
from trader.portfolio import DayResult


def _series(rets, start=date(2026, 3, 2)):
    """Serie de jornadas hábiles con las rentabilidades diarias dadas."""
    out = []
    cum = 1.0
    day = start
    for r in rets:
        while day.weekday() >= 5:  # saltar fines de semana
            day += timedelta(days=1)
        cum *= 1.0 + r
        out.append(DayResult(day=day, start_value=100.0, end_value=100.0,
                             external_flow=0.0, pnl=0.0, daily_return=r,
                             cumulative_return=cum - 1.0))
        day += timedelta(days=1)
    return out


def _month_series(specs):
    """Serie a partir de ``(año, mes, r_diario, nº jornadas)`` por tramo."""
    out = []
    cum = 1.0
    for year, month, r, n in specs:
        day = date(year, month, 1)
        count = 0
        while count < n:
            if day.weekday() < 5:
                cum *= 1.0 + r
                out.append(DayResult(day=day, start_value=100.0, end_value=100.0,
                                     external_flow=0.0, pnl=0.0, daily_return=r,
                                     cumulative_return=cum - 1.0))
                count += 1
            day += timedelta(days=1)
    return out


def test_milestones_and_week_streak():
    fede = Player(player_id="fede", display_name="Fede")
    # 6 jornadas seguidas al +2 % (una semana en verde y supera +10 %).
    computed = [(fede, _series([0.02] * 6))]
    store, display = badges.update_badges(computed, {}, today=date(2026, 3, 20))

    keys = {a["key"] for a in store["awards"]}
    assert "milestone:fede:5" in keys
    assert "milestone:fede:10" in keys
    assert "milestone:fede:25" not in keys      # no llega al 25 %
    assert "week_streak:fede" in keys
    # El display trae el color (slot) de cada jugador.
    assert all("slot" in a for a in display["awards"])


def test_week_streak_needs_five_consecutive():
    ana = Player(player_id="ana", display_name="Ana")
    # Verde, verde, rojo, verde... nunca cinco seguidos.
    computed = [(ana, _series([0.01, 0.01, -0.01, 0.01, 0.01, 0.01, -0.01]))]
    store, _ = badges.update_badges(computed, {}, today=date(2026, 3, 20))
    assert "week_streak:ana" not in {a["key"] for a in store["awards"]}


def test_champion_and_consecutive_months():
    fede = Player(player_id="fede", display_name="Fede")
    ana = Player(player_id="ana", display_name="Ana")
    fede_s = _month_series([(2026, 1, 0.01, 5), (2026, 2, 0.01, 5), (2026, 3, 0.01, 5)])
    ana_s = _month_series([(2026, 1, 0.005, 5), (2026, 2, 0.005, 5), (2026, 3, 0.005, 5)])
    computed = [(fede, fede_s), (ana, ana_s)]

    store, _ = badges.update_badges(computed, {}, today=date(2026, 4, 10))
    awards = {a["key"]: a for a in store["awards"]}

    # Campeón de cada mes cerrado (fede gana los tres).
    for ym in ("2026-01", "2026-02", "2026-03"):
        assert awards[f"champion:{ym}"]["player"] == "fede"
    # Dos y tres meses consecutivos ganando.
    assert "months_2:fede" in awards
    assert "months_3:fede" in awards
    assert awards["months_3:fede"]["month"] == "2026-03"


def test_current_month_champion_is_provisional_not_persisted():
    fede = Player(player_id="fede", display_name="Fede")
    computed = [(fede, _month_series([(2026, 3, 0.01, 5)]))]
    store, display = badges.update_badges(computed, {}, today=date(2026, 3, 20))

    # El mes en curso no se graba en el histórico, pero se muestra provisional.
    assert not any(a["key"].startswith("champion:") for a in store["awards"])
    assert display["provisional"]
    prov = display["provisional"][0]
    assert prov["type"] == "champion_month" and prov["provisional"] is True


def test_awards_accumulate_without_duplicates():
    fede = Player(player_id="fede", display_name="Fede")
    computed = [(fede, _series([0.02] * 6))]
    store, _ = badges.update_badges(computed, {}, today=date(2026, 3, 20))
    n_first = len(store["awards"])
    # Segunda pasada con los mismos datos: no se añade nada nuevo.
    store, _ = badges.update_badges(computed, store, today=date(2026, 3, 21))
    assert len(store["awards"]) == n_first


def test_record_updates_only_when_beaten_and_keeps_history():
    fede = Player(player_id="fede", display_name="Fede")
    computed = [(fede, _series([0.01]))]

    ph1 = {"NVDA": [(date(2026, 3, 2), 100.0), (date(2026, 3, 3), 115.0)]}  # +15 %
    store, _ = badges.update_badges(computed, {}, price_history=ph1,
                                    today=date(2026, 3, 20))
    assert store["record"]["ticker"] == "NVDA"
    assert store["record"]["pct"] == 15.0

    # Subida menor: el récord no cambia.
    ph2 = {"AAA": [(date(2026, 3, 4), 10.0), (date(2026, 3, 5), 10.5)]}      # +5 %
    store, _ = badges.update_badges(computed, store, price_history=ph2,
                                    today=date(2026, 3, 21))
    assert store["record"]["ticker"] == "NVDA"
    assert store["record"]["history"] == []

    # Subida mayor: se reescribe y el anterior pasa al historial.
    ph3 = {"BBB": [(date(2026, 3, 6), 10.0), (date(2026, 3, 7), 13.0)]}      # +30 %
    store, _ = badges.update_badges(computed, store, price_history=ph3,
                                    today=date(2026, 3, 22))
    assert store["record"]["ticker"] == "BBB"
    assert store["record"]["pct"] == 30.0
    assert [h["ticker"] for h in store["record"]["history"]] == ["NVDA"]


def test_store_roundtrip(tmp_path):
    fede = Player(player_id="fede", display_name="Fede")
    computed = [(fede, _series([0.02] * 6))]
    path = tmp_path / "badges.json"

    store = badges.load_store(str(path))          # no existe -> vacío
    assert store["awards"] == [] and store["record"] is None
    store, _ = badges.update_badges(computed, store, today=date(2026, 3, 20))
    badges.save_store(store, str(path))

    reloaded = badges.load_store(str(path))
    assert {a["key"] for a in reloaded["awards"]} == {a["key"] for a in store["awards"]}
