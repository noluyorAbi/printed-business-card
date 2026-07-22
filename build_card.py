#!/usr/bin/env python3
"""Generate a 3D-printable business card (black base + white raised features).

Output: STL for each color part, a combined Bambu Studio 3MF, and a top-view
preview PNG. Card: 80 x 45 mm. Base 0.0-0.6 mm (black), features 0.6-1.0 mm
(white). The QR code is recessed through the white panel so the black base
shows, which keeps the whole print at a single filament change.
"""

from collections import namedtuple
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
HIGH_Z = 0.3          # extra height for embossed features (feels raised)
ENGRAVE_Z = 0.3       # groove depth cut into the top of the base
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
def qr_matrix():
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M,
                       border=0, box_size=1)
    qr.add_data(QR_DATA)
    qr.make(fit=True)
    return qr.get_matrix()


def qr_dark_modules(shape="square"):
    """Dark modules as one polygon.

    shape: "square" is the plain grid, "round" softens the corners and "dot"
    turns every module into a disc. Rounded and dotted modules stay above the
    contrast a decoder needs, which the test suite checks for every style.
    """
    m = qr_matrix()
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


def qr_finder_frame():
    """Corner brackets around the QR panel, like a viewfinder."""
    x0, y0, x1, y1 = PANEL
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
    if layout == "centered":
        for txt, em, y, fp in (("Alperen Adatepe", 5.4, 33.0, FONT_BOLD),
                               ("Creating powerful digital experiences", 2.8, 28.5, FONT),
                               ("through modern solutions.", 2.8, 25.0, FONT)):
            shape = text_shape(txt, em, fp)
            b = shape.bounds
            parts.append(shp_translate(shape, 25.0 - (b[0] + b[2]) / 2, y))
        for i, (_, label, _) in enumerate(ROWS):
            shape = text_shape(label, 2.9, FONT)
            b = shape.bounds
            parts.append(shp_translate(shape, 25.0 - (b[0] + b[2]) / 2, 18.0 - i * 4.0))
        return unary_union(parts).buffer(0)

    if layout == "monogram":
        parts.append(place_text("AA", 15.0, 4.0, 16.0, FONT_BOLD))
        parts.append(place_text("Alperen Adatepe", 3.4, 4.5, 10.0, FONT_BOLD))
        for i, (_, label, _) in enumerate(ROWS):
            parts.append(place_text(label, 2.6, 27.5, 16.0 + i * 3.6))
        return unary_union(parts).buffer(0)

    if layout == "vertical":
        from shapely.affinity import rotate

        name = rotate(text_shape("ALPEREN ADATEPE", 3.4, FONT_BOLD), 90, origin=(0, 0))
        b = name.bounds
        parts.append(shp_translate(name, 8.0 - b[0], 4.0 - b[1]))
        parts.append(place_text("Creating powerful digital", 2.8, 13.0, 33.0))
        parts.append(place_text("experiences through", 2.8, 13.0, 29.4))
        parts.append(place_text("modern solutions.", 2.8, 13.0, 25.8))
        for i, (icon_fn, label, _) in enumerate(ROWS):
            y = 19.0 - i * 4.4
            parts.append(icon_fn(15.0, y + 1.1))
            parts.append(place_text(label, 2.9, 18.4, y))
        return unary_union(parts).buffer(0)

    if layout == "outline":
        # letters as hollow rings: less filament, and a sharper tactile edge
        solid = [place_text("Alperen Adatepe", 5.0, 5.0, 34.5, FONT_BOLD)]
        rings = unary_union(solid).buffer(0)
        parts.append(rings.difference(rings.buffer(-0.45)))
        parts.append(place_text("Creating powerful digital experiences", 3.0, 5.5, 30.0))
        parts.append(place_text("through modern solutions.", 3.0, 5.5, 26.2))
        for icon_fn, label, y in ROWS:
            parts.append(icon_fn(7.3, y + 1.1))
            parts.append(place_text(label, 3.1, 10.6, y))
        return unary_union(parts).buffer(0)

    if layout == "ticker":
        # one long line per row, like a departure board
        parts.append(place_text("ALPEREN  ADATEPE", 5.2, 4.5, 35.0, FONT_BOLD))
        parts.append(place_text("DIGITAL  EXPERIENCES", 2.3, 4.5, 30.8))
        parts.append(place_text("MODERN  SOLUTIONS", 2.3, 4.5, 27.0))
        for i, (_, label, _) in enumerate(ROWS):
            parts.append(place_text(label.upper(), 2.3, 4.5, 22.0 - i * 4.4, FONT_BOLD))
        return unary_union(parts).buffer(0)

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


BOTTOM = (0.0, 1.5, CARD_W, 8.6)   # strip below the contact rows


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
    for r in np.arange(3.0, 60.0, 4.0):
        disc = Point(26.0, 22.5).buffer(r, 96)
        rings.append(disc.difference(disc.buffer(-0.55)))
    return _all(rings, base)


def decor_sunburst(base):
    """Rays fanning out of the top left corner."""
    rays = []
    for a in np.linspace(-1.45, 0.05, 22):
        tip = (2.0 + 130.0 * np.cos(a), 43.0 + 130.0 * np.sin(a))
        rays.append(Polygon([(2.0, 43.4), (2.0, 42.4), tip]))
    return _all(rays, base)


def decor_mountains(base):
    """Two layered ridge lines along the bottom."""
    rng = np.random.default_rng(19)
    shapes = []
    for k, (baseline, height) in enumerate(((2.0, 4.5), (2.0, 7.0))):
        pts = [(0.0, baseline)]
        x = 0.0
        while x < CARD_W:
            x += float(rng.uniform(4.0, 9.0))
            pts.append((x, baseline + float(rng.uniform(1.5, height))))
        pts += [(CARD_W + 2.0, baseline), (CARD_W + 2.0, baseline - 2.0), (0.0, baseline - 2.0)]
        poly = Polygon(pts)
        shapes.append(poly if k else poly.difference(poly.buffer(-0.6)))
    return _band(shapes, base, (0.0, 1.5, CARD_W, 9.5))


def decor_city(base):
    """Skyline blocks with lit windows."""
    rng = np.random.default_rng(31)
    blocks, x = [], 2.0
    while x < CARD_W - 2.0:
        w = float(rng.uniform(2.5, 5.0))
        h = float(rng.uniform(2.0, 6.0))
        tower = box(x, 1.8, x + w, 1.8 + h)
        windows = [box(wx, wy, wx + 0.6, wy + 0.6)
                   for wx in np.arange(x + 0.7, x + w - 0.6, 1.4)
                   for wy in np.arange(2.6, 1.8 + h - 0.7, 1.4)]
        blocks.append(tower.difference(unary_union(windows)) if windows else tower)
        x += w + 0.7
    return _band(blocks, base, (0.0, 1.5, CARD_W, 9.5))


def decor_waveform(base):
    """Audio bars along the bottom."""
    rng = np.random.default_rng(41)
    bars = []
    for x in np.arange(3.0, CARD_W - 2.0, 1.8):
        h = 0.8 + 3.0 * abs(float(rng.normal()))
        bars.append(box(x, 5.0 - h / 2, x + 1.0, 5.0 + h / 2))
    return _band(bars, base)


def decor_helix(base):
    """Double helix with rungs, running along the bottom."""
    from shapely.geometry import LineString

    xs = np.linspace(0, CARD_W, 200)
    a = LineString(list(zip(xs, 5.0 + 2.6 * np.sin(xs / 5.0))))
    b = LineString(list(zip(xs, 5.0 - 2.6 * np.sin(xs / 5.0))))
    shapes = [a.buffer(0.28, cap_style=2), b.buffer(0.28, cap_style=2)]
    for x in np.arange(1.0, CARD_W, 2.5):
        y = 2.6 * np.sin(x / 5.0)
        shapes.append(box(x - 0.2, 5.0 - y, x + 0.2, 5.0 + y))
    return _band(shapes, base)


def decor_spiral(base):
    """One archimedean coil in the bottom strip."""
    from shapely.geometry import LineString

    t = np.linspace(0.0, 7.0 * np.pi, 700)
    r = 0.26 * t
    pts = list(zip(12.0 + r * np.cos(t), 5.4 + r * np.sin(t)))
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

    a = rotate(box(-8.0, 36.5, 16.0, 41.5), -45, origin=(4.0, 39.0))
    b = rotate(box(CARD_W - 16.0, 36.5, CARD_W + 8.0, 41.5), 45, origin=(CARD_W - 4.0, 39.0))
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
            lines.append(rotate(box(x, -40, x + 0.4, 90), angle, origin=(40.0, 22.5)))
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
    for cx, cy, sx, sy in ((3.0, 42.0, 1, -1), (CARD_W - 3.0, 42.0, -1, -1),
                           (3.0, 3.0, 1, 1), (CARD_W - 3.0, 3.0, -1, 1)):
        marks.append(box(min(cx, cx + sx * arm), min(cy, cy + sy * w),
                         max(cx, cx + sx * arm), max(cy, cy + sy * w)))
        marks.append(box(min(cx, cx + sx * w), min(cy, cy + sy * arm),
                         max(cx, cx + sx * w), max(cy, cy + sy * arm)))
    return _all(marks, base)


def decor_ticket(base):
    """Perforation line and a row of punch holes."""
    holes = [Point(x, 5.6).buffer(0.55, 20) for x in np.arange(3.0, CARD_W, 3.0)]
    rule = box(2.0, 7.4, CARD_W - 2.0, 7.9)
    notches = [Point(x, 2.6).buffer(0.5, 20) for x in np.arange(3.0, CARD_W, 2.4)]
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
    for r in np.arange(2.0, 46.0, 3.2):
        sq = box(20.0 - r, 22.5 - r, 20.0 + r, 22.5 + r)
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
        bars.append(rotate(shp_translate(bar, 24.0, 22.5), a, origin=(24.0, 22.5)))
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
    vp = (40.0, 24.0)
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


def build_shapes(style=DEFAULT_STYLE):
    """Resolve a style into the four 2D layers of a Card."""
    st = STYLES[style] if isinstance(style, str) else style
    qr_mode = st["qr"]
    base = box(CORNER_R, CORNER_R, CARD_W - CORNER_R, CARD_H - CORNER_R).buffer(CORNER_R, 32)
    panel = box(*PANEL)

    frame = build_frame(base, st["frame"], "recess" if qr_mode in PANEL_MODES else "relief")
    content = build_content(st.get("layout", "default"))
    modules = qr_dark_modules(st.get("qr_shape", "square"))

    texture = Polygon()
    if st.get("decor"):
        texture = DECOR[st["decor"]](base)
        # keep the texture clear of the text and of the QR quiet zone
        texture = texture.difference(content.buffer(1.4)).difference(panel.buffer(1.2))
        if st.get("decor_keepout"):
            # dense patterns get a clean rectangle around the whole text block
            texture = texture.difference(content.envelope.buffer(1.6))
        texture = despeckle(texture)

    engraved = st.get("decor_mode") == "engrave"
    feature = [frame]
    if not engraved:
        feature.append(texture)

    if st.get("plate"):
        # full bleed slab with the text knocked out of it
        feature.append(base.buffer(-FRAME_OUT).difference(content.buffer(0.0)))
    else:
        if st.get("shadow"):
            # only the name casts the ghost; doubling the small type is mush
            name = content.intersection(box(0, 33.0, CARD_W, CARD_H))
            feature.append(shp_translate(name, 0.6, -0.6))
        feature.append(content)

    if qr_mode in PANEL_MODES:
        feature.append(panel)
    if qr_mode == "framed":
        feature.append(qr_finder_frame())

    feature = unary_union(feature).buffer(0)
    if qr_mode in PANEL_MODES:
        feature = feature.difference(modules).buffer(0)
    else:
        feature = unary_union([feature, modules]).buffer(0)
    feature = _clean(feature, base)

    # engrave layer: grooves cut into the top of the base
    engrave = []
    if engraved:
        engrave.append(texture)
    if qr_mode == "deep":
        engrave.append(modules.intersection(panel))
    if engrave:
        engrave = _clean(unary_union(engrave).buffer(0), base.buffer(-0.8))
        # the grooves are subtracted from the base, so the same crumb and point
        # contact cleanup applies here, otherwise the split base is not solid
        engrave = despeckle(engrave.difference(feature.buffer(0.25)).buffer(0), 0.4, 0.12)
        engrave = engrave.simplify(0.005).buffer(0.01).buffer(-0.01).buffer(0)
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
    fig, ax = plt.subplots(figsize=(10, 6.5))
    fig.patch.set_facecolor("#3a3a3a")
    patch(card.base, facecolor=st["base_color"], edgecolor="none")
    if not card.engrave.is_empty:
        # grooves read as a darker shade of the base filament
        patch(card.engrave, facecolor=_shade(st["base_color"], -0.55), edgecolor="none")
    patch(card.feature, facecolor=st["feature_color"], edgecolor="none")
    if not card.high.is_empty:
        # embossed geometry catches more light than the rest of the feature
        patch(shp_translate(card.high, 0.25, -0.25),
              facecolor=_shade(st["feature_color"], -0.35), edgecolor="none")
        patch(card.high, facecolor=_shade(st["feature_color"], 0.35), edgecolor="none")
    ax.set_xlim(-3, CARD_W + 3)
    ax.set_ylim(-3, CARD_H + 3)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.savefig(path, dpi=160, bbox_inches="tight", facecolor="#3a3a3a")
    plt.close(fig)


def build_style(style, prefix, preview_path, meshes=True):
    st = STYLES[style]
    card = build_shapes(style)
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
        card = build_shapes(DEFAULT_STYLE)
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
                    f"visitenkarte_{args.style}_preview.png")
    print("done")


if __name__ == "__main__":
    main()
