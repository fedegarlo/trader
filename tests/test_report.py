"""Ganador de cada día del mes en el ranking."""

import json
from datetime import date, datetime, timezone

from trader import report, webpage
from trader.players import Player
from trader.portfolio import DayResult


def _day(d: date, ret: float) -> DayResult:
    return DayResult(
        day=d, start_value=100.0, end_value=100.0, external_flow=0.0,
        pnl=0.0, daily_return=ret, cumulative_return=ret,
    )


def _computed():
    fede = Player(player_id="fede", display_name="Fede")
    ana = Player(player_id="ana", display_name="Ana")
    fede_series = [
        _day(date(2026, 7, 14), 0.0179),
        _day(date(2026, 7, 15), -0.0485),
        _day(date(2026, 7, 16), -0.0496),
    ]
    ana_series = [
        _day(date(2026, 7, 14), 0.0153),
        _day(date(2026, 7, 15), 0.0003),
        _day(date(2026, 7, 16), -0.0263),
    ]
    return [(fede, fede_series), (ana, ana_series)]


def test_daily_winners_picks_best_return_each_day():
    winners = report.daily_winners(_computed(), 2026, 7)
    assert [(d.isoformat(), names) for d, names, _ in winners] == [
        ("2026-07-14", ["Fede"]),   # +1.79% > +1.53%
        ("2026-07-15", ["Ana"]),    # +0.03% > -4.85%
        ("2026-07-16", ["Ana"]),    # -2.63% (menos negativo) > -4.96%
    ]


def test_daily_winners_handles_ties():
    fede = Player(player_id="fede", display_name="Fede")
    ana = Player(player_id="ana", display_name="Ana")
    computed = [
        (fede, [_day(date(2026, 7, 14), 0.02)]),
        (ana, [_day(date(2026, 7, 14), 0.02)]),
    ]
    winners = report.daily_winners(computed, 2026, 7)
    assert winners[0][1] == ["Fede", "Ana"]


def test_daily_winners_filters_by_month():
    fede = Player(player_id="fede", display_name="Fede")
    computed = [(fede, [
        _day(date(2026, 6, 30), 0.5),
        _day(date(2026, 7, 1), 0.1),
    ])]
    winners = report.daily_winners(computed, 2026, 7)
    assert [d.isoformat() for d, _, _ in winners] == ["2026-07-01"]


def test_ranking_includes_daily_winners_section(tmp_path):
    content = report.write_ranking(
        _computed(), out_path=str(tmp_path / "ranking.md"),
        today=date(2026, 7, 16),
        now=datetime(2026, 10, 3, 23, 23, tzinfo=timezone.utc),
    )
    assert "## 🏅 Ganador de cada día (julio 2026)" in content
    assert "| 2026-07-14 | 🏅 Fede | +1.79% |" in content
    assert "_Actualizado: 2026-07-16 01:23_" in content


def test_ranking_actualizado_is_madrid_when_utc_is_still_yesterday(tmp_path, monkeypatch):
    """El «Actualizado» del markdown es el mismo instante de Madrid que la API.

    ``date.today()`` en Actions sigue en el 3; Madrid ya es el 4 a la 01:23.
    El sello tiene que llevar día y hora de Madrid, no la fecha UTC a secas.
    """
    utc = datetime(2026, 10, 3, 23, 23, tzinfo=timezone.utc)

    class _UtcDate(date):
        @classmethod
        def today(cls):
            return date(2026, 10, 3)

    monkeypatch.setattr(report, "date", _UtcDate)
    monkeypatch.setattr(webpage, "date", _UtcDate)

    content = report.write_ranking(
        _computed(), out_path=str(tmp_path / "ranking.md"), now=utc)
    assert "_Actualizado: 2026-10-04 01:23_" in content
    assert "## 🏅 Ganador de cada día (octubre 2026)" in content


def test_ranking_and_api_publish_the_same_madrid_stamp(tmp_path, monkeypatch):
    """El markdown y league.json no pueden discrepar: mismo instante, misma zona."""
    utc = datetime(2026, 10, 3, 23, 23, tzinfo=timezone.utc)

    class _UtcDate(date):
        @classmethod
        def today(cls):
            return date(2026, 10, 3)

    monkeypatch.setattr(report, "date", _UtcDate)
    monkeypatch.setattr(webpage, "date", _UtcDate)

    out = webpage.write_api(
        _computed(), out_path=str(tmp_path / "api" / "league.json"), now=utc)
    with open(out, encoding="utf-8") as fh:
        api = json.load(fh)
    content = report.write_ranking(
        _computed(), out_path=str(tmp_path / "ranking.md"), now=utc)
    assert api["updated"] == "2026-10-04 01:23"
    assert f"_Actualizado: {api['updated']}_" in content
