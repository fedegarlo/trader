"""Genera docs/index.html: dashboard estático para GitHub Pages.

Autocontenido (datos embebidos, sin CDNs). La portada es un **hilo de
conversación** al estilo de los agentes (dibujitos + burbujas): Warren
(Trader) y Scout (Watch) van contando la liga, y debajo de cada turno
siguen los mismos módulos de siempre. De primero, el «Canada Grand Prix
26/27»: el banner de turismo de Canadá hace de cabecera de la clasificación
general —el viaje es el premio—, debajo va quién lo lleva ganado (líder y
podio) y luego la clasificación en formato tabla (1º, 2º, 3º… con su
acumulado y el % de la última jornada). El mes en curso se cuenta igual, con
su propia carrera: el «Gran Premio de la ciudad de Vancouver», con el banner
del ayuntamiento (vancouver.ca) de cabecera, el líder y el podio del mes, y
detrás la gráfica de todos los jugadores. Las líneas van suavizadas (spline
cúbico monótono, sin sobreoscilación) y el color se asigna a cada jugador por
orden alfabético de id (estable: no cambia si cambia su posición en el
ranking) de una paleta cálida: naranja, marrón y ocres.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from datetime import date, datetime, time, timezone

from .players import DEFAULT_GOAL, Player
from .portfolio import CASH_KEY, DayResult
from .revolut import BUY, SELL
from .tickers import ticker_meta

COMPETITION_START = date(2026, 7, 14)
GOAL_MONTH, GOAL_DAY = 8, 1
