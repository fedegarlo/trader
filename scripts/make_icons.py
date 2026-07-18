#!/usr/bin/env python3
"""Genera los iconos de la app (pantalla de inicio) a partir de un logo SVG.

Un mismo logo de trading en blanco sobre dos fondos:
  - iPhone (apple-touch-icon): azul de ganancias  -> docs/icon-ios.png
  - Android (manifest):        rosa de perdidas    -> docs/icon-android-*.png

Ejecuta:  python3 scripts/make_icons.py
Requiere: cairosvg
"""
from __future__ import annotations

import os

import cairosvg

HERE = os.path.dirname(os.path.abspath(__file__))
DOCS = os.path.normpath(os.path.join(HERE, "..", "docs"))

BLUE = "#1667e0"   # --up (ganancias)
PINK = "#d61f8f"   # --down (perdidas)

# Logo de trading en blanco: linea de tendencia ascendente con flecha,
# velas (candlesticks) crecientes y una linea base. viewBox 512x512.
# El contenido se mantiene dentro de la "safe zone" central (~80%) para
# que la mascara circular de Android (iconos maskable) no lo recorte.
LOGO = """
  <g fill="none" stroke="#ffffff" stroke-linecap="round" stroke-linejoin="round">
    <!-- ejes -->
    <path d="M140 128 L140 384 L400 384" stroke-width="22" opacity="0.5"/>
    <!-- linea de tendencia ascendente -->
    <path d="M172 332 L246 288 L306 314 L392 176" stroke-width="34"/>
    <!-- flecha (chevron apuntando arriba-derecha) -->
    <path d="M330 176 L392 176 L392 238" stroke-width="34"/>
    <!-- marcadores en los vertices -->
    <g fill="#ffffff" stroke="none">
      <circle cx="172" cy="332" r="17"/>
      <circle cx="246" cy="288" r="17"/>
      <circle cx="306" cy="314" r="17"/>
    </g>
  </g>
"""

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
