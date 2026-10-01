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

TREAT_TIERS: list[dict] = [
    {"min": None, "euros": "€", "price": 15,
     "places": ["El Tigre", "Casa Julio", "Bar Santurce"]},
    {"min": 0.0, "euros": "€€", "price": 30,
     "places": ["La Ardosa", "La Musa", "La Carmencita"]},
    {"min": 2.5, "euros": "€€€", "price": 55,
     "places": ["Casa Lucio", "Sala de Despiece", "Ten con Ten"]},
    {"min": 5.0, "euros": "€€€€", "price": 110,
     "places": ["Sacha", "Horcher", "Kabuki"]},
    {"min": 10.0, "euros": "€€€€€", "price": 200,
     "places": ["DiverXO", "Coque", "DSTAgE"]},
]


def treat_tier(value: float | None) -> int | None:
    if value is None:
        return None
    tier = 0
    for i, step in enumerate(TREAT_TIERS):
        if step["min"] is not None and value >= step["min"]:
            tier = i
    return tier


def _assemble_template() -> str:
    web = Path(__file__).resolve().parent / "web"
    css = (web / "style.css").read_text(encoding="utf-8")
    head = (web / "head.html").read_text(encoding="utf-8").replace("/* __PAGE_CSS__ */", css)
    body = (web / "body.html").read_text(encoding="utf-8")
    boot = (web / "boot.js").read_text(encoding="utf-8")
    app = (web / "app.js").read_text(encoding="utf-8")
    return (
        head
        + body
        + "<script>\n"
        + boot
        + app
        + "</script>\n</body>\n</html>\n"
    )


_TEMPLATE = _assemble_template()
