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
def build_shapes():
    base = box(CORNER_R, CORNER_R, CARD_W - CORNER_R, CARD_H - CORNER_R).buffer(CORNER_R, 32)

    frame = base.buffer(-FRAME_OUT).difference(base.buffer(-FRAME_IN))
    panel = box(*PANEL)

    white = [frame, panel]

    # Name
    white.append(place_text("Alperen Adatepe", 5.6, 5.5, 35.5))
    # Tagline
    white.append(place_text("Creating powerful digital experiences", 3.0, 5.5, 31.4))
    white.append(place_text("through modern solutions.", 3.0, 5.5, 27.5))
    # Contact rows: (icon builder, text, baseline y)
    rows = [
        (icon_globe, "www.adatepe.dev", 20.6),
        (icon_linkedin, "in.adatepe.dev", 15.4),
        (icon_github, "git.adatepe.dev", 10.2),
    ]
    for icon_fn, label, y in rows:
        white.append(icon_fn(7.3, y + 1.1))
        white.append(place_text(label, 3.1, 10.6, y))

    white_union = unary_union(white).buffer(0)
    white_union = white_union.difference(qr_dark_modules()).buffer(0)
    # keep everything on the card
    white_union = white_union.intersection(base)
    # drop collinear T-vertices left over from module-grid unions; 5 µm tolerance
    # is invisible but required for watertight extrusion
    white_union = white_union.simplify(0.005).buffer(0)
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


def preview(base, white, path):
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

    fig, ax = plt.subplots(figsize=(10, 6.5))
    fig.patch.set_facecolor("#3a3a3a")
    patch(base, facecolor="#151515", edgecolor="none")
    patch(white, facecolor="#ececec", edgecolor="none")
    ax.set_xlim(-3, CARD_W + 3)
    ax.set_ylim(-3, CARD_H + 3)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.savefig(path, dpi=200, bbox_inches="tight", facecolor="#3a3a3a")


def main():
    base2d, white2d = build_shapes()
    base_mesh = extrude(base2d, BASE_Z, 0.0)
    white_mesh = extrude(white2d, TOP_Z, BASE_Z)

    print(f"base: {len(base_mesh.faces)} faces, watertight={base_mesh.is_watertight}")
    print(f"white: {len(white_mesh.faces)} faces, watertight={white_mesh.is_watertight}")

    base_mesh.export("visitenkarte_base_black.stl")
    white_mesh.export("visitenkarte_top_white.stl")
    write_3mf(
        "visitenkarte.3mf",
        [
            ("Basis Schwarz", 1, base_mesh),
            ("Schrift Weiss", 2, white_mesh),
        ],
    )
    preview(base2d, white2d, "visitenkarte_preview.png")
    print("done")


if __name__ == "__main__":
    main()
