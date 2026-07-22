#!/usr/bin/env python3
"""Generate a 3D-printable business card (black base + white raised features).

Output: STL for each color part, a combined Bambu Studio 3MF, and a top-view
preview PNG. The card is CARD_W x CARD_H mm (84 x 52, inside the ID-1 bank
card format so it still fits a wallet slot). Base 0.0-0.6 mm (black), features
0.6-1.0 mm (white), plus optional 0.3 mm engraved grooves and 0.3 mm of
emboss. The QR code is recessed through the white panel so the black base
shows, which keeps the whole print at a single filament change.

Type sizes, tracking and icon sizes are set from measurements against a 0.2 mm
nozzle: strokes and inter-letter gaps stay at or above roughly 0.45 mm, which
is what stops letters from bleeding into each other on the print.
"""

from collections import namedtuple
from functools import lru_cache, reduce

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
# Card. ISO/IEC 7810 ID-1 (bank card) is 85.60 x 53.98 mm, so 84 x 52 leaves
# 1.6 mm of width and 2.0 mm of height clearance. A printed card is rigid and
# cannot cam itself into a tight wallet slot the way a 0.76 mm bank card does,
# and FDM adds a few tenths per edge, so that clearance is the point.
CARD_W, CARD_H = 84.0, 52.0
CORNER_R = 3.0        # matches the ID-1 corner family (2.88 to 3.48 mm)
CORNERS = "round"     # "round" or "square"; a style may override it, and so
                      # may --corners on the command line
BASE_Z = 0.6          # black base thickness
TOP_Z = 0.4           # white feature height
HIGH_Z = 0.3          # extra height for embossed features (feels raised)
ENGRAVE_Z = 0.3       # groove depth cut into the top of the base
FRAME_IN, FRAME_OUT = 1.8, 1.0   # frame band: inset 1.0..1.8 mm from edge

CX, CY = CARD_W / 2, CARD_H / 2
DIAG = (CARD_W ** 2 + CARD_H ** 2) ** 0.5
MARGIN = 5.0          # text column starts here
EDGE_SAFE = 2.0       # decor never comes closer than this to the card edge
GUTTER = 3.0          # clear space between the text column and the QR panel

# QR. 22 mm over a 25 x 25 matrix is a 0.88 mm module, comfortably above the
# ~0.8 mm floor a 0.2 mm nozzle prints reliably. The quiet zone is expressed
# in modules, not millimetres, so it survives any change of QR_SIZE.
QR_SIZE = 22.0
QR_MODULES = 25
QR_QUIET = 3.0 * QR_SIZE / QR_MODULES   # 3 modules
PANEL_SIDE = QR_SIZE + 2 * QR_QUIET
PANEL_MARGIN = 2.6    # equal gap to the right and bottom edge

# Decors that live in the bottom strip. Those styles keep the panel centred on
# the right edge so the pattern keeps its full run; everything else parks the
# code in the bottom right corner, which reads cleaner.
BOTTOM_DECORS = {"wave", "waveform", "helix", "spiral", "mountains", "city",
                 "barcode", "hazard", "ticket", "scanlines", "gitgraph",
                 "diffnote", "vimchrome", "ledmatrix", "railroad",
                 "keycaps", "turingtape", "morse", "punchtape", "magstripe",
                 "teletext", "flamegraph", "frontpanel", "code39"}


def panel_box(st=None):
    """QR panel rectangle: bottom right by default, centred for bottom decor."""
    x1 = CARD_W - PANEL_MARGIN
    x0 = x1 - PANEL_SIDE
    if st and st.get("decor") in BOTTOM_DECORS:
        return (x0, CY - PANEL_SIDE / 2, x1, CY + PANEL_SIDE / 2)
    return (x0, PANEL_MARGIN, x1, PANEL_MARGIN + PANEL_SIDE)


PANEL = panel_box()
QR_CENTER = ((PANEL[0] + PANEL[2]) / 2, (PANEL[1] + PANEL[3]) / 2)
QR_DATA = "https://www.adatepe.dev"

# Text column. Everything the layouts draw lives between TEXT_X0 and TEXT_X1;
# a test asserts it, so type can never creep under the QR panel again.
TEXT_X0 = MARGIN
TEXT_X1 = PANEL[0] - GUTTER
TEXT_CX = (TEXT_X0 + TEXT_X1) / 2

# Type. Sizes and tracking come from measuring the real Arial outlines against
# what a 0.2 mm nozzle holds: strokes want 0.45 mm or more, and the gap between
# neighbouring letters wants 0.45 mm or it bleeds shut on the print. Tracking
# buys the gap without making the card a poster.
EM_NAME, TRACK_NAME = 6.0, 0.20     # stroke 1.13 mm, gap 0.43 mm, width 51.5
EM_TAG, TRACK_TAG = 4.2, 0.28       # stroke 0.50 mm, gap 0.39 mm
EM_ROW, TRACK_ROW = 4.8, 0.25       # stroke 0.56 mm, gap 0.46 mm
EM_HERO, TRACK_HERO = 8.7, 0.10     # oversized name in the brutal layouts
EM_SMALL, TRACK_SMALL = 4.2, 0.20   # prompt lines and other dense variants

# Baseline grid
NAME_Y = CARD_H - MARGIN - EM_NAME * 0.75
TAG_Y = NAME_Y - EM_TAG * 1.10
TAG_LEAD = EM_TAG * 1.15
ROW_Y0 = 11.0                        # bottom contact row
ROW_LEAD = EM_ROW * 1.55
BOTTOM = (0.0, EDGE_SAFE * 0.8, CARD_W, ROW_Y0 - 2.0)   # strip for bottom decor
BOTTOM_CY = (BOTTOM[1] + BOTTOM[3]) / 2

# Icon column. The printed icons were the least legible part of the card, so
# they grow with the type instead of staying at their old 3.4 mm.
ICON_R = 2.4
ICON_X = TEXT_X0 + ICON_R
LABEL_X = ICON_X + ICON_R + 1.6
ICON_DY = EM_ROW * 0.35


def card_outline(corners=CORNERS):
    """The card blank. Rounded corners follow the ID-1 radius; square corners
    print just as well and read harder, which some styles want."""
    if corners == "square":
        return box(0.0, 0.0, CARD_W, CARD_H)
    return box(CORNER_R, CORNER_R, CARD_W - CORNER_R, CARD_H - CORNER_R).buffer(CORNER_R, 32)


def row_y(i):
    """Baseline of contact row i, counted from the top of the block."""
    return ROW_Y0 + (len(ROWS) - 1 - i) * ROW_LEAD


# Every style resolves to these four 2D layers. base and feature are the two
# filaments; engrave is cut ENGRAVE_Z deep into the top of the base, high sits
# HIGH_Z above the feature. Both extra layers are optional and cost nothing at
# print time: they change z only, never the filament, so the card still needs a
# single change.
Card = namedtuple("Card", "base engrave feature high")

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
    "terrazzo": {
        "label": "Terrazzo: scattered chips, teal on cream",
        "frame": "band",
        "qr": "relief",
        "decor": "terrazzo",
        "base_color": "#f6f1e7",
        "feature_color": "#3a7d6c",
        "base_name": "Basis Creme",
        "feature_name": "Schrift Petrol",
    },
    "hex": {
        "label": "Hex: honeycomb outlines, gold on forest",
        "frame": "none",
        "qr": "recess",
        "decor": "hex",
        "decor_keepout": True,
        "base_color": "#12261f",
        "feature_color": "#e7c86a",
        "base_name": "Basis Dunkelgruen",
        "feature_name": "Schrift Gold",
    },
    "chevron": {
        "label": "Chevron: zigzag rows, amber on plum",
        "frame": "none",
        "qr": "recess",
        "decor": "chevron",
        "decor_keepout": True,
        "base_color": "#2b1b3d",
        "feature_color": "#ffd166",
        "base_name": "Basis Pflaume",
        "feature_name": "Schrift Amber",
    },
    "polka": {
        "label": "Polka: even dot grid, plum on rose",
        "frame": "band",
        "qr": "relief",
        "decor": "polka",
        "decor_keepout": True,
        "base_color": "#ffd9e8",
        "feature_color": "#7a1f4b",
        "base_name": "Basis Rose",
        "feature_name": "Schrift Pflaume",
    },
    "bullseye": {
        "label": "Bullseye: concentric rings, red on black",
        "frame": "none",
        "qr": "recess",
        "decor": "bullseye",
        "decor_keepout": True,
        "base_color": "#0f0f10",
        "feature_color": "#ff5252",
        "base_name": "Basis Schwarz",
        "feature_name": "Schrift Rot",
    },
    "sunburst": {
        "label": "Sunburst: rays from the top left, amber on umber",
        "frame": "none",
        "qr": "recess",
        "decor": "sunburst",
        "decor_keepout": True,
        "base_color": "#1b1200",
        "feature_color": "#ffb703",
        "base_name": "Basis Umbra",
        "feature_name": "Schrift Amber",
    },
    "mountains": {
        "label": "Mountains: layered ridges along the bottom",
        "frame": "none",
        "qr": "recess",
        "decor": "mountains",
        "base_color": "#0e2233",
        "feature_color": "#9fd0e0",
        "base_name": "Basis Nachtblau",
        "feature_name": "Schrift Eisblau",
    },
    "city": {
        "label": "City: skyline with lit windows",
        "frame": "none",
        "qr": "recess",
        "decor": "city",
        "base_color": "#06070f",
        "feature_color": "#f2f2f2",
        "base_name": "Basis Nachtschwarz",
        "feature_name": "Schrift Weiss",
    },
    "waveform": {
        "label": "Waveform: audio bars along the bottom",
        "frame": "none",
        "qr": "recess",
        "decor": "waveform",
        "base_color": "#101010",
        "feature_color": "#00e5ff",
        "base_name": "Basis Schwarz",
        "feature_name": "Schrift Cyan",
    },
    "helix": {
        "label": "Helix: double strand with rungs",
        "frame": "band",
        "qr": "recess",
        "decor": "helix",
        "base_color": "#071a2b",
        "feature_color": "#59d9a4",
        "base_name": "Basis Tiefblau",
        "feature_name": "Schrift Mint",
    },
    "spiral": {
        "label": "Spiral: one archimedean coil, slate on bone",
        "frame": "none",
        "qr": "relief",
        "decor": "spiral",
        "decor_keepout": True,
        "base_color": "#efeae3",
        "feature_color": "#21303d",
        "base_name": "Basis Bone",
        "feature_name": "Schrift Schiefer",
    },
    "hatch": {
        "label": "Hatch: 45 degree hatching, ink on solar",
        "frame": "band",
        "qr": "relief",
        "decor": "hatch",
        "decor_keepout": True,
        "base_color": "#fdf6e3",
        "feature_color": "#073642",
        "base_name": "Basis Solar",
        "feature_name": "Schrift Tinte",
    },
    "brick": {
        "label": "Brick: running bond wall, clay on oxblood",
        "frame": "none",
        "qr": "recess",
        "decor": "brick",
        "decor_keepout": True,
        "base_color": "#2a120c",
        "feature_color": "#d98b5f",
        "base_name": "Basis Oxblood",
        "feature_name": "Schrift Ton",
    },
    "plus": {
        "label": "Plus: grid of plus marks, blue on paper",
        "frame": "band",
        "qr": "relief",
        "decor": "plus",
        "decor_keepout": True,
        "base_color": "#f5f5f7",
        "feature_color": "#2b6cb0",
        "base_name": "Basis Papier",
        "feature_name": "Schrift Blau",
    },
    "stitch": {
        "label": "Stitch: dashed seam inside the edge",
        "frame": "none",
        "qr": "recess",
        "decor": "stitch",
        "base_color": "#163020",
        "feature_color": "#ede0c8",
        "base_name": "Basis Waldgruen",
        "feature_name": "Schrift Leinen",
    },
    "tape": {
        "label": "Tape: two strips across the top corners",
        "frame": "none",
        "qr": "relief",
        "layout": "bauhaus",
        "decor": "tape",
        "base_color": "#ece7dd",
        "feature_color": "#b3452f",
        "base_name": "Basis Leinen",
        "feature_name": "Schrift Ziegel",
    },
    "glitch": {
        "label": "Glitch: torn scanline slabs, magenta on ink",
        "frame": "none",
        "qr": "recess",
        "layout": "terminal",
        "decor": "glitch",
        "base_color": "#0b0b12",
        "feature_color": "#ff2e88",
        "base_name": "Basis Tinte",
        "feature_name": "Schrift Magenta",
    },
    "moire": {
        "label": "Moire: two grids at a small angle",
        "frame": "none",
        "qr": "recess",
        "decor": "moire",
        "decor_keepout": True,
        "base_color": "#101010",
        "feature_color": "#c0c0c0",
        "base_name": "Basis Schwarz",
        "feature_name": "Schrift Silber",
    },
    "checker": {
        "label": "Checker: board fading out to the left",
        "frame": "none",
        "qr": "relief",
        "decor": "checker",
        "decor_keepout": True,
        "base_color": "#f2f2f2",
        "feature_color": "#111111",
        "base_name": "Basis Weiss",
        "feature_name": "Schrift Schwarz",
    },
    "matrix": {
        "label": "Matrix: digital rain in columns",
        "frame": "none",
        "qr": "recess",
        "layout": "terminal",
        "decor": "matrix",
        "base_color": "#030b03",
        "feature_color": "#22ff88",
        "base_name": "Basis Schwarz",
        "feature_name": "Schrift Gruen",
    },
    "starfield": {
        "label": "Starfield: four pointed stars, denser up top",
        "frame": "band",
        "qr": "recess",
        "decor": "starfield",
        "base_color": "#060a1a",
        "feature_color": "#ffffff",
        "base_name": "Basis Nachtblau",
        "feature_name": "Schrift Weiss",
    },
    "snake": {
        "label": "Snake: one serpentine path folding across",
        "frame": "none",
        "qr": "recess",
        "decor": "snake",
        "decor_keepout": True,
        "base_color": "#101418",
        "feature_color": "#ffd166",
        "base_name": "Basis Schiefer",
        "feature_name": "Schrift Amber",
    },
    "brackets": {
        "label": "Brackets: camera framing marks in the corners",
        "frame": "none",
        "qr": "recess",
        "layout": "brutal",
        "decor": "brackets",
        "base_color": "#0d0d0d",
        "feature_color": "#f5f5f5",
        "base_name": "Basis Schwarz",
        "feature_name": "Schrift Weiss",
    },
    "ticket": {
        "label": "Ticket: perforation holes and a tear rule",
        "frame": "none",
        "qr": "relief",
        "decor": "ticket",
        "base_color": "#f7f3e8",
        "feature_color": "#8a2b2b",
        "base_name": "Basis Papier",
        "feature_name": "Schrift Bordeaux",
    },
    "knit": {
        "label": "Knit: fair isle rows of V stitches and dots",
        "frame": "band",
        "qr": "recess",
        "decor": "knit",
        "decor_keepout": True,
        "base_color": "#33203a",
        "feature_color": "#f0e4d0",
        "base_name": "Basis Aubergine",
        "feature_name": "Schrift Wolle",
    },
    "lattice": {
        "label": "Lattice: square kufic interlock, gold on teal",
        "frame": "double",
        "qr": "recess",
        "decor": "lattice",
        "decor_keepout": True,
        "base_color": "#0d2b2b",
        "feature_color": "#e0b354",
        "base_name": "Basis Petrol",
        "feature_name": "Schrift Gold",
    },
    "mesh": {
        "label": "Mesh: low poly triangle net, blue on graphite",
        "frame": "none",
        "qr": "recess",
        "decor": "mesh",
        "decor_keepout": True,
        "base_color": "#10131a",
        "feature_color": "#8ab4f8",
        "base_name": "Basis Graphit",
        "feature_name": "Schrift Blau",
    },
    "scales": {
        "label": "Scales: overlapping arcs, brass on ink",
        "frame": "none",
        "qr": "recess",
        "decor": "scales",
        "decor_keepout": True,
        "base_color": "#12161c",
        "feature_color": "#d9a441",
        "base_name": "Basis Tinte",
        "feature_name": "Schrift Messing",
    },
    "ripple": {
        "label": "Ripple: concentric squares, cyan on navy",
        "frame": "none",
        "qr": "recess",
        "decor": "squares",
        "decor_keepout": True,
        "base_color": "#0b1b2b",
        "feature_color": "#7fe3ff",
        "base_name": "Basis Navy",
        "feature_name": "Schrift Cyan",
    },
    "tri": {
        "label": "Tri: triangle tessellation, lime on olive",
        "frame": "none",
        "qr": "recess",
        "decor": "tri",
        "decor_keepout": True,
        "base_color": "#1a2113",
        "feature_color": "#c3e88d",
        "base_name": "Basis Olive",
        "feature_name": "Schrift Limette",
    },
    "arrows": {
        "label": "Arrows: rows pointing at the QR panel",
        "frame": "none",
        "qr": "recess",
        "decor": "arrows",
        "decor_keepout": True,
        "base_color": "#141414",
        "feature_color": "#ff8a5b",
        "base_name": "Basis Schwarz",
        "feature_name": "Schrift Koralle",
    },
    "crosses": {
        "label": "Crosses: scattered X marks, ice on steel",
        "frame": "band",
        "qr": "recess",
        "decor": "crosses",
        "decor_keepout": True,
        "base_color": "#1c2126",
        "feature_color": "#dfe9f3",
        "base_name": "Basis Stahl",
        "feature_name": "Schrift Eis",
    },
    "zebra": {
        "label": "Zebra: sine warped bands, bone on charcoal",
        "frame": "none",
        "qr": "recess",
        "decor": "zebra",
        "decor_keepout": True,
        "base_color": "#171717",
        "feature_color": "#efe7dc",
        "base_name": "Basis Kohle",
        "feature_name": "Schrift Bone",
    },
    "bamboo": {
        "label": "Bamboo: rods with nodes, jade on paper",
        "frame": "band",
        "qr": "relief",
        "decor": "bamboo",
        "decor_keepout": True,
        "base_color": "#f3f1e7",
        "feature_color": "#2f6b4f",
        "base_name": "Basis Papier",
        "feature_name": "Schrift Jade",
    },
    "rain": {
        "label": "Rain: diagonal dashes on a window",
        "frame": "none",
        "qr": "recess",
        "decor": "rain",
        "base_color": "#0b1220",
        "feature_color": "#9ec8ff",
        "base_name": "Basis Mitternacht",
        "feature_name": "Schrift Regenblau",
    },
    "bubbles": {
        "label": "Bubbles: rings floating upward",
        "frame": "none",
        "qr": "recess",
        "decor": "bubbles",
        "base_color": "#04212b",
        "feature_color": "#8ff0e8",
        "base_name": "Basis Tiefsee",
        "feature_name": "Schrift Aqua",
    },
    "radiate": {
        "label": "Radiate: bars fanning from one point",
        "frame": "none",
        "qr": "recess",
        "decor": "radiate",
        "decor_keepout": True,
        "base_color": "#1b1020",
        "feature_color": "#ffb3f0",
        "base_name": "Basis Nachtviolett",
        "feature_name": "Schrift Rosa",
    },
    "sunset": {
        "label": "Sunset: bars thinning towards the top",
        "frame": "none",
        "qr": "recess",
        "decor": "sunset",
        "decor_keepout": True,
        "base_color": "#2a0f2e",
        "feature_color": "#ff9e58",
        "base_name": "Basis Beere",
        "feature_name": "Schrift Orange",
    },
    "perspective": {
        "label": "Perspective: grid converging on a vanishing point",
        "frame": "none",
        "qr": "recess",
        "decor": "perspective",
        "decor_keepout": True,
        "base_color": "#0d0f14",
        "feature_color": "#b6c2ff",
        "base_name": "Basis Nacht",
        "feature_name": "Schrift Lavendel",
    },
    "braille": {
        "label": "Braille: engraved dot cells you can feel",
        "frame": "none",
        "qr": "recess",
        "decor": "braille",
        "decor_keepout": True,
        "decor_mode": "engrave",
        "base_color": "#1d1d1f",
        "feature_color": "#f5f5f7",
        "base_name": "Basis Anthrazit",
        "feature_name": "Schrift Weiss",
    },
    "blocks": {
        "label": "Blocks: coarse random rectangles",
        "frame": "none",
        "qr": "recess",
        "decor": "blocks",
        "decor_keepout": True,
        "base_color": "#101010",
        "feature_color": "#7ef9a2",
        "base_name": "Basis Schwarz",
        "feature_name": "Schrift Neongruen",
    },
    "relief": {
        "label": "Relief: the whole text block raised a second step",
        "frame": "band",
        "qr": "recess",
        "emboss": "text",
        "base_color": "#151515",
        "feature_color": "#ececec",
        "base_name": "Basis Schwarz",
        "feature_name": "Schrift Weiss",
    },
    "deepqr": {
        "label": "Deep QR: modules cut through the panel and into the base",
        "frame": "band",
        "qr": "deep",
        "base_color": "#101010",
        "feature_color": "#f0f0f0",
        "base_name": "Basis Schwarz",
        "feature_name": "Schrift Weiss",
    },
    "dotmatrix": {
        "label": "Dot matrix: every QR module is a raised disc",
        "frame": "none",
        "qr": "relief",
        "qr_shape": "dot",
        "base_color": "#f7f7f5",
        "feature_color": "#101010",
        "base_name": "Basis Weiss",
        "feature_name": "Schrift Schwarz",
    },
    "softqr": {
        "label": "Soft QR: rounded modules, gentler on the eye",
        "frame": "band",
        "qr": "relief",
        "qr_shape": "round",
        "base_color": "#f7f2ea",
        "feature_color": "#3b2f2f",
        "base_name": "Basis Creme",
        "feature_name": "Schrift Espresso",
    },
    "viewfinder": {
        "label": "Viewfinder: corner brackets around the code",
        "frame": "none",
        "qr": "framed",
        "base_color": "#0e0e0e",
        "feature_color": "#ffd166",
        "base_name": "Basis Schwarz",
        "feature_name": "Schrift Amber",
    },
    "embossqr": {
        "label": "Emboss QR: raised modules standing off the base",
        "frame": "none",
        "qr": "relief",
        "emboss": "qr",
        "base_color": "#f2f2f2",
        "feature_color": "#1b1b1b",
        "base_name": "Basis Weiss",
        "feature_name": "Schrift Schwarz",
    },
    "stencil": {
        "label": "Stencil: text knocked out of a full bleed slab",
        "frame": "none",
        "qr": "recess",
        "plate": True,
        "base_color": "#141414",
        "feature_color": "#f2f2f2",
        "base_name": "Basis Schwarz",
        "feature_name": "Schrift Weiss",
    },
    "shadow": {
        "label": "Shadow: text over its own offset ghost",
        "frame": "none",
        "qr": "recess",
        "emboss": "text",
        "shadow": True,
        "base_color": "#101010",
        "feature_color": "#ff5252",
        "base_name": "Basis Schwarz",
        "feature_name": "Schrift Rot",
    },
    "poster": {
        "label": "Poster: everything centred on the left half",
        "frame": "none",
        "qr": "recess",
        "layout": "centered",
        "base_color": "#111318",
        "feature_color": "#f4f1ea",
        "base_name": "Basis Nacht",
        "feature_name": "Schrift Bone",
    },
    "signet": {
        "label": "Signet: an embossed monogram next to the links",
        "frame": "band",
        "qr": "recess",
        "qr_shape": "round",
        "layout": "monogram",
        "emboss": "text",
        "base_color": "#12212b",
        "feature_color": "#e8c88c",
        "base_name": "Basis Petrol",
        "feature_name": "Schrift Gold",
    },
    "spine": {
        "label": "Spine: the name set vertically along the edge",
        "frame": "none",
        "qr": "recess",
        "layout": "vertical",
        "base_color": "#161616",
        "feature_color": "#7fd1ff",
        "base_name": "Basis Schwarz",
        "feature_name": "Schrift Himmel",
    },
    "hollow": {
        "label": "Hollow: outlined letters, less filament, sharper edge",
        "frame": "band",
        "qr": "recess",
        "layout": "outline",
        "base_color": "#1a1a1a",
        "feature_color": "#f0e6d2",
        "base_name": "Basis Schwarz",
        "feature_name": "Schrift Leinen",
    },
    "board": {
        "label": "Board: departure board caps",
        "frame": "none",
        "qr": "recess",
        "layout": "ticker",
        "emboss": "text",
        "base_color": "#0a0a0a",
        "feature_color": "#ffcc33",
        "base_name": "Basis Schwarz",
        "feature_name": "Schrift Bernstein",
    },
    "groove": {
        "label": "Groove: hatching engraved into the base",
        "frame": "band",
        "qr": "recess",
        "decor": "hatch",
        "decor_keepout": True,
        "decor_mode": "engrave",
        "base_color": "#1e1e22",
        "feature_color": "#f5f5f5",
        "base_name": "Basis Graphit",
        "feature_name": "Schrift Weiss",
    },
    "valley": {
        "label": "Valley: contour rings engraved, not raised",
        "frame": "band",
        "qr": "recess",
        "decor": "topo",
        "decor_mode": "engrave",
        "base_color": "#16232b",
        "feature_color": "#e6d5b8",
        "base_name": "Basis Schiefer",
        "feature_name": "Schrift Sand",
    },
    "carved": {
        "label": "Carved: labyrinth grooves under the text",
        "frame": "none",
        "qr": "recess",
        "decor": "maze",
        "decor_mode": "engrave",
        "base_color": "#241a12",
        "feature_color": "#e8c9a0",
        "base_name": "Basis Nussbaum",
        "feature_name": "Schrift Sand",
    },
    "tide": {
        "label": "Tide: engraved ribbons along the bottom",
        "frame": "none",
        "qr": "recess",
        "decor": "wave",
        "decor_mode": "engrave",
        "base_color": "#06212e",
        "feature_color": "#a8e6f0",
        "base_name": "Basis Tiefblau",
        "feature_name": "Schrift Eis",
    },
    "millimeter": {
        "label": "Millimeter: engraved 5 mm paper grid",
        "frame": "band",
        "qr": "relief",
        "decor": "graph",
        "decor_keepout": True,
        "decor_mode": "engrave",
        "base_color": "#f0efe9",
        "feature_color": "#26343d",
        "base_name": "Basis Papier",
        "feature_name": "Schrift Schiefer",
    },
    "comb": {
        "label": "Comb: engraved honeycomb, matte inside the cells",
        "frame": "none",
        "qr": "recess",
        "decor": "hex",
        "decor_keepout": True,
        "decor_mode": "engrave",
        "base_color": "#1b1b1b",
        "feature_color": "#e0b354",
        "base_name": "Basis Schwarz",
        "feature_name": "Schrift Gold",
    },
    "dune": {
        "label": "Dune: engraved ridges with an embossed name",
        "frame": "none",
        "qr": "recess",
        "decor": "mountains",
        "decor_mode": "engrave",
        "emboss": "text",
        "base_color": "#241c12",
        "feature_color": "#f0dcb4",
        "base_name": "Basis Sandstein",
        "feature_name": "Schrift Sand",
    },
    "skyline": {
        "label": "Skyline: raised city with an embossed name",
        "frame": "none",
        "qr": "recess",
        "decor": "city",
        "emboss": "text",
        "base_color": "#05070d",
        "feature_color": "#f2f2f2",
        "base_name": "Basis Nachtschwarz",
        "feature_name": "Schrift Weiss",
    },
    "crest": {
        "label": "Crest: embossed Bauhaus primitives",
        "frame": "none",
        "qr": "relief",
        "layout": "bauhaus",
        "decor": "bauhaus",
        "emboss": "decor",
        "base_color": "#f0ebe1",
        "feature_color": "#1f4b99",
        "base_name": "Basis Creme",
        "feature_name": "Schrift Blau",
    },
    "waffle": {
        "label": "Waffle: embossed lattice you can feel",
        "frame": "double",
        "qr": "recess",
        "decor": "lattice",
        "decor_keepout": True,
        "emboss": "decor",
        "base_color": "#122626",
        "feature_color": "#e0b354",
        "base_name": "Basis Petrol",
        "feature_name": "Schrift Gold",
    },
    "pinstripe": {
        "label": "Pinstripe: engraved hairlines under a raised name",
        "frame": "none",
        "qr": "recess",
        "decor": "moire",
        "decor_keepout": True,
        "decor_mode": "engrave",
        "emboss": "text",
        "base_color": "#101014",
        "feature_color": "#dcdce4",
        "base_name": "Basis Nachtblau",
        "feature_name": "Schrift Silber",
    },
    "weathered": {
        "label": "Weathered: engraved terrazzo chips",
        "frame": "band",
        "qr": "relief",
        "decor": "terrazzo",
        "decor_mode": "engrave",
        "base_color": "#efe9dd",
        "feature_color": "#4a5a4a",
        "base_name": "Basis Kalk",
        "feature_name": "Schrift Moos",
    },
    "frost": {
        "label": "Frost: engraved starfield, raised text",
        "frame": "band",
        "qr": "recess",
        "decor": "starfield",
        "decor_mode": "engrave",
        "emboss": "text",
        "base_color": "#0a1020",
        "feature_color": "#e8f0ff",
        "base_name": "Basis Nachtblau",
        "feature_name": "Schrift Frost",
    },
    "bark": {
        "label": "Bark: engraved chevrons, warm palette",
        "frame": "none",
        "qr": "recess",
        "decor": "chevron",
        "decor_keepout": True,
        "decor_mode": "engrave",
        "base_color": "#2b1d12",
        "feature_color": "#e3b98a",
        "base_name": "Basis Rinde",
        "feature_name": "Schrift Holz",
    },
    "dotwork": {
        "label": "Dotwork: engraved polka grid",
        "frame": "band",
        "qr": "relief",
        "decor": "polka",
        "decor_keepout": True,
        "decor_mode": "engrave",
        "base_color": "#f6f1f4",
        "feature_color": "#5b2a4a",
        "base_name": "Basis Rose",
        "feature_name": "Schrift Beere",
    },
    "tread": {
        "label": "Tread: hazard stripes embossed like a step edge",
        "frame": "none",
        "qr": "recess",
        "decor": "hazard",
        "emboss": "decor",
        "base_color": "#131313",
        "feature_color": "#f2c200",
        "base_name": "Basis Schwarz",
        "feature_name": "Schrift Gelb",
    },
    "circuitry": {
        "label": "Circuitry: PCB traces raised a second step",
        "frame": "double",
        "qr": "framed",
        "decor": "circuit",
        "emboss": "decor",
        "base_color": "#0b3d2e",
        "feature_color": "#d9b45b",
        "base_name": "Basis Platinengruen",
        "feature_name": "Schrift Gold",
    },
    "weave": {
        "label": "Weave: carbon bundles engraved into the base",
        "frame": "none",
        "qr": "recess",
        "decor": "carbon",
        "decor_keepout": True,
        "decor_mode": "engrave",
        "base_color": "#1b1b1d",
        "feature_color": "#c8ccd2",
        "base_name": "Basis Graphit",
        "feature_name": "Schrift Silber",
    },
    "nightsky": {
        "label": "Nightsky: raised stars, rounded QR",
        "frame": "none",
        "qr": "recess",
        "qr_shape": "round",
        "decor": "starfield",
        "emboss": "decor",
        "base_color": "#060a1a",
        "feature_color": "#ffffff",
        "base_name": "Basis Nachtblau",
        "feature_name": "Schrift Weiss",
    },
    "mosaic": {
        "label": "Mosaic: engraved checker fading left",
        "frame": "none",
        "qr": "relief",
        "decor": "checker",
        "decor_keepout": True,
        "decor_mode": "engrave",
        "base_color": "#f2f2f2",
        "feature_color": "#1b1b1b",
        "base_name": "Basis Weiss",
        "feature_name": "Schrift Schwarz",
    },
    "rainstorm": {
        "label": "Rainstorm: engraved rain over a raised name",
        "frame": "none",
        "qr": "recess",
        "decor": "rain",
        "decor_mode": "engrave",
        "emboss": "text",
        "base_color": "#0b1220",
        "feature_color": "#cfe3ff",
        "base_name": "Basis Mitternacht",
        "feature_name": "Schrift Eisblau",
    },
    "coral": {
        "label": "Coral: engraved scales, warm on warm",
        "frame": "none",
        "qr": "recess",
        "decor": "scales",
        "decor_keepout": True,
        "decor_mode": "engrave",
        "base_color": "#2b1414",
        "feature_color": "#ff8f7a",
        "base_name": "Basis Bordeaux",
        "feature_name": "Schrift Koralle",
    },
    "plateau": {
        "label": "Plateau: knocked out slab with dotted QR",
        "frame": "none",
        "qr": "recess",
        "qr_shape": "dot",
        "plate": True,
        "base_color": "#0f0f0f",
        "feature_color": "#f6f6f6",
        "base_name": "Basis Schwarz",
        "feature_name": "Schrift Weiss",
    },
    "ghost": {
        "label": "Ghost: outlined name over its own shadow",
        "frame": "none",
        "qr": "recess",
        "emboss": "text",
        "shadow": True,
        "base_color": "#1a1a1a",
        "feature_color": "#9be7c4",
        "base_name": "Basis Schwarz",
        "feature_name": "Schrift Mint",
    },
    "depth": {
        "label": "Depth: engraved grid, raised text, deep QR",
        "frame": "none",
        "qr": "deep",
        "decor": "graph",
        "decor_keepout": True,
        "decor_mode": "engrave",
        "emboss": "text",
        "base_color": "#12161a",
        "feature_color": "#e9eef2",
        "base_name": "Basis Schiefer",
        "feature_name": "Schrift Weiss",
    },
    "totem": {
        "label": "Totem: vertical name, engraved lattice",
        "frame": "none",
        "qr": "recess",
        "layout": "vertical",
        "decor": "lattice",
        "decor_keepout": True,
        "decor_mode": "engrave",
        "base_color": "#161a12",
        "feature_color": "#d8e07a",
        "base_name": "Basis Waldnacht",
        "feature_name": "Schrift Limette",
    },
    "gitgraph": {
        "label": "Gitgraph: a commit graph running along the bottom",
        "frame": "none",
        "qr": "recess",
        "decor": "gitgraph",
        "base_color": "#1b1b1f",
        "feature_color": "#f05133",
        "base_name": "Basis Anthrazit",
        "feature_name": "Schrift Git-Orange",
    },
    "diff": {
        "label": "Diff: added lines raised, removed lines engraved",
        "frame": "none",
        "qr": "recess",
        "layout": "diff",
        "decor": "diffnote",
        "decor_mode": "engrave",
        "base_color": "#0f1419",
        "feature_color": "#a6e3a1",
        "base_name": "Basis Tinte",
        "feature_name": "Schrift Gruen",
    },
    "punchcard": {
        "label": "Punchcard: 80 column holes engraved into manila",
        "frame": "band",
        "qr": "relief",
        "decor": "punchcard",
        "decor_mode": "engrave",
        "base_color": "#e8dcc0",
        "feature_color": "#26221c",
        "base_name": "Basis Manila",
        "feature_name": "Schrift Schwarz",
    },
    "perfboard": {
        "label": "Perfboard: 2.54 mm hole grid with power rails",
        "frame": "none",
        "qr": "relief",
        "decor": "perfboard",
        "decor_keepout": True,
        "decor_mode": "engrave",
        "base_color": "#d9c39a",
        "feature_color": "#2b2b2b",
        "base_name": "Basis FR4",
        "feature_name": "Schrift Schwarz",
    },
    "dip": {
        "label": "DIP: the card as a chip, legs and a pin 1 notch",
        "frame": "none",
        "qr": "recess",
        "decor": "dip",
        "decor_keepout": True,
        "emboss": "decor",
        "base_color": "#1a1a1c",
        "feature_color": "#c9ccd1",
        "base_name": "Basis Kunststoff",
        "feature_name": "Schrift Silber",
    },
    "vim": {
        "label": "Vim: buffer with a tilde column and a status line",
        "frame": "none",
        "qr": "recess",
        "layout": "vim",
        "decor": "vimchrome",
        "emboss": "decor",
        "decor_clear": 0.6,
        "base_color": "#1e1e2e",
        "feature_color": "#a6e3a1",
        "base_name": "Basis Nachtblau",
        "feature_name": "Schrift Gruen",
    },
    "tree": {
        "label": "Tree: the card as tree output",
        "frame": "none",
        "qr": "recess",
        "layout": "tree",
        "base_color": "#101010",
        "feature_color": "#e6e6e6",
        "base_name": "Basis Schwarz",
        "feature_name": "Schrift Weiss",
    },
    "json": {
        "label": "JSON: the card as an object literal",
        "frame": "none",
        "qr": "relief",
        "layout": "json",
        "base_color": "#f6f8fa",
        "feature_color": "#24292f",
        "base_name": "Basis Papier",
        "feature_name": "Schrift Tinte",
    },
    "scope": {
        "label": "Scope: graticule with a sine and a square trace",
        "frame": "none",
        "qr": "recess",
        "decor": "scope",
        "base_color": "#05130d",
        "feature_color": "#7dff9b",
        "base_name": "Basis Phosphor",
        "feature_name": "Schrift Gruen",
    },
    "conway": {
        "label": "Conway: gliders and still lifes, embossed",
        "frame": "none",
        "qr": "recess",
        "decor": "conway",
        "emboss": "decor",
        "base_color": "#0d0d12",
        "feature_color": "#dfe6ff",
        "base_name": "Basis Nachtschwarz",
        "feature_name": "Schrift Weiss",
    },
    "hexdump": {
        "label": "Hexdump: the card as xxd output",
        "frame": "none",
        "qr": "recess",
        "layout": "hexdump",
        "base_color": "#0b0f14",
        "feature_color": "#9ad1ff",
        "base_name": "Basis Tinte",
        "feature_name": "Schrift Hellblau",
    },
    "makefile": {
        "label": "Makefile: targets, a phony and one variable",
        "frame": "none",
        "qr": "recess",
        "layout": "makefile",
        "base_color": "#101210",
        "feature_color": "#e8c07d",
        "base_name": "Basis Schwarz",
        "feature_name": "Schrift Sand",
    },
    "dockerfile": {
        "label": "Dockerfile: FROM, LABEL, EXPOSE, CMD",
        "frame": "none",
        "qr": "recess",
        "layout": "dockerfile",
        "base_color": "#0d1b2a",
        "feature_color": "#7fd3f7",
        "base_name": "Basis Docker-Blau",
        "feature_name": "Schrift Hellblau",
    },
    "manpage": {
        "label": "Manpage: NAME, SYNOPSIS, SEE ALSO",
        "frame": "band",
        "qr": "relief",
        "layout": "manpage",
        "base_color": "#f4f1e8",
        "feature_color": "#1f1c18",
        "base_name": "Basis Papier",
        "feature_name": "Schrift Tinte",
    },
    "stacktrace": {
        "label": "Stacktrace: a NameError that resolves to a contact",
        "frame": "none",
        "qr": "recess",
        "layout": "stacktrace",
        "base_color": "#1a1114",
        "feature_color": "#ff8080",
        "base_name": "Basis Dunkelrot",
        "feature_name": "Schrift Rot",
    },
    "rustc": {
        "label": "Rustc: a borrow checker error with carets",
        "frame": "none",
        "qr": "recess",
        "layout": "rustc",
        "base_color": "#12100e",
        "feature_color": "#ffb454",
        "base_name": "Basis Schwarz",
        "feature_name": "Schrift Rost",
    },
    "sql": {
        "label": "SQL: a SELECT over the developers table",
        "frame": "none",
        "qr": "recess",
        "layout": "sql",
        "base_color": "#0f1a14",
        "feature_color": "#8fe3b0",
        "base_name": "Basis Dunkelgruen",
        "feature_name": "Schrift Mint",
    },
    "haskell": {
        "label": "Haskell: a record type and its one value",
        "frame": "band",
        "qr": "relief",
        "layout": "haskell",
        "base_color": "#f7f4fb",
        "feature_color": "#5e5086",
        "base_name": "Basis Weiss",
        "feature_name": "Schrift Violett",
    },
    "roguelike": {
        "label": "Roguelike: an ASCII dungeon with the name in a vault",
        "frame": "none",
        "qr": "recess",
        "layout": "roguelike",
        "base_color": "#0a0a0a",
        "feature_color": "#d8c98a",
        "base_name": "Basis Schwarz",
        "feature_name": "Schrift Pergament",
    },
    "tracker": {
        "label": "Tracker: a ProTracker pattern, notes and volumes",
        "frame": "none",
        "qr": "recess",
        "layout": "tracker",
        "base_color": "#1b1030",
        "feature_color": "#8ce0ff",
        "base_name": "Basis Violett",
        "feature_name": "Schrift Cyan",
    },
    "ledmatrix": {
        "label": "LED matrix: the domain lit on a dot panel",
        "frame": "none",
        "qr": "recess",
        "decor": "ledmatrix",
        "base_color": "#121212",
        "feature_color": "#ff5a3c",
        "base_name": "Basis Schwarz",
        "feature_name": "Schrift LED-Rot",
    },
    "railroad": {
        "label": "Railroad: a syntax diagram with a bypass",
        "frame": "none",
        "qr": "relief",
        "decor": "railroad",
        "base_color": "#f6f6f2",
        "feature_color": "#24333d",
        "base_name": "Basis Papier",
        "feature_name": "Schrift Schiefer",
    },
    "logicgates": {
        "label": "Logic: an AND gate with an inverted output",
        "frame": "none",
        "qr": "recess",
        "decor": "logicgates",
        "base_color": "#0e1420",
        "feature_color": "#cfe8ff",
        "base_name": "Basis Nachtblau",
        "feature_name": "Schrift Eisblau",
    },
    "keycaps": {
        "label": "Keycaps: the surname on a row of embossed caps",
        "frame": "none",
        "qr": "recess",
        "decor": "keycaps",
        "emboss": "decor",
        "base_color": "#16181d",
        "feature_color": "#e9e6de",
        "base_name": "Basis Anthrazit",
        "feature_name": "Schrift Creme",
    },
    "turingtape": {
        "label": "Turing tape: cells and a read head",
        "frame": "none",
        "qr": "recess",
        "decor": "turingtape",
        "base_color": "#101014",
        "feature_color": "#f2e6c4",
        "base_name": "Basis Schwarz",
        "feature_name": "Schrift Sand",
    },
    "treeplate": {
        "label": "Treeplate: tree output knocked out of a full bleed slab",
        "frame": "none",
        "qr": "recess",
        "layout": "tree",
        "plate": True,
        "base_color": "#101010",
        "feature_color": "#ececec",
        "base_name": "Basis Schwarz",
        "feature_name": "Schrift Weiss",
    },
    "treeblind": {
        "label": "Treeblind: tree output debossed, depth instead of colour",
        "frame": "band",
        "qr": "recess",
        "layout": "tree",
        "text_mode": "engrave",
        "base_color": "#4c4c55",
        "feature_color": "#e8e8ec",
        "base_name": "Basis Graphit",
        "feature_name": "Schrift Weiss",
    },
    "jsonplate": {
        "label": "Jsonplate: object literal knocked out of a slab",
        "frame": "none",
        "qr": "recess",
        "layout": "json",
        "plate": True,
        "base_color": "#24292f",
        "feature_color": "#f6f8fa",
        "base_name": "Basis Schiefer",
        "feature_name": "Schrift Weiss",
    },
    "jsonblind": {
        "label": "Jsonblind: object literal debossed into a warm base",
        "frame": "band",
        "qr": "relief",
        "layout": "json",
        "text_mode": "engrave",
        "base_color": "#e8e4dc",
        "feature_color": "#2b2b2b",
        "base_name": "Basis Leinen",
        "feature_name": "Schrift Schwarz",
    },
    "devtag": {
        "label": "Devtag: the </> glyph over the name",
        "frame": "none",
        "qr": "recess",
        "layout": "devtag",
        "base_color": "#0f1117",
        "feature_color": "#7ee787",
        "base_name": "Basis Nacht",
        "feature_name": "Schrift Gruen",
    },
    "tags": {
        "label": "Tags: the card wrapped in a dev element",
        "frame": "none",
        "qr": "recess",
        "layout": "tags",
        "corners": "square",
        "base_color": "#1d1f21",
        "feature_color": "#f0c674",
        "base_name": "Basis Anthrazit",
        "feature_name": "Schrift Gelb",
    },
    "commit": {
        "label": "Commit: author, date and a one line message",
        "frame": "none",
        "qr": "recess",
        "layout": "commit",
        "base_color": "#101418",
        "feature_color": "#e6edf3",
        "base_name": "Basis Tinte",
        "feature_name": "Schrift Weiss",
    },
    "readme": {
        "label": "Readme: the card as markdown source",
        "frame": "band",
        "qr": "relief",
        "layout": "readme",
        "base_color": "#f8f8f7",
        "feature_color": "#24292f",
        "base_name": "Basis Papier",
        "feature_name": "Schrift Tinte",
    },
    "env": {
        "label": "Env: a dotenv file that should not be committed",
        "frame": "none",
        "qr": "recess",
        "layout": "env",
        "base_color": "#12140f",
        "feature_color": "#d7ff8a",
        "base_name": "Basis Schwarz",
        "feature_name": "Schrift Limette",
    },
    "curl": {
        "label": "Curl: the response headers of a developer",
        "frame": "none",
        "qr": "recess",
        "layout": "curl",
        "base_color": "#0b1020",
        "feature_color": "#9fe0ff",
        "base_name": "Basis Nachtblau",
        "feature_name": "Schrift Hellblau",
    },
    "todo": {
        "label": "Todo: two things done, three left",
        "frame": "band",
        "qr": "relief",
        "layout": "todo",
        "base_color": "#fdf6e3",
        "feature_color": "#073642",
        "base_name": "Basis Solarized",
        "feature_name": "Schrift Tinte",
    },
    "manifesto": {
        "label": "Manifesto: three words, square corners",
        "frame": "none",
        "qr": "recess",
        "layout": "manifesto",
        "corners": "square",
        "emboss": "text",
        "base_color": "#111111",
        "feature_color": "#fafafa",
        "base_name": "Basis Schwarz",
        "feature_name": "Schrift Weiss",
    },
    "hilbert": {
        "label": "Hilbert: one unbroken space filling curve",
        "frame": "none",
        "qr": "recess",
        "decor": "hilbert",
        "decor_keepout": True,
        "base_color": "#0b1220",
        "feature_color": "#8fd3ff",
        "base_name": "Basis Nachtblau",
        "feature_name": "Schrift Hellblau",
    },
    "sierpinski": {
        "label": "Sierpinski: a triangle subdivided five times",
        "frame": "none",
        "qr": "recess",
        "decor": "sierpinski",
        "decor_keepout": True,
        "base_color": "#150e1e",
        "feature_color": "#f0c0ff",
        "base_name": "Basis Violett",
        "feature_name": "Schrift Flieder",
    },
    "dragon": {
        "label": "Dragon: twelve folds of the dragon curve",
        "frame": "none",
        "qr": "recess",
        "decor": "dragon",
        "decor_keepout": True,
        "base_color": "#101010",
        "feature_color": "#ff8f5c",
        "base_name": "Basis Schwarz",
        "feature_name": "Schrift Koralle",
    },
    "truchet": {
        "label": "Truchet: quarter arcs that wander into loops",
        "frame": "band",
        "qr": "relief",
        "decor": "truchet",
        "decor_keepout": True,
        "base_color": "#f4f1ea",
        "feature_color": "#2f3e46",
        "base_name": "Basis Papier",
        "feature_name": "Schrift Schiefer",
    },
    "lissajous": {
        "label": "Lissajous: three figures a scope would draw",
        "frame": "none",
        "qr": "recess",
        "decor": "lissajous",
        "decor_keepout": True,
        "base_color": "#04140f",
        "feature_color": "#6effc0",
        "base_name": "Basis Dunkelgruen",
        "feature_name": "Schrift Mint",
    },
    "rule30": {
        "label": "Rule 30: order on the left, chaos on the right",
        "frame": "none",
        "qr": "recess",
        "decor": "rule30",
        "decor_keepout": True,
        "base_color": "#0d0d0f",
        "feature_color": "#e8e8ea",
        "base_name": "Basis Schwarz",
        "feature_name": "Schrift Weiss",
    },
    "mandelbrot": {
        "label": "Mandelbrot: the set, eroded to what a nozzle holds",
        "frame": "none",
        "qr": "recess",
        "decor": "mandelbrot",
        "decor_keepout": True,
        "base_color": "#05060a",
        "feature_color": "#b6c9ff",
        "base_name": "Basis Nacht",
        "feature_name": "Schrift Lavendel",
    },
    "phyllotaxis": {
        "label": "Phyllotaxis: sunflower packing at 137.5 degrees",
        "frame": "none",
        "qr": "recess",
        "decor": "phyllotaxis",
        "decor_keepout": True,
        "base_color": "#1a1408",
        "feature_color": "#ffd98a",
        "base_name": "Basis Umbra",
        "feature_name": "Schrift Honig",
    },
    "fibonacci": {
        "label": "Fibonacci: squares with the golden spiral through them",
        "frame": "band",
        "qr": "relief",
        "decor": "fibonacci",
        "decor_keepout": True,
        "base_color": "#f7f3e8",
        "feature_color": "#2b3a2f",
        "base_name": "Basis Bone",
        "feature_name": "Schrift Moos",
    },
    "wireglobe": {
        "label": "Wireglobe: latitudes and longitudes, no fill",
        "frame": "none",
        "qr": "recess",
        "decor": "wireglobe",
        "base_color": "#071019",
        "feature_color": "#7fe3ff",
        "base_name": "Basis Tiefsee",
        "feature_name": "Schrift Cyan",
    },
    "code39": {
        "label": "Code 39: a real barcode of the surname, verified by the tests",
        "frame": "none",
        "qr": "relief",
        "decor": "code39",
        "base_color": "#f5f5f2",
        "feature_color": "#141414",
        "base_name": "Basis Weiss",
        "feature_name": "Schrift Schwarz",
    },
    "morse": {
        "label": "Morse: ADATEPE engraved as dots and dashes",
        "frame": "band",
        "qr": "recess",
        "decor": "morse",
        "decor_mode": "engrave",
        "base_color": "#161616",
        "feature_color": "#f2f2f2",
        "base_name": "Basis Schwarz",
        "feature_name": "Schrift Weiss",
    },
    "punchtape": {
        "label": "Punchtape: the name in ASCII on eight hole tape",
        "frame": "none",
        "qr": "relief",
        "decor": "punchtape",
        "decor_mode": "engrave",
        "base_color": "#d9cdb4",
        "feature_color": "#241f1a",
        "base_name": "Basis Tape",
        "feature_name": "Schrift Schwarz",
    },
    "magstripe": {
        "label": "Magstripe: the three track layout, homage not data",
        "frame": "none",
        "qr": "recess",
        "decor": "magstripe",
        "base_color": "#1c1c20",
        "feature_color": "#d8d8dc",
        "base_name": "Basis Anthrazit",
        "feature_name": "Schrift Silber",
    },
    "coremem": {
        "label": "Coremem: ferrite cores with the wires threaded between",
        "frame": "none",
        "qr": "recess",
        "decor": "coremem",
        "decor_keepout": True,
        "base_color": "#14100c",
        "feature_color": "#e0c9a6",
        "base_name": "Basis Ferrit",
        "feature_name": "Schrift Kupfer",
    },
    "dsky": {
        "label": "DSKY: Apollo registers up top, caution lamps below",
        "frame": "none",
        "qr": "recess",
        "decor": "dsky",
        "base_color": "#0b0b0d",
        "feature_color": "#8de08d",
        "base_name": "Basis Schwarz",
        "feature_name": "Schrift Gruen",
    },
    "graycode": {
        "label": "Graycode: a six bit encoder disc, one bit per step",
        "frame": "none",
        "qr": "recess",
        "decor": "graycode",
        "base_color": "#0f0f12",
        "feature_color": "#d7d7dd",
        "base_name": "Basis Schwarz",
        "feature_name": "Schrift Silber",
    },
    "frontpanel": {
        "label": "Frontpanel: blinkenlights over a row of paddles",
        "frame": "none",
        "qr": "recess",
        "decor": "frontpanel",
        "emboss": "decor",
        "base_color": "#161a1f",
        "feature_color": "#ffd166",
        "base_name": "Basis Schiefer",
        "feature_name": "Schrift Bernstein",
    },
    "monoscope": {
        "label": "Monoscope: a broadcast test card with a resolution wedge",
        "frame": "none",
        "qr": "recess",
        "decor": "monoscope",
        "base_color": "#0a0a0a",
        "feature_color": "#f0f0f0",
        "base_name": "Basis Schwarz",
        "feature_name": "Schrift Weiss",
    },
    "flamegraph": {
        "label": "Flamegraph: the profiler mountain range",
        "frame": "none",
        "qr": "recess",
        "decor": "flamegraph",
        "base_color": "#140f0a",
        "feature_color": "#ff9f45",
        "base_name": "Basis Kohle",
        "feature_name": "Schrift Flamme",
    },
    "teletext": {
        "label": "Teletext: a header band over mosaic cells",
        "frame": "none",
        "qr": "recess",
        "decor": "teletext",
        "base_color": "#0a0a0a",
        "feature_color": "#ffe066",
        "base_name": "Basis Schwarz",
        "feature_name": "Schrift Gelb",
    },
    "workbench": {
        "label": "Workbench: Amiga window chrome with gadgets",
        "frame": "none",
        "qr": "recess",
        "decor": "workbench",
        "decor_clear": 0.6,
        "base_color": "#0e1a2b",
        "feature_color": "#dfe6ef",
        "base_name": "Basis Amiga-Blau",
        "feature_name": "Schrift Weiss",
    },
    "ansi": {
        "label": "ANSI: a BBS box drawn in double lines",
        "frame": "none",
        "qr": "recess",
        "layout": "ansi",
        "base_color": "#101010",
        "feature_color": "#55ff55",
        "base_name": "Basis Schwarz",
        "feature_name": "Schrift Gruen",
    },
    "konami": {
        "label": "Konami: up up down down, then hire me",
        "frame": "none",
        "qr": "recess",
        "layout": "konami",
        "base_color": "#0b0b1a",
        "feature_color": "#ff4d6d",
        "base_name": "Basis Nachtblau",
        "feature_name": "Schrift Rot",
    },
    "vcard": {
        "label": "Vcard: the card as its own vCard source",
        "frame": "band",
        "qr": "relief",
        "layout": "vcard",
        "base_color": "#f7f7f5",
        "feature_color": "#1b2733",
        "base_name": "Basis Papier",
        "feature_name": "Schrift Tinte",
    },
    "asm": {
        "label": "Asm: seven instructions and a string literal",
        "frame": "none",
        "qr": "recess",
        "layout": "asm",
        "base_color": "#141414",
        "feature_color": "#ffd166",
        "base_name": "Basis Schwarz",
        "feature_name": "Schrift Bernstein",
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
# DejaVu Sans Mono ships with matplotlib, so the code layouts render the same
# everywhere. Its advance is 0.595 em, which is what sets the line budget:
# at EM_CODE the text column holds 21 characters.
FONT_MONO = FontProperties(family="DejaVu Sans Mono")
FONT_MONO_BOLD = FontProperties(family="DejaVu Sans Mono", weight="bold")
EM_CODE = 3.6         # stroke 0.44 mm, 2.14 mm per character
CODE_LEAD = EM_CODE * 1.55


# ---------------------------------------------------------------- text -> shapely
def _outline(tp):
    """Even-odd fill of a TextPath: cumulative symmetric difference."""
    polys = [Polygon(p) for p in tp.to_polygons() if len(p) >= 3]
    polys = [p if p.is_valid else p.buffer(0) for p in polys]
    if not polys:
        return Polygon()
    return reduce(lambda a, b: a.symmetric_difference(b), polys).buffer(0)


@lru_cache(maxsize=32)
def _ft_font(path, em):
    from matplotlib.ft2font import FT2Font

    font = FT2Font(path)
    font.set_size(em, 72)   # TextPath renders at 72 dpi, so 1 point == 1 unit
    return font


def _advances(s, em, fp):
    """Exact pen positions for a string: real glyph advances plus kerning.

    Measuring prefixes with bounding boxes gets this wrong, because a bounding
    box drops side bearings and trailing spaces, which shows up as random wide
    gaps between letter pairs.
    """
    from matplotlib.ft2font import Kerning
    from matplotlib.font_manager import findfont

    font = _ft_font(findfont(fp), em)
    xs, x, prev = [], 0.0, None
    for ch in s:
        idx = font.get_char_index(ord(ch))
        if prev is not None:
            x += font.get_kerning(prev, idx, Kerning.DEFAULT) / 64.0
        xs.append(x)
        x += font.load_char(ord(ch)).linearHoriAdvance / 65536.0
        prev = idx
    return xs


def text_shape(s, em, fp=FONT, track=0.0):
    """Text as a polygon at em size.

    track adds letterspacing in mm. On a 0.2 mm nozzle the gap between glyphs
    matters as much as the stroke width: below roughly 0.45 mm neighbouring
    letters bleed into each other on the print. Tracking buys that gap without
    making the type bigger, so it is the cheaper half of the fix.
    """
    if not track:
        return _outline(TextPath((0, 0), s, size=em, prop=fp))

    glyphs = []
    for i, (ch, x) in enumerate(zip(s, _advances(s, em, fp))):
        if ch == " ":
            continue
        glyph = _outline(TextPath((0, 0), ch, size=em, prop=fp))
        glyphs.append(shp_translate(glyph, xoff=x + i * track))
    return unary_union(glyphs).buffer(0) if glyphs else Polygon()


def place_text(s, em, x, y, fp=FONT, track=0.0):
    return shp_translate(text_shape(s, em, fp, track), xoff=x, yoff=y)


# ---------------------------------------------------------------- icons
def icon_globe(cx, cy, r=None, stroke=None):
    r = ICON_R if r is None else r
    stroke = r * 0.26 if stroke is None else stroke
    disk = Point(cx, cy).buffer(r, 64)
    ring = Point(cx, cy).buffer(r, 64).exterior.buffer(stroke / 2)
    equator = box(cx - r, cy - stroke / 2, cx + r, cy + stroke / 2)
    meridian = shp_scale(Point(cx, cy).buffer(r, 64).exterior, 0.45, 1.0).buffer(stroke / 2)
    return unary_union([ring, equator.intersection(disk), meridian.intersection(disk)])


def icon_linkedin(cx, cy, size=None):
    size = ICON_R * 2.1 if size is None else size
    half = size / 2
    sq = box(cx - half, cy - half, cx + half, cy + half).buffer(-size * 0.2).buffer(size * 0.2)
    # the recessed "in" was the worst offender on the print: 0.18 mm between
    # the two glyphs. Bigger, and tracked apart.
    txt = text_shape("in", size * 0.78, FONT_BOLD, track=size * 0.05)
    b = txt.bounds
    txt = shp_translate(txt, xoff=cx - (b[0] + b[2]) / 2, yoff=cy - (b[1] + b[3]) / 2)
    return sq.difference(txt)


def icon_github(cx, cy, r=None):
    r = ICON_R if r is None else r
    k = r / 1.8 * 0.92   # scale of the old drawing, cat pulled in 8 percent so
    disk = Point(cx, cy).buffer(r, 64)          # the thinnest ring stays >= 0.5 mm
    head = Point(cx, cy + 0.22 * k).buffer(0.95 * k, 32)
    ear_l = Polygon([(cx - 0.9 * k, cy + 0.45 * k), (cx - 1.05 * k, cy + 1.4 * k),
                     (cx - 0.22 * k, cy + 1.05 * k)])
    ear_r = Polygon([(cx + 0.9 * k, cy + 0.45 * k), (cx + 1.05 * k, cy + 1.4 * k),
                     (cx + 0.22 * k, cy + 1.05 * k)])
    body = box(cx - 0.68 * k, cy - 1.55 * k, cx + 0.68 * k, cy - 0.45 * k) \
        .buffer(-0.3 * k).buffer(0.3 * k)
    cat = unary_union([head, ear_l, ear_r, body])
    return disk.difference(cat)


# ---------------------------------------------------------------- QR
def qr_matrix():
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M,
                       border=0, box_size=1)
    qr.add_data(QR_DATA)
    qr.make(fit=True)
    return qr.get_matrix()


def qr_dark_modules(shape="square", panel=None):
    """Dark modules as one polygon.

    shape: "square" is the plain grid, "round" softens the corners and "dot"
    turns every module into a disc. Rounded and dotted modules stay above the
    contrast a decoder needs, which the test suite checks for every style.
    """
    m = qr_matrix()
    n = len(m)
    mod = QR_SIZE / n
    px0, py0, px1, py1 = panel or PANEL
    x0 = (px0 + px1) / 2 - QR_SIZE / 2
    y0 = (py0 + py1) / 2 - QR_SIZE / 2
    eps = 0.02
    cells = []
    for row in range(n):
        for col in range(n):
            if m[row][col]:
                # row 0 is top of the QR -> highest y
                cx0 = x0 + col * mod
                cy0 = y0 + (n - 1 - row) * mod
                if shape == "dot":
                    cells.append(Point(cx0 + mod / 2, cy0 + mod / 2)
                                 .buffer(mod * 0.56, 16))
                else:
                    cells.append(box(cx0 - eps, cy0 - eps,
                                     cx0 + mod + eps, cy0 + mod + eps))
    union = unary_union(cells)
    if shape == "round":
        r = mod * 0.22
        union = union.buffer(-r).buffer(r * 2).buffer(-r)
    return union


def qr_finder_frame(panel=None):
    """Corner brackets around the QR panel, like a viewfinder."""
    x0, y0, x1, y1 = panel or PANEL
    arm, w = 5.0, 0.7
    marks = []
    for cx, sx in ((x0 + 0.4, 1), (x1 - 0.4, -1)):
        for cy, sy in ((y0 + 0.4, 1), (y1 - 0.4, -1)):
            marks.append(box(min(cx, cx + sx * arm), min(cy, cy + sy * w),
                             max(cx, cx + sx * arm), max(cy, cy + sy * w)))
            marks.append(box(min(cx, cx + sx * w), min(cy, cy + sy * arm),
                             max(cx, cx + sx * w), max(cy, cy + sy * arm)))
    return unary_union(marks)


# ---------------------------------------------------------------- build 2D layout
def build_frame(base, kind, qr_mode="recess", panel=None):
    if kind == "none":
        return Polygon()
    if kind == "double":
        hair = 0.35
        outer = base.buffer(-FRAME_OUT).difference(base.buffer(-FRAME_OUT - hair))
        inner = base.buffer(-FRAME_IN - 0.6).difference(base.buffer(-FRAME_IN - 0.6 - hair))
        band = unary_union([outer, inner])
        # let the hairlines stop cleanly at the QR panel instead of running under it
        if qr_mode == "recess":
            return band.difference(box(*(panel or PANEL)).buffer(0.5))
        return band
    return base.buffer(-FRAME_OUT).difference(base.buffer(-FRAME_IN))


# "www." can never print: the w-w pair measures 0.03 mm of gap at any size a
# business card can hold, so it fuses into a block. The domain reads fine
# without it.
ROWS = [
    (icon_globe, "adatepe.dev"),
    (icon_linkedin, "in.adatepe.dev"),
    (icon_github, "git.adatepe.dev"),
]


# Code shaped layouts. Every line is monospaced and at most 21 characters,
# which is what the text column holds at EM_CODE.
CODE_BLOCKS = {
    "diff": [
        ("+++ b/adatepe.card", 0),
        ("+ Alperen Adatepe", 1),
        ("+ digital experiences", 0),
        ("+ adatepe.dev", 0),
        ("+ in.adatepe.dev", 0),
        ("+ git.adatepe.dev", 0),
    ],
    "tree": [
        ("adatepe.dev/", 1),
        ("\u251c\u2500 Alperen Adatepe", 0),
        ("\u251c\u2500 links/", 0),
        ("\u2502  \u251c\u2500 adatepe.dev", 0),
        ("\u2502  \u251c\u2500 in.adatepe.dev", 0),
        ("\u2502  \u2514\u2500 git.adatepe.dev", 0),
        ("\u2514\u2500 card.3mf", 0),
    ],
    "json": [
        ("{", 0),
        (' "name":', 0),
        ('   "Alperen Adatepe",', 1),
        (' "links": [', 0),
        ('   "adatepe.dev",', 0),
        ('   "in.adatepe.dev",', 0),
        ('   "git.adatepe.dev" ]', 0),
        ("}", 0),
    ],
    "hexdump": [
        ("$ xxd adatepe.card", 1),
        ("00000000 41 6c 70 65", 0),
        ("00000004 72 65 6e 20", 0),
        ("00000008 41 64 61 74", 0),
        ("0000000c 65 70 65 0a", 0),
        ("|Alperen Adatepe|", 0),
        ("adatepe.dev", 1),
    ],
    "makefile": [
        ("SITE = adatepe.dev", 1),
        ("LINKS = in git", 0),
        ("", 0),
        ("card.3mf: card.py", 0),
        ("    python card.py", 0),
        (".PHONY: contact", 0),
        ("contact:", 0),
        ("    open $(SITE)", 0),
    ],
    "dockerfile": [
        ("FROM alpine:3.20", 0),
        ('LABEL dev="Alperen"', 0),
        ("LABEL url=adatepe.dev", 1),
        ("COPY card.3mf /card", 0),
        ("EXPOSE 443", 0),
        ('CMD ["open","/card"]', 0),
    ],
    "manpage": [
        ("ADATEPE(1)     CARD", 1),
        ("NAME", 1),
        ("  alperen - builds", 0),
        ("SYNOPSIS", 1),
        ("  adatepe.dev [--in]", 0),
        ("SEE ALSO", 1),
        ("  git.adatepe.dev", 0),
    ],
    "stacktrace": [
        ("Traceback (most", 0),
        ("  recent call last):", 0),
        (' File "you.py", l.42', 0),
        ("   hire(alperen)", 0),
        ("NameError: contact", 1),
        (" at adatepe.dev", 1),
    ],
    "rustc": [
        ("error[E0499]: hire", 1),
        (" --> alperen.rs:1:5", 0),
        ("  |", 0),
        ("1 | let dev = Alperen", 0),
        ("  |     ^^^ found me", 0),
        ("  = note: adatepe.dev", 1),
    ],
    "sql": [
        ("SELECT name, site", 1),
        ("  FROM developers", 0),
        (" WHERE handle =", 0),
        ("   'noluyorAbi';", 0),
        ("-- adatepe.dev", 0),
        ("-- git.adatepe.dev", 0),
    ],
    "haskell": [
        ("data Dev = Dev", 0),
        ("  { name :: String", 0),
        ("  , site :: URL }", 0),
        ("", 0),
        ("alperen :: Dev", 1),
        ("alperen = Dev", 0),
        ('  "Alperen Adatepe"', 0),
        ('  "adatepe.dev"', 0),
    ],
    "roguelike": [
        ("####################", 0),
        ("#@..............>..#", 0),
        ("#.####.#####.####..#", 0),
        ("#.#  ALPEREN   #...#", 1),
        ("#.#  ADATEPE   #.$.#", 1),
        ("#.##############...#", 0),
        ("#....adatepe.dev...#", 0),
        ("####################", 0),
    ],
    "tracker": [
        ("PAT 01      SPD 06", 1),
        ("00 C-4 01 v40 ---", 0),
        ("01 E-4 01 v3C ---", 0),
        ("02 G-4 01 v38 ---", 0),
        ("03 --- -- --- OFF", 0),
        ("04 A-4 02 v40 ---", 0),
        ("-- adatepe.dev  --", 1),
    ],
    "tags": [
        ("<dev>", 1),
        ("  Alperen Adatepe", 0),
        ("  digital experiences", 0),
        ("  adatepe.dev", 0),
        ("  in.adatepe.dev", 0),
        ("  git.adatepe.dev", 0),
        ("</dev>", 1),
    ],
    "commit": [
        ("commit 8f3a2b1c9d4e", 1),
        ("Author: Alperen", 0),
        ("  <hi@adatepe.dev>", 0),
        ("Date:   available", 0),
        ("", 0),
        ("    feat: hire me", 1),
        ("    adatepe.dev", 0),
    ],
    "readme": [
        ("# Alperen Adatepe", 1),
        ("> digital experiences", 0),
        ("", 0),
        ("## links", 1),
        ("- adatepe.dev", 0),
        ("- in.adatepe.dev", 0),
        ("- git.adatepe.dev", 0),
    ],
    "env": [
        ("NAME=Alperen Adatepe", 1),
        ("ROLE=developer", 0),
        ("SITE=adatepe.dev", 0),
        ("IN=in.adatepe.dev", 0),
        ("GIT=git.adatepe.dev", 0),
        ("", 0),
        ("# do not commit ;)", 0),
    ],
    "curl": [
        ("$ curl adatepe.dev", 1),
        ("HTTP/1.1 200 OK", 1),
        ("Server: alperen", 0),
        ("X-Role: developer", 0),
        ("Link: in.adatepe.dev", 0),
        ("Link: git.adatepe.dev", 0),
    ],
    "todo": [
        ("TODO  adatepe.dev", 1),
        ("", 0),
        ("[x] ship the card", 0),
        ("[x] print it twice", 0),
        ("[ ] hire Alperen", 1),
        ("[ ] in.adatepe.dev", 0),
        ("[ ] git.adatepe.dev", 0),
    ],
    "ansi": [
        ("\u2554\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2557", 0),
        ("\u2551  ALPEREN ADATEPE  \u2551", 1),
        ("\u255f\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2562", 0),
        ("\u2551 adatepe.dev       \u2551", 0),
        ("\u2551 in.adatepe.dev    \u2551", 0),
        ("\u2551 git.adatepe.dev   \u2551", 0),
        ("\u255a\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u255d", 0),
    ],
    "konami": [
        ("\u2191 \u2191 \u2193 \u2193 \u2190 \u2192 \u2190 \u2192 B A", 1),
        ("", 0),
        ("cheat: hire Alperen", 1),
        ("adatepe.dev", 0),
        ("in.adatepe.dev", 0),
        ("git.adatepe.dev", 0),
    ],
    "vcard": [
        ("BEGIN:VCARD", 0),
        ("VERSION:4.0", 0),
        ("FN:Alperen Adatepe", 1),
        ("ROLE:developer", 0),
        ("URL:adatepe.dev", 0),
        ("URL:git.adatepe.dev", 0),
        ("END:VCARD", 0),
    ],
    "asm": [
        ("section .text", 0),
        ("global _alperen", 0),
        ("_alperen:", 1),
        ("  mov rdi, site", 0),
        ("  call hire", 0),
        ("  ret", 0),
        ('site db "adatepe.dev"', 0),
    ],
    "vim": [
        ("Alperen Adatepe", 1),
        ("digital experiences", 0),
        ("", 0),
        ("adatepe.dev", 0),
        ("in.adatepe.dev", 0),
        ("git.adatepe.dev", 0),
    ],
}


def _code_block(layout):
    """A monospaced block of lines, top aligned under the top margin."""
    lines = CODE_BLOCKS[layout]
    x0 = TEXT_X0 + (3.0 if layout == "vim" else 0.0)   # vim leaves room for ~
    top = CARD_H - MARGIN - EM_CODE
    parts = []
    for i, (text, bold) in enumerate(lines):
        if not text:
            continue
        parts.append(place_text(text, EM_CODE, x0, top - i * CODE_LEAD,
                                FONT_MONO_BOLD if bold else FONT_MONO))
    return unary_union(parts).buffer(0)


TAGLINE = ("Creating powerful", "digital experiences")


def _centered(txt, em, y, fp=FONT, track=0.0, cx=None):
    shape = text_shape(txt, em, fp, track)
    b = shape.bounds
    return shp_translate(shape, (TEXT_CX if cx is None else cx) - (b[0] + b[2]) / 2, y)


def build_content(layout):
    """Name, tagline and contact rows as one polygon, per layout variant.

    Every branch places type on the shared grid (TEXT_X0, NAME_Y, row_y), so a
    change of card size or type scale moves all nine layouts at once.
    """
    parts = []

    if layout in CODE_BLOCKS:
        return _code_block(layout)

    if layout == "devtag":
        # the one glyph every developer reads as "this person writes code"
        parts.append(place_text("</>", 13.0, TEXT_X0, CARD_H - MARGIN - 9.6,
                                FONT_MONO_BOLD))
        parts.append(place_text("Alperen Adatepe", EM_NAME, TEXT_X0, 31.6,
                                FONT_BOLD, TRACK_NAME))
        parts.append(place_text("digital experiences", EM_TAG, TEXT_X0, 25.0,
                                FONT, TRACK_TAG))
        for i, (icon_fn, label) in enumerate(ROWS):
            y = 18.2 - i * 5.5
            parts.append(icon_fn(ICON_X, y + ICON_DY))
            parts.append(place_text(label, EM_ROW * 0.82, LABEL_X, y, FONT, TRACK_ROW))
        return unary_union(parts).buffer(0)

    if layout == "manifesto":
        for i, word in enumerate(("BUILD.", "SHIP.", "REPEAT.")):
            parts.append(place_text(word, EM_HERO, TEXT_X0,
                                    CARD_H - MARGIN - EM_HERO - i * EM_HERO * 1.25,
                                    FONT_BOLD, TRACK_HERO))
        parts.append(place_text("Alperen Adatepe", EM_ROW * 0.9, TEXT_X0, 9.5,
                                FONT_BOLD, TRACK_ROW))
        parts.append(place_text("adatepe.dev  in  git", EM_ROW * 0.72, TEXT_X0, 4.6,
                                FONT, TRACK_ROW))
        return unary_union(parts).buffer(0)

    if layout == "centered":
        parts.append(_centered("Alperen Adatepe", EM_NAME, NAME_Y, FONT_BOLD, TRACK_NAME))
        for i, line in enumerate(TAGLINE):
            parts.append(_centered(line, EM_TAG, TAG_Y - i * TAG_LEAD, FONT, TRACK_TAG))
        for i, (_, label) in enumerate(ROWS):
            parts.append(_centered(label, EM_ROW, row_y(i), FONT, TRACK_ROW))
        return unary_union(parts).buffer(0)

    if layout == "monogram":
        parts.append(place_text("AA", EM_NAME * 2.7, TEXT_X0, CY - 3.0, FONT_BOLD))
        parts.append(place_text("Alperen Adatepe", EM_ROW * 0.85, TEXT_X0, MARGIN + 1.0,
                                FONT_BOLD, TRACK_ROW))
        for i, (_, label) in enumerate(ROWS):
            parts.append(place_text(label, EM_ROW * 0.66, TEXT_X0 + 22.5,
                                    CY + 4.0 - i * ROW_LEAD * 0.75, FONT, TRACK_ROW))
        return unary_union(parts).buffer(0)

    if layout == "vertical":
        from shapely.affinity import rotate

        name = rotate(text_shape("ALPEREN ADATEPE", EM_ROW * 0.8, FONT_BOLD, TRACK_ROW),
                      90, origin=(0, 0))
        b = name.bounds
        parts.append(shp_translate(name, TEXT_X0 + EM_ROW - b[0], MARGIN - b[1]))
        col = TEXT_X0 + EM_ROW * 2.0
        for i, line in enumerate(TAGLINE):
            parts.append(place_text(line, EM_TAG * 0.85, col, TAG_Y - i * TAG_LEAD,
                                    FONT, TRACK_TAG))
        for i, (icon_fn, label) in enumerate(ROWS):
            y = row_y(i)
            parts.append(icon_fn(col + ICON_R, y + ICON_DY))
            parts.append(place_text(label, EM_ROW * 0.78, col + 2 * ICON_R + 1.4, y,
                                    FONT, TRACK_ROW))
        return unary_union(parts).buffer(0)

    if layout == "outline":
        # letters as hollow rings: less filament, and a sharper tactile edge
        solid = text_shape("Alperen Adatepe", EM_NAME, FONT_BOLD, TRACK_NAME)
        solid = shp_translate(solid, TEXT_X0, NAME_Y)
        parts.append(solid.difference(solid.buffer(-EM_NAME * 0.085)))
        for i, line in enumerate(TAGLINE):
            parts.append(place_text(line, EM_TAG, TEXT_X0, TAG_Y - i * TAG_LEAD, FONT, TRACK_TAG))
        for i, (icon_fn, label) in enumerate(ROWS):
            y = row_y(i)
            parts.append(icon_fn(ICON_X, y + ICON_DY))
            parts.append(place_text(label, EM_ROW, LABEL_X, y, FONT, TRACK_ROW))
        return unary_union(parts).buffer(0)

    if layout == "ticker":
        # one long line per row, like a departure board
        parts.append(place_text("ALPEREN  ADATEPE", EM_NAME * 0.9, TEXT_X0, NAME_Y,
                                FONT_BOLD, TRACK_NAME))
        for i, line in enumerate(TAGLINE):
            parts.append(place_text(line.upper(), EM_TAG * 0.8, TEXT_X0,
                                    TAG_Y - i * TAG_LEAD, FONT, TRACK_TAG))
        for i, (_, label) in enumerate(ROWS):
            parts.append(place_text(label.upper(), EM_ROW * 0.78, TEXT_X0, row_y(i),
                                    FONT_BOLD, TRACK_ROW))
        return unary_union(parts).buffer(0)

    if layout in ("bauhaus", "brutal"):
        # the name owns the card: two hero lines up top, a tight contact block
        # underneath. bauhaus indents the block to clear the quarter disc.
        indent = 12.0 if layout == "bauhaus" else 0.0
        parts.append(place_text("ALPEREN", EM_HERO, TEXT_X0, CARD_H - MARGIN - EM_HERO,
                                FONT_BOLD, TRACK_HERO))
        parts.append(place_text("ADATEPE", EM_HERO, TEXT_X0,
                                CARD_H - MARGIN - EM_HERO * 2.2, FONT_BOLD, TRACK_HERO))
        for i, (_, label) in enumerate(ROWS):
            parts.append(place_text(label, EM_ROW * 0.75, TEXT_X0 + indent,
                                    MARGIN + 1.5 + (len(ROWS) - 1 - i) * EM_ROW * 1.25,
                                    FONT, TRACK_ROW))
        return unary_union(parts).buffer(0)

    if layout == "terminal":
        parts.append(place_text("> Alperen Adatepe", EM_NAME * 0.88, TEXT_X0, NAME_Y,
                                FONT_BOLD, TRACK_NAME))
        for i, line in enumerate(TAGLINE):
            parts.append(place_text(f"# {line.lower()}", EM_SMALL, TEXT_X0,
                                    TAG_Y - i * TAG_LEAD, FONT, TRACK_SMALL))
        for i, (_, label) in enumerate(ROWS):
            parts.append(place_text(f"$ open {label}", EM_SMALL, TEXT_X0, row_y(i),
                                    FONT, TRACK_SMALL))
        return unary_union(parts).buffer(0)

    parts.append(place_text("Alperen Adatepe", EM_NAME, TEXT_X0, NAME_Y, FONT_BOLD, TRACK_NAME))
    for i, line in enumerate(TAGLINE):
        parts.append(place_text(line, EM_TAG, TEXT_X0, TAG_Y - i * TAG_LEAD, FONT, TRACK_TAG))
    for i, (icon_fn, label) in enumerate(ROWS):
        y = row_y(i)
        parts.append(icon_fn(ICON_X, y + ICON_DY))
        parts.append(place_text(label, EM_ROW, LABEL_X, y, FONT, TRACK_ROW))
    return unary_union(parts).buffer(0)


# ---------------------------------------------------------------- decor
# A decor builder returns background texture in feature color. It is always
# carved away from the text and the QR panel afterwards, so it never touches
# legibility or scannability.
def decor_scanlines(base):
    """Window chrome bar, a block cursor and a few scanlines at the bottom."""
    bar_y = CARD_H - EDGE_SAFE - 3.4
    bar = box(EDGE_SAFE, bar_y, CARD_W - EDGE_SAFE, bar_y + 2.2).intersection(base.buffer(-1.0))
    dots = unary_union([Point(x, bar_y + 1.1).buffer(0.55, 24)
                        for x in (EDGE_SAFE + 2.6, EDGE_SAFE + 4.6, EDGE_SAFE + 6.6)])
    # block cursor after the last prompt line, wherever that line now ends
    last = build_content("terminal").bounds[2] + 0.8
    cursor = box(last, row_y(2) - 0.6, last + 1.6, row_y(2) + EM_SMALL * 0.75)
    lines = [box(0, y, CARD_W, y + 0.5) for y in (2.6, 5.0)]
    floor = unary_union(lines).intersection(base.buffer(-1.2))
    return unary_union([bar.difference(dots), cursor, floor])


def decor_circuit(base):
    """PCB-ish traces: horizontal runs with 45 degree elbows, plus round pads."""
    w = 0.45
    shapes = []
    for i, y in enumerate(np.linspace(CARD_H * 0.13, CARD_H * 0.88, 5)):
        end = TEXT_X1 - 6.0 - i * 3.0
        run = box(3.0, y - w / 2, end, y + w / 2)
        elbow = Polygon([
            (end, y - w / 2), (end, y + w / 2),
            (end + 6.0, y + 6.0 + w / 2), (end + 6.0, y + 6.0 - w / 2),
        ])
        shapes += [run, elbow]
        shapes.append(Point(3.0, y).buffer(1.0, 24).difference(
            Point(3.0, y).buffer(0.45, 24)))
    for x in np.arange(6.0, CARD_W - 6.0, 6.0):
        shapes.append(Point(x, EDGE_SAFE + 0.6).buffer(0.55, 16))
    return unary_union(shapes).intersection(base.buffer(-1.0))


def decor_topo(base):
    """Contour rings, like a topographic map, offset inward from a seed blob."""
    seed = unary_union([
        Point(CARD_W * 0.70, CARD_H * 0.74).buffer(9.0, 48),
        Point(CARD_W * 0.58, CARD_H * 0.56).buffer(7.5, 48),
        Point(CARD_W * 0.76, CARD_H * 0.42).buffer(6.0, 48),
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
        ys = BOTTOM_CY + 2.4 * np.sin(xs / 7.0 + phase)
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

    band = box(*BOTTOM)
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
    for r in np.arange(6.0, DIAG, 5.0):
        disc = Point(3.0, 2.0).buffer(r, 96)
        rings.append(disc.difference(disc.buffer(-0.5)))
    return unary_union(rings).intersection(base.buffer(-1.2))


def decor_barcode(base):
    """EAN-ish bars along the bottom edge."""
    rng = np.random.default_rng(11)
    bars, x = [], 3.0
    while x < CARD_W - 3.0:
        w = float(rng.choice([0.5, 0.8, 1.3]))
        bars.append(box(x, BOTTOM[1] + 0.6, x + w, BOTTOM[3] - 0.6))
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
            lines.append(rotate(box(x, -40, x + 0.4, 90), angle, origin=(x, CY)))
    return unary_union(lines).intersection(base.buffer(-1.4))


def decor_bauhaus(base):
    """Three primitives: a ring, a quarter disc and a solid dot."""
    ring = Point(CARD_W * 0.80, CARD_H * 0.80).buffer(6.0, 64)
    ring = ring.difference(ring.buffer(-1.2))
    quarter = Point(EDGE_SAFE, EDGE_SAFE).buffer(11.0, 64).intersection(
        box(EDGE_SAFE, EDGE_SAFE, EDGE_SAFE + 11.0, EDGE_SAFE + 11.0))
    dot = Point(CARD_W * 0.56, CARD_H * 0.83).buffer(2.4, 48)
    bar = box(EDGE_SAFE, CY - 4.6, TEXT_X1 - 4.0, CY - 3.6)
    return unary_union([ring, quarter, dot, bar]).intersection(base.buffer(-1.2))


def _band(shapes, base, bounds=BOTTOM):
    return unary_union(shapes).intersection(box(*bounds)).intersection(base.buffer(-1.0))


def _all(shapes, base, inset=1.2):
    return unary_union(shapes).intersection(base.buffer(-inset))


def decor_terrazzo(base):
    """Scattered chips, like a terrazzo floor."""
    rng = np.random.default_rng(5)
    chips = []
    for _ in range(120):
        cx, cy = rng.uniform(2, CARD_W - 2), rng.uniform(2, CARD_H - 2)
        r = rng.uniform(0.45, 1.15)
        n = int(rng.integers(3, 6))
        ang = rng.uniform(0, 6.28) + np.linspace(0, 6.28, n, endpoint=False)
        pts = [(cx + r * np.cos(a), cy + r * np.sin(a) * 0.8) for a in ang]
        chips.append(Polygon(pts))
    return _all(chips, base)


def decor_hex(base):
    """Honeycomb outlines on a 5 mm pitch."""
    cells, r = [], 2.6
    for row, y in enumerate(np.arange(1.0, CARD_H + 4.0, 3.9)):
        for x in np.arange(1.0 + (2.25 if row % 2 else 0.0), CARD_W + 4.0, 4.5):
            hexa = Point(x, y).buffer(r, 6)
            cells.append(hexa.difference(hexa.buffer(-0.45)))
    return _all(cells, base)


def decor_chevron(base):
    """Chevron zigzag rows across the card."""
    from shapely.geometry import LineString

    rows = []
    for y in np.arange(2.5, CARD_H, 4.5):
        pts = []
        for i, x in enumerate(np.arange(0.0, CARD_W + 4.0, 4.0)):
            pts.append((x, y + (2.0 if i % 2 else 0.0)))
        rows.append(LineString(pts).buffer(0.28, cap_style=2, join_style=1))
    return _all(rows, base)


def decor_polka(base):
    """Even dot grid."""
    dots = []
    for i, x in enumerate(np.arange(2.5, CARD_W - 1.0, 3.6)):
        for y in np.arange(2.5 + (1.8 if i % 2 else 0.0), CARD_H - 1.0, 3.6):
            dots.append(Point(x, y).buffer(0.62, 20))
    return _all(dots, base)


def decor_bullseye(base):
    """Concentric rings around the middle of the text side."""
    rings = []
    for r in np.arange(3.0, DIAG, 4.0):
        disc = Point(CARD_W * 0.31, CY).buffer(r, 96)
        rings.append(disc.difference(disc.buffer(-0.55)))
    return _all(rings, base)


def decor_sunburst(base):
    """Rays fanning out of the top left corner."""
    rays = []
    for a in np.linspace(-1.45, 0.05, 22):
        tip = (EDGE_SAFE + 2 * DIAG * np.cos(a), CARD_H - EDGE_SAFE + 2 * DIAG * np.sin(a))
        rays.append(Polygon([(EDGE_SAFE, CARD_H - EDGE_SAFE - 0.6),
                             (EDGE_SAFE, CARD_H - EDGE_SAFE - 1.6), tip]))
    return _all(rays, base)


def decor_mountains(base):
    """Two layered ridge lines along the bottom."""
    rng = np.random.default_rng(19)
    shapes = []
    for k, (baseline, height) in enumerate(((BOTTOM[1] + 0.5, 4.5), (BOTTOM[1] + 0.5, 7.0))):
        pts = [(0.0, baseline)]
        x = 0.0
        while x < CARD_W:
            x += float(rng.uniform(4.0, 9.0))
            pts.append((x, baseline + float(rng.uniform(1.5, height))))
        pts += [(CARD_W + 2.0, baseline), (CARD_W + 2.0, baseline - 2.0), (0.0, baseline - 2.0)]
        poly = Polygon(pts)
        shapes.append(poly if k else poly.difference(poly.buffer(-0.6)))
    return _band(shapes, base)


def decor_city(base):
    """Skyline blocks with lit windows."""
    rng = np.random.default_rng(31)
    blocks, x = [], 2.0
    while x < CARD_W - 2.0:
        w = float(rng.uniform(2.5, 5.0))
        h = float(rng.uniform(2.0, 6.0))
        tower = box(x, BOTTOM[1] + 0.3, x + w, BOTTOM[1] + 0.3 + h)
        windows = [box(wx, wy, wx + 0.6, wy + 0.6)
                   for wx in np.arange(x + 0.7, x + w - 0.6, 1.4)
                   for wy in np.arange(BOTTOM[1] + 1.1, BOTTOM[1] + 0.3 + h - 0.7, 1.4)]
        blocks.append(tower.difference(unary_union(windows)) if windows else tower)
        x += w + 0.7
    return _band(blocks, base)


def decor_waveform(base):
    """Audio bars along the bottom."""
    rng = np.random.default_rng(41)
    bars = []
    for x in np.arange(3.0, CARD_W - 2.0, 1.8):
        h = 0.8 + 3.0 * abs(float(rng.normal()))
        bars.append(box(x, BOTTOM_CY - h / 2, x + 1.0, BOTTOM_CY + h / 2))
    return _band(bars, base)


def decor_helix(base):
    """Double helix with rungs, running along the bottom."""
    from shapely.geometry import LineString

    xs = np.linspace(0, CARD_W, 200)
    a = LineString(list(zip(xs, BOTTOM_CY + 2.6 * np.sin(xs / 5.0))))
    b = LineString(list(zip(xs, BOTTOM_CY - 2.6 * np.sin(xs / 5.0))))
    shapes = [a.buffer(0.28, cap_style=2), b.buffer(0.28, cap_style=2)]
    for x in np.arange(1.0, CARD_W, 2.5):
        y = 2.6 * np.sin(x / 5.0)
        shapes.append(box(x - 0.2, BOTTOM_CY - y, x + 0.2, BOTTOM_CY + y))
    return _band(shapes, base)


def decor_spiral(base):
    """One archimedean coil in the bottom strip."""
    from shapely.geometry import LineString

    t = np.linspace(0.0, 7.0 * np.pi, 700)
    r = 0.26 * t
    pts = list(zip(12.0 + r * np.cos(t), BOTTOM_CY + r * np.sin(t)))
    return _band([LineString(pts).buffer(0.3, cap_style=2)], base)


def decor_hatch(base):
    """Single direction 45 degree hatching."""
    from shapely.affinity import rotate

    lines = [rotate(box(x, -40, x + 0.45, 90), 45, origin=(x, 22.5))
             for x in np.arange(-60.0, CARD_W + 60.0, 3.2)]
    return _all(lines, base, 1.4)


def decor_brick(base):
    """Running bond brick wall."""
    bricks = []
    for row, y in enumerate(np.arange(2.0, CARD_H - 1.0, 2.6)):
        offset = 3.0 if row % 2 else 0.0
        for x in np.arange(1.0 + offset - 6.0, CARD_W + 6.0, 6.0):
            b = box(x, y, x + 5.4, y + 2.2)
            bricks.append(b.difference(b.buffer(-0.35)))
    return _all(bricks, base)


def decor_plus(base):
    """Grid of plus signs."""
    marks = []
    for x in np.arange(3.0, CARD_W - 1.0, 4.2):
        for y in np.arange(3.0, CARD_H - 1.0, 4.2):
            marks.append(unary_union([box(x - 0.9, y - 0.25, x + 0.9, y + 0.25),
                                      box(x - 0.25, y - 0.9, x + 0.25, y + 0.9)]))
    return _all(marks, base)


def decor_stitch(base):
    """Dashed sewing stitch just inside the edge."""
    ring = base.buffer(-2.2)
    ring = ring.difference(ring.buffer(-0.5))
    dashes = [box(x, -5, x + 1.6, 60) for x in np.arange(-2.0, CARD_W + 4.0, 2.8)]
    dashes += [box(-5, y, 60, y + 1.6) for y in np.arange(-2.0, CARD_H + 4.0, 2.8)]
    return ring.intersection(unary_union(dashes))


def decor_tape(base):
    """Two strips of tape across the top corners."""
    from shapely.affinity import rotate

    top = CARD_H - 10.0
    a = rotate(box(-8.0, top, 16.0, top + 5.0), -45, origin=(4.0, top + 2.5))
    b = rotate(box(CARD_W - 16.0, top, CARD_W + 8.0, top + 5.0), 45,
               origin=(CARD_W - 4.0, top + 2.5))
    return _all([a, b], base, 0.6)


def decor_glitch(base):
    """Displaced slabs, like a torn scanline."""
    rng = np.random.default_rng(13)
    slabs = []
    for y in np.arange(2.5, CARD_H - 2.0, 2.4):
        x0 = float(rng.uniform(0.0, CARD_W * 0.55))
        w = float(rng.uniform(6.0, 26.0))
        slabs.append(box(x0, y, x0 + w, y + float(rng.uniform(0.5, 1.2))))
    return _all(slabs, base)


def decor_moire(base):
    """Two line grids at a small angle, which beat against each other."""
    from shapely.affinity import rotate

    lines = []
    for angle in (0, 7):
        for x in np.arange(-60.0, CARD_W + 60.0, 2.0):
            lines.append(rotate(box(x, -40, x + 0.4, 90), angle, origin=(CX, CY)))
    return _all(lines, base, 1.4)


def decor_checker(base):
    """Checkerboard that fades out towards the left."""
    rng = np.random.default_rng(2)
    cells, size = [], 3.0
    for x in np.arange(2.0, CARD_W - 1.0, size):
        for y in np.arange(2.0, CARD_H - 1.0, size):
            if (int(x / size) + int(y / size)) % 2:
                if rng.random() < 0.15 + 0.9 * (x / CARD_W):
                    cells.append(box(x, y, x + size - 0.3, y + size - 0.3))
    return _all(cells, base)


def decor_matrix(base):
    """Digital rain: dashes falling in columns."""
    rng = np.random.default_rng(29)
    marks = []
    for x in np.arange(3.0, CARD_W - 2.0, 3.0):
        y = float(rng.uniform(CARD_H - 12.0, CARD_H - 2.0))
        while y > 2.0:
            marks.append(box(x, y, x + 1.1, y + 1.1))
            y -= float(rng.uniform(1.8, 4.5))
    return _all(marks, base)


def decor_starfield(base):
    """Four pointed stars, denser towards the top."""
    rng = np.random.default_rng(17)
    stars = []
    for _ in range(70):
        x, y = rng.uniform(2, CARD_W - 2), rng.uniform(2, CARD_H - 2)
        if rng.random() > (y / CARD_H) ** 1.5:
            continue
        r = float(rng.uniform(0.7, 1.6))
        stars.append(Polygon([(x - r, y), (x, y + 0.25 * r), (x + r, y),
                              (x, y - 0.25 * r)]))
        stars.append(Polygon([(x, y - r), (x + 0.25 * r, y), (x, y + r),
                              (x - 0.25 * r, y)]))
    return _all(stars, base)


def decor_snake(base):
    """One serpentine path folding across the card."""
    from shapely.geometry import LineString

    pts, left = [], True
    for y in np.arange(2.8, CARD_H - 1.5, 2.6):
        pts += [(3.0 if left else CARD_W - 3.0, y),
                (CARD_W - 3.0 if left else 3.0, y)]
        left = not left
    return _all([LineString(pts).buffer(0.3, join_style=1)], base)


def decor_brackets(base):
    """Camera framing marks in the four corners."""
    marks, arm, w = [], 7.0, 0.7
    top, bot = CARD_H - 3.0, 3.0
    for cx, cy, sx, sy in ((3.0, top, 1, -1), (CARD_W - 3.0, top, -1, -1),
                           (3.0, bot, 1, 1), (CARD_W - 3.0, bot, -1, 1)):
        marks.append(box(min(cx, cx + sx * arm), min(cy, cy + sy * w),
                         max(cx, cx + sx * arm), max(cy, cy + sy * w)))
        marks.append(box(min(cx, cx + sx * w), min(cy, cy + sy * arm),
                         max(cx, cx + sx * w), max(cy, cy + sy * arm)))
    return _all(marks, base)


def decor_ticket(base):
    """Perforation line and a row of punch holes."""
    holes = [Point(x, BOTTOM_CY).buffer(0.55, 20) for x in np.arange(3.0, CARD_W, 3.0)]
    rule = box(2.0, BOTTOM[3] - 0.5, CARD_W - 2.0, BOTTOM[3])
    notches = [Point(x, BOTTOM[1] + 0.6).buffer(0.5, 20) for x in np.arange(3.0, CARD_W, 2.4)]
    return _all(holes + [rule] + notches, base)


def decor_knit(base):
    """Fair isle rows: alternating V stitches and dot bands."""
    from shapely.geometry import LineString

    rows = []
    for i, y in enumerate(np.arange(2.5, CARD_H - 1.0, 3.4)):
        if i % 2:
            rows += [Point(x, y).buffer(0.45, 16) for x in np.arange(2.5, CARD_W, 2.4)]
        else:
            for x in np.arange(2.0, CARD_W, 3.0):
                rows.append(LineString([(x, y + 1.1), (x + 1.5, y), (x + 3.0, y + 1.1)])
                            .buffer(0.26, cap_style=2, join_style=1))
    return _all(rows, base)


def decor_lattice(base):
    """Square kufic lattice: interlocking L shapes."""
    tiles = []
    for i, x in enumerate(np.arange(2.0, CARD_W - 1.0, 5.0)):
        for j, y in enumerate(np.arange(2.0, CARD_H - 1.0, 5.0)):
            arm = unary_union([box(x, y, x + 3.6, y + 0.6),
                               box(x, y, x + 0.6, y + 3.6)])
            if (i + j) % 2:
                arm = unary_union([box(x + 1.0, y + 4.0, x + 4.6, y + 4.6),
                                   box(x + 4.0, y + 1.0, x + 4.6, y + 4.6)])
            tiles.append(arm)
    return _all(tiles, base)


def decor_mesh(base):
    """Low poly mesh: a jittered triangle grid, edges only."""
    from shapely.geometry import LineString

    rng = np.random.default_rng(37)
    step = 6.5
    pts = {}
    for i, x in enumerate(np.arange(-2.0, CARD_W + 6.0, step)):
        for j, y in enumerate(np.arange(-2.0, CARD_H + 6.0, step)):
            pts[(i, j)] = (x + float(rng.uniform(-1.6, 1.6)),
                           y + float(rng.uniform(-1.6, 1.6)))
    edges = []
    for (i, j), p in pts.items():
        for nb in ((i + 1, j), (i, j + 1), (i + 1, j - 1)):
            if nb in pts:
                edges.append(LineString([p, pts[nb]]).buffer(0.22, cap_style=2))
    return _all(edges, base, 1.4)


def decor_scales(base):
    """Fish scales: overlapping arcs on a staggered grid."""
    arcs = []
    for row, y in enumerate(np.arange(2.0, CARD_H + 3.0, 2.4)):
        for x in np.arange(1.0 + (1.8 if row % 2 else 0.0), CARD_W + 4.0, 3.6):
            disc = Point(x, y).buffer(2.0, 40)
            arcs.append(disc.difference(disc.buffer(-0.42)).intersection(
                box(x - 2.2, y - 2.2, x + 2.2, y)))
    return _all(arcs, base)


def decor_squares(base):
    """Concentric squares, like a ripple in a pond with corners."""
    rings = []
    for r in np.arange(2.0, DIAG, 3.2):
        sq = box(CARD_W * 0.24 - r, CY - r, CARD_W * 0.24 + r, CY + r)
        rings.append(sq.difference(sq.buffer(-0.5)))
    return _all(rings, base)


def decor_tri(base):
    """Triangle tessellation."""
    from shapely.geometry import LineString

    lines = []
    step = 5.0
    for y in np.arange(0.0, CARD_H + step, step):
        lines.append(box(0, y, CARD_W, y + 0.4))
    for x in np.arange(-CARD_H, CARD_W + CARD_H, step):
        lines.append(LineString([(x, 0), (x + CARD_H, CARD_H)]).buffer(0.2, cap_style=2))
        lines.append(LineString([(x, 0), (x - CARD_H, CARD_H)]).buffer(0.2, cap_style=2))
    return _all(lines, base, 1.4)


def decor_arrows(base):
    """Rows of small arrows pointing at the QR panel."""
    marks = []
    for y in np.arange(3.0, CARD_H - 1.0, 4.0):
        for x in np.arange(3.0, CARD_W - 2.0, 4.5):
            marks.append(Polygon([(x, y - 1.1), (x + 2.0, y), (x, y + 1.1),
                                  (x + 0.5, y)]))
    return _all(marks, base)


def decor_crosses(base):
    """Scattered X marks."""
    from shapely.geometry import LineString

    rng = np.random.default_rng(53)
    marks = []
    for x in np.arange(3.0, CARD_W - 1.0, 4.0):
        for y in np.arange(3.0, CARD_H - 1.0, 4.0):
            r = float(rng.uniform(0.7, 1.4))
            marks.append(LineString([(x - r, y - r), (x + r, y + r)]).buffer(0.24, cap_style=2))
            marks.append(LineString([(x - r, y + r), (x + r, y - r)]).buffer(0.24, cap_style=2))
    return _all(marks, base)


def decor_zebra(base):
    """Vertical bands warped by a slow sine, like brushed stripes."""
    bands = []
    ys = np.linspace(0, CARD_H, 90)
    for x in np.arange(1.0, CARD_W + 2.0, 3.4):
        left = x + 1.6 * np.sin(ys / 7.0 + x / 9.0)
        pts = [(lx, y) for lx, y in zip(left, ys)]
        pts += [(lx + 1.4, y) for lx, y in zip(left[::-1], ys[::-1])]
        bands.append(Polygon(pts))
    return _all(bands, base)


def decor_bamboo(base):
    """Vertical rods with nodes."""
    rods = []
    for x in np.arange(3.0, CARD_W - 1.0, 5.0):
        rods.append(box(x, 2.0, x + 1.0, CARD_H - 2.0))
        for y in np.arange(4.0, CARD_H - 2.0, 6.0):
            rods.append(box(x - 0.6, y, x + 1.6, y + 0.6))
    return _all(rods, base)


def decor_rain(base):
    """Diagonal dashes, like rain on a window."""
    from shapely.geometry import LineString

    rng = np.random.default_rng(61)
    drops = []
    for _ in range(150):
        x, y = rng.uniform(1, CARD_W - 1), rng.uniform(1, CARD_H - 1)
        length = float(rng.uniform(1.4, 3.2))
        drops.append(LineString([(x, y), (x + length * 0.4, y - length)])
                     .buffer(0.22, cap_style=2))
    return _all(drops, base)


def decor_bubbles(base):
    """Rings of mixed radius, floating upward."""
    rng = np.random.default_rng(67)
    rings = []
    for _ in range(60):
        x, y = rng.uniform(2, CARD_W - 2), rng.uniform(2, CARD_H - 2)
        r = float(rng.uniform(0.9, 3.4))
        disc = Point(x, y).buffer(r, 40)
        rings.append(disc.difference(disc.buffer(-0.42)))
    return _all(rings, base)


def decor_radiate(base):
    """Bars radiating from a point, longer where there is room."""
    from shapely.affinity import rotate

    bars = []
    for i, a in enumerate(np.linspace(0, 360, 48, endpoint=False)):
        length = 6.0 + 5.0 * abs(np.sin(i * 1.7))
        bar = box(3.0, -0.35, 3.0 + length, 0.35)
        bars.append(rotate(shp_translate(bar, CARD_W * 0.29, CY), a,
                           origin=(CARD_W * 0.29, CY)))
    return _all(bars, base)


def decor_sunset(base):
    """Horizontal bars thinning out towards the top, a printed gradient."""
    bars, y, gap = [], 2.0, 0.6
    height = 2.2
    while y < CARD_H - 2.0:
        bars.append(box(0, y, CARD_W, y + height))
        y += height + gap
        height = max(0.45, height * 0.82)
    return _all(bars, base)


def decor_perspective(base):
    """Grid lines converging on a vanishing point."""
    from shapely.geometry import LineString

    lines = []
    vp = (CX, CY * 1.06)
    for x in np.arange(-30.0, CARD_W + 30.0, 6.0):
        lines.append(LineString([(x, -2.0), vp]).buffer(0.22, cap_style=2))
    for k in range(1, 12):
        y = 2.0 + (vp[1] - 2.0) * (1 - 0.78 ** k)
        lines.append(box(0, y, CARD_W, y + 0.4))
    return _all(lines, base, 1.4)


def decor_braille(base):
    """Dot pairs on a braille cell grid: the most tactile texture here."""
    rng = np.random.default_rng(71)
    dots = []
    for x in np.arange(3.0, CARD_W - 2.0, 4.2):
        for y in np.arange(3.0, CARD_H - 2.0, 5.4):
            for dx in (0.0, 1.6):
                for dy in (0.0, 1.6, 3.2):
                    if rng.random() < 0.55:
                        dots.append(Point(x + dx, y + dy).buffer(0.55, 20))
    return _all(dots, base)


def decor_blocks(base):
    """Random rectangles on a coarse grid, like a QR that lost its mind."""
    rng = np.random.default_rng(73)
    cells = []
    for x in np.arange(2.0, CARD_W - 1.0, 2.6):
        for y in np.arange(2.0, CARD_H - 1.0, 2.6):
            if rng.random() < 0.45:
                w = 2.2 * float(rng.choice([1, 1, 2]))
                cells.append(box(x, y, x + w, y + 2.2))
    return _all(cells, base)


def decor_gitgraph(base):
    """A commit graph running along the bottom strip, git log style."""
    from shapely.geometry import LineString

    y = BOTTOM_CY
    shapes = [box(4.0, y - 0.25, CARD_W - 4.0, y + 0.25)]
    for x in np.arange(6.0, CARD_W - 4.0, 9.0):
        ring = Point(x, y).buffer(1.15, 32)
        shapes.append(ring.difference(ring.buffer(-0.45)))
    # one branch that forks off, carries two commits and merges back
    for sign, x0, x1 in ((1.0, 12.0, 34.0), (-1.0, 40.0, 64.0)):
        off = 3.4 * sign
        xs = np.linspace(x0, x1, 90)
        ys = y + off * np.sin(np.pi * (xs - x0) / (x1 - x0))
        shapes.append(LineString(list(zip(xs, ys))).buffer(0.32, cap_style=2))
        for xb in (x0 + (x1 - x0) * 0.35, x0 + (x1 - x0) * 0.65):
            yb = y + off * np.sin(np.pi * (xb - x0) / (x1 - x0))
            shapes.append(Point(xb, yb).buffer(0.85, 24))
    return _band(shapes, base)


def decor_diffnote(base):
    """The removed lines of the diff, engraved under the added ones."""
    lines = [
        place_text("@@ -1,3 +1,6 @@", EM_CODE, TEXT_X0, BOTTOM_CY + 1.6, FONT_MONO),
        place_text("- www.adatepe.dev", EM_CODE, TEXT_X0, BOTTOM_CY - 3.0, FONT_MONO),
    ]
    return unary_union(lines).intersection(base.buffer(-1.0))


def decor_punchcard(base):
    """IBM punched card: rows of rectangular holes, engraved."""
    rng = np.random.default_rng(1928)   # the year the 80 column card shipped
    # punched in two bands, top and bottom, so the middle stays a print area
    bands = (list(np.arange(3.0, 9.0, 3.0)),
             list(np.arange(CARD_H - 9.0, CARD_H - 3.0, 3.0)))
    holes = []
    for col in np.arange(3.0, CARD_W - 3.0, 2.1):
        for rows in bands:
            for row in rng.choice(rows, size=int(rng.integers(1, len(rows) + 1)),
                                  replace=False):
                holes.append(box(col, row, col + 1.1, row + 2.0))
    return _all(holes, base)


def decor_perfboard(base):
    """Prototyping board: 2.54 mm hole grid with power rails."""
    holes = [Point(x, y).buffer(0.55, 20)
             for x in np.arange(3.5, CARD_W - 2.0, 2.54)
             for y in np.arange(3.5, CARD_H - 2.0, 2.54)]
    rails = [box(2.5, CARD_H - 3.4, CARD_W - 2.5, CARD_H - 2.9),
             box(2.5, CARD_H - 5.0, CARD_W - 2.5, CARD_H - 4.5)]
    return _all(holes + rails, base)


def decor_dip(base):
    """The card as a DIP package: legs along both long edges, pin 1 notch."""
    legs = []
    for x in np.arange(6.0, CARD_W - 5.0, 6.4):
        legs.append(box(x, CARD_H - 5.2, x + 2.6, CARD_H - 2.2))
        legs.append(box(x, 2.2, x + 2.6, 5.2))
    notch = Point(EDGE_SAFE + 0.4, CY).buffer(2.6, 40)
    notch = notch.difference(notch.buffer(-0.6))
    dot = Point(EDGE_SAFE + 4.6, CY - 6.0).buffer(0.9, 24)
    body = base.buffer(-1.4)
    body = body.difference(body.buffer(-0.5))
    return _all(legs + [notch, dot, body], base, 0.6)


def decor_scope(base):
    """Oscilloscope graticule with a trace across it."""
    from shapely.geometry import LineString

    lines = []
    for x in np.arange(CX % 8.4, CARD_W, 8.4):
        lines.append(box(x - 0.15, EDGE_SAFE, x + 0.15, CARD_H - EDGE_SAFE))
    for y in np.arange(CY % 6.5, CARD_H, 6.5):
        lines.append(box(EDGE_SAFE, y - 0.15, CARD_W - EDGE_SAFE, y + 0.15))
    xs = np.linspace(EDGE_SAFE, CARD_W - EDGE_SAFE, 300)
    sine = CY + 9.0 * np.sin(xs / 6.0)
    lines.append(LineString(list(zip(xs, sine))).buffer(0.35, cap_style=2))
    # a square wave under it, the way a scope shows two channels
    sq, y_lo, y_hi, period = [], CY - 15.0, CY - 10.0, 9.0
    for i, x in enumerate(np.arange(EDGE_SAFE, CARD_W - EDGE_SAFE, period / 2)):
        y = y_hi if i % 2 else y_lo
        sq.append(box(x, y - 0.3, min(x + period / 2, CARD_W - EDGE_SAFE), y + 0.3))
        sq.append(box(x - 0.3, min(y_lo, y_hi), x + 0.3, max(y_lo, y_hi)))
    lines += sq
    return _all(lines, base, 1.4)


def decor_conway(base):
    """Game of Life: a glider fleet, a blinker and a couple of still lifes."""
    cell = 2.6
    glider = [(0, 2), (1, 0), (1, 2), (2, 1), (2, 2)]
    blinker = [(0, 0), (1, 0), (2, 0)]
    block = [(0, 0), (0, 1), (1, 0), (1, 1)]
    beacon = [(0, 0), (0, 1), (1, 0), (2, 3), (3, 2), (3, 3)]
    placed = [
        (glider, 3.0, CARD_H - 11.0), (glider, 13.0, CARD_H - 8.0),
        (glider, CARD_W - 15.0, CARD_H - 12.0), (glider, CARD_W - 27.0, CARD_H - 8.0),
        (blinker, CARD_W - 7.0, CARD_H - 20.0), (beacon, CARD_W - 21.0, 3.0),
        (block, 3.5, 3.5), (block, 22.0, 3.0), (blinker, 33.0, 3.2),
        (block, 44.0, 3.4), (glider, CARD_W - 9.0, 12.0),
    ]
    cells = []
    for pattern, ox, oy in placed:
        for gx, gy in pattern:
            x, y = ox + gx * cell, oy + gy * cell
            cells.append(box(x, y, x + cell - 0.35, y + cell - 0.35))
    return _all(cells, base)


def decor_vimchrome(base):
    """The tilde column of an empty buffer plus a filled status line."""
    # bold and a size up, because a regular "~" is a 0.29 mm stroke and the
    # despeckle pass drops it (correctly: it would not print)
    tildes = [place_text("~", EM_CODE * 1.2, TEXT_X0 - 2.8, y, FONT_MONO_BOLD)
              for y in np.arange(MARGIN + 5.0, CARD_H - MARGIN - EM_CODE, CODE_LEAD)]
    bar_h = EM_CODE * 2.2
    bar = box(EDGE_SAFE, EDGE_SAFE + 0.4, CARD_W - EDGE_SAFE, EDGE_SAFE + 0.4 + bar_h)
    label = place_text("-- NORMAL --  adatepe.card", EM_CODE, TEXT_X0 - 1.0,
                       EDGE_SAFE + 0.4 + bar_h * 0.30, FONT_MONO_BOLD)
    ruler = place_text("1,1", EM_CODE, CARD_W - 12.0,
                       EDGE_SAFE + 0.4 + bar_h * 0.30, FONT_MONO_BOLD)
    cursor = box(TEXT_X0 + 3.0, CARD_H - MARGIN - EM_CODE - 2 * CODE_LEAD - 0.4,
                 TEXT_X0 + 3.0 + EM_CODE * 0.6, CARD_H - MARGIN - 2 * CODE_LEAD + 0.2)
    bar = bar.difference(unary_union([label, ruler]).buffer(0.2))
    return _all(tildes + [bar, cursor], base, 0.6)


def decor_ledmatrix(base):
    """The domain rendered as a lit dot matrix panel in the bottom strip."""
    # only the lit dots: an unlit dot small enough to read as "off" is below
    # what a 0.2 mm nozzle prints, and the despeckle pass would drop it anyway
    pitch, lit_r = 0.95, 0.42
    label = text_shape("ADATEPE", 8.0, FONT_BOLD)
    b = label.bounds
    label = shp_translate(label, TEXT_X0 - b[0], BOTTOM_CY - (b[1] + b[3]) / 2)
    dots = [Point(x, y).buffer(lit_r, 16)
            for x in np.arange(b[0] + TEXT_X0 - b[0], CARD_W - 4.0, pitch)
            for y in np.arange(BOTTOM[1] + 0.4, BOTTOM[3] + 0.6, pitch)
            if label.contains(Point(x, y))]
    return _band(dots, base, (0.0, BOTTOM[1], CARD_W, BOTTOM[3] + 1.0))


def decor_railroad(base):
    """A syntax diagram: two terms on the line and one bypass over them."""
    from shapely.geometry import LineString

    y = BOTTOM_CY
    shapes = [box(4.0, y - 0.22, CARD_W - 6.0, y + 0.22),
              Point(4.0, y).buffer(0.9, 24), Point(CARD_W - 6.0, y).buffer(0.9, 24)]
    for x0, x1 in ((11.0, 27.0), (33.0, 49.0)):
        term = box(x0, y - 2.4, x1, y + 2.4).buffer(-1.1).buffer(1.1)
        shapes.append(term.difference(term.buffer(-0.45)))
    bypass = LineString([(8.0, y), (9.6, y + 3.2), (52.0, y + 3.2), (53.6, y)])
    shapes.append(bypass.buffer(0.22, join_style=1, cap_style=2))
    return _band(shapes, base, (0.0, BOTTOM[1], CARD_W, BOTTOM[3] + 3.6))


def decor_logicgates(base):
    """A small gate schematic in the corner the QR panel leaves free."""
    from shapely.geometry import LineString

    x0, y0 = CARD_W - 28.0, CARD_H - 17.0
    shapes = []
    # AND gate: a box with a rounded output side
    body = box(x0 + 5.0, y0 + 5.0, x0 + 10.0, y0 + 11.0)
    nose = Point(x0 + 10.0, y0 + 8.0).buffer(3.0, 40).intersection(
        box(x0 + 10.0, y0 + 5.0, x0 + 13.0, y0 + 11.0))
    gate = unary_union([body, nose])
    shapes.append(gate.difference(gate.buffer(-0.45)))
    # inputs, output, and a NOT bubble
    shapes.append(box(x0, y0 + 6.2, x0 + 5.0, y0 + 6.6))
    shapes.append(box(x0, y0 + 9.4, x0 + 5.0, y0 + 9.8))
    shapes.append(box(x0 + 13.6, y0 + 7.8, x0 + 22.0, y0 + 8.2))
    bubble = Point(x0 + 13.3, y0 + 8.0).buffer(0.85, 24)
    shapes.append(bubble.difference(bubble.buffer(-0.4)))
    shapes.append(Point(x0, y0 + 6.4).buffer(0.6, 20))
    shapes.append(Point(x0, y0 + 9.6).buffer(0.6, 20))
    shapes.append(LineString([(x0 + 22.0, y0 + 8.0), (x0 + 22.0, y0 + 2.0),
                              (x0 + 2.0, y0 + 2.0)]).buffer(0.2, cap_style=2))
    return _all(shapes, base, 1.0)


def decor_keycaps(base):
    """A row of keycaps spelling the surname, letters knocked out of the cap."""
    size, gap = 5.8, 0.9
    caps = []
    for i, ch in enumerate("ADATEPE"):
        x = TEXT_X0 - 1.0 + i * (size + gap)
        cap = box(x, BOTTOM_CY - size / 2, x + size, BOTTOM_CY + size / 2)
        cap = cap.buffer(-0.9).buffer(0.9)
        glyph = text_shape(ch, size * 0.55, FONT_BOLD)
        gb = glyph.bounds
        glyph = shp_translate(glyph, x + size / 2 - (gb[0] + gb[2]) / 2,
                              BOTTOM_CY - (gb[1] + gb[3]) / 2)
        caps.append(cap.difference(glyph.buffer(0.25)))
    return _band(caps, base)


def decor_turingtape(base):
    """A tape of cells with a read head sitting over one of them."""
    size = 6.0
    shapes = []
    for i, sym in enumerate("01101001"):
        x = TEXT_X0 - 1.5 + i * size
        cell = box(x, BOTTOM_CY - size / 2, x + size, BOTTOM_CY + size / 2)
        shapes.append(cell.difference(cell.buffer(-0.4)))
        glyph = text_shape(sym, size * 0.5, FONT_BOLD)
        gb = glyph.bounds
        shapes.append(shp_translate(glyph, x + size / 2 - (gb[0] + gb[2]) / 2,
                                    BOTTOM_CY - (gb[1] + gb[3]) / 2))
    head_x = TEXT_X0 - 1.5 + 3 * size + size / 2
    shapes.append(Polygon([(head_x - 1.6, BOTTOM_CY + size / 2 + 3.0),
                           (head_x + 1.6, BOTTOM_CY + size / 2 + 3.0),
                           (head_x, BOTTOM_CY + size / 2 + 0.6)]))
    return _band(shapes, base, (0.0, BOTTOM[1], CARD_W, BOTTOM[3] + 3.4))


FIGURE = (TEXT_X1 + 1.5, CARD_H - 20.0, CARD_W - EDGE_SAFE, CARD_H - EDGE_SAFE)
FIGURE_CX = (FIGURE[0] + FIGURE[2]) / 2
FIGURE_CY = (FIGURE[1] + FIGURE[3]) / 2


def _fit(geom, pad=0.0):
    """Scale and centre a drawing into the free block above the QR panel."""
    b = geom.bounds
    w, h = FIGURE[2] - FIGURE[0] - 2 * pad, FIGURE[3] - FIGURE[1] - 2 * pad
    k = min(w / max(b[2] - b[0], 1e-9), h / max(b[3] - b[1], 1e-9))
    geom = shp_scale(geom, k, k, origin=(b[0], b[1]))
    b = geom.bounds
    return shp_translate(geom, FIGURE_CX - (b[0] + b[2]) / 2, FIGURE_CY - (b[1] + b[3]) / 2)


def _hilbert(order):
    """Points of a Hilbert curve on the unit square, recursively."""
    def rot(n, x, y, rx, ry):
        if ry == 0:
            if rx == 1:
                x, y = n - 1 - x, n - 1 - y
            x, y = y, x
        return x, y

    n = 2 ** order
    pts = []
    for d in range(n * n):
        rx = ry = 0
        x = y = 0
        t = d
        s = 1
        while s < n:
            rx = 1 & (t // 2)
            ry = 1 & (t ^ rx)
            x, y = rot(s, x, y, rx, ry)
            x += s * rx
            y += s * ry
            t //= 4
            s *= 2
        pts.append((x, y))
    return pts, n


def decor_hilbert(base):
    """A space filling Hilbert curve over the whole card."""
    from shapely.geometry import LineString

    # order 3 in the free block: 2.5 mm pitch, so the ribbon and the gap
    # between two passes both stay above what the nozzle holds
    pts, _ = _hilbert(3)
    line = _fit(LineString([(float(x), float(y)) for x, y in pts]), pad=0.6)
    return _all([line.buffer(0.42, cap_style=2, join_style=1)], base, 1.0)


def decor_sierpinski(base):
    """Sierpinski triangle, subdivided five times."""
    def split(tri, depth):
        if depth == 0:
            return [Polygon(tri)]
        (ax, ay), (bx, by), (cx, cy) = tri
        ab = ((ax + bx) / 2, (ay + by) / 2)
        bc = ((bx + cx) / 2, (by + cy) / 2)
        ca = ((cx + ax) / 2, (cy + ay) / 2)
        return (split((tri[0], ab, ca), depth - 1)
                + split((ab, tri[1], bc), depth - 1)
                + split((ca, bc, tri[2]), depth - 1))

    tri = ((0.0, 0.0), (20.0, 0.0), (10.0, 17.0))
    return _all([_fit(unary_union(split(tri, 4)), pad=0.4)], base, 1.0)


def decor_dragon(base):
    """The dragon curve, twelve folds of it."""
    from shapely.geometry import LineString

    turns = []
    for _ in range(10):
        turns = turns + [1] + [0 if t else 1 for t in reversed(turns)]
    x, y, dx, dy, step = 0.0, 0.0, 1.0, 0.0, 1.0
    pts = [(0.0, 0.0)]
    for t in turns:
        x, y = x + dx * step, y + dy * step
        pts.append((x, y))
        dx, dy = (-dy, dx) if t else (dy, -dx)
    return _all([_fit(LineString(pts), pad=0.6).buffer(0.3, cap_style=2, join_style=1)],
                base, 1.0)


def decor_truchet(base):
    """Truchet tiles: quarter arcs that link up into wandering paths."""
    rng = np.random.default_rng(101)
    size = 6.0
    arcs = []
    for x in np.arange(1.0, CARD_W, size):
        for y in np.arange(1.0, CARD_H, size):
            corners = ((x, y), (x + size, y + size)) if rng.random() < 0.5 else \
                      ((x + size, y), (x, y + size))
            for cx, cy in corners:
                ring = Point(cx, cy).buffer(size / 2, 48)
                arcs.append(ring.difference(ring.buffer(-0.5))
                            .intersection(box(x, y, x + size, y + size)))
    return _all(arcs, base)


def decor_lissajous(base):
    """Three Lissajous figures, the way a scope draws them."""
    from shapely.geometry import LineString

    curves = []
    t = np.linspace(0, 2 * np.pi, 700)
    for i, (a, b_, r) in enumerate(((3, 2, 8.0), (5, 4, 8.0))):
        cx = FIGURE_CX + (-6.5 if i == 0 else 6.5)
        pts = list(zip(cx + r * np.sin(a * t), FIGURE_CY + r * np.sin(b_ * t + i)))
        curves.append(LineString(pts).buffer(0.3, cap_style=2))
    return _all(curves, base, 1.0)


def decor_rule30(base):
    """Rule 30, the cellular automaton that ships inside Mathematica."""
    size = 1.7
    cols = int((CARD_W - 2 * EDGE_SAFE) / size)
    rows = int((CARD_H - 2 * EDGE_SAFE) / size)
    state = np.zeros(cols, dtype=int)
    state[cols // 2] = 1
    cells = []
    for r in range(rows):
        for c in np.nonzero(state)[0]:
            x = EDGE_SAFE + c * size
            y = CARD_H - EDGE_SAFE - (r + 1) * size
            cells.append(box(x, y, x + size - 0.4, y + size - 0.4))
        left, right = np.roll(state, 1), np.roll(state, -1)
        state = np.bitwise_xor(left, np.bitwise_or(state, right))
    return _all(cells, base)


def decor_mandelbrot(base):
    """The Mandelbrot set, sampled coarse enough to print."""
    size = 1.3
    cells = []
    for px in np.arange(EDGE_SAFE, CARD_W - EDGE_SAFE, size):
        for py in np.arange(EDGE_SAFE, CARD_H - EDGE_SAFE, size):
            cr = -2.2 + (px - EDGE_SAFE) / (CARD_W - 2 * EDGE_SAFE) * 3.0
            ci = -1.25 + (py - EDGE_SAFE) / (CARD_H - 2 * EDGE_SAFE) * 2.5
            zr = zi = 0.0
            for _ in range(40):
                zr, zi = zr * zr - zi * zi + cr, 2 * zr * zi + ci
                if zr * zr + zi * zi > 4.0:
                    break
            else:
                cells.append(box(px, py, px + size - 0.25, py + size - 0.25))
    # the seahorse valley filaments are infinitely thin, so erode anything the
    # nozzle could not hold before printing it
    body = unary_union(cells).buffer(-0.25).buffer(0.25)
    return _all([body], base)


def decor_phyllotaxis(base):
    """Sunflower packing: Vogel's model, 137.5 degrees per seed."""
    golden = np.pi * (3 - np.sqrt(5))
    seeds = []
    for i in range(320):
        r = 1.55 * np.sqrt(i)
        a = i * golden
        x, y = CX + r * np.cos(a), CY + r * np.sin(a)
        seeds.append(Point(x, y).buffer(0.34 + 0.0016 * i, 16))
    return _all(seeds, base)


def decor_fibonacci(base):
    """Fibonacci squares with the golden spiral drawn through them.

    Drawn at final size and only translated into place: scaling the drawing
    would thin the 0.4 mm outlines below what the nozzle can hold.
    """
    from shapely.geometry import LineString

    unit = 0.92
    a, b_ = 1, 1
    x, y = 0.0, 0.0
    shapes, direction = [], 0
    for _ in range(6):
        s_ = a * unit * 2.0
        if direction == 0:
            rect, corner = box(x, y, x + s_, y + s_), (x, y + s_)
            nxt = (x + s_, y)
        elif direction == 1:
            rect, corner = box(x, y, x + s_, y + s_), (x, y)
            nxt = (x, y + s_)
        elif direction == 2:
            rect, corner = box(x - s_, y, x, y + s_), (x, y)
            nxt = (x - s_, y)
        else:
            rect, corner = box(x - s_, y - s_, x, y), (x, y)
            nxt = (x, y - s_)
        shapes.append(rect.difference(rect.buffer(-0.42)))
        arc = LineString(Point(corner).buffer(s_, 72).exterior)
        shapes.append(arc.buffer(0.26).intersection(rect))
        x, y = nxt
        direction = (direction + 1) % 4
        a, b_ = b_, a + b_
    drawing = unary_union(shapes)
    b = drawing.bounds
    return _all([shp_translate(drawing, FIGURE_CX - (b[0] + b[2]) / 2,
                               FIGURE_CY - (b[1] + b[3]) / 2)], base, 1.0)


def decor_wireglobe(base):
    """A wireframe globe: latitudes and longitudes, no fill."""
    from shapely.affinity import scale as aff_scale

    cx, cy, r = CARD_W * 0.72, CY, 13.0
    shapes = []
    outer = Point(cx, cy).buffer(r, 96)
    shapes.append(outer.difference(outer.buffer(-0.45)))
    for k in (0.28, 0.58, 0.86):
        ell = aff_scale(Point(cx, cy).buffer(r, 96), k, 1.0)
        shapes.append(ell.difference(ell.buffer(-0.35)))
    for dy in (-0.62, -0.3, 0.0, 0.3, 0.62):
        ell = aff_scale(Point(cx, cy + dy * r).buffer(r, 96), 1.0, 0.16)
        shapes.append(ell.difference(ell.buffer(-0.35)).intersection(outer))
    return _all(shapes, base, 1.0)


MORSE = {"A": ".-", "D": "-..", "E": ".", "P": ".--.", "T": "-", "V": "...-",
         ".": ".-.-.-", "0": "-----"}


def decor_morse(base):
    """ADATEPE in Morse, engraved: dots and dashes you can feel."""
    unit, h = 1.4, 2.2
    shapes, x = [], TEXT_X0
    for ch in "ADATEPE":
        for sym in MORSE[ch]:
            width = unit if sym == "." else unit * 3
            shapes.append(box(x, BOTTOM_CY - h / 2, x + width, BOTTOM_CY + h / 2))
            x += width + unit
        x += unit * 2       # gap between letters
    return _band(shapes, base)


def decor_punchtape(base):
    """Eight hole paper tape: the name in ASCII, with the sprocket track."""
    pitch, hole, sprocket = 2.54, 0.9, 0.5
    shapes = []
    for i, ch in enumerate("ALPEREN"):
        x = TEXT_X0 + i * pitch * 1.6
        bits = format(ord(ch), "08b")
        for b_i, bit in enumerate(reversed(bits)):
            y = BOTTOM[1] + 0.9 + b_i * 0.78
            if bit == "1":
                shapes.append(Point(x, y).buffer(hole / 2, 16))
        shapes.append(Point(x, BOTTOM[1] + 0.9 + 3.5 * 0.78).buffer(sprocket / 2, 12))
    return _band(shapes, base)


def decor_magstripe(base):
    """The magnetic stripe of a bank card, with its three tracks."""
    top = BOTTOM[1] + 0.6
    stripe = box(0.0, top, CARD_W, top + 4.6)
    tracks = [box(2.0, top + 0.9 + i * 1.4, CARD_W - 2.0, top + 1.2 + i * 1.4)
              for i in range(3)]
    return _all([stripe.difference(unary_union(tracks))], base, 0.4)


def decor_teletext(base):
    """Teletext mosaic: a header band and blocky graphics cells."""
    rng = np.random.default_rng(1974)   # Ceefax went live in 1974
    cell_w, cell_h = 2.1, 1.6
    shapes = [box(EDGE_SAFE, CARD_H - EDGE_SAFE - 3.2, CARD_W - EDGE_SAFE, CARD_H - EDGE_SAFE)]
    for x in np.arange(EDGE_SAFE, CARD_W - EDGE_SAFE, cell_w):
        for y in np.arange(EDGE_SAFE, EDGE_SAFE + 8 * cell_h, cell_h):
            if rng.random() < 0.5:
                shapes.append(box(x, y, x + cell_w - 0.35, y + cell_h - 0.3))
    return _all(shapes, base)


def decor_workbench(base):
    """Amiga Workbench window chrome: title bar, gadgets, drag lines."""
    win = base.buffer(-1.6)
    frame = win.difference(win.buffer(-0.6))
    bx0, by0, bx1, by1 = win.bounds
    bar_h = 5.2
    bar = box(bx0, by1 - bar_h, bx1, by1)
    lines = [box(bx0 + 9.0, by1 - bar_h + 1.2 + i * 1.0, bx1 - 14.0,
                 by1 - bar_h + 1.6 + i * 1.0) for i in range(3)]
    close = box(bx0 + 1.2, by1 - bar_h + 1.0, bx0 + 6.0, by1 - 1.0)
    depth = box(bx1 - 6.6, by1 - bar_h + 1.0, bx1 - 1.4, by1 - 1.0)
    gadgets = unary_union([close.difference(close.buffer(-0.55)),
                           depth.difference(depth.buffer(-0.55))])
    return _all([frame, bar.difference(unary_union(lines).buffer(0.0)).difference(
        unary_union([close, depth]).buffer(0.6)), gadgets], base, 0.6)


CODE39 = {
    "0": "nnnwwnwnn", "1": "wnnwnnnnw", "2": "nnwwnnnnw", "3": "wnwwnnnnn",
    "4": "nnnwwnnnw", "5": "wnnwwnnnn", "6": "nnwwwnnnn", "7": "nnnwnnwnw",
    "8": "wnnwnnwnn", "9": "nnwwnnwnn", "A": "wnnnnwnnw", "B": "nnwnnwnnw",
    "C": "wnwnnwnnn", "D": "nnnnwwnnw", "E": "wnnnwwnnn", "F": "nnwnwwnnn",
    "G": "nnnnnwwnw", "H": "wnnnnwwnn", "I": "nnwnnwwnn", "J": "nnnnwwwnn",
    "K": "wnnnnnnww", "L": "nnwnnnnww", "M": "wnwnnnnwn", "N": "nnnnwnnww",
    "O": "wnnnwnnwn", "P": "nnwnwnnwn", "Q": "nnnnnnwww", "R": "wnnnnnwwn",
    "S": "nnwnnnwwn", "T": "nnnnwnwwn", "U": "wwnnnnnnw", "V": "nwwnnnnnw",
    "W": "wwwnnnnnn", "X": "nwnnwnnnw", "Y": "wwnnwnnnn", "Z": "nwwnwnnnn",
    "-": "nwnnnnwnw", ".": "wwnnnnwnn", " ": "nwwnnnwnn", "$": "nwnwnwnnn",
    "/": "nwnwnnnwn", "+": "nwnnnwnwn", "%": "nnnwnwnwn", "*": "nwnnwnwnn",
}


def code39_bars(text, narrow=0.5, ratio=3.0):
    """Code 39 as (x, width) bar pairs. Start and stop are the * character.

    Nine elements per character, alternating bar and space, three of them
    wide. The test suite decodes the rendered card with zxing to prove the
    table is right, so this is a real barcode and not barcode shaped decor.
    """
    bars, x = [], 0.0
    for ch in f"*{text.upper()}*":
        for i, el in enumerate(CODE39[ch]):
            w = narrow * (ratio if el == "w" else 1.0)
            if i % 2 == 0:
                bars.append((x, w))
            x += w
        x += narrow      # inter character gap
    return bars, x - narrow


def decor_code39(base):
    """A Code 39 barcode of the surname, raised dark bars on a light base."""
    narrow = 0.52
    bars, width = code39_bars("ADATEPE", narrow)
    x0 = (CARD_W - width) / 2
    h = min(6.4, BOTTOM[3] - BOTTOM[1] - 0.6)
    return _band([box(x0 + x, BOTTOM_CY - h / 2, x0 + x + w, BOTTOM_CY + h / 2)
                  for x, w in bars], base)


def decor_coremem(base):
    """Ferrite core memory: toroids on 45 degree diagonals, wires threaded
    between them. The wires stop at the cores, so the holes stay open."""
    from shapely.affinity import rotate

    from shapely.geometry import LineString

    pitch, od, wall = 3.6, 2.7, 0.6
    cores, disks, centres = [], [], []
    for i, x in enumerate(np.arange(EDGE_SAFE + 2.0, CARD_W - EDGE_SAFE, pitch)):
        for j, y in enumerate(np.arange(EDGE_SAFE + 1.5, CARD_H - EDGE_SAFE, pitch)):
            ring = Point(x, y).buffer(od / 2, 32)
            ring = ring.difference(ring.buffer(-wall))
            ring = rotate(shp_scale(ring, 1.0, 0.62), 45 if (i + j) % 2 else -45,
                          origin=(x, y))
            cores.append(ring)
            disks.append(Point(x, y).buffer(od / 2 + 0.25, 24))
            centres.append((x, y))
    xs = sorted({round(c[0], 2) for c in centres})
    ys = sorted({round(c[1], 2) for c in centres})
    wires = [LineString([(EDGE_SAFE, y), (CARD_W - EDGE_SAFE, y)]).buffer(0.25)
             for y in ys]
    wires += [LineString([(x, EDGE_SAFE), (x, CARD_H - EDGE_SAFE)]).buffer(0.25)
              for x in xs]
    threaded = unary_union(wires).difference(unary_union(disks))
    return _all(cores + [threaded], base)


def decor_dsky(base):
    """The Apollo guidance computer panel: three registers up in the corner,
    the caution annunciators along the bottom."""
    shapes = []
    rx, ry = CARD_W - 30.0, CARD_H - 18.0
    shapes.append(box(rx - 1.4, ry - 1.4, rx + 27.0, ry + 15.6).difference(
        box(rx - 1.4, ry - 1.4, rx + 27.0, ry + 15.6).buffer(-0.5)))
    for row in range(3):
        y = ry + row * 5.2
        for col in range(5):
            x = rx + 1.0 + col * 5.0
            cell = box(x, y, x + 3.6, y + 4.2)
            shapes.append(cell.difference(cell.buffer(-0.42)))
    for col in range(4):
        x = EDGE_SAFE + 2.0 + col * 12.0
        lamp = box(x, BOTTOM_CY - 2.6, x + 10.0, BOTTOM_CY + 2.6)
        shapes.append(lamp.difference(lamp.buffer(-0.45)))
    return _all(shapes, base, 1.0)


def decor_flamegraph(base):
    """A profiler flame graph: frames stacked, each one narrower than its
    parent, in the strip under the contact rows."""
    h, gap = 2.1, 0.5
    rows = [
        [(0.0, 46.0)],
        [(0.0, 27.0), (28.0, 18.0)],
        [(2.0, 12.0), (15.0, 9.0), (30.0, 14.0)],
    ]
    shapes = []
    for level, frames in enumerate(rows):
        y = BOTTOM[1] + 0.4 + level * (h + gap)
        for x0, w in frames:
            shapes.append(box(TEXT_X0 + x0, y, TEXT_X0 + x0 + w, y + h))
    return _band(shapes, base, (0.0, BOTTOM[1], CARD_W, BOTTOM[3] + 1.2))


def decor_monoscope(base):
    """A broadcast test card: circle in a grid, castellations, a centre cross."""
    cx, cy, r = CARD_W * 0.72, CARD_H * 0.70, 11.5
    shapes = []
    disc = Point(cx, cy).buffer(r, 96)
    shapes.append(disc.difference(disc.buffer(-0.5)))
    inner = Point(cx, cy).buffer(r * 0.62, 96)
    shapes.append(inner.difference(inner.buffer(-0.4)))
    for gx in np.arange(cx - r, cx + r + 0.1, r / 3):
        shapes.append(box(gx - 0.2, cy - r, gx + 0.2, cy + r).intersection(disc))
    for gy in np.arange(cy - r, cy + r + 0.1, r / 3):
        shapes.append(box(cx - r, gy - 0.2, cx + r, gy + 0.2).intersection(disc))
    shapes.append(box(cx - 3.2, cy - 0.45, cx + 3.2, cy + 0.45))
    shapes.append(box(cx - 0.45, cy - 3.2, cx + 0.45, cy + 3.2))
    # resolution wedge: bars that stop at the printable limit
    for i, w in enumerate((1.6, 1.2, 0.9, 0.7, 0.55)):
        x = cx - r - 1.0 - i * 1.9
        shapes.append(box(x, cy - 3.0, x + w, cy + 3.0))
    return _all(shapes, base, 1.0)


def decor_graycode(base):
    """A six bit Gray code encoder disc: one bit flips per step."""
    from shapely.geometry import Polygon as Poly

    cx, cy = CARD_W * 0.73, CARD_H * 0.70
    shapes = []
    for bit in range(6):
        r_out = 4.2 + bit * 2.0
        r_in = r_out - 1.5
        for step in range(64):
            gray = step ^ (step >> 1)
            if not (gray >> bit) & 1:
                continue
            a0, a1 = step * 2 * np.pi / 64, (step + 1) * 2 * np.pi / 64
            pts = [(cx + r_in * np.cos(a), cy + r_in * np.sin(a))
                   for a in np.linspace(a0, a1, 6)]
            pts += [(cx + r_out * np.cos(a), cy + r_out * np.sin(a))
                    for a in np.linspace(a1, a0, 6)]
            shapes.append(Poly(pts))
    hub = Point(cx, cy).buffer(2.6, 48)
    shapes.append(hub.difference(hub.buffer(-0.6)))
    return _all(shapes, base, 1.0)


def decor_frontpanel(base):
    """Blinkenlights: a row of indicator lamps over a row of switch paddles."""
    shapes = []
    for i in range(16):
        x = EDGE_SAFE + 1.5 + i * 3.1
        gap = 0.9 if i in (5, 10) else 0.0
        shapes.append(Point(x + gap, BOTTOM_CY + 1.8).buffer(1.05, 24))
    for i in range(8):
        x = EDGE_SAFE + 2.5 + i * 6.2
        paddle = box(x, BOTTOM_CY - 3.4, x + 2.4, BOTTOM_CY - 0.6)
        shapes.append(paddle.difference(paddle.buffer(-0.45)))
    return _band(shapes, base)


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
    "terrazzo": decor_terrazzo,
    "hex": decor_hex,
    "chevron": decor_chevron,
    "polka": decor_polka,
    "bullseye": decor_bullseye,
    "sunburst": decor_sunburst,
    "mountains": decor_mountains,
    "city": decor_city,
    "waveform": decor_waveform,
    "helix": decor_helix,
    "spiral": decor_spiral,
    "hatch": decor_hatch,
    "brick": decor_brick,
    "plus": decor_plus,
    "stitch": decor_stitch,
    "tape": decor_tape,
    "glitch": decor_glitch,
    "moire": decor_moire,
    "checker": decor_checker,
    "matrix": decor_matrix,
    "starfield": decor_starfield,
    "snake": decor_snake,
    "brackets": decor_brackets,
    "ticket": decor_ticket,
    "knit": decor_knit,
    "lattice": decor_lattice,
    "mesh": decor_mesh,
    "scales": decor_scales,
    "squares": decor_squares,
    "tri": decor_tri,
    "arrows": decor_arrows,
    "crosses": decor_crosses,
    "zebra": decor_zebra,
    "bamboo": decor_bamboo,
    "rain": decor_rain,
    "bubbles": decor_bubbles,
    "radiate": decor_radiate,
    "sunset": decor_sunset,
    "perspective": decor_perspective,
    "braille": decor_braille,
    "blocks": decor_blocks,
    "gitgraph": decor_gitgraph,
    "diffnote": decor_diffnote,
    "punchcard": decor_punchcard,
    "perfboard": decor_perfboard,
    "dip": decor_dip,
    "scope": decor_scope,
    "conway": decor_conway,
    "vimchrome": decor_vimchrome,
    "ledmatrix": decor_ledmatrix,
    "railroad": decor_railroad,
    "logicgates": decor_logicgates,
    "keycaps": decor_keycaps,
    "turingtape": decor_turingtape,
    "hilbert": decor_hilbert,
    "sierpinski": decor_sierpinski,
    "dragon": decor_dragon,
    "truchet": decor_truchet,
    "lissajous": decor_lissajous,
    "rule30": decor_rule30,
    "mandelbrot": decor_mandelbrot,
    "phyllotaxis": decor_phyllotaxis,
    "fibonacci": decor_fibonacci,
    "wireglobe": decor_wireglobe,
    "morse": decor_morse,
    "punchtape": decor_punchtape,
    "magstripe": decor_magstripe,
    "teletext": decor_teletext,
    "workbench": decor_workbench,
    "coremem": decor_coremem,
    "dsky": decor_dsky,
    "flamegraph": decor_flamegraph,
    "monoscope": decor_monoscope,
    "graycode": decor_graycode,
    "frontpanel": decor_frontpanel,
    "code39": decor_code39,
}


# QR modes. "recess" cuts the dark modules out of a light panel, "relief"
# raises them with no panel (only readable on a light base), "deep" also sinks
# them into the base, "framed" adds corner brackets. The module outline itself
# is a separate axis: qr_shape is "square", "round" or "dot".
PANEL_MODES = {"recess", "deep", "framed"}
RELIEF_MODES = {"relief"}


def _clean(geom, base):
    """Trim to the card, drop T-vertices and point contacts, then heal."""
    geom = geom.intersection(base).simplify(0.005).buffer(0)
    # the close-then-open pass below fixes point contacts but re-inserts a lot
    # of near collinear vertices; simplifying again keeps the meshes small
    return geom.buffer(0.01).buffer(-0.01).buffer(0).simplify(0.002).buffer(0)


def build_shapes(style=DEFAULT_STYLE, corners=None):
    """Resolve a style into the four 2D layers of a Card."""
    st = STYLES[style] if isinstance(style, str) else style
    qr_mode = st["qr"]
    base = card_outline(corners or st.get("corners", CORNERS))
    panel_rect = panel_box(st)
    panel = box(*panel_rect)

    frame = build_frame(base, st["frame"], "recess" if qr_mode in PANEL_MODES else "relief",
                        panel_rect)
    content = build_content(st.get("layout", "default"))
    modules = qr_dark_modules(st.get("qr_shape", "square"), panel_rect)

    texture = Polygon()
    if st.get("decor"):
        texture = DECOR[st["decor"]](base)
        # keep the texture clear of the text and of the QR quiet zone
        clear = st.get("decor_clear", 1.4)
        texture = texture.difference(content.buffer(clear)).difference(panel.buffer(1.2))
        if st.get("decor_keepout"):
            # dense patterns get a clean rectangle around the whole text block
            texture = texture.difference(content.envelope.buffer(1.6))
        texture = despeckle(texture)

    engraved = st.get("decor_mode") == "engrave"
    feature = [frame]
    if not engraved:
        feature.append(texture)

    blind = st.get("text_mode") == "engrave"
    if st.get("plate"):
        # full bleed slab with the text knocked out of it
        feature.append(base.buffer(-FRAME_OUT).difference(content.buffer(0.0)))
    elif blind:
        pass    # blind deboss: the text is sunk into the base, see below
    else:
        if st.get("shadow"):
            # only the name casts the ghost; doubling the small type is mush
            name = content.intersection(box(0, NAME_Y - 0.5, CARD_W, CARD_H))
            feature.append(shp_translate(name, EM_NAME * 0.11, -EM_NAME * 0.11))
        feature.append(content)

    if qr_mode in PANEL_MODES:
        feature.append(panel)
    if qr_mode == "framed":
        feature.append(qr_finder_frame(panel_rect))

    feature = unary_union(feature).buffer(0)
    if qr_mode in PANEL_MODES:
        feature = feature.difference(modules).buffer(0)
    else:
        feature = unary_union([feature, modules]).buffer(0)
    feature = _clean(feature, base)

    # engrave layer: grooves cut into the top of the base
    engrave, engrave_keep = [], Polygon()
    if blind:
        # the text becomes a groove instead of a raised feature: no colour
        # contrast at all, only depth, which is what a blind deboss is
        engrave_keep = content
    if engraved:
        engrave.append(texture)
    if qr_mode == "deep":
        engrave.append(modules.intersection(panel))
    if engrave or not engrave_keep.is_empty:
        grooves = Polygon()
        if engrave:
            grooves = _clean(unary_union(engrave).buffer(0), base.buffer(-0.8))
            # decor crumbs get the same cleanup as the raised side
            grooves = despeckle(grooves.difference(feature.buffer(0.25)).buffer(0),
                                0.4, 0.12)
        if not engrave_keep.is_empty:
            kept = _clean(engrave_keep, base.buffer(-0.8))
            grooves = unary_union([grooves, kept.difference(feature.buffer(0.25))])
        engrave = grooves.buffer(0).simplify(0.005).buffer(0.01).buffer(-0.01).buffer(0)
    else:
        engrave = Polygon()

    # high layer: whatever the style wants to feel raised under a thumb
    emboss = st.get("emboss")
    high = {
        None: Polygon(),
        "text": content,
        "frame": frame,
        "panel": panel,
        "decor": texture if not engraved else Polygon(),
        "qr": modules if qr_mode in RELIEF_MODES else Polygon(),
    }[emboss]
    high = _clean(high.intersection(feature), base) if not high.is_empty else Polygon()

    return Card(base, engrave, feature, high)


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


def card_meshes(card):
    """Two printable parts: the base filament and the feature filament.

    A style with an engrave layer splits the base into two stacked solids, so
    the grooves are real geometry instead of a texture. A style with a high
    layer stacks a second solid on the features. Both stay inside their own
    filament, so the print is still one color change.
    """
    if card.engrave.is_empty:
        base_mesh = extrude(card.base, BASE_Z, 0.0)
    else:
        lower = extrude(card.base, BASE_Z - ENGRAVE_Z, 0.0)
        upper = extrude(card.base.difference(card.engrave), ENGRAVE_Z, BASE_Z - ENGRAVE_Z)
        base_mesh = trimesh.util.concatenate([lower, upper])

    feature_mesh = extrude(card.feature, TOP_Z, BASE_Z)
    if not card.high.is_empty:
        feature_mesh = trimesh.util.concatenate(
            [feature_mesh, extrude(card.high, HIGH_Z, BASE_Z + TOP_Z)])
    return base_mesh, feature_mesh


def _shade(hex_color, amount):
    """Blend a hex color towards white (amount > 0) or black (amount < 0)."""
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    target = 255 if amount > 0 else 0
    f = abs(amount)
    return "#%02x%02x%02x" % tuple(int(c + (target - c) * f) for c in (r, g, b))


def preview(card, path, style=DEFAULT_STYLE):
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
    fig, ax = plt.subplots(figsize=(10, 10 * CARD_H / CARD_W))
    fig.patch.set_facecolor("#3a3a3a")
    patch(card.base, facecolor=st["base_color"], edgecolor="none")
    if not card.engrave.is_empty:
        # grooves read as a darker shade of the base filament
        patch(card.engrave, facecolor=_shade(st["base_color"], -0.55), edgecolor="none")
    patch(card.feature, facecolor=st["feature_color"], edgecolor="none")
    if not card.high.is_empty:
        # embossed geometry catches more light than the rest of the feature
        patch(shp_translate(card.high, 0.15, -0.15),
              facecolor=_shade(st["feature_color"], -0.22), edgecolor="none")
        patch(card.high, facecolor=_shade(st["feature_color"], 0.22), edgecolor="none")
    ax.set_xlim(-3, CARD_W + 3)
    ax.set_ylim(-3, CARD_H + 3)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.savefig(path, dpi=160, bbox_inches="tight", facecolor="#3a3a3a")
    plt.close(fig)


def build_style(style, prefix, preview_path, meshes=True, corners=None):
    st = STYLES[style]
    card = build_shapes(style, corners)
    if meshes:
        base_mesh, feature_mesh = card_meshes(card)
        print(f"{style} base: {len(base_mesh.faces)} faces")
        print(f"{style} features: {len(feature_mesh.faces)} faces")
        base_mesh.export(f"{prefix}_base.stl")
        feature_mesh.export(f"{prefix}_top.stl")
        write_3mf(
            f"{prefix}.3mf",
            [(st["base_name"], 1, base_mesh), (st["feature_name"], 2, feature_mesh)],
        )
    preview(card, preview_path, style)
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
    ap.add_argument("--corners", choices=("round", "square"), default=None,
                    help="override the card corners for this run")
    args = ap.parse_args()

    if args.all:
        import os

        os.makedirs(args.preview_dir, exist_ok=True)
        for name in sorted(STYLES):
            build_style(name, f"visitenkarte_{name}",
                        os.path.join(args.preview_dir, f"{name}.png"), meshes=False,
                        corners=args.corners)
        print("done")
        return

    if args.style == DEFAULT_STYLE:
        # keep the historical filenames for the default card
        card = build_shapes(DEFAULT_STYLE, args.corners)
        base_mesh, white_mesh = card_meshes(card)
        print(f"base: {len(base_mesh.faces)} faces, watertight={base_mesh.is_watertight}")
        print(f"white: {len(white_mesh.faces)} faces, watertight={white_mesh.is_watertight}")
        base_mesh.export("visitenkarte_base_black.stl")
        white_mesh.export("visitenkarte_top_white.stl")
        write_3mf(
            "visitenkarte.3mf",
            [("Basis Schwarz", 1, base_mesh), ("Schrift Weiss", 2, white_mesh)],
        )
        preview(card, "visitenkarte_preview.png", DEFAULT_STYLE)
    else:
        build_style(args.style, f"visitenkarte_{args.style}",
                    f"visitenkarte_{args.style}_preview.png", corners=args.corners)
    print("done")


if __name__ == "__main__":
    main()
