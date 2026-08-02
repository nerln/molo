"""Genera le icone PNG dell'app senza dipendenze grafiche.

Pillow non è fra le dipendenze di Molo e non ha senso aggiungerlo per due file
statici. Qui disegniamo con campi di distanza (l'antialiasing viene gratis) e
scriviamo il PNG a mano: sono ~40 righe di zlib e struct.

    python3 scripts/make_icons.py
"""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "molo" / "web" / "icons"

BG_TOP = (18, 48, 92)
BG_BOTTOM = (10, 17, 32)
ACCENT = (63, 208, 189)


def _mix(a, b, t):
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def _smooth(edge0, edge1, x):
    t = max(0.0, min(1.0, (x - edge0) / (edge1 - edge0)))
    return t * t * (3 - 2 * t)


def _seg_dist(px, py, ax, ay, bx, by):
    """Distanza punto-segmento: dà linee con estremi arrotondati."""
    vx, vy = bx - ax, by - ay
    wx, wy = px - ax, py - ay
    length = vx * vx + vy * vy
    t = 0.0 if length == 0 else max(0.0, min(1.0, (wx * vx + wy * vy) / length))
    dx, dy = wx - t * vx, wy - t * vy
    return (dx * dx + dy * dy) ** 0.5


def _rounded_box(px, py, size, radius):
    """Distanza con segno da un quadrato con angoli arrotondati."""
    half = size / 2
    qx = abs(px - half) - (half - radius)
    qy = abs(py - half) - (half - radius)
    ax, ay = max(qx, 0.0), max(qy, 0.0)
    return (ax * ax + ay * ay) ** 0.5 + min(max(qx, qy), 0.0) - radius


def render(size: int) -> bytes:
    s = size / 512  # il disegno è pensato a 512, tutto il resto scala
    stroke = 26 * s
    arrow = [
        ((256 * s, 132 * s), (256 * s, 322 * s)),   # asta
        ((256 * s, 322 * s), (176 * s, 242 * s)),   # punta sinistra
        ((256 * s, 322 * s), (336 * s, 242 * s)),   # punta destra
    ]
    pier = ((104 * s, 396 * s), (408 * s, 396 * s))

    rows = []
    for y in range(size):
        row = bytearray([0])  # filtro 0 = nessuno
        for x in range(size):
            px, py = x + 0.5, y + 0.5

            base = _mix(BG_TOP, BG_BOTTOM, py / size)
            alpha = 1.0 - _smooth(-1.0, 1.0, _rounded_box(px, py, size, 112 * s))
            r, g, b = base

            best = min(_seg_dist(px, py, *a, *bb) for a, bb in arrow)
            ink = 1.0 - _smooth(stroke / 2 - 1.0, stroke / 2 + 1.0, best)
            if ink > 0:
                r, g, b = _mix((r, g, b), ACCENT, ink)

            dock = 1.0 - _smooth(stroke / 2 - 1.0, stroke / 2 + 1.0, _seg_dist(px, py, *pier[0], *pier[1]))
            if dock > 0:
                r, g, b = _mix((r, g, b), ACCENT, dock * 0.5)

            row += bytes((r, g, b, round(alpha * 255)))
        rows.append(bytes(row))

    return _png(size, size, b"".join(rows))


def _png(width: int, height: int, raw: bytes) -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)  # 8 bit, RGBA
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for size in (192, 512):
        path = OUT / f"icon-{size}.png"
        path.write_bytes(render(size))
        print(f"{path.relative_to(OUT.parent.parent.parent)}  {path.stat().st_size / 1024:.1f} KB")
