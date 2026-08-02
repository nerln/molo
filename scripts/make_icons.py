"""Draw the app icons without a graphics dependency.

Pillow is not a dependency of Molo and adding one for two static files would
be poor value. Shapes are drawn as signed distance fields, which gives
antialiasing for free, and the PNG is written by hand: about forty lines of
zlib and struct.

    python3 scripts/make_icons.py

The mark is a pier seen from the side: a solid arrow coming down onto a deck
with two pilings under it. A plain download arrow is what every other app in
the category uses, and it says nothing about this one.
"""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "molo" / "web" / "icons"

BRASS_TOP = (233, 186, 122)
BRASS_BOTTOM = (198, 140, 66)
INK = (26, 20, 12)


def _mix(a, b, t):
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def _smooth(edge0, edge1, x):
    t = max(0.0, min(1.0, (x - edge0) / (edge1 - edge0)))
    return t * t * (3 - 2 * t)


def _rounded_box(px, py, cx, cy, half_w, half_h, radius):
    """Signed distance to a rounded rectangle centred on (cx, cy)."""
    qx = abs(px - cx) - (half_w - radius)
    qy = abs(py - cy) - (half_h - radius)
    ax, ay = max(qx, 0.0), max(qy, 0.0)
    return (ax * ax + ay * ay) ** 0.5 + min(max(qx, qy), 0.0) - radius


def _triangle(px, py, a, b, c):
    """Signed distance to a triangle. Negative inside.

    Distance is the nearest edge; the sign comes from the winding test, which
    is what lets the arrowhead antialias like the other shapes.
    """
    def edge(p0, p1):
        vx, vy = p1[0] - p0[0], p1[1] - p0[1]
        wx, wy = px - p0[0], py - p0[1]
        length = vx * vx + vy * vy
        t = 0.0 if length == 0 else max(0.0, min(1.0, (wx * vx + wy * vy) / length))
        dx, dy = wx - t * vx, wy - t * vy
        return (dx * dx + dy * dy) ** 0.5

    def side(p0, p1):
        return (p1[0] - p0[0]) * (py - p0[1]) - (p1[1] - p0[1]) * (px - p0[0])

    nearest = min(edge(a, b), edge(b, c), edge(c, a))
    s1, s2, s3 = side(a, b), side(b, c), side(c, a)
    inside = (s1 >= 0 and s2 >= 0 and s3 >= 0) or (s1 <= 0 and s2 <= 0 and s3 <= 0)
    return -nearest if inside else nearest


def render(size: int) -> bytes:
    u = size / 32.0          # the mark is drawn on a 32 unit grid
    aa = 0.8 * (size / 512)  # antialiasing width, scaled so small icons stay crisp
    aa = max(aa, 0.35)

    shaft = (16 * u, 9.2 * u, 1.5 * u, 4.6 * u, 0.7 * u)      # cx, cy, hw, hh, r
    head = ((10.2 * u, 12.4 * u), (21.8 * u, 12.4 * u), (16 * u, 19.4 * u))
    deck = (16 * u, 22.6 * u, 11.4 * u, 1.5 * u, 0.75 * u)
    piling_l = (10.6 * u, 26.2 * u, 1.3 * u, 2.4 * u, 0.65 * u)
    piling_r = (21.4 * u, 26.2 * u, 1.3 * u, 2.4 * u, 0.65 * u)

    rows = []
    for y in range(size):
        row = bytearray([0])   # filter 0, none
        for x in range(size):
            px, py = x + 0.5, y + 0.5

            badge = _rounded_box(px, py, size / 2, size / 2, size / 2, size / 2, 7.2 * u)
            alpha = 1.0 - _smooth(-aa, aa, badge)

            r, g, b = _mix(BRASS_TOP, BRASS_BOTTOM, py / size)

            mark = min(
                _rounded_box(px, py, *shaft),
                _triangle(px, py, *head),
                _rounded_box(px, py, *deck),
                _rounded_box(px, py, *piling_l),
                _rounded_box(px, py, *piling_r),
            )
            ink = 1.0 - _smooth(-aa, aa, mark)
            if ink > 0:
                r, g, b = _mix((r, g, b), INK, ink)

            row += bytes((r, g, b, round(alpha * 255)))
        rows.append(bytes(row))

    return _png(size, size, b"".join(rows))


def _png(width: int, height: int, raw: bytes) -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)   # 8 bit RGBA
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
        print(f"molo/web/icons/{path.name}  {path.stat().st_size / 1024:.1f} KB")
