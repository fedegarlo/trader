"""Reconstrucción diaria de la cartera y cálculo de rentabilidad.

Para cada día natural desde la primera operación:

* se aplican los eventos del día (compras, ventas, dividendos, comisiones,
  ingresos y retiradas de efectivo),
* se valora la cartera al cierre (efectivo + acciones a precio de cierre),
* se calcula la rentabilidad del día con la fórmula de Dietz simple, que
  neutraliza los flujos externos: ingresar más dinero no sube la puntuación.

      r_dia = (V_fin - V_ini - flujo) / (V_ini + flujo/2)

La rentabilidad acumulada es la composición geométrica de las diarias:
``prod(1 + r_dia) - 1`` (time-weighted return), que es la métrica justa
para comparar jugadores con importes distintos.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

from .prices import PriceCache
from .revolut import BUY, DIVIDEND, FEE, SELL, SPLIT, TOPUP, WITHDRAWAL, Event


@dataclass(frozen=True)
class DayResult:
    day: date
    start_value: float   # valor de la cartera al empezar el día
    end_value: float     # valor al cierre
    external_flow: float # ingresos - retiradas del día
    pnl: float           # ganancia/pérdida del día en importe
    daily_return: float  # rentabilidad del día (0.01 = 1 %)
    cumulative_return: float  # acumulada desde el inicio


def _apply_event(ev: Event, positions: dict[str, float], cash: float) -> tuple[float, float]:
    """Aplica un evento. Devuelve (cash, flujo_externo_del_evento)."""
    if ev.kind == BUY:
        positions[ev.ticker] = positions.get(ev.ticker, 0.0) + ev.quantity
        return cash - ev.total, 0.0
    if ev.kind == SELL:
        positions[ev.ticker] = positions.get(ev.ticker, 0.0) - ev.quantity
        if abs(positions[ev.ticker]) < 1e-9:
            del positions[ev.ticker]
        return cash + ev.total, 0.0
    if ev.kind == TOPUP:
        return cash + ev.total, ev.total
    if ev.kind == WITHDRAWAL:
        return cash - ev.total, -ev.total
    if ev.kind == DIVIDEND:
        return cash + ev.total, 0.0
    if ev.kind == FEE:
        return cash - ev.total, 0.0
    if ev.kind == SPLIT:
        # Revolut refleja los splits como ajuste de cantidad sin importe.
        if ev.ticker and ev.quantity:
            positions[ev.ticker] = positions.get(ev.ticker, 0.0) + ev.quantity
        return cash, 0.0
    return cash, 0.0


def _positions_at(events: list[Event], until: date) -> tuple[dict[str, float], float]:
    """Reproduce los eventos hasta ``until`` y devuelve (posiciones, efectivo)."""
    positions: dict[str, float] = {}
    cash = 0.0
    for ev in events:
        if ev.day > until:
            continue
        cash, _ = _apply_event(ev, positions, cash)
    return {t: q for t, q in positions.items() if q > 1e-9}, cash


def holdings_value(
    events: list[Event],
    prices: PriceCache,
    until: date | None = None,
) -> dict[str, float]:
    """Valor de mercado por ticker de la cartera al último día.

    Reproduce todos los eventos y valora las posiciones abiertas al cierre de
    ``until`` (o del último día con datos). Devuelve ``{ticker: valor}`` en la
    divisa del extracto; solo incluye posiciones con cantidad positiva. El
    efectivo no se incluye (el widget muestra el reparto entre acciones).
    """
    if not events:
        return {}

    days = [ev.day for ev in events]
    last = until or max(max(days), date.today())

    tickers = {ev.ticker for ev in events if ev.ticker and ev.kind in (BUY, SELL, SPLIT)}
    for ticker in tickers:
        prices.ensure_range(ticker, min(days), last)

    positions, _ = _positions_at(events, last)
    return {t: qty * prices.close_on(t, last) for t, qty in positions.items()}


def provisional_today(
    events: list[Event],
    series: list[DayResult],
    prices: PriceCache,
    live_price,
) -> dict[str, float] | None:
    """Revalora *solo hoy* con precios en vivo, sin tocar la serie oficial.

    Es un indicador provisional: la rentabilidad del día se recalcula usando
    ``live_price(ticker)`` (que puede devolver ``None`` si no hay cotización) y
    se compone sobre el acumulado hasta *ayer* de la serie oficial. No escribe
    en la caché ni altera la clasificación. Devuelve ``{"cum", "day"}`` en % o
    ``None`` si no hay posiciones abiertas o ninguna cotización en vivo.
    """
    if not events or not series:
        return None
    today = series[-1].day
    positions, cash = _positions_at(events, today)
    if not positions:
        return None

    prices_now: dict[str, float] = {}
    any_live = False
    for ticker in positions:
        live = live_price(ticker)
        if live is not None:
            prices_now[ticker] = float(live)
            any_live = True
        else:
            prices_now[ticker] = prices.close_on(ticker, today)
    if not any_live:
        return None

    last = series[-1]
    end_value = cash + sum(qty * prices_now[t] for t, qty in positions.items())
    denom = last.start_value + last.external_flow / 2.0
    daily = (end_value - last.start_value - last.external_flow) / denom if denom > 1e-9 else 0.0
    base = 1.0 + (series[-2].cumulative_return if len(series) >= 2 else 0.0)
    cumulative = base * (1.0 + daily) - 1.0
    return {"cum": round(cumulative * 100, 4), "day": round(daily * 100, 4)}


def compute_daily_series(
    events: list[Event],
    prices: PriceCache,
    until: date | None = None,
) -> list[DayResult]:
    """Serie diaria de valor, P&L y rentabilidad a partir de los eventos."""
    if not events:
        return []

    by_day: dict[date, list[Event]] = defaultdict(list)
    for ev in events:
        by_day[ev.day].append(ev)

    first = min(by_day)
    last = until or max(max(by_day), date.today())

    tickers = {ev.ticker for ev in events if ev.ticker and ev.kind in (BUY, SELL, SPLIT)}
    for ticker in tickers:
        prices.ensure_range(ticker, first, last)

    positions: dict[str, float] = {}
    cash = 0.0
    prev_value = 0.0
    cumulative = 1.0
    results: list[DayResult] = []

    day = first
    while day <= last:
        flow = 0.0
        for ev in by_day.get(day, ()):
            cash, ev_flow = _apply_event(ev, positions, cash)
            flow += ev_flow

        end_value = cash + sum(
            qty * prices.close_on(ticker, day) for ticker, qty in positions.items()
        )
        pnl = end_value - prev_value - flow
        denom = prev_value + flow / 2.0
        daily_return = pnl / denom if denom > 1e-9 else 0.0
        cumulative *= 1.0 + daily_return

        results.append(DayResult(
            day=day,
            start_value=prev_value,
            end_value=end_value,
            external_flow=flow,
            pnl=pnl,
            daily_return=daily_return,
            cumulative_return=cumulative - 1.0,
        ))
        prev_value = end_value
        day += timedelta(days=1)

    return results
