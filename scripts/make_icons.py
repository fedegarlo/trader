#!/usr/bin/env python3
"""Genera los iconos de la app (pantalla de inicio) a partir de un logo SVG.

El logo es el kanji japones 株 (kabu, «accion / valor bursatil») en blanco
sobre dos fondos:
  - iPhone (apple-touch-icon): azul de ganancias  -> docs/icon-ios.png
  - Android (manifest):        rosa de perdidas    -> docs/icon-android-*.png

Ejecuta:  python3 scripts/make_icons.py
Requiere: cairosvg y una fuente japonesa instalada (p. ej. IPAGothic,
          paquete fonts-ipafont-gothic). El nombre de familia se puede
          ajustar con la variable de entorno ICON_FONT.
"""
from __future__ import annotations

import os

import cairosvg

HERE = os.path.dirname(os.path.abspath(__file__))
DOCS = os.path.normpath(os.path.join(HERE, "..", "docs"))

BLUE = "#1667e0"   # --up (ganancias)
PINK = "#d61f8f"   # --down (perdidas)

# Kanji 株 (kabu = accion/valor). Fuente japonesa; se puede sobreescribir con
# ICON_FONT si el sistema usa otra familia (Noto Sans CJK JP, etc.).
FONT = os.environ.get("ICON_FONT", "IPAGothic")

# El glifo se centra y se mantiene dentro de la «safe zone» central (~80%)
# para que la mascara circular de Android (iconos maskable) no lo recorte.
LOGO = """
  <text x="256" y="272" fill="#ffffff" font-family="{font}" font-weight="bold"
        font-size="300" text-anchor="middle" dominant-baseline="central">株</text>
""".format(font=FONT)

SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512">
  <rect width="512" height="512" rx="0" ry="0" fill="{bg}"/>
  {logo}
</svg>"""


def render(bg: str, out: str, size: int) -> None:
    svg = SVG.format(bg=bg, logo=LOGO)
    cairosvg.svg2png(
        bytestring=svg.encode("utf-8"),
        write_to=os.path.join(DOCS, out),
        output_width=size,
        output_height=size,
    )
    print("escrito", out, f"{size}x{size}")


def main() -> None:
    # iPhone: iOS aplica su propia mascara redondeada -> fondo a sangre.
    render(BLUE, "icon-ios.png", 180)
    # Android / PWA: manifest necesita 192 y 512.
    render(PINK, "icon-android-192.png", 192)
    render(PINK, "icon-android-512.png", 512)


if __name__ == "__main__":
    main()
