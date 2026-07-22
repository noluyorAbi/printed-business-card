#!/usr/bin/env python3
"""Generate a 3D-printable business card (black base + white raised features).

Output: STL for each color part, a combined Bambu Studio 3MF, and a top-view
preview PNG. Card: 80 x 45 mm. Base 0.0-0.6 mm (black), features 0.6-1.0 mm
(white). The QR code is recessed through the white panel so the black base
shows, which keeps the whole print at a single filament change.
"""

from functools import reduce

import numpy as np
import qrcode
import trimesh
from matplotlib.font_manager import FontProperties
from matplotlib.textpath import TextPath
from shapely.affinity import scale as shp_scale
from shapely.affinity import translate as shp_translate
from shapely.geometry import Point, Polygon, box
from shapely.ops import unary_union

# ---------------------------------------------------------------- constants
CARD_W, CARD_H = 80.0, 45.0   # compact wallet card, 80 mm long x 45 mm wide
CORNER_R = 2.5
BASE_Z = 0.6          # black base thickness
TOP_Z = 0.4           # white feature height
FRAME_IN, FRAME_OUT = 1.8, 1.0   # frame band: inset 1.0..1.8 mm from edge

QR_SIZE = 25.0
QR_QUIET = 2.0        # white margin around the QR (2 modules, kept tight)
PANEL = (
    CARD_W - FRAME_OUT - QR_SIZE - 2 * QR_QUIET,
    1.0,
    CARD_W - FRAME_OUT,
    1.0 + QR_SIZE + 2 * QR_QUIET,
)  # x0, y0, x1, y1
QR_CENTER = ((PANEL[0] + PANEL[2]) / 2, (PANEL[1] + PANEL[3]) / 2)
QR_DATA = "https://www.adatepe.dev"

# ---------------------------------------------------------------- styles
# A style only changes the 2D layout and which filament reads as "base" or
# "feature". The two-part, single-filament-change structure stays identical,
# so every style prints the same way.
#
#   frame:      "band" (default), "double" (two hairlines), "none"
#   qr:         "recess" (dark modules cut out of a feature-color panel) or
#               "relief" (dark modules raised in feature color, no panel)
#   layout:     text block variant ("default", "terminal", "brutal", "bauhaus")
#   decor:      background texture, any key in DECOR; always carved back out
#               of the text and the QR quiet zone
#   decor_keepout: also keep the texture out of the whole text bounding box
#   base/feat:  preview colors, and which filament goes in which slot
STYLES = {
    "classic": {
        "label": "Classic: black base, white features",
        "frame": "band",
        "qr": "recess",
        "base_color": "#151515",
        "feature_color": "#ececec",
        "base_name": "Basis Schwarz",
        "feature_name": "Schrift Weiss",
    },
    "inverse": {
        "label": "Inverse: white base, black features",
        "frame": "band",
        "qr": "relief",
        "base_color": "#ececec",
        "feature_color": "#151515",
        "base_name": "Basis Weiss",
        "feature_name": "Schrift Schwarz",
    },
    "minimal": {
        "label": "Minimal: no frame, black base",
        "frame": "none",
        "qr": "recess",
        "base_color": "#151515",
        "feature_color": "#ececec",
        "base_name": "Basis Schwarz",
        "feature_name": "Schrift Weiss",
    },
    "outline": {
        "label": "Outline: two hairlines instead of a band",
        "frame": "double",
        "qr": "recess",
        "base_color": "#151515",
        "feature_color": "#ececec",
        "base_name": "Basis Schwarz",
        "feature_name": "Schrift Weiss",
    },
    "blueprint": {
        "label": "Blueprint: white base, blue features",
        "frame": "double",
        "qr": "relief",
        "base_color": "#f2f4f7",
        "feature_color": "#1b3a6b",
        "base_name": "Basis Weiss",
        "feature_name": "Schrift Blau",
    },
    "terminal": {
        "label": "Terminal: shell prompt lines on scanlines",
        "frame": "none",
        "qr": "recess",
        "layout": "terminal",
        "decor": "scanlines",
        "base_color": "#0a0f0a",
        "feature_color": "#35ff6a",
        "base_name": "Basis Schwarz",
        "feature_name": "Schrift Gruen",
    },
    "circuit": {
        "label": "Circuit: PCB traces and pads, gold on board green",
        "frame": "double",
        "qr": "recess",
        "decor": "circuit",
        "base_color": "#0b3d2e",
        "feature_color": "#d9b45b",
        "base_name": "Basis Platinengruen",
        "feature_name": "Schrift Gold",
    },
    "topo": {
        "label": "Topo: contour rings behind the card, sand on navy",
        "frame": "band",
        "qr": "recess",
        "decor": "topo",
        "base_color": "#10202b",
        "feature_color": "#e6d5b8",
        "base_name": "Basis Navy",
        "feature_name": "Schrift Sand",
    },
    "neon": {
        "label": "Neon: sine ribbons, pink on deep purple",
        "frame": "none",
        "qr": "recess",
        "decor": "wave",
        "base_color": "#1a0b2e",
        "feature_color": "#ff7ad9",
        "base_name": "Basis Violett",
        "feature_name": "Schrift Pink",
    },
    "brutal": {
        "label": "Brutal: oversized name over a halftone gradient",
        "frame": "none",
        "qr": "recess",
        "layout": "brutal",
        "decor": "halftone",
        "base_color": "#151515",
        "feature_color": "#f5f1e6",
        "base_name": "Basis Schwarz",
        "feature_name": "Schrift Creme",
    },
    "carbon": {
        "label": "Carbon: woven bundles, silver on graphite",
        "frame": "none",
        "qr": "recess",
        "decor": "carbon",
        "decor_keepout": True,
        "base_color": "#1c1c1e",
        "feature_color": "#b9bcc2",
        "base_name": "Basis Graphit",
        "feature_name": "Schrift Silber",
    },
    "graph": {
        "label": "Graph: 5 mm engineering paper, green ink on paper white",
        "frame": "band",
        "qr": "relief",
        "decor": "graph",
        "decor_keepout": True,
        "base_color": "#f4f6f2",
        "feature_color": "#2f6f4e",
        "base_name": "Basis Weiss",
        "feature_name": "Schrift Gruen",
    },
    "hazard": {
        "label": "Hazard: diagonal warning stripes along the bottom",
        "frame": "none",
        "qr": "recess",
        "decor": "hazard",
        "base_color": "#141414",
        "feature_color": "#f2c200",
        "base_name": "Basis Schwarz",
        "feature_name": "Schrift Gelb",
    },
    "maze": {
        "label": "Maze: a labyrinth of unit segments, red on black",
        "frame": "none",
        "qr": "recess",
        "decor": "maze",
        "base_color": "#101010",
        "feature_color": "#e0483a",
        "base_name": "Basis Schwarz",
        "feature_name": "Schrift Rot",
    },
    "constellation": {
        "label": "Constellation: star map with linked neighbours",
        "frame": "band",
        "qr": "recess",
        "decor": "constellation",
        "base_color": "#0d1730",
        "feature_color": "#f0f4ff",
        "base_name": "Basis Navy",
        "feature_name": "Schrift Weiss",
    },
    "radar": {
        "label": "Radar: rings sweeping from the bottom left corner",
        "frame": "none",
        "qr": "recess",
        "decor": "radar",
        "base_color": "#041b16",
        "feature_color": "#4ff0c0",
        "base_name": "Basis Dunkelgruen",
        "feature_name": "Schrift Tuerkis",
    },
    "barcode": {
        "label": "Barcode: bars along the bottom, black on white",
        "frame": "none",
        "qr": "relief",
        "decor": "barcode",
        "base_color": "#f5f5f5",
        "feature_color": "#111111",
        "base_name": "Basis Weiss",
        "feature_name": "Schrift Schwarz",
    },
    "pixel": {
        "label": "Pixel: dither ramp out of the top right corner",
        "frame": "none",
        "qr": "recess",
        "decor": "pixel",
        "base_color": "#14121f",
        "feature_color": "#f7e26b",
        "base_name": "Basis Violett",
        "feature_name": "Schrift Gelb",
    },
    "iso": {
        "label": "Iso: isometric graph paper, blue on slate",
        "frame": "double",
        "qr": "recess",
        "decor": "iso",
        "decor_keepout": True,
        "base_color": "#101418",
        "feature_color": "#7fb3ff",
        "base_name": "Basis Schiefer",
        "feature_name": "Schrift Blau",
    },
    "bauhaus": {
        "label": "Bauhaus: ring, quarter disc and dot, red on cream",
        "frame": "none",
        "qr": "relief",
        "layout": "bauhaus",
        "decor": "bauhaus",
        "base_color": "#f2ece1",
        "feature_color": "#c8321e",
        "base_name": "Basis Creme",
        "feature_name": "Schrift Rot",
    },
}
DEFAULT_STYLE = "classic"

def _font(candidates, weight="normal"):
    import os

    for path in candidates:
        if os.path.exists(path):
            return FontProperties(fname=path)
    # DejaVu ships with matplotlib, so this works on any platform
    return FontProperties(family="DejaVu Sans", weight=weight)


FONT = _font(["/System/Library/Fonts/Supplemental/Arial.ttf"])
FONT_BOLD = _font(["/System/Library/Fonts/Supplemental/Arial Bold.ttf"], weight="bold")


# ---------------------------------------------------------------- text -> shapely
def text_shape(s, em, fp=FONT):
    """Render text at em size, even-odd fill via cumulative symmetric difference."""
    tp = TextPath((0, 0), s, size=em, prop=fp)
    polys = [Polygon(p) for p in tp.to_polygons() if len(p) >= 3]
    polys = [p if p.is_valid else p.buffer(0) for p in polys]
    if not polys:
        return Polygon()
    return reduce(lambda a, b: a.symmetric_difference(b), polys).buffer(0)


def place_text(s, em, x, y, fp=FONT):
    return shp_translate(text_shape(s, em, fp), xoff=x, yoff=y)


# ---------------------------------------------------------------- icons
def icon_globe(cx, cy, r=1.7, stroke=0.40):
    disk = Point(cx, cy).buffer(r, 64)
    ring = Point(cx, cy).buffer(r, 64).exterior.buffer(stroke / 2)
    equator = box(cx - r, cy - stroke / 2, cx + r, cy + stroke / 2)
    meridian = shp_scale(Point(cx, cy).buffer(r, 64).exterior, 0.45, 1.0).buffer(stroke / 2)
    return unary_union([ring, equator.intersection(disk), meridian.intersection(disk)])


def icon_linkedin(cx, cy, size=3.4):
    half = size / 2
    sq = box(cx - half, cy - half, cx + half, cy + half).buffer(-0.7).buffer(0.7)
    txt = text_shape("in", 2.6, FONT_BOLD)
    b = txt.bounds
    txt = shp_translate(txt, xoff=cx - (b[0] + b[2]) / 2, yoff=cy - (b[1] + b[3]) / 2)
    return sq.difference(txt)


def icon_github(cx, cy, r=1.8):
    disk = Point(cx, cy).buffer(r, 64)
    head = Point(cx, cy + 0.22).buffer(0.95, 32)
    ear_l = Polygon([(cx - 0.9, cy + 0.45), (cx - 1.05, cy + 1.4), (cx - 0.22, cy + 1.05)])
    ear_r = Polygon([(cx + 0.9, cy + 0.45), (cx + 1.05, cy + 1.4), (cx + 0.22, cy + 1.05)])
    body = box(cx - 0.68, cy - 1.55, cx + 0.68, cy - 0.45).buffer(-0.3).buffer(0.3)
    cat = unary_union([head, ear_l, ear_r, body])
    return disk.difference(cat)


# ---------------------------------------------------------------- QR
def qr_dark_modules():
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M,
                       border=0, box_size=1)
    qr.add_data(QR_DATA)
    qr.make(fit=True)
    m = qr.get_matrix()
    n = len(m)
    mod = QR_SIZE / n
    x0 = QR_CENTER[0] - QR_SIZE / 2
    y0 = QR_CENTER[1] - QR_SIZE / 2
    eps = 0.02
    cells = []
    for row in range(n):
        for col in range(n):
            if m[row][col]:
                # row 0 is top of the QR -> highest y
                cx0 = x0 + col * mod
                cy0 = y0 + (n - 1 - row) * mod
                cells.append(box(cx0 - eps, cy0 - eps, cx0 + mod + eps, cy0 + mod + eps))
    print(f"QR: version {qr.version}, {n}x{n} modules, module {mod:.2f} mm")
    return unary_union(cells)


# ---------------------------------------------------------------- build 2D layout
def build_frame(base, kind, qr_mode="recess"):
    if kind == "none":
        return Polygon()
    if kind == "double":
        hair = 0.35
        outer = base.buffer(-FRAME_OUT).difference(base.buffer(-FRAME_OUT - hair))
        inner = base.buffer(-FRAME_IN - 0.6).difference(base.buffer(-FRAME_IN - 0.6 - hair))
        band = unary_union([outer, inner])
        # let the hairlines stop cleanly at the QR panel instead of running under it
        if qr_mode == "recess":
            return band.difference(box(*PANEL).buffer(0.5))
        return band
    return base.buffer(-FRAME_OUT).difference(base.buffer(-FRAME_IN))


ROWS = [
    (icon_globe, "www.adatepe.dev", 20.6),
    (icon_linkedin, "in.adatepe.dev", 15.4),
    (icon_github, "git.adatepe.dev", 10.2),
]


def build_content(layout):
    """Name, tagline and contact rows as one polygon, per layout variant."""
    parts = []
    if layout == "bauhaus":
        # same oversized name, but the contact block clears the quarter disc
        parts.append(place_text("ALPEREN", 7.6, 4.5, 32.0, FONT_BOLD))
        parts.append(place_text("ADATEPE", 7.6, 4.5, 23.0, FONT_BOLD))
        for i, (_, label, _) in enumerate(ROWS):
            parts.append(place_text(label, 2.6, 16.0, 14.0 - i * 3.6))
        return unary_union(parts).buffer(0)

    if layout == "brutal":
        # name owns the card, tagline drops, contact lines shrink to one block
        parts.append(place_text("ALPEREN", 7.6, 4.5, 30.5, FONT_BOLD))
        parts.append(place_text("ADATEPE", 7.6, 4.5, 21.5, FONT_BOLD))
        for i, (_, label, _) in enumerate(ROWS):
            parts.append(place_text(label, 2.6, 4.8, 15.0 - i * 3.6))
        return unary_union(parts).buffer(0)

    if layout == "terminal":
        parts.append(place_text("> Alperen Adatepe", 5.0, 5.5, 35.5, FONT_BOLD))
        parts.append(place_text("# creating powerful digital experiences", 2.7, 5.5, 31.4))
        parts.append(place_text("# through modern solutions.", 2.7, 5.5, 27.7))
        for i, (_, label, y) in enumerate(ROWS):
            parts.append(place_text(f"$ open {label}", 2.9, 5.5, y))
        return unary_union(parts).buffer(0)

    parts.append(place_text("Alperen Adatepe", 5.6, 5.5, 35.5))
    parts.append(place_text("Creating powerful digital experiences", 3.0, 5.5, 31.4))
    parts.append(place_text("through modern solutions.", 3.0, 5.5, 27.5))
    for icon_fn, label, y in ROWS:
        parts.append(icon_fn(7.3, y + 1.1))
        parts.append(place_text(label, 3.1, 10.6, y))
    return unary_union(parts).buffer(0)


# ---------------------------------------------------------------- decor
# A decor builder returns background texture in feature color. It is always
# carved away from the text and the QR panel afterwards, so it never touches
# legibility or scannability.
def decor_scanlines(base):
    """Window chrome bar, a block cursor and a few scanlines at the bottom."""
    bar = box(2.0, 40.6, CARD_W - 2.0, 42.8).intersection(base.buffer(-1.0))
    dots = unary_union([Point(x, 41.7).buffer(0.55, 24) for x in (4.6, 6.6, 8.6)])
    cursor = box(40.4, 9.9, 42.0, 12.6)
    lines = [box(0, y, CARD_W, y + 0.5) for y in (2.6, 5.0)]
    floor = unary_union(lines).intersection(base.buffer(-1.2))
    return unary_union([bar.difference(dots), cursor, floor])


def decor_circuit(base):
    """PCB-ish traces: horizontal runs with 45 degree elbows, plus round pads."""
    w = 0.45
    shapes = []
    for i, y in enumerate((6.0, 13.5, 24.0, 33.0, 40.0)):
        run = box(3.0, y - w / 2, 46.0 - i * 3.0, y + w / 2)
        elbow = Polygon([
            (46.0 - i * 3.0, y - w / 2), (46.0 - i * 3.0, y + w / 2),
            (52.0 - i * 3.0, y + 6.0 + w / 2), (52.0 - i * 3.0, y + 6.0 - w / 2),
        ])
        shapes += [run, elbow]
        shapes.append(Point(3.0, y).buffer(1.0, 24).difference(
            Point(3.0, y).buffer(0.45, 24)))
    for x in np.arange(6.0, CARD_W - 6.0, 6.0):
        shapes.append(Point(x, 2.6).buffer(0.55, 16))
    return unary_union(shapes).intersection(base.buffer(-1.0))


def decor_topo(base):
    """Contour rings, like a topographic map, offset inward from a seed blob."""
    seed = unary_union([
        Point(58.0, 34.0).buffer(9.0, 48),
        Point(48.0, 26.0).buffer(7.5, 48),
        Point(62.0, 20.0).buffer(6.0, 48),
    ])
    rings = []
    for i in range(9):
        grown = seed.buffer(i * 3.0, 48)
        ring = grown.difference(grown.buffer(-0.3))
        rings.append(ring)
    return unary_union(rings).intersection(base.buffer(-1.0))


def decor_wave(base):
    """Sine ribbons sweeping across the bottom of the card."""
    from shapely.geometry import LineString

    # kept in the bottom band, where the layout leaves room
    xs = np.linspace(0, CARD_W, 240)
    ribbons = []
    for k, phase in enumerate(np.linspace(0.0, 2.2, 4)):
        ys = 5.2 + 2.4 * np.sin(xs / 7.0 + phase)
        line = LineString(list(zip(xs, ys)))
        ribbons.append(line.buffer(0.30 + 0.12 * k, cap_style=2, join_style=1))
    return unary_union(ribbons).intersection(base.buffer(-1.0))


def decor_halftone(base):
    """Dot gradient: dots grow from left to right."""
    dots = []
    for x in np.arange(3.0, CARD_W - 2.0, 2.3):
        for j, y in enumerate(np.arange(3.0, CARD_H - 2.0, 2.3)):
            offset = 1.15 if j % 2 else 0.0
            # never below 0.25 mm radius, otherwise a 0.2 mm nozzle skips it
            r = 0.25 + 0.72 * (x / CARD_W) ** 2
            dots.append(Point(x + offset, y).buffer(r, 12))
    return unary_union(dots).intersection(base.buffer(-1.2))


def decor_carbon(base):
    """Carbon fibre weave: alternating bundles on a 3.4 mm grid."""
    tiles = []
    for i, x in enumerate(np.arange(2.0, CARD_W - 1.0, 3.4)):
        for j, y in enumerate(np.arange(2.0, CARD_H - 1.0, 3.4)):
            if (i + j) % 2:
                tiles.append(box(x, y + 0.4, x + 2.9, y + 1.5))
            else:
                tiles.append(box(x + 0.4, y, x + 1.5, y + 2.9))
    return unary_union(tiles).intersection(base.buffer(-1.2))


def decor_graph(base):
    """Engineering paper: 5 mm grid with a heavier line every 25 mm."""
    lines = []
    for x in np.arange(0.0, CARD_W + 1.0, 5.0):
        w = 0.8 if x % 25 == 0 else 0.45
        lines.append(box(x - w / 2, 0, x + w / 2, CARD_H))
    for y in np.arange(0.0, CARD_H + 1.0, 5.0):
        w = 0.8 if y % 25 == 0 else 0.45
        lines.append(box(0, y - w / 2, CARD_W, y + w / 2))
    return unary_union(lines).intersection(base.buffer(-1.4))


def decor_hazard(base):
    """Diagonal hazard stripes in the bottom band."""
    from shapely.affinity import rotate

    band = box(0, 1.5, CARD_W, 8.0)
    stripes = [
        rotate(box(x, -20, x + 2.4, 60), -45, origin=(x, 0))
        for x in np.arange(-40.0, CARD_W + 40.0, 5.4)
    ]
    return unary_union(stripes).intersection(band).intersection(base.buffer(-1.2))


def decor_maze(base):
    """Labyrinth of unit segments on a fixed pseudo-random grid."""
    rng = np.random.default_rng(7)
    cell, w = 3.2, 0.5
    segs = []
    for x in np.arange(2.5, CARD_W - 2.5, cell):
        for y in np.arange(2.5, CARD_H - 2.5, cell):
            if rng.random() < 0.5:
                segs.append(box(x, y - w / 2, x + cell, y + w / 2))
            else:
                segs.append(box(x - w / 2, y, x + w / 2, y + cell))
    return unary_union(segs).intersection(base.buffer(-1.4))


def decor_constellation(base):
    """Star map: dots plus the short links between neighbouring dots."""
    from shapely.geometry import LineString

    rng = np.random.default_rng(23)
    pts = [(float(rng.uniform(3, CARD_W - 3)), float(rng.uniform(3, CARD_H - 3)))
           for _ in range(46)]
    shapes = [Point(p).buffer(0.30 + 0.35 * float(rng.random()), 16) for p in pts]
    for i, a in enumerate(pts):
        for b in pts[i + 1:]:
            d = np.hypot(a[0] - b[0], a[1] - b[1])
            if d < 9.0:
                shapes.append(LineString([a, b]).buffer(0.25, cap_style=2))
    return unary_union(shapes).intersection(base.buffer(-1.2))


def decor_radar(base):
    """Radar sweep: rings around the bottom left corner."""
    rings = []
    for r in np.arange(6.0, 90.0, 5.0):
        disc = Point(3.0, 2.0).buffer(r, 96)
        rings.append(disc.difference(disc.buffer(-0.5)))
    return unary_union(rings).intersection(base.buffer(-1.2))


def decor_barcode(base):
    """EAN-ish bars along the bottom edge."""
    rng = np.random.default_rng(11)
    bars, x = [], 3.0
    while x < CARD_W - 3.0:
        w = float(rng.choice([0.5, 0.8, 1.3]))
        bars.append(box(x, 2.2, x + w, 7.4))
        x += w + float(rng.choice([0.6, 0.9]))
    return unary_union(bars).intersection(base.buffer(-1.2))


def decor_pixel(base):
    """Dither ramp: 1.6 mm pixels thinning out from the top right corner."""
    rng = np.random.default_rng(3)
    cell = 1.6
    px = []
    for x in np.arange(2.0, CARD_W - 2.0, cell):
        for y in np.arange(2.0, CARD_H - 2.0, cell):
            # density falls off with distance from the top right corner
            d = np.hypot((CARD_W - x) / CARD_W, (CARD_H - y) / CARD_H)
            if rng.random() < max(0.0, 0.95 - 1.5 * d):
                px.append(box(x, y, x + cell - 0.25, y + cell - 0.25))
    return unary_union(px).intersection(base.buffer(-1.2))


def decor_iso(base):
    """Isometric graph paper: two 30 degree families of lines."""
    from shapely.affinity import rotate

    lines = []
    for angle in (30, -30):
        for x in np.arange(-60.0, CARD_W + 60.0, 4.5):
            lines.append(rotate(box(x, -40, x + 0.4, 90), angle, origin=(x, 22.5)))
    return unary_union(lines).intersection(base.buffer(-1.4))


def decor_bauhaus(base):
    """Three primitives: a ring, a quarter disc and a solid dot."""
    ring = Point(64.0, 37.5).buffer(6.0, 64)
    ring = ring.difference(ring.buffer(-1.2))
    quarter = Point(2.0, 2.0).buffer(11.0, 64).intersection(box(2.0, 2.0, 13.0, 13.0))
    dot = Point(44.5, 39.0).buffer(2.4, 48)
    bar = box(2.0, 18.4, 46.0, 19.4)
    return unary_union([ring, quarter, dot, bar]).intersection(base.buffer(-1.2))


def despeckle(geom, min_area=0.4, min_half_width=0.15):
    """Drop crumbs left behind when decor is carved around text.

    Anything smaller than min_area, or thinner than 2 x min_half_width, is
    removed: it would not print cleanly and it reads as noise.
    """
    polys = list(geom.geoms) if geom.geom_type == "MultiPolygon" else [geom]
    keep = [p for p in polys
            if p.area >= min_area and not p.buffer(-min_half_width).is_empty]
    return unary_union(keep) if keep else Polygon()


DECOR = {
    "scanlines": decor_scanlines,
    "circuit": decor_circuit,
    "topo": decor_topo,
    "wave": decor_wave,
    "halftone": decor_halftone,
    "carbon": decor_carbon,
    "graph": decor_graph,
    "hazard": decor_hazard,
    "maze": decor_maze,
    "constellation": decor_constellation,
    "radar": decor_radar,
    "barcode": decor_barcode,
    "pixel": decor_pixel,
    "iso": decor_iso,
    "bauhaus": decor_bauhaus,
}


def build_shapes(style=DEFAULT_STYLE):
    """2D layout for a style: returns (base polygon, feature polygon)."""
    st = STYLES[style] if isinstance(style, str) else style
    base = box(CORNER_R, CORNER_R, CARD_W - CORNER_R, CARD_H - CORNER_R).buffer(CORNER_R, 32)
    panel = box(*PANEL)

    white = [build_frame(base, st["frame"], st["qr"])]
    if st["qr"] == "recess":
        white.append(panel)

    content = build_content(st.get("layout", "default"))

    white.append(content)

    if st.get("decor"):
        texture = DECOR[st["decor"]](base)
        # keep the texture clear of text and of the QR quiet zone
        texture = texture.difference(content.buffer(1.4)).difference(panel.buffer(1.2))
        if st.get("decor_keepout"):
            # dense patterns get a clean rectangle around the whole text block
            texture = texture.difference(content.envelope.buffer(1.6))
        texture = despeckle(texture)
        white.append(texture)

    modules = qr_dark_modules()
    white_union = unary_union(white).buffer(0)
    if st["qr"] == "recess":
        white_union = white_union.difference(modules).buffer(0)
    else:
        white_union = unary_union([white_union, modules]).buffer(0)
    # keep everything on the card
    white_union = white_union.intersection(base)
    # drop collinear T-vertices left over from module-grid unions; 5 µm tolerance
    # is invisible but required for watertight extrusion
    white_union = white_union.simplify(0.005).buffer(0)
    # close-then-open by 10 um: removes point-touching contacts between decor
    # and frame, which shapely accepts but extrusion cannot make watertight
    white_union = white_union.buffer(0.01).buffer(-0.01).buffer(0)
    return base, white_union


# ---------------------------------------------------------------- 3D + export
def extrude(geom, height, z0):
    polys = list(geom.geoms) if geom.geom_type == "MultiPolygon" else [geom]
    meshes = []
    for p in polys:
        if p.area < 0.01:
            continue
        m = trimesh.creation.extrude_polygon(p, height)
        m.apply_translation([0, 0, z0])
        meshes.append(m)
    return trimesh.util.concatenate(meshes)


def write_3mf(path, parts):
    """Bambu-Studio project 3MF: one object with one part per filament.

    parts: list of (name, extruder_number, trimesh). Extruder numbers are
    1-based filament slots, stored in Metadata/model_settings.config so
    Bambu Studio opens the file already two-colored.
    """
    import uuid
    import zipfile

    def uid(tag):
        return str(uuid.uuid5(uuid.NAMESPACE_URL, f"adatepe-card-{tag}"))

    identity = "1 0 0 0 1 0 0 0 1 0 0 0"
    objects, components, part_cfg = [], [], []
    for i, (name, extruder, mesh) in enumerate(parts):
        oid = i + 2
        verts = "".join(
            f'<vertex x="{v[0]:.4f}" y="{v[1]:.4f}" z="{v[2]:.4f}"/>'
            for v in mesh.vertices
        )
        tris = "".join(
            f'<triangle v1="{t[0]}" v2="{t[1]}" v3="{t[2]}"/>' for t in mesh.faces
        )
        objects.append(
            f'<object id="{oid}" p:UUID="{uid(oid)}" type="model">'
            f"<mesh><vertices>{verts}</vertices><triangles>{tris}</triangles></mesh></object>"
        )
        components.append(f'<component objectid="{oid}" transform="{identity}"/>')
        part_cfg.append(
            f'  <part id="{oid}" subtype="normal_part">\n'
            f'    <metadata key="name" value="{name}"/>\n'
            f'    <metadata key="matrix" value="1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"/>\n'
            f'    <metadata key="extruder" value="{extruder}"/>\n'
            "  </part>\n"
        )

    parent_id = len(parts) + 2
    model = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<model unit="millimeter" xml:lang="en-US" '
        'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" '
        'xmlns:BambuStudio="http://schemas.bambulab.com/package/2021" '
        'xmlns:p="http://schemas.microsoft.com/3dmanufacturing/production/2015/06">'
        '<metadata name="Application">BambuStudio-01.10.00.00</metadata>'
        '<metadata name="BambuStudio:3mfVersion">1</metadata>'
        f"<resources>{''.join(objects)}"
        f'<object id="{parent_id}" p:UUID="{uid(parent_id)}" type="model">'
        f"<components>{''.join(components)}</components></object>"
        f'</resources><build p:UUID="{uid("build")}">'
        f'<item objectid="{parent_id}" transform="{identity}" printable="1"/>'
        "</build></model>"
    )
    model_settings = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<config>\n"
        f'<object id="{parent_id}">\n'
        '  <metadata key="name" value="Visitenkarte"/>\n'
        '  <metadata key="extruder" value="1"/>\n'
        f"{''.join(part_cfg)}"
        "</object>\n"
        "</config>\n"
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>'
        '<Default Extension="config" ContentType="text/xml"/>'
        "</Types>"
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Target="/3D/3dmodel.model" Id="rel0" '
        'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>'
        "</Relationships>"
    )
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", rels)
        z.writestr("3D/3dmodel.model", model)
        z.writestr("Metadata/model_settings.config", model_settings)


def preview(base, white, path, style=DEFAULT_STYLE):
    import matplotlib.pyplot as plt
    from matplotlib.patches import PathPatch
    from matplotlib.path import Path as MplPath

    def patch(geom, **kw):
        polys = list(geom.geoms) if geom.geom_type == "MultiPolygon" else [geom]
        for p in polys:
            verts = list(p.exterior.coords)
            codes = [MplPath.MOVETO] + [MplPath.LINETO] * (len(verts) - 2) + [MplPath.CLOSEPOLY]
            for ring in p.interiors:
                rv = list(ring.coords)
                verts += rv
                codes += [MplPath.MOVETO] + [MplPath.LINETO] * (len(rv) - 2) + [MplPath.CLOSEPOLY]
            ax.add_patch(PathPatch(MplPath(verts, codes), **kw))

    st = STYLES[style] if isinstance(style, str) else style
    fig, ax = plt.subplots(figsize=(10, 6.5))
    fig.patch.set_facecolor("#3a3a3a")
    patch(base, facecolor=st["base_color"], edgecolor="none")
    patch(white, facecolor=st["feature_color"], edgecolor="none")
    ax.set_xlim(-3, CARD_W + 3)
    ax.set_ylim(-3, CARD_H + 3)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.savefig(path, dpi=200, bbox_inches="tight", facecolor="#3a3a3a")
    plt.close(fig)


def build_style(style, prefix, preview_path, meshes=True):
    st = STYLES[style]
    base2d, white2d = build_shapes(style)
    if meshes:
        base_mesh = extrude(base2d, BASE_Z, 0.0)
        white_mesh = extrude(white2d, TOP_Z, BASE_Z)
        print(f"{style} base: {len(base_mesh.faces)} faces, "
              f"watertight={base_mesh.is_watertight}")
        print(f"{style} features: {len(white_mesh.faces)} faces, "
              f"watertight={white_mesh.is_watertight}")
        base_mesh.export(f"{prefix}_base.stl")
        white_mesh.export(f"{prefix}_top.stl")
        write_3mf(
            f"{prefix}.3mf",
            [(st["base_name"], 1, base_mesh), (st["feature_name"], 2, white_mesh)],
        )
    preview(base2d, white2d, preview_path, style)
    print(f"{style}: {preview_path}")


def main():
    import argparse

    ap = argparse.ArgumentParser(description="Generate the printable business card.")
    ap.add_argument("--style", default=DEFAULT_STYLE, choices=sorted(STYLES),
                    help="card style to build (default: %(default)s)")
    ap.add_argument("--all", action="store_true",
                    help="render a preview for every style into --preview-dir")
    ap.add_argument("--preview-dir", default="assets/previews",
                    help="where --all writes its previews (default: %(default)s)")
    args = ap.parse_args()

    if args.all:
        import os

        os.makedirs(args.preview_dir, exist_ok=True)
        for name in sorted(STYLES):
            build_style(name, f"visitenkarte_{name}",
                        os.path.join(args.preview_dir, f"{name}.png"), meshes=False)
        print("done")
        return

    if args.style == DEFAULT_STYLE:
        # keep the historical filenames for the default card
        base2d, white2d = build_shapes(DEFAULT_STYLE)
        base_mesh = extrude(base2d, BASE_Z, 0.0)
        white_mesh = extrude(white2d, TOP_Z, BASE_Z)
        print(f"base: {len(base_mesh.faces)} faces, watertight={base_mesh.is_watertight}")
        print(f"white: {len(white_mesh.faces)} faces, watertight={white_mesh.is_watertight}")
        base_mesh.export("visitenkarte_base_black.stl")
        white_mesh.export("visitenkarte_top_white.stl")
        write_3mf(
            "visitenkarte.3mf",
            [("Basis Schwarz", 1, base_mesh), ("Schrift Weiss", 2, white_mesh)],
        )
        preview(base2d, white2d, "visitenkarte_preview.png", DEFAULT_STYLE)
    else:
        build_style(args.style, f"visitenkarte_{args.style}",
                    f"visitenkarte_{args.style}_preview.png")
    print("done")


if __name__ == "__main__":
    main()
