#!/usr/bin/env python3
"""Genera los iconos de la app a partir de una imagen fuente cuadrada.

Fuente: scripts/assets/icon-source.jpg (dos trazos blancos sobre azul).
Salidas en docs/:
  - icon-ios.png            180x180  apple-touch-icon (iPhone, marcadores)
  - icon-android-192/512    manifest (Android / PWA, maskable)
  - favicon-32.png, favicon.ico     pestaña del navegador
  - og-image.png            1200x630 vista previa al compartir el enlace

Ejecuta:  python3 scripts/make_icons.py
Requiere: ImageMagick (`convert`).
"""
from __future__ import annotations

import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
DOCS = os.path.normpath(os.path.join(HERE, "..", "docs"))
SRC = os.path.join(HERE, "assets", "icon-source.jpg")

BG = "#3c82f4"  # azul del fondo de la imagen fuente


def convert(*args: str) -> None:
    subprocess.run(["convert", SRC, *args], check=True)


def square(out: str, size: int) -> None:
    convert("-resize", f"{size}x{size}", "-strip", os.path.join(DOCS, out))
    print("escrito", out, f"{size}x{size}")


def main() -> None:
    # iOS aplica su propia mascara redondeada -> fondo a sangre. El logo ya
    # cae dentro de la «safe zone» central, asi que sirve tambien como maskable.
    square("icon-ios.png", 180)
    square("icon-android-192.png", 192)
    square("icon-android-512.png", 512)
    square("favicon-32.png", 32)
    convert("-define", "icon:auto-resize=48,32,16", os.path.join(DOCS, "favicon.ico"))
    print("escrito favicon.ico")
    # Vista previa social: el logo centrado sobre el mismo azul.
    convert("-resize", "630x630", "-background", BG, "-gravity", "center",
            "-extent", "1200x630", "-strip", os.path.join(DOCS, "og-image.png"))
    print("escrito og-image.png 1200x630")


if __name__ == "__main__":
    main()
