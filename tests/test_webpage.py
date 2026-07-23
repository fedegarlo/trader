"""La página embebe solo los últimos 30 días, pero conserva inicio y acumulado."""

from datetime import date, timedelta

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


def test_payload_limits_to_last_30_days():
    player = Player(player_id="fede", display_name="Fede")
    series = _series(45)
    payload = webpage.build_payload([(player, series)])
    p = payload["players"][0]

    # Solo las últimas 30 jornadas hábiles en la ventana visible.
    assert len(p["days"]) == 30
    assert p["days"][0]["date"] == series[-30].day.isoformat()   # jornada 45-30+1
    assert p["days"][-1]["date"] == series[-1].day.isoformat()   # jornada 45

    # Pero la fecha de inicio real y el acumulado se conservan.
    assert p["since"] == series[0].day.isoformat()
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
    assert cur["spark"] == [5.0, 3.95]
    # Junio no tiene datos de competición: sin widget de mes pasado.
    assert payload["monthly"]["previous"] is None


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


def test_ticker_details_no_analyst_key_without_data():
    player = Player(player_id="fede", display_name="Fede")
    payload = webpage.build_payload([(player, _series(5))], allocation={"AAPL": 100.0})
    assert "analyst" not in payload["tickers"][0]


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


def _ev(day, kind, ticker=None, qty=1.0, total=100.0):
    return Event(day=day, kind=kind, ticker=ticker, quantity=qty,
                 total=total, currency="USD")


def test_recent_operations_last_three_across_players():
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

    # Las tres más recientes de toda la liga, de más nueva a más antigua.
    assert [(o["date"], o["name"], o["kind"], o["ticker"]) for o in ops] == [
        ("2026-07-17", "Ana", "BUY", "TSM"),
        ("2026-07-16", "Fede", "SELL", "MSFT"),
        ("2026-07-15", "Ana", "BUY", "NVDA"),
    ]
    # El slot de color acompaña al jugador (ana < fede por orden alfabético de id).
    assert ops[0]["slot"] == 0 and ops[0]["id"] == "ana"
    assert ops[1]["slot"] == 1 and ops[1]["id"] == "fede"


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
