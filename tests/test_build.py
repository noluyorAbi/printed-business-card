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


def test_qr_scans(tmp_path):
    import cv2
    import matplotlib

    matplotlib.use("Agg")
    card = build_card.build_shapes()
    png = tmp_path / "preview.png"
    build_card.preview(card, str(png))
    data, _, _ = cv2.QRCodeDetector().detectAndDecode(cv2.imread(str(png)))
    assert data == build_card.QR_DATA
