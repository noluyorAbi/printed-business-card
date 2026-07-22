"""Smoke tests: geometry builds, extrudes watertight, and the QR still scans."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import build_card  # noqa: E402


def test_shapes_build():
    base, white = build_card.build_shapes()
    assert base.area > 3000  # roughly 80 x 45 minus rounded corners
    assert white.area > 100
    assert white.within(base.buffer(0.01))


def test_extrusions_watertight():
    base, white = build_card.build_shapes()
    base_mesh = build_card.extrude(base, build_card.BASE_Z, 0.0)
    white_mesh = build_card.extrude(white, build_card.TOP_Z, build_card.BASE_Z)
    assert base_mesh.is_watertight
    for body in white_mesh.split(only_watertight=False):
        assert body.is_watertight
    assert float(white_mesh.bounds[0][2]) == build_card.BASE_Z


def test_every_style_builds_and_scans(tmp_path):
    import cv2
    import matplotlib

    matplotlib.use("Agg")
    for style in sorted(build_card.STYLES):
        base, white = build_card.build_shapes(style)
        assert white.within(base.buffer(0.01)), style
        white_mesh = build_card.extrude(white, build_card.TOP_Z, build_card.BASE_Z)
        for body in white_mesh.split(only_watertight=False):
            assert body.is_watertight, style
        png = tmp_path / f"{style}.png"
        build_card.preview(base, white, str(png), style)
        data, _, _ = cv2.QRCodeDetector().detectAndDecode(cv2.imread(str(png)))
        assert data == build_card.QR_DATA, style


def test_qr_scans(tmp_path):
    import cv2
    import matplotlib

    matplotlib.use("Agg")
    base, white = build_card.build_shapes()
    png = tmp_path / "preview.png"
    build_card.preview(base, white, str(png))
    data, _, _ = cv2.QRCodeDetector().detectAndDecode(cv2.imread(str(png)))
    assert data == build_card.QR_DATA
