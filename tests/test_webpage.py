"""La página embebe la serie completa de cada jugador (la liga es desde el inicio)."""

import os
import re
from datetime import date, datetime, timedelta, timezone

from trader import webpage
from trader.players import Player
from trader.portfolio import DayResult
from trader.revolut import BUY, FEE, SELL, TOPUP, Event
