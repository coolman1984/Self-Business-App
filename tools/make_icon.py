"""Draws the program icon (four interlocking blocks - the "Meccano" idea: one core, modules that click in) and writes it as
a Windows .ico file. Pure Python, so the build needs no image files or extra packages.

    python tools/make_icon.py <output.ico>
"""
import struct
import sys
import zlib

TEAL, TEAL_DARK, COPPER, PAPER = (31, 78, 71, 255), (20, 52, 47, 255), (224, 122, 63, 255), (250, 248, 245, 255)


def draw(n):
    px = [[(0, 0, 0, 0)] * n for _ in range(n)]

    def rounded(x0, y0, x1, y1, radius, color_at):
        X0, Y0, X1, Y1, r = x0 * n, y0 * n, x1 * n, y1 * n, radius * n
        for y in range(max(0, int(Y0)), min(n, int(Y1) + 1)):
            for x in range(max(0, int(X0)), min(n, int(X1) + 1)):
                cx = min(max(x, X0 + r), X1 - r)
                cy = min(max(y, Y0 + r), Y1 - r)
                if (x - cx) ** 2 + (y - cy) ** 2 <= r * r:
                    px[y][x] = color_at(x, y)

    def gradient(x, y):
        t = y / n
        return tuple(int(TEAL[i] * (1 - t) + TEAL_DARK[i] * t) for i in range(3)) + (255,)
    rounded(0.02, 0.02, 0.98, 0.98, 0.20, gradient)   # tile
    block = lambda x0, y0, c: rounded(x0, y0, x0 + 0.34, y0 + 0.34, 0.07, lambda x, y: c)  # noqa: E731
    block(0.14, 0.14, PAPER)      # the core
    block(0.52, 0.14, PAPER)
    block(0.14, 0.52, PAPER)
    block(0.52, 0.52, COPPER)     # the module that clicks in
    return px


def png(px):
    n = len(px)
    raw = b''.join(b'\x00' + bytes(v for p in row for v in p) for row in px)

    def chunk(t, d):
        return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', n, n, 8, 6, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b'')


def ico(sizes=(256, 64, 48, 32, 16)):
    imgs = [png(draw(s)) for s in sizes]
    out = struct.pack('<HHH', 0, 1, len(imgs))
    off = 6 + 16 * len(imgs)
    for s, d in zip(sizes, imgs):
        out += struct.pack('<BBBBHHII', s % 256, s % 256, 0, 0, 1, 32, len(d), off)
        off += len(d)
    return out + b''.join(imgs)


if __name__ == '__main__':
    with open(sys.argv[1], 'wb') as f:
        f.write(ico())
    print('icon written to', sys.argv[1])
