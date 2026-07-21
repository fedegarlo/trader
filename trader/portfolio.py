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
from dataclasses import dataclass, replace
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


def compute_daily_series(
    events: list[Event],
    prices: PriceCache,
    until: date | None = None,
) -> list[DayResult]:
    """Serie diaria de valor, P&L y rentabilidad a partir de los eventos.

    Solo se genera una fila en los días con información de mercado (algún valor
    de la cartera tiene cierre real ese día). Los días sin cotización —fines de
    semana, festivos y la jornada en curso antes del cierre— no aportan
    rentabilidad real (el precio se arrastraría del último cierre), así que se
    omiten. Los flujos de efectivo de esos días se acumulan hasta la siguiente
    jornada de mercado, para que no se pierdan ni cuenten como ganancia.
    """
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

    def is_market_day(day: date) -> bool:
        # Hay información de mercado si algún valor de la cartera cotizó ese día
        # (cierre real en la caché). Una cartera que nunca ha tenido valores
        # (solo efectivo) no tiene con qué distinguir: se conservan todos los días.
        if not tickers:
            return True
        return any(prices.has_close(t, day) for t in tickers)

    positions: dict[str, float] = {}
    cash = 0.0
    prev_value = 0.0
    cumulative = 1.0
    pending_flow = 0.0
    results: list[DayResult] = []

    day = first
    while day <= last:
        for ev in by_day.get(day, ()):
            cash, ev_flow = _apply_event(ev, positions, cash)
            pending_flow += ev_flow

        if is_market_day(day):
            flow = pending_flow
            pending_flow = 0.0
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


def rebase_from(series: list[DayResult], start: date) -> list[DayResult]:
    """Recorta la serie a los días ``>= start`` y recompone la rentabilidad
    acumulada desde ese día.

    Los días anteriores a ``start`` (histórico previo o pruebas) no cuentan: la
    competición empieza en ``start`` (incluido) y todos los jugadores se comparan
    desde la misma fecha. La rentabilidad diaria de cada día se conserva; solo se
    recompone el acumulado (``prod(1 + r_dia) - 1``) sobre los días de la
    competición.
    """
    cumulative = 1.0
    out: list[DayResult] = []
    for r in series:
        if r.day < start:
            continue
        cumulative *= 1.0 + r.daily_return
        out.append(replace(r, cumulative_return=cumulative - 1.0))
    return out
