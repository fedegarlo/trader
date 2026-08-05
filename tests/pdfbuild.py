"""Generador de PDF mínimo para los tests (una página, texto plano).

Evita depender de una librería de escritura de PDF y, sobre todo, evita
guardar en el repositorio un extracto real (que lleva nombre, dirección y
número de cuenta). Los tests construyen aquí el texto que Revolut imprime.
"""

from __future__ import annotations


def _escape(line: str) -> bytes:
    data = line.encode("cp1252", errors="replace")
    for char, repl in ((b"\\", b"\\\\"), (b"(", b"\\("), (b")", b"\\)")):
        data = data.replace(char, repl)
    return data


def make_pdf(lines: list[str]) -> bytes:
    """PDF de una página con una línea de texto por elemento de ``lines``."""
    body = b"BT\n/F1 9 Tf\n11 TL\n1 0 0 1 30 780 Tm\n"
    for line in lines:
        body += b"(" + _escape(line) + b") Tj T*\n"
    body += b"ET\n"

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length " + str(len(body)).encode() + b" >>\nstream\n" + body + b"endstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
        b"/Encoding /WinAnsiEncoding >>",
    ]

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + obj + b"\nendobj\n"

    xref_at = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode() + b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_at}\n%%EOF\n").encode()
    return bytes(out)
