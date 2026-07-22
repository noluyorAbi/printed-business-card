"""Smoke tests: geometry builds, extrudes watertight, and the QR still scans."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import build_card  # noqa: E402


def test_shapes_build():
    card = build_card.build_shapes()
    assert card.base.area > 3000  # roughly 80 x 45 minus rounded corners
    assert card.feature.area > 100
    assert card.feature.within(card.base.buffer(0.01))


def test_extrusions_watertight():
    card = build_card.build_shapes()
    base_mesh, feature_mesh = build_card.card_meshes(card)
    assert base_mesh.is_watertight
    for body in feature_mesh.split(only_watertight=False):
        assert body.is_watertight
    assert float(feature_mesh.bounds[0][2]) == build_card.BASE_Z


def test_every_style_builds_and_scans(tmp_path):
    import cv2
    import matplotlib

    matplotlib.use("Agg")
    for style in sorted(build_card.STYLES):
        card = build_card.build_shapes(style)
        assert card.feature.within(card.base.buffer(0.01)), style
        base_mesh, feature_mesh = build_card.card_meshes(card)
        for mesh in (base_mesh, feature_mesh):
            for body in mesh.split(only_watertight=False):
                assert body.is_watertight, style
        # the engrave layer never eats through the base, and never collides
        # with the feature layer sitting on top of it
        assert card.engrave.intersection(card.feature).area < 0.01, style
        png = tmp_path / f"{style}.png"
        build_card.preview(card, str(png), style)
        data, _, _ = cv2.QRCodeDetector().detectAndDecode(cv2.imread(str(png)))
        assert data == build_card.QR_DATA, style


def test_text_stays_inside_the_column():
    """Type may never creep under the QR panel, at any card or type size."""
    from shapely.geometry import box

    panel = box(*build_card.PANEL).buffer(1.0)
    layouts = {st.get("layout", "default") for st in build_card.STYLES.values()}
    for layout in sorted(layouts):
        content = build_card.build_content(layout)
        assert content.intersection(panel).area < 0.01, layout
        x0, y0, x1, y1 = content.bounds
        assert x0 >= 2.0, layout
        assert y0 >= 2.0 and y1 <= build_card.CARD_H - 2.0, layout


def test_printable_feature_sizes():
    """Type and QR modules stay above what a 0.2 mm nozzle holds.

    A stroke or a gap under about 0.45 mm bleeds shut on the print, which is
    what made the first printed card's small text run together.
    """
    module = build_card.QR_SIZE / build_card.QR_MODULES
    assert module >= 0.80, module
    assert build_card.QR_QUIET >= 3 * module - 1e-9  # quiet zone in modules

    def stroke_and_gap(geom):
        lo, hi = 0.0, 1.0
        for _ in range(24):
            mid = (lo + hi) / 2
            if geom.buffer(-mid).is_empty:
                hi = mid
            else:
                lo = mid
        parts = list(geom.geoms) if geom.geom_type == "MultiPolygon" else [geom]
        gap = min((a.distance(b) for i, a in enumerate(parts) for b in parts[i + 1:]),
                  default=9.0)
        return 2 * lo, gap

    cases = [
        ("Alperen Adatepe", build_card.EM_NAME, build_card.FONT_BOLD, build_card.TRACK_NAME),
        ("digital experiences", build_card.EM_TAG, build_card.FONT, build_card.TRACK_TAG),
        ("git.adatepe.dev", build_card.EM_ROW, build_card.FONT, build_card.TRACK_ROW),
        ("in.adatepe.dev", build_card.EM_ROW, build_card.FONT, build_card.TRACK_ROW),
    ]
    for text, em, font, track in cases:
        stroke, gap = stroke_and_gap(build_card.text_shape(text, em, font, track))
        assert stroke >= 0.45, (text, stroke)
        assert gap >= 0.38, (text, gap)


def test_card_fits_a_wallet():
    """ID-1 (bank card) is 85.60 x 53.98 mm; stay inside it with clearance."""
    assert build_card.CARD_W <= 85.6 - 1.0
    assert build_card.CARD_H <= 53.98 - 1.0


def test_qr_scans(tmp_path):
    import cv2
    import matplotlib

    matplotlib.use("Agg")
    card = build_card.build_shapes()
    png = tmp_path / "preview.png"
    build_card.preview(card, str(png))
    data, _, _ = cv2.QRCodeDetector().detectAndDecode(cv2.imread(str(png)))
    assert data == build_card.QR_DATA
