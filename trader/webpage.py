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

# La competición oficial empezó este día: los días anteriores (pruebas o
# histórico previo) no cuentan. Todos los jugadores se comparan desde esta
# fecha (incluida), rebasando la rentabilidad acumulada al inicio real de la
# competición (ver ``rebase_from`` en portfolio.py), y también acota los
# widgets de «mejor del mes».
COMPETITION_START = date(2026, 7, 14)

# El objetivo de la liga tiene fecha: el 1 de agosto. Es una meta que se
# renueva cada año, así que la cuenta atrás mira siempre al **próximo** 1 de
# agosto (el mismo día 1 todavía cuenta como plazo abierto, con 0 días).
GOAL_MONTH, GOAL_DAY = 8, 1

# Quién invita y **dónde**: el ganador del mes paga la comida, y su propia
# rentabilidad decide el precio del sitio. Cuanto mejor le haya ido, más caro
# es el restaurante; un mes en rojo se salda con unas cañas.
#
# La escala vive aquí (y viaja entera al payload, ``treatScale``) para que la
# página, el README y las pruebas hablen del mismo baremo. Cada peldaño lleva:
#
# - ``min``: rentabilidad mensual (en %) a partir de la cual se entra en él;
#   ``None`` es el primero, el de los meses en negativo.
# - ``euros``: los € de la categoría, como en cualquier guía.
# - ``price``: precio orientativo por persona (en euros, bebida incluida); en
#   el último peldaño se lee como «a partir de».
# - ``places``: restaurantes de Madrid de ejemplo, solo como referencia de a
#   qué precio juega cada escalón.
#
# El nombre de cada peldaño se traduce en el cliente (``treatTiers``): aquí no
# hay texto que traducir, solo el baremo.
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
    """Peldaño de :data:`TREAT_TIERS` que le toca a una rentabilidad mensual.

    ``value`` va en porcentaje (el mismo que se pinta en el widget), así que el
    tramo y el número que se enseña nunca se contradicen. Devuelve ``None`` si
    no hay dato.
    """
    if value is None:
        return None
    tier = 0
    for i, step in enumerate(TREAT_TIERS):
        if step["min"] is not None and value >= step["min"]:
            tier = i
    return tier



def _read_web_text(web: Path, name: str) -> str:
    """Lee ``trader/web/<name>`` o, si falta, concatena ``_pack/<name>.p*``.

    Las partes son texto UTF-8 crudo (no gzip): así el ensamblado no depende
    de un script extra y GitHub puede recibir el CSS/JS en trozos pequeños.
    """
    direct = web / name
    if direct.is_file() and direct.stat().st_size:
        return direct.read_text(encoding="utf-8")
    parts = sorted((web / "_pack").glob(name + ".p*"))
    if not parts:
        raise FileNotFoundError(direct)
    return "".join(p.read_text(encoding="utf-8") for p in parts)


def _assemble_template() -> str:
    """Junta cabecera, CSS, cuerpo y JS de ``trader/web`` en un HTML autocontenido."""
    web = Path(__file__).resolve().parent / "web"
    css = _read_web_text(web, "style.css")
    head = _read_web_text(web, "head.html").replace("/* __PAGE_CSS__ */", css)
    body = _read_web_text(web, "body.html")
    boot = _read_web_text(web, "boot.js")
    app = _read_web_text(web, "app.js")
    return (
        head
        + body
        + "<script>\n"
        + boot
        + app
        + "</script>\n</body>\n</html>\n"
    )


_TEMPLATE = _assemble_template()


def _allocation_weights(allocation: dict[str, float] | None) -> list[dict]:
    """Normaliza el valor de mercado agregado por ticker a pesos (%).

    Recibe ``{ticker: valor}`` (agregado de toda la liga) y devuelve una lista
    ordenada de mayor a menor ``[{\"ticker\", \"w\"}]`` con el peso en porcentaje.
    Solo se exponen pesos, nunca importes: el mix agregado no revela ni las
    operaciones ni el dinero de ningún jugador.
    """
    if not allocation:
        return []
    total = sum(v for v in allocation.values() if v > 0)
    if total <= 0:
        return []
    out = [{"ticker": t, "w": round(v / total * 100, 2)}
           for t, v in allocation.items() if v > 0]
    out.sort(key=lambda d: d["w"], reverse=True)
    return out
