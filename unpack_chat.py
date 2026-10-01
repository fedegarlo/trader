#!/usr/bin/env python3
"""Desempaqueta trader/webpage.py y trader/web/{style.css,boot.js,app.js}."""
from __future__ import annotations

import base64
import gzip
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PACK = ROOT / "trader" / "web" / "_pack"
DEST = {
    "webpage.py": ROOT / "trader" / "webpage.py",
    "style.css": ROOT / "trader" / "web" / "style.css",
    "boot.js": ROOT / "trader" / "web" / "boot.js",
    "app.js": ROOT / "trader" / "web" / "app.js",
}


def main() -> None:
    for name, dest in DEST.items():
        parts = sorted(PACK.glob(name + ".p*"))
        if not parts:
            raise SystemExit(f"faltan partes de {name}")
        blob = gzip.decompress(base64.b64decode("".join(p.read_text() for p in parts)))
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(blob)
        print(f"{name} -> {dest} ({len(blob)} bytes)")


if __name__ == "__main__":
    main()
