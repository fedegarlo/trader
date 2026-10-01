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
        if day.weekday() < 5:
            cum += 0.01
            out.append(DayResult(
                day=day,
                start_value=100.0, end_value=101.0, external_flow=0.0, pnl=1.0,
                daily_return=0.01, cumulative_return=cum,
            ))
        day += timedelta(days=1)
    return out
