"""La página embebe la serie completa de cada jugador (la liga es desde el inicio)."""

import os
import re
from datetime import date, datetime, timedelta, timezone

from trader import webpage
from trader.players import Player
from trader.portfolio import DayResult
from trader.revolut import BUY, FEE, SELL, TOPUP, Event


def _series(n_days: int) -> list[DayResult]:
    """``n_days`` jornadas hábiles consecutivas (sin sábados ni domingos)."""
    out = []
    cum = 0.0
    day = date(2026, 1, 1)
    while len(out) < n_days:
        if day.weekday() < 5:  # los fines de semana no hay competición
            cum += 0.01  # +1% cada jornada, acumulado desde el inicio
            out.append(DayResult(
                day=day,
                start_value=100.0, end_value=101.0, external_flow=0.0, pnl=1.0,
                daily_return=0.01, cumulative_return=cum,
            ))
        day += timedelta(days=1)
    return out


def test_payload_keeps_the_whole_series_since_the_start():
    player = Player(player_id="fede", display_name="Fede")
    series = _series(45)
    payload = webpage.build_payload([(player, series)])
    p = payload["players"][0]

    # La gráfica principal es de toda la competición, no de los últimos 30 días.
    assert len(p["days"]) == 45
    assert p["days"][0]["date"] == series[0].day.isoformat()
    assert p["days"][-1]["date"] == series[-1].day.isoformat()

    # La fecha de inicio real y el acumulado se conservan.
    assert p["since"] == series[0].day.isoformat()
    assert p["days"][-1]["cum"] == round(45 * 1.0, 4)  # 45% acumulado desde el inicio


def test_payload_keeps_all_when_short_history():
    player = Player(player_id="ana", display_name="Ana")
    payload = webpage.build_payload([(player, _series(10))])
    p = payload["players"][0]
    assert len(p["days"]) == 10
    assert p["since"] == "2026-01-01"


def test_custom_window():
    player = Player(player_id="fede", display_name="Fede")
    payload = webpage.build_payload([(player, _series(45))], last_days=7)
    assert len(payload["players"][0]["days"]) == 7


def test_badges_flow_into_payload_and_html(tmp_path):
    from trader import badges
    player = Player(player_id="fede", display_name="Fede")
    series = _series(6)  # 6 jornadas al +1 %: una semana en verde y +5 %
    computed = [(player, series)]

    store, display = badges.update_badges(computed, {}, today=date(2026, 3, 1))
    payload = webpage.build_payload(computed, badges=display)
    types = {a["type"] for a in payload["badges"]["awards"]}
    assert "week_streak" in types and "milestone" in types

    out = tmp_path / "index.html"
    webpage.write_index(computed, out_path=str(out), badges=display)
    html = out.read_text(encoding="utf-8")
    assert "badges-card" in html and "paintBadges" in html
    # También en la ficha del jugador: índice por jugador + render de chips.
    assert "PLAYER_BADGES" in html and "mbadge-chip" in html


def _july(pid, name, rows):
    player = Player(player_id=pid, display_name=name)
    series = [DayResult(
        day=d, start_value=100.0, end_value=100.0, external_flow=0.0,
        pnl=0.0, daily_return=ret, cumulative_return=ret,
    ) for d, ret in rows]
    return (player, series)


def test_player_months_compose_the_daily_returns():
    computed = [_july("fede", "Fede", [
        (date(2026, 7, 14), 0.02),
        (date(2026, 7, 15), 0.01),
        (date(2026, 8, 3), -0.01),
    ])]
    months = webpage.build_payload(
        computed, today=date(2026, 8, 3))["players"][0]["months"]
    # Un mes por fila, del más reciente al más antiguo, con la composición de
    # los % diarios del mes (1,02 × 1,01 − 1 = +3,02 % en julio).
    assert [(m["month_year"], m["month"], m["ret"]) for m in months] == [
        (2026, 8, -1.0),
        (2026, 7, 3.02),
    ]
    # El acumulado de cada fila es el del cierre de ese mes.
    assert [m["cum"] for m in months] == [-1.0, 1.0]


def test_player_months_never_carry_amounts():
    # El detalle mensual es solo rentabilidad, también para quien publica sus
    # importes (esos siguen viajando en ``days`` para su propia ficha).
    player = Player(player_id="fede", display_name="Fede", show_amounts=True)
    p = webpage.build_payload([(player, _series(3))])["players"][0]
    assert p["amounts"] is True and "start" in p["days"][0]
    assert all(set(m) == {"month", "month_year", "ret", "cum"} for m in p["months"])


def test_player_months_follow_the_published_window():
    player = Player(player_id="fede", display_name="Fede")
    p = webpage.build_payload([(player, _series(45))], last_days=7)["players"][0]
    assert {(m["month_year"], m["month"]) for m in p["months"]} == {
        (int(d["date"][:4]), int(d["date"][5:7])) for d in p["days"]}


def test_daily_winners_picks_best_each_day():
    computed = [
        _july("fede", "Fede", [
            (date(2026, 7, 14), 0.0179),
            (date(2026, 7, 15), -0.0485),
            (date(2026, 7, 16), -0.0496),
        ]),
        _july("ana", "Ana", [
            (date(2026, 7, 14), 0.0153),
            (date(2026, 7, 15), 0.0003),
            (date(2026, 7, 16), -0.0263),
        ]),
    ]
    dw = webpage.build_payload(computed, today=date(2026, 7, 16))["dailyWinners"]
    assert dw["month"] == 7 and dw["month_year"] == 2026
    # Ordenados de más reciente a más antiguo.
    assert [(r["date"], r["names"]) for r in dw["rows"]] == [
        ("2026-07-16", ["Ana"]),
        ("2026-07-15", ["Ana"]),
        ("2026-07-14", ["Fede"]),
    ]


def test_daily_winners_ignore_days_before_competition_start():
    computed = [_july("fede", "Fede", [
        (date(2026, 7, 13), 0.9),   # anterior al inicio de la competición
        (date(2026, 7, 14), 0.1),
    ])]
    rows = webpage.build_payload(computed, today=date(2026, 7, 14))["dailyWinners"]["rows"]
    assert [r["date"] for r in rows] == ["2026-07-14"]


def test_daily_winners_tie_lists_both_and_no_slot():
    computed = [
        _july("fede", "Fede", [(date(2026, 7, 14), 0.02)]),
        _july("ana", "Ana", [(date(2026, 7, 14), 0.02)]),
    ]
    row = webpage.build_payload(computed, today=date(2026, 7, 14))["dailyWinners"]["rows"][0]
    assert row["names"] == ["Ana", "Fede"] and row["slot"] is None


def test_daily_winners_carry_player_ids():
    computed = [
        _july("fede", "Fede", [(date(2026, 7, 14), 0.03)]),
        _july("ana", "Ana", [(date(2026, 7, 14), 0.01)]),
    ]
    row = webpage.build_payload(computed, today=date(2026, 7, 14))["dailyWinners"]["rows"][0]
    # El id del campeón viaja para poder abrir su detalle del día en la web.
    assert row["names"] == ["Fede"] and row["ids"] == ["fede"]


def test_day_breakdown_percentages_sum_to_day_return():
    player = Player(player_id="fede", display_name="Fede")
    series = [DayResult(
        day=date(2026, 7, 14), start_value=200.0, end_value=210.0,
        external_flow=0.0, pnl=10.0, daily_return=0.05, cumulative_return=0.05,
    )]
    # AAPL aporta 6 y MSFT 4 (suman el P&L de 10 sobre base 200 => +5%).
    contributions = {"fede": {date(2026, 7, 14): {"AAPL": 6.0, "MSFT": 4.0}}}
    payload = webpage.build_payload(
        [(player, series)], contributions=contributions, today=date(2026, 7, 14))
    bd = payload["players"][0]["days"][0]["bd"]
    assert [(d["ticker"], d["pct"]) for d in bd] == [("AAPL", 3.0), ("MSFT", 2.0)]
    assert round(sum(d["pct"] for d in bd), 4) == payload["players"][0]["days"][0]["day"]


def test_day_breakdown_keeps_held_ticker_even_if_negligible():
    # Un valor que apenas se movió (ASML el 22-jul: +0,02 %) aporta una fracción
    # ínfima del día, pero sigue siendo una posición de la cartera y debe
    # aparecer en el desglose. Solo el ruido de efectivo/comisiones se oculta.
    player = Player(player_id="fede", display_name="Fede")
    series = [DayResult(
        day=date(2026, 7, 22), start_value=3500.0, end_value=3505.25,
        external_flow=0.0, pnl=5.25, daily_return=0.0015, cumulative_return=0.0015,
    )]
    contributions = {"fede": {date(2026, 7, 22): {
        "NVDA": 14.7, "ASML": 0.1162, "": 0.001,  # "" = efectivo/comisiones
    }}}
    payload = webpage.build_payload(
        [(player, series)], contributions=contributions, today=date(2026, 7, 22))
    bd = payload["players"][0]["days"][0]["bd"]
    tickers = [d["ticker"] for d in bd]
    assert "ASML" in tickers     # posición real: se conserva aunque ~0,00 %
    assert "" not in tickers     # ruido de efectivo por debajo del umbral: oculto


def test_day_breakdown_absent_without_contributions():
    player = Player(player_id="fede", display_name="Fede")
    payload = webpage.build_payload([(player, _series(3))])
    assert all("bd" not in d for d in payload["players"][0]["days"])


def test_weekends_are_dropped_from_payload():
    # 17 jul = viernes, 18/19 = fin de semana, 20 = lunes.
    computed = [_july("fede", "Fede", [
        (date(2026, 7, 17), 0.01),
        (date(2026, 7, 18), 0.05),   # sábado: no hay competición
        (date(2026, 7, 19), 0.05),   # domingo: no hay competición
        (date(2026, 7, 20), 0.02),
    ])]
    payload = webpage.build_payload(computed, today=date(2026, 7, 20))
    dates = [d["date"] for d in payload["players"][0]["days"]]
    assert dates == ["2026-07-17", "2026-07-20"]
    # El «campeón de cada día» tampoco lista el fin de semana.
    winner_dates = [r["date"] for r in payload["dailyWinners"]["rows"]]
    assert winner_dates == ["2026-07-20", "2026-07-17"]


def test_pending_in_payload():
    player = Player(player_id="fede", display_name="Fede")
    pending = [{"id": "ana", "name": "Ana"}]
    payload = webpage.build_payload([(player, _series(5))], pending=pending)
    assert payload["pending"] == pending


def test_pending_defaults_empty():
    player = Player(player_id="fede", display_name="Fede")
    payload = webpage.build_payload([(player, _series(5))])
    assert payload["pending"] == []


def test_allocation_normalized_to_weights_sorted():
    player = Player(player_id="fede", display_name="Fede")
    alloc = {"AAPL": 300.0, "MSFT": 100.0}
    payload = webpage.build_payload([(player, _series(5))], allocation=alloc)
    assert payload["allocation"] == [
        {"ticker": "AAPL", "w": 75.0},
        {"ticker": "MSFT", "w": 25.0},
    ]


def test_allocation_defaults_empty():
    player = Player(player_id="fede", display_name="Fede")
    payload = webpage.build_payload([(player, _series(5))])
    assert payload["allocation"] == []


def test_holdings_per_player_normalized_to_weights():
    fede = Player(player_id="fede", display_name="Fede")
    ana = Player(player_id="ana", display_name="Ana")
    holdings = {
        "fede": {"AAPL": 300.0, "MSFT": 100.0},
        "ana": {"TSLA": 50.0, "NVDA": 50.0},
    }
    payload = webpage.build_payload(
        [(fede, _series(5)), (ana, _series(5))], holdings=holdings)
    by_id = {p["id"]: p for p in payload["players"]}
    assert by_id["fede"]["holdings"] == [
        {"ticker": "AAPL", "w": 75.0},
        {"ticker": "MSFT", "w": 25.0},
    ]
    assert by_id["ana"]["holdings"] == [
        {"ticker": "TSLA", "w": 50.0},
        {"ticker": "NVDA", "w": 50.0},
    ]


def test_holdings_default_empty_per_player():
    player = Player(player_id="fede", display_name="Fede")
    payload = webpage.build_payload([(player, _series(5))])
    assert payload["players"][0]["holdings"] == []


def _day(day: date, daily_return: float) -> DayResult:
    return DayResult(
        day=day, start_value=100.0, end_value=100.0 * (1 + daily_return),
        external_flow=0.0, pnl=100.0 * daily_return,
        daily_return=daily_return, cumulative_return=0.0,
    )


def test_monthly_best_current_month():
    fede = Player(player_id="fede", display_name="Fede")
    ana = Player(player_id="ana", display_name="Ana")
    fede_series = [_day(date(2026, 7, 14), 0.02), _day(date(2026, 7, 15), 0.01)]
    ana_series = [_day(date(2026, 7, 14), 0.05), _day(date(2026, 7, 15), -0.01)]
    payload = webpage.build_payload(
        [(fede, fede_series), (ana, ana_series)], today=date(2026, 7, 15))

    cur = payload["monthly"]["current"]
    assert cur["month"] == 7
    assert cur["month_year"] == 2026
    # Ana: 1.05*0.99-1 = 3.95% > Fede: 1.02*1.01-1 = 3.02%
    assert cur["name"] == "Ana"
    assert cur["value"] == 3.95
    # Junio no tiene datos de competición: sin widget de mes pasado.
    assert payload["monthly"]["previous"] is None


def test_monthly_series_includes_every_player():
    """El widget pinta a todos los jugadores del mes, no solo al ganador."""
    fede = Player(player_id="fede", display_name="Fede")
    ana = Player(player_id="ana", display_name="Ana")
    fede_series = [_day(date(2026, 7, 14), 0.02), _day(date(2026, 7, 15), 0.01)]
    ana_series = [_day(date(2026, 7, 14), 0.05), _day(date(2026, 7, 15), -0.01)]
    payload = webpage.build_payload(
        [(fede, fede_series), (ana, ana_series)], today=date(2026, 7, 15))

    cur = payload["monthly"]["current"]
    assert cur["dates"] == ["2026-07-14", "2026-07-15"]
    # ordenadas de mejor a peor: primero la del ganador
    assert [s["name"] for s in cur["series"]] == ["Ana", "Fede"]
    assert [s["value"] for s in cur["series"]] == [3.95, 3.02]
    assert cur["series"][0]["cum"] == [5.0, 3.95]
    assert cur["series"][1]["cum"] == [2.0, 3.02]
    # cada jugador lleva su id (ficha) y su slot (color), como en la gráfica
    slots = {p["id"]: p["slot"] for p in payload["players"]}
    assert {s["id"]: s["slot"] for s in cur["series"]} == slots


def test_monthly_series_aligns_missing_days():
    """Si un jugador no tiene jornada ese día, su punto va a ``None``."""
    fede = Player(player_id="fede", display_name="Fede")
    ana = Player(player_id="ana", display_name="Ana")
    payload = webpage.build_payload(
        [(fede, [_day(date(2026, 7, 14), 0.02), _day(date(2026, 7, 15), 0.01)]),
         (ana, [_day(date(2026, 7, 15), 0.05)])],
        today=date(2026, 7, 15))

    cur = payload["monthly"]["current"]
    assert cur["dates"] == ["2026-07-14", "2026-07-15"]
    by_name = {s["name"]: s["cum"] for s in cur["series"]}
    assert by_name["Ana"] == [None, 5.0]
    assert by_name["Fede"] == [2.0, 3.02]


def test_monthly_ignores_pre_competition_days():
    fede = Player(player_id="fede", display_name="Fede")
    # El 10 de julio es anterior al inicio oficial (14 de julio): no cuenta.
    series = [_day(date(2026, 7, 10), 0.50), _day(date(2026, 7, 14), 0.01)]
    payload = webpage.build_payload([(fede, series)], today=date(2026, 7, 14))
    assert payload["monthly"]["current"]["value"] == 1.0


def test_monthly_previous_month_when_data():
    fede = Player(player_id="fede", display_name="Fede")
    series = [_day(date(2026, 7, 20), 0.03), _day(date(2026, 8, 3), 0.02)]
    payload = webpage.build_payload([(fede, series)], today=date(2026, 8, 5))
    assert payload["monthly"]["current"]["month"] == 8
    assert payload["monthly"]["current"]["value"] == 2.0
    assert payload["monthly"]["previous"]["month"] == 7
    assert payload["monthly"]["previous"]["value"] == 3.0


def test_previous_month_widget_is_a_headline_with_a_second_level(tmp_path):
    """El mes pasado se queda en titular: su gráfica va tras «ver más»."""
    fede = Player(player_id="fede", display_name="Fede")
    series = [_day(date(2026, 7, 20), 0.03), _day(date(2026, 8, 3), 0.02)]
    out = tmp_path / "index.html"
    webpage.write_index([(fede, series)], out_path=str(out), today=date(2026, 8, 5))
    html = out.read_text(encoding="utf-8")

    # el widget sigue, pero sin gráfica ni leyenda dentro de la tarjeta
    assert 'id="month-prev-card"' in html
    assert 'id="month-prev-chart"' not in html
    assert 'id="month-prev-legend"' not in html
    # la del mes en curso, que es la carrera viva, se queda donde estaba
    assert 'id="month-cur-chart"' in html
    # y el detalle del mes pasado se abre desde el botón «ver más»
    assert 'id="month-prev-more"' in html
    assert "function openMonthDetail(info)" in html


def test_treat_tier_climbs_with_the_month():
    """Cuanto mejor va el mes, más caro el restaurante que invita el ganador."""
    # los cortes son cerrados por abajo: justo en el umbral ya se sube de peldaño
    assert webpage.treat_tier(-3.0) == 0      # mes en rojo: cañas y tapas
    assert webpage.treat_tier(-0.01) == 0
    assert webpage.treat_tier(0.0) == 1
    assert webpage.treat_tier(2.49) == 1
    assert webpage.treat_tier(2.5) == 2
    assert webpage.treat_tier(4.99) == 2
    assert webpage.treat_tier(5.0) == 3
    assert webpage.treat_tier(9.99) == 3
    assert webpage.treat_tier(10.0) == 4      # tope de la escala
    assert webpage.treat_tier(120.0) == 4
    assert webpage.treat_tier(None) is None


def test_treat_scale_is_ordered_and_travels_with_the_payload():
    """La escala llega entera a la página: precios y ejemplos de Madrid."""
    scale = webpage.build_payload([])["treatScale"]
    assert len(scale) == len(webpage.TREAT_TIERS)
    # el primer peldaño es el de los meses en negativo (sin umbral)
    assert scale[0]["min"] is None
    umbrales = [s["min"] for s in scale[1:]]
    assert umbrales == sorted(umbrales)
    # cada escalón es más caro que el anterior y lleva sus € y sus ejemplos
    precios = [s["price"] for s in scale]
    assert precios == sorted(precios)
    for i, step in enumerate(scale):
        assert step["euros"] == "€" * (i + 1)
        assert step["places"]


def test_month_widgets_carry_the_restaurant_tier():
    """Cada mes publica su peldaño: el de ahora y el del ganador del anterior."""
    fede = Player(player_id="fede", display_name="Fede")
    # julio +12% (estrellas Michelin), agosto -2% (cañas y tapas)
    series = [_day(date(2026, 7, 20), 0.12), _day(date(2026, 8, 3), -0.02)]
    payload = webpage.build_payload([(fede, series)], today=date(2026, 8, 5))

    assert payload["monthly"]["previous"]["value"] == 12.0
    assert payload["monthly"]["previous"]["treat"] == 4
    assert payload["monthly"]["current"]["value"] == -2.0
    assert payload["monthly"]["current"]["treat"] == 0


def test_restaurant_scale_reaches_the_page(tmp_path):
    """Los dos widgets del mes enseñan la categoría y abren la escala."""
    fede = Player(player_id="fede", display_name="Fede")
    series = [_day(date(2026, 7, 20), 0.03), _day(date(2026, 8, 3), 0.02)]
    out = tmp_path / "index.html"
    webpage.write_index([(fede, series)], out_path=str(out), today=date(2026, 8, 5))
    html = out.read_text(encoding="utf-8")

    # la categoría se canta en el mes en curso y en el ganador del mes pasado
    assert 'id="month-cur-note"' in html
    assert 'id="month-prev-note"' in html
    # …y cada tarjeta tiene su interrogación, como la de la clasificación
    assert 'id="month-cur-help"' in html
    assert 'id="month-prev-help"' in html
    assert "function openTreatHelp(info)" in html
    # la leyenda es una tabla con la escala y sus restaurantes de Madrid
    assert '"treatScale"' in html
    assert "DiverXO" in html and "Casa Lucio" in html


def test_goal_and_badges_close_the_page(tmp_path):
    """Objetivo e insignias van al final, detrás del detalle diario."""
    fede = Player(player_id="fede", display_name="Fede")
    out = tmp_path / "index.html"
    webpage.write_index([(fede, _series(6))], out_path=str(out))
    html = out.read_text(encoding="utf-8")

    last_module = html.index('id="wallets-card"')
    assert last_module < html.index('id="goal-card"') < html.index('id="badges-card"')
    assert html.index('id="badges-card"') < html.index("</main>")


def test_monthly_none_when_no_competition_data():
    fede = Player(player_id="fede", display_name="Fede")
    # Serie de enero de 2026, anterior al inicio de la competición.
    payload = webpage.build_payload([(fede, _series(5))], today=date(2026, 1, 20))
    assert payload["monthly"]["current"] is None
    assert payload["monthly"]["previous"] is None


def test_ticker_details_meta_weight_and_holders():
    fede = Player(player_id="fede", display_name="Fede")
    ana = Player(player_id="ana", display_name="Ana")
    allocation = {"AAPL": 300.0, "ZZZZ": 100.0}
    holdings = {"fede": {"AAPL": 300.0}, "ana": {"AAPL": 0.0, "ZZZZ": 100.0}}
    payload = webpage.build_payload(
        [(fede, _series(5)), (ana, _series(5))],
        allocation=allocation, holdings=holdings)
    tickers = {t["ticker"]: t for t in payload["tickers"]}

    # Ordenado por peso agregado (AAPL 75% antes que ZZZZ 25%).
    assert [t["ticker"] for t in payload["tickers"]] == ["AAPL", "ZZZZ"]
    # Ticker conocido: nombre y dominio para el logo.
    assert tickers["AAPL"]["name"] == "Apple"
    assert tickers["AAPL"]["domain"] == "apple.com"
    assert tickers["AAPL"]["w"] == 75.0
    # Solo lo tiene Fede (Ana lo tiene a peso 0 → no cuenta como holder).
    assert [h["name"] for h in tickers["AAPL"]["holders"]] == ["Fede"]
    # Ticker desconocido: nombre = símbolo, sin dominio (la web usa monograma).
    assert tickers["ZZZZ"]["name"] == "ZZZZ"
    assert tickers["ZZZZ"]["domain"] == ""
    assert [h["name"] for h in tickers["ZZZZ"]["holders"]] == ["Ana"]


def test_ticker_details_price_series_and_return():
    from datetime import date as _date
    player = Player(player_id="fede", display_name="Fede")
    prices = {"AAPL": [(_date(2026, 7, 14), 100.0), (_date(2026, 7, 15), 110.0)]}
    payload = webpage.build_payload(
        [(player, _series(5))], allocation={"AAPL": 100.0}, prices=prices)
    aapl = payload["tickers"][0]
    assert aapl["prices"] == [
        {"date": "2026-07-14", "close": 100.0},
        {"date": "2026-07-15", "close": 110.0},
    ]
    assert aapl["ret"] == 10.0  # de 100 a 110 → +10%


def test_ticker_price_window_is_independent_of_the_league_series():
    """La mini-serie del ticker sigue siendo una ventana (contexto de mercado).

    La serie del jugador va desde el inicio, pero los precios del detalle de
    cada valor se recortan a ``price_days``.
    """
    from datetime import date as _date
    player = Player(player_id="fede", display_name="Fede")
    prices = {"AAPL": [(_date(2026, 1, 1) + timedelta(days=i), 100.0 + i)
                       for i in range(60)]}
    payload = webpage.build_payload(
        [(player, _series(45))], allocation={"AAPL": 100.0}, prices=prices)
    assert len(payload["players"][0]["days"]) == 45      # liga: desde el inicio
    assert len(payload["tickers"][0]["prices"]) == 30    # ticker: últimos 30

    payload = webpage.build_payload(
        [(player, _series(45))], allocation={"AAPL": 100.0}, prices=prices,
        price_days=5)
    assert len(payload["tickers"][0]["prices"]) == 5


def test_ticker_details_empty_without_allocation():
    player = Player(player_id="fede", display_name="Fede")
    payload = webpage.build_payload([(player, _series(5))])
    assert payload["tickers"] == []


def test_ticker_details_include_peers():
    player = Player(player_id="fede", display_name="Fede")
    payload = webpage.build_payload([(player, _series(5))], allocation={"AAPL": 100.0})
    peers = payload["tickers"][0]["peers"]
    assert [p["ticker"] for p in peers] == ["MSFT", "GOOGL", "AMZN"]
    assert peers[0]["name"] == "Microsoft" and peers[0]["domain"] == "microsoft.com"


def test_ticker_details_attach_analyst_consensus():
    player = Player(player_id="fede", display_name="Fede")
    analysts = {"AAPL": {"label": "Comprar", "tone": "pos", "upside": 12.0}}
    payload = webpage.build_payload(
        [(player, _series(5))], allocation={"AAPL": 100.0}, analysts=analysts)
    assert payload["tickers"][0]["analyst"] == analysts["AAPL"]


def test_revolut_buttons_use_same_tab_universal_link():
    assert 'https://revolut.com/app/trading/stocks/" + encodeURIComponent(sym)' in webpage._TEMPLATE
    snippet = webpage._TEMPLATE.split("function revolutRow(sym)", 1)[1].split(
        "function sectionEl", 1)[0]
    assert 'a.target = "_blank"' not in snippet


def test_ticker_details_carry_the_news_of_their_ticker():
    player = Player(player_id="fede", display_name="Fede")
    news = {"AAPL": [{"title": "Apple presenta resultados",
                      "link": "https://finance.yahoo.com/news/a",
                      "source": "Yahoo Finance", "at": "2026-08-14T13:05:00Z"}]}
    payload = webpage.build_payload(
        [(player, _series(5))], allocation={"AAPL": 100.0, "ZZZZ": 50.0},
        news=news)
    tickers = {t["ticker"]: t for t in payload["tickers"]}
    assert tickers["AAPL"]["news"] == news["AAPL"]
    assert "news" not in tickers["ZZZZ"]  # sin titulares, sin clave


def test_ticker_details_no_news_key_without_data():
    player = Player(player_id="fede", display_name="Fede")
    payload = webpage.build_payload([(player, _series(5))], allocation={"AAPL": 100.0})
    assert "news" not in payload["tickers"][0]


def test_news_travel_to_the_html(tmp_path):
    player = Player(player_id="fede", display_name="Fede")
    out = webpage.write_index(
        [(player, _series(5))], out_path=str(tmp_path / "index.html"),
        allocation={"AAPL": 100.0},
        news={"AAPL": [{"title": "Apple presenta resultados",
                        "link": "https://finance.yahoo.com/news/a"}]})
    html = open(out, encoding="utf-8").read()
    assert "Apple presenta resultados" in html


def test_player_news_gather_the_whole_portfolio():
    """La ficha del jugador reúne los titulares de todas sus posiciones."""
    snippet = webpage._TEMPLATE.split("function newsFor(", 1)[1].split(
        "function newsSectionEl", 1)[0]
    assert "TICKERS[sym] || {}).news" in snippet
    assert "newsFor(syms, 6)" in webpage._TEMPLATE


def test_news_of_several_tickers_are_dealt_in_rounds():
    """Una cola por valor y una ronda cada vez: sin esto las primeras filas se
    llenaban con la empresa que más hubiera publicado ese día."""
    snippet = webpage._TEMPLATE.split("function newsFor(", 1)[1].split(
        "function newsSectionEl", 1)[0]
    # una cola por valor, y de cada ronda sale un titular de cada una
    assert "queues.push(queue)" in snippet
    assert "queues.forEach(q => out.push(q.shift()))" in snippet
    # dentro de la ronda manda la fecha (lo más fresco primero)
    assert 'queues.sort((a, b) => (b[0].at || "").localeCompare(a[0].at || ""))' in snippet
    # y las colas que se vacían salen del reparto
    assert "queues.splice(i, 1)" in snippet


def test_news_titles_are_never_injected_as_html():
    """Los textos vienen de una API de terceros: solo textContent, nunca innerHTML."""
    snippet = webpage._TEMPLATE.split("function newsListEl(items)", 1)[1].split(
        "function newsFor(", 1)[0]
    assert "innerHTML" not in snippet
    assert "title.textContent = n.title" in snippet


def test_home_has_a_news_card_fed_by_every_ticker():
    """El módulo de portada mezcla los titulares de todos los valores."""
    assert 'id="news-card"' in webpage._TEMPLATE
    assert "paintNews();" in webpage._TEMPLATE
    snippet = webpage._TEMPLATE.split("function paintNews()", 1)[1].split(
        "paintNews();", 1)[0]
    assert "(DATA.tickers || []).map(t => t.ticker)" in snippet
    assert "newsFor(syms, NEWS_HOME_MAX)" in snippet
    assert "collapseList(rows, box)" in snippet  # 5 filas y el resto tras «ver más»


def test_home_news_card_hides_itself_without_news():
    snippet = webpage._TEMPLATE.split("function paintNews()", 1)[1].split(
        "paintNews();", 1)[0]
    assert 'if (!items.length) { card.style.display = "none"; return; }' in snippet


def test_home_news_card_is_translated_in_every_language():
    for key in ("leagueNews", "newsCount", "newsTickers", "newsNote"):
        assert webpage._TEMPLATE.count(key + ":") == 3, key


def test_home_news_rows_open_the_article_in_another_window():
    snippet = webpage._TEMPLATE.split("function paintNews()", 1)[1].split(
        "paintNews();", 1)[0]
    assert "externalLink(n.link)" in snippet
    assert "innerHTML" not in snippet.replace("box.innerHTML = \"\";", "")


def test_every_news_link_goes_through_external_link():
    """Titulares y enlaces de búsqueda: todos salen a otra ventana."""
    for fn in ("function newsRow(sym)", "function newsListEl(items)"):
        snippet = webpage._TEMPLATE.split(fn, 1)[1].split("\nfunction ", 1)[0]
        assert "externalLink(" in snippet
        assert 'target = "_blank"' not in snippet  # lo pone externalLink


def test_external_links_escape_the_installed_app():
    """Instalada como app (standalone) un _blank se abre dentro: window.open."""
    snippet = webpage._TEMPLATE.split("function externalLink(href)", 1)[1].split(
        "function newsRow(", 1)[0]
    assert 'a.target = "_blank"; a.rel = "noopener noreferrer"' in snippet
    assert "ev.preventDefault()" in snippet
    assert 'window.open(href, "_blank", "noopener,noreferrer")' in snippet
    assert "if (STANDALONE)" in snippet  # en el navegador manda el target
    assert "window.navigator.standalone === true" in webpage._TEMPLATE  # iOS


def test_search_links_survive_without_downloaded_news():
    """Sin titulares (API caída) la sección se queda con los enlaces de siempre."""
    snippet = webpage._TEMPLATE.split("function newsSectionEl(", 1)[1].split(
        "// Botones", 1)[0]
    assert "items.length ? newsListEl(items) : newsRow(sym)" in snippet


def test_ticker_details_no_analyst_key_without_data():
    player = Player(player_id="fede", display_name="Fede")
    payload = webpage.build_payload([(player, _series(5))], allocation={"AAPL": 100.0})
    assert "analyst" not in payload["tickers"][0]


# ---- sesión extendida (pre-market / after-hours) ---------------------------

def _ext(session, pct, price=100.0):
    return {"state": session.upper(), "session": session, "price": price,
            "pct": pct, "regular": 100.0, "currency": "USD"}


def test_extended_quote_travels_with_its_ticker():
    player = Player(player_id="fede", display_name="Fede")
    extended = {"AAPL": _ext("post", 1.25, price=210.0)}
    payload = webpage.build_payload(
        [(player, _series(5))], allocation={"AAPL": 100.0}, extended=extended)
    assert payload["tickers"][0]["ext"] == extended["AAPL"]


def test_no_ext_key_without_extended_data():
    player = Player(player_id="fede", display_name="Fede")
    payload = webpage.build_payload([(player, _series(5))], allocation={"AAPL": 100.0})
    assert "ext" not in payload["tickers"][0]
    assert payload["market"] is None


def test_market_snapshot_weights_by_position_size():
    """La variación de la liga pondera cada valor por su peso en la cartera."""
    player = Player(player_id="fede", display_name="Fede")
    now = datetime(2026, 8, 11, 22, 45, tzinfo=timezone.utc)
    payload = webpage.build_payload(
        [(player, _series(5))],
        allocation={"AAPL": 750.0, "MSFT": 250.0},
        extended={"AAPL": _ext("post", 2.0), "MSFT": _ext("post", -2.0)},
        now=now)
    market = payload["market"]
    assert market["session"] == "post"
    assert market["count"] == 2
    assert market["pct"] == 1.0  # 0.75 * 2 + 0.25 * (-2)
    assert market["asOf"] == int(now.timestamp())


def test_market_snapshot_ignores_tickers_of_another_session():
    player = Player(player_id="fede", display_name="Fede")
    payload = webpage.build_payload(
        [(player, _series(5))],
        allocation={"AAPL": 900.0, "MSFT": 100.0},
        extended={"AAPL": _ext("pre", 3.0), "MSFT": _ext("post", -9.0)})
    # Manda la sesión mayoritaria por peso de datos; el rezagado no la contamina.
    assert payload["market"]["session"] == "pre"
    assert payload["market"]["pct"] == 3.0
    assert payload["market"]["count"] == 1


def test_market_snapshot_none_when_no_session_open():
    player = Player(player_id="fede", display_name="Fede")
    quote = {"state": "REGULAR", "session": None, "regular": 100.0}
    payload = webpage.build_payload(
        [(player, _series(5))], allocation={"AAPL": 100.0}, extended={"AAPL": quote})
    assert payload["market"] is None
    # El ticker conserva su cotización aunque no haya sesión extendida.
    assert payload["tickers"][0]["ext"] == quote


def test_market_closed_widget_shows_the_last_session_winner():
    """Con el mercado cerrado el widget no se queda en blanco.

    Antes pintaba un 🚧 sin ganador; ahora enseña al ganador de la última
    jornada cerrada y le añade la etiqueta de «mercado cerrado».
    """
    snippet = webpage._TEMPLATE.split("const marketClosed =", 1)[1].split(
        "// diferencia 1º - último", 1)[0]
    assert 'bv.textContent = fmtPct(bd.day)' in snippet
    assert 'tag.className = "closed-tag"' in snippet
    assert 'bDate.textContent = ""' not in snippet


def test_player_suggestion_prefers_highest_upside_buy():
    fede = Player(player_id="fede", display_name="Fede")
    holdings = {"fede": {"AAPL": 60.0, "MSFT": 40.0}}
    analysts = {
        "AAPL": {"label": "Comprar", "tone": "pos", "upside": 8.0, "count": 30},
        "MSFT": {"label": "Compra fuerte", "tone": "pos", "upside": 22.0, "count": 45},
    }
    payload = webpage.build_payload(
        [(fede, _series(5))], holdings=holdings, analysts=analysts)
    s = payload["players"][0]["suggestion"]
    assert s["ticker"] == "MSFT" and s["action"] == "buy"
    assert s["upside"] == 22.0 and s["w"] == 40.0


def test_player_suggestion_trims_negative_tone():
    fede = Player(player_id="fede", display_name="Fede")
    holdings = {"fede": {"AAPL": 100.0}}
    analysts = {"AAPL": {"label": "Vender", "tone": "neg", "upside": -15.0, "count": 20}}
    payload = webpage.build_payload(
        [(fede, _series(5))], holdings=holdings, analysts=analysts)
    s = payload["players"][0]["suggestion"]
    assert s["ticker"] == "AAPL" and s["action"] == "trim"


def _ev(day, kind, ticker=None, qty=1.0, total=100.0, at=None):
    return Event(day=day, kind=kind, ticker=ticker, quantity=qty,
                 total=total, currency="USD", at=at)


def test_recent_operations_across_players():
    fede = Player(player_id="fede", display_name="Fede", events=[
        _ev(date(2026, 7, 14), BUY, "AAPL"),
        _ev(date(2026, 7, 16), SELL, "MSFT"),
    ])
    ana = Player(player_id="ana", display_name="Ana", events=[
        _ev(date(2026, 7, 15), BUY, "NVDA"),
        _ev(date(2026, 7, 17), BUY, "TSM"),
    ])
    ops = webpage.build_payload(
        [(fede, _series(5)), (ana, _series(5))])["operations"]

    # De más nueva a más antigua, mezclando a los dos jugadores.
    assert [(o["date"], o["name"], o["kind"], o["ticker"]) for o in ops] == [
        ("2026-07-17", "Ana", "BUY", "TSM"),
        ("2026-07-16", "Fede", "SELL", "MSFT"),
        ("2026-07-15", "Ana", "BUY", "NVDA"),
        ("2026-07-14", "Fede", "BUY", "AAPL"),
    ]
    # El slot de color acompaña al jugador (ana < fede por orden alfabético de id).
    assert ops[0]["slot"] == 0 and ops[0]["id"] == "ana"
    assert ops[1]["slot"] == 1 and ops[1]["id"] == "fede"


def test_recent_operations_shows_a_whole_days_trading(tmp_path):
    """Una jornada movida de la liga cabe entera: no se corta a tres.

    Con el corte anterior, un día con cuatro operaciones dejaba fuera la más
    antigua de la jornada y parecía que no se había registrado.
    """
    def at(hh, mm):
        return datetime(2026, 8, 5, hh, mm)

    fede = Player(player_id="fede", display_name="Fede", events=[
        _ev(date(2026, 8, 5), BUY, "SNDK", at=at(14, 10)),
        _ev(date(2026, 8, 5), SELL, "NVDA", at=at(14, 5)),
    ])
    ana = Player(player_id="ana", display_name="Ana", events=[
        _ev(date(2026, 8, 5), BUY, "MU", at=at(8, 58)),
        _ev(date(2026, 8, 5), SELL, "MU", at=at(13, 35)),
    ])
    ops = webpage.build_payload(
        [(fede, _series(5)), (ana, _series(5))])["operations"]

    # Las cuatro, ordenadas por la hora del extracto (no por jugador).
    assert [(o["name"], o["kind"], o["ticker"]) for o in ops] == [
        ("Fede", "BUY", "SNDK"),
        ("Fede", "SELL", "NVDA"),
        ("Ana", "SELL", "MU"),
        ("Ana", "BUY", "MU"),
    ]


def test_recent_operations_are_capped():
    fede = Player(player_id="fede", display_name="Fede", events=[
        _ev(date(2026, 7, 1) + timedelta(days=i), BUY, "AAPL") for i in range(12)
    ])
    ops = webpage.build_payload([(fede, _series(5))])["operations"]
    assert len(ops) == 8
    assert ops[0]["date"] == "2026-07-12"          # la más reciente primero


def test_recent_operations_ignores_non_trades():
    fede = Player(player_id="fede", display_name="Fede", events=[
        _ev(date(2026, 7, 14), TOPUP, None),
        _ev(date(2026, 7, 15), FEE, None),
        _ev(date(2026, 7, 16), BUY, "AAPL"),
    ])
    ops = webpage.build_payload([(fede, _series(5))])["operations"]
    assert [(o["kind"], o["ticker"]) for o in ops] == [("BUY", "AAPL")]


def test_recent_operations_empty_without_events():
    fede = Player(player_id="fede", display_name="Fede")
    assert webpage.build_payload([(fede, _series(5))])["operations"] == []


def test_recent_operations_same_day_uses_statement_order():
    # Mismo día: la última fila del extracto es la operación más reciente.
    fede = Player(player_id="fede", display_name="Fede", events=[
        _ev(date(2026, 7, 16), BUY, "AAPL"),
        _ev(date(2026, 7, 16), SELL, "MSFT"),
    ])
    ops = webpage.build_payload([(fede, _series(5))])["operations"]
    assert [o["ticker"] for o in ops] == ["MSFT", "AAPL"]


def test_player_suggestion_absent_without_analyst_data():
    fede = Player(player_id="fede", display_name="Fede")
    holdings = {"fede": {"AAPL": 100.0}}
    payload = webpage.build_payload([(fede, _series(5))], holdings=holdings)
    assert "suggestion" not in payload["players"][0]


# ---- objetivo de la liga (14.000 antes del 1 de agosto) --------------------

_EUR = {"EUR": 1.0}


def _goal_series(end_value: float) -> list[DayResult]:
    """Una jornada cuyo cierre vale ``end_value`` (lo que mide el objetivo)."""
    return [DayResult(
        day=date(2026, 7, 14), start_value=end_value, end_value=end_value,
        external_flow=0.0, pnl=0.0, daily_return=0.0, cumulative_return=0.0,
    )]


def test_goal_countdown_targets_the_next_first_of_august():
    payload = webpage.build_payload(
        [(Player(player_id="fede", display_name="Fede"), _series(5))],
        today=date(2026, 8, 14))
    goal = payload["goal"]
    assert goal["deadline"] == "2027-08-01"
    assert goal["days"] == (date(2027, 8, 1) - date(2026, 8, 14)).days
    assert goal["target"] == 14000.0


def test_goal_countdown_before_the_first_of_august_stays_this_year():
    payload = webpage.build_payload(
        [(Player(player_id="fede", display_name="Fede"), _series(5))],
        today=date(2026, 7, 20))
    assert payload["goal"]["deadline"] == "2026-08-01"
    assert payload["goal"]["days"] == 12


def test_goal_deadline_day_itself_still_counts():
    payload = webpage.build_payload(
        [(Player(player_id="fede", display_name="Fede"), _series(5))],
        today=date(2026, 8, 1))
    assert payload["goal"] == {"target": 14000.0, "deadline": "2026-08-01",
                               "days": 0, "fx": {}}


def test_goal_progress_is_opt_in_per_player():
    """Sin ``show_goal`` no se publica el avance: delata el valor de la cartera."""
    quiet = Player(player_id="ana", display_name="Ana")
    payload = webpage.build_payload([(quiet, _goal_series(7000.0))], fx=_EUR)
    assert "goal" not in payload["players"][0]


def test_goal_progress_published_when_opted_in():
    fede = Player(player_id="fede", display_name="Fede",
                  currency="EUR", show_goal=True)
    payload = webpage.build_payload([(fede, _goal_series(7000.0))], fx=_EUR)
    # 7.000 € de 14.000 € = 50 %, y sin show_amounts no se publica el importe.
    assert payload["players"][0]["goal"] == {"target": 14000.0, "pct": 50.0}


def test_goal_converts_the_portfolio_to_euros():
    """El objetivo está en euros y la cartera se valora en dólares: se convierte.

    5.895 $ al cambio 1 $ = 0,848 € son 5.000 €, o sea el 36 % de 14.000 € —
    no el 42 % que salía comparando dólares contra euros.
    """
    fede = Player(player_id="fede", display_name="Fede",
                  currency="USD", show_goal=True, show_amounts=True)
    goal = webpage.build_payload([(fede, _goal_series(5895.4))],
                                 fx={"USD": 1 / 1.1791})["players"][0]["goal"]
    assert round(goal["value"]) == 5000
    assert goal["pct"] == 35.71
    assert goal["currency"] == "USD"


def test_goal_in_euros_carries_no_exchange_rate():
    fede = Player(player_id="fede", display_name="Fede",
                  currency="EUR", show_goal=True)
    payload = webpage.build_payload([(fede, _goal_series(7000.0))], fx=_EUR)
    assert "currency" not in payload["players"][0]["goal"]
    assert payload["goal"]["fx"] == {}          # nada que convertir


def test_exchange_rate_is_published_for_the_league_not_per_player():
    """El cambio es un precio de mercado: va en la cabecera, no en el jugador.

    Colgado de cada jugador desaparecía de la web en cuanto todos tenían su
    avance en privado — justo el dato que explica cómo se cuenta el objetivo.
    """
    fede = Player(player_id="fede", display_name="Fede",
                  currency="USD", show_goal=True)
    payload = webpage.build_payload([(fede, _goal_series(5895.4))],
                                    fx={"USD": 1 / 1.1791})
    assert round(payload["goal"]["fx"]["USD"], 4) == 0.8481
    assert "rate" not in payload["players"][0]["goal"]


def test_exchange_rate_survives_everyone_going_private():
    quiet = Player(player_id="ana", display_name="Ana", currency="USD")
    payload = webpage.build_payload([(quiet, _goal_series(5895.4))],
                                    fx={"USD": 1 / 1.1791})
    assert "goal" not in payload["players"][0]      # sin avance publicado
    assert round(payload["goal"]["fx"]["USD"], 4) == 0.8481   # pero sí el cambio


def test_only_the_currencies_in_play_are_published():
    fede = Player(player_id="fede", display_name="Fede", currency="USD")
    payload = webpage.build_payload(
        [(fede, _goal_series(1000.0))],
        fx={"USD": 0.85, "GBP": 1.18, "EUR": 1.0})
    assert set(payload["goal"]["fx"]) == {"USD"}   # ni GBP (nadie) ni EUR (1:1)


def test_goal_without_exchange_rate_says_so_instead_of_guessing():
    """Sin cambio no se enseña un porcentaje inventado: se dice que falta."""
    fede = Player(player_id="fede", display_name="Fede",
                  currency="USD", show_goal=True, show_amounts=True)
    goal = webpage.build_payload([(fede, _goal_series(5895.4))],
                                 fx={})["players"][0]["goal"]
    assert goal == {"target": 14000.0, "noFx": True, "currency": "USD"}
    assert "pct" not in goal and "value" not in goal


def test_goal_progress_includes_the_amount_only_with_show_amounts():
    fede = Player(player_id="fede", display_name="Fede", currency="EUR",
                  show_goal=True, show_amounts=True)
    goal = webpage.build_payload([(fede, _goal_series(3500.0))],
                                 fx=_EUR)["players"][0]["goal"]
    assert goal == {"target": 14000.0, "pct": 25.0, "value": 3500.0}


def test_goal_progress_uses_the_players_own_target():
    fede = Player(player_id="fede", display_name="Fede", currency="EUR",
                  goal=7000.0, show_goal=True)
    goal = webpage.build_payload([(fede, _goal_series(3500.0))],
                                 fx=_EUR)["players"][0]["goal"]
    assert goal["target"] == 7000.0 and goal["pct"] == 50.0


def test_goal_progress_can_go_past_the_target():
    fede = Player(player_id="fede", display_name="Fede",
                  currency="EUR", show_goal=True)
    goal = webpage.build_payload([(fede, _goal_series(21000.0))],
                                 fx=_EUR)["players"][0]["goal"]
    assert goal["pct"] == 150.0


def test_goal_progress_never_goes_negative():
    fede = Player(player_id="fede", display_name="Fede",
                  currency="EUR", show_goal=True)
    goal = webpage.build_payload([(fede, _goal_series(-50.0))],
                                 fx=_EUR)["players"][0]["goal"]
    assert goal["pct"] == 0.0


def test_goal_module_reaches_the_html(tmp_path):
    fede = Player(player_id="fede", display_name="Fede",
                  currency="EUR", show_goal=True)
    out = tmp_path / "index.html"
    webpage.write_index([(fede, _goal_series(7000.0))], out_path=str(out),
                        today=date(2026, 8, 14), fx=_EUR)
    html = out.read_text(encoding="utf-8")
    assert "goal-card" in html and "paintGoal" in html
    assert '"deadline": "2027-08-01"' in html or '"deadline":"2027-08-01"' in html


def test_long_lists_collapse_to_five(tmp_path):
    """Los listados largos se pintan a 5 y el resto va tras «ver más»."""
    out = tmp_path / "index.html"
    webpage.write_index([(Player(player_id="fede", display_name="Fede"), _series(9))],
                        out_path=str(out))
    html = out.read_text(encoding="utf-8")
    assert "const LIST_MAX = 5;" in html
    assert "function collapseList(rows, host)" in html
    # y se aplica a cada listado que puede crecer
    assert html.count("collapseList(") >= 8


def _lang_block(code: str) -> str:
    """Cuerpo del bloque ``code`` de ``I18N`` (las traducciones de ese idioma)."""
    blocks = webpage._TEMPLATE.split("const I18N = {", 1)[1].split("\nconst T = I18N", 1)[0]
    return blocks.split("\n  %s: {\n" % code, 1)[1].split("\n  },\n", 1)[0]


def _lang_keys(code: str) -> set[str]:
    """Nombres de clave del bloque ``code`` de ``I18N`` (incluidos los anidados)."""
    return set(re.findall(r"^\s+([A-Za-z]\w*):", _lang_block(code), re.M))


def test_language_selector_offers_english_japanese_and_french():
    assert '{code: "en"' in webpage._TEMPLATE
    assert '{code: "ja"' in webpage._TEMPLATE
    assert '{code: "fr"' in webpage._TEMPLATE
    # el selector se pinta a partir de esa lista, no de un toggle de dos
    assert 'LANGS.forEach(l => {' in webpage._TEMPLATE
    # cada idioma con nombre propio tiene su manifest (nombre de la app)
    assert os.path.exists("docs/manifest-ja.webmanifest")
    assert os.path.exists("docs/manifest-fr.webmanifest")


def test_french_translates_every_string():
    """El francés cubre exactamente las mismas claves que el inglés."""
    en = _lang_keys("en")
    assert "appTitle" in en and "footer" in en  # el bloque se ha leído bien
    assert _lang_keys("fr") == en == _lang_keys("ja")


def test_canada_banner_links_to_the_official_tourism_site():
    assert 'id="ca-banner"' in webpage._TEMPLATE
    assert 'banner.href = T.caHref' in webpage._TEMPLATE
    for locale in ("en-ca", "ja-jp", "fr-fr"):
        assert 'https://travel.destinationcanada.com/' + locale in webpage._TEMPLATE


def test_canada_banner_is_a_single_short_line_without_a_button():
    """El banner es bajito: titular, una línea de texto y ya. Sin botón."""
    assert "ccta" not in webpage._TEMPLATE and "caCta" not in webpage._TEMPLATE
    # el subtítulo de cada idioma cabe en una línea (nada de párrafos)
    for locale in ("en", "ja", "fr"):
        sub = re.search(r'caSub: "([^"]*)"', _lang_block(locale)).group(1)
        assert len(sub) <= 45, (locale, sub)


def test_charts_are_drawn_with_smooth_monotone_curves():
    """Las líneas se dibujan con curvas (C), no con segmentos rectos (L)."""
    assert "function smoothD(pts)" in webpage._TEMPLATE
    # las dos gráficas de líneas (el spark de las tarjetas y la del mes) pasan
    # por el mismo suavizado, y ninguna arma ya el camino a base de "L"
    calls = webpage._TEMPLATE.count("smoothD(pts)") - 1  # sin la definición
    assert calls == 2
    assert '(i ? "L" : "M")' not in webpage._TEMPLATE


def test_gains_are_green_and_losses_red():
    """Verde arriba y rojo abajo, en los tres bloques de tema."""
    ups = re.findall(r"--up: (#[0-9a-f]{6});", webpage._TEMPLATE)
    downs = re.findall(r"--down: (#[0-9a-f]{6});", webpage._TEMPLATE)
    assert len(ups) == len(downs) == 3

    def rgb(c):
        return tuple(int(c[i:i + 2], 16) for i in (1, 3, 5))

    for c in ups:  # el verde manda: más verde que rojo y que azul
        r, g, b = rgb(c)
        assert g > r and g > b, c
    for c in downs:  # el rojo manda, y sin azul de sobra (carmín, no rosa)
        r, g, b = rgb(c)
        assert r > g and r > b and b <= g + 10, c


def test_the_theme_accent_is_orange():
    """El color de marca (botones, enlaces, estado activo) es naranja."""
    accents = re.findall(r"--accent: (#[0-9a-f]{6});", webpage._TEMPLATE)
    assert len(accents) == 3  # claro, oscuro del sistema y oscuro forzado
    for c in accents:
        r, g, b = (int(c[i:i + 2], 16) for i in (1, 3, 5))
        # naranja: el rojo manda, el verde va a media altura y el azul casi no está
        assert r > g > b, c
        assert b < r // 3, c


def test_players_use_the_warm_orange_and_brown_palette():
    """Naranja, marrón y ocres: los colores de jugador son su propia familia."""
    assert 'const SLOTS = ["--p1"' in webpage._TEMPLATE
    # los ocho tonos están definidos en los tres bloques de tema (claro, oscuro
    # por preferencia del sistema y oscuro forzado)
    for slot in range(1, 9):
        assert webpage._TEMPLATE.count("--p%d: #" % slot) == 3
