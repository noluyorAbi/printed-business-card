"""The library surface the web app builds on: Spec, SVG, print check, catalog.

`tests/test_build.py` guards the printed card. This file guards the promise
that arbitrary text goes through the same machinery and comes out obeying the
same invariants.
"""

import json
import os
import sys

from shapely.geometry import box

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import build_card  # noqa: E402

# a spec that stresses every axis at once: a long name, four rows, an icon the
# stock card does not use, a QR payload longer than the default
LOADED = build_card.Spec(
    style="classic",
    name="Dr. Maximiliane Wolkenstein",
    tagline=("Systems and", "embedded work"),
    rows=(("mail", "max@wolkenstein.io"),
          ("github", "git.wolkenstein.io"),
          ("linkedin", "in/maxwolken"),
          ("globe", "wolkenstein.io")),
    qr_data="https://wolkenstein.io/c",
)


def test_default_spec_reproduces_the_shipped_card():
    """A Spec with no arguments has to be the card this repo has always built."""
    for style in ("classic", "terminal", "tree", "signet", "brutal", "manifesto"):
        plain = build_card.build_shapes(style)
        viaspec = build_card.build_shapes(spec=build_card.Spec(style=style))
        for layer in ("base", "engrave", "feature", "high"):
            a, b = getattr(plain, layer), getattr(viaspec, layer)
            assert a.symmetric_difference(b).area < 1e-6, (style, layer)


def test_free_text_obeys_the_same_invariants():
    """Someone else's name may not break the column, the panel or the card."""
    # one style per layout family, so every branch of build_content is exercised
    for style in ("classic", "poster", "terminal", "signet", "spine", "hollow",
                  "board", "brutal", "bauhaus", "devtag", "manifesto", "tree",
                  "json", "vim"):
        spec = build_card.spec_replace(LOADED, style=style)
        card = build_card.build_shapes(spec=spec)
        assert card.feature.within(card.base.buffer(0.01)), style
        assert card.engrave.intersection(card.feature).area < 0.01, style

        content = build_card.build_content(spec.resolved().get("layout", "default"),
                                           spec)
        panel = box(*build_card.panel_box(spec.resolved())).buffer(0.8)
        assert content.intersection(panel).area < 0.01, style
        x0, y0, _, y1 = content.bounds
        assert x0 >= 2.0, style
        assert y0 >= 2.0 and y1 <= build_card.CARD_H - 2.0, style


def test_four_rows_stay_clear_of_the_tagline():
    """The contact block grows upward, so a fourth row has to tighten, not collide."""
    spec = build_card.spec_replace(LOADED, style="classic")
    ys = build_card.row_ys(len(spec.rows), build_card._row_ceiling(spec))
    assert len(ys) == 4
    assert ys[0] > ys[-1]                      # first row sits highest
    assert ys[0] <= build_card._row_ceiling(spec) + 1e-9
    assert min(a - b for a, b in zip(ys, ys[1:])) >= build_card.EM_ROW * 0.95


def test_rows_without_an_icon_start_at_the_column_edge():
    spec = build_card.spec_replace(
        LOADED, rows=(("none", "wolkenstein.io"), ("none", "in/maxwolken")))
    content = build_card.build_content("default", spec)
    assert content.bounds[0] >= build_card.TEXT_X0 - 0.01


def test_meshes_stay_watertight_for_free_text():
    for style in ("classic", "signet", "terminal", "conway"):
        spec = build_card.spec_replace(LOADED, style=style)
        card = build_card.build_shapes(spec=spec)
        for mesh in build_card.card_meshes(card):
            for body in mesh.split(only_watertight=False):
                assert body.is_watertight, style


def test_render_svg_covers_the_same_geometry():
    """The SVG is the polygons the meshes get, not a second drawing of them."""
    card = build_card.build_shapes(spec=LOADED)
    out = build_card.render_svg(card)
    ids = [layer["id"] for layer in out["layers"]]
    assert ids == ["engrave", "base", "feature", "high"]

    z = {layer["id"]: (layer["z0"], layer["z1"]) for layer in out["layers"]}
    assert z["base"] == (0.0, build_card.BASE_Z)
    assert z["feature"] == (build_card.BASE_Z, build_card.BASE_Z + build_card.TOP_Z)
    assert z["engrave"][1] == build_card.BASE_Z          # cut into the base top

    geoms = {"engrave": card.engrave, "base": card.base,
             "feature": card.feature, "high": card.high}
    for layer in out["layers"]:
        geom = geoms[layer["id"]]
        if geom.is_empty:
            assert layer["d"] == ""
            continue
        # every ring of the polygon shows up as a subpath
        rings = sum(1 + len(p.interiors)
                    for p in (geom.geoms if geom.geom_type == "MultiPolygon"
                              else [geom]))
        assert layer["d"].count("Z") == rings, layer["id"]


def test_svg_document_carries_every_layer_the_card_has():
    """"depth" is the style that uses all four layers, so it is the honest case."""
    spec = build_card.spec_replace(LOADED, style="depth")
    card = build_card.build_shapes(spec=spec)
    doc = build_card.svg_document(card)

    assert doc.startswith("<svg ") and doc.endswith("</svg>")
    assert f'viewBox="0 0 {build_card.CARD_W} {build_card.CARD_H}"' in doc
    # y points up in the generator, so the document flips it once, at the top
    assert f'transform="translate(0,{build_card.CARD_H}) scale(1,-1)"' in doc
    assert doc.count("<path") == 4
    assert doc.count('fill-rule="evenodd"') == 4

    # a card without an engrave or a high layer must not emit empty paths
    plain = build_card.build_shapes(spec=build_card.spec_replace(LOADED,
                                                                 style="classic"))
    assert build_card.svg_document(plain).count("<path") == 2


def test_check_passes_every_style_with_its_own_text():
    """A check that flags the project's own cards teaches people to ignore it.

    All 163 styles were rendered and reviewed, and one of them was printed and
    inspected. Whatever the check reports, it may not report a problem with
    the cards this repo ships.
    """
    for style in sorted(build_card.STYLES):
        report = build_card.check_printability(spec=build_card.Spec(style=style))
        assert report["ok"], (style, report["issues"])
        assert report["issues"] == [], (style, report["issues"])


def test_check_measures_the_reference_card():
    report = build_card.check_printability()
    m = report["metrics"]
    assert m["min_stroke_mm"] >= build_card.STROKE_TARGET
    assert m["qr_module_mm"] >= build_card.MODULE_TARGET
    assert m["qr_quiet_modules"] >= 3
    assert m["text_within_column"]


def test_check_holds_a_style_to_its_own_baseline():
    """The bar is the style's stock text, not a number picked in the abstract.

    "signet" sets two initials 0.06 mm apart on purpose. A fixed threshold
    would call that broken; what actually matters is whether the user's own
    text made it worse.
    """
    stroke, gap = build_card._style_baseline("signet")
    assert gap < build_card.GAP_FLOOR            # a fixed floor would fail it
    assert build_card.check_printability(spec=build_card.Spec(style="signet"))["ok"]

    # a row long enough to be scaled into hairlines is a real defect, and the
    # baseline does not excuse it
    worse = build_card.Spec(style="signet",
                            rows=(("globe", "mmmmmmmmmmmmmmmmmmmm.example"),))
    report = build_card.check_printability(spec=worse)
    assert report["metrics"]["min_stroke_mm"] < stroke
    assert not report["ok"]
    assert {i["code"] for i in report["issues"]} == {"stroke_thin"}


def test_check_catches_a_qr_target_that_is_too_long():
    spec = build_card.Spec(qr_data="https://example.com/" + "x" * 140)
    report = build_card.check_printability(spec=spec)
    assert not report["ok"]
    codes = {i["code"] for i in report["issues"] if i["level"] == "error"}
    assert "qr_dense" in codes


def test_check_warns_before_it_errors():
    """A LinkedIn style URL still prints, so it warns rather than blocks."""
    spec = build_card.Spec(qr_data="https://linkedin.com/in/maxwolkenstein")
    report = build_card.check_printability(spec=spec)
    assert report["ok"]
    warned = {i["code"] for i in report["issues"] if i["level"] == "warn"}
    assert "qr_small" in warned


def test_check_flags_type_that_would_bleed_shut():
    spec = build_card.spec_replace(
        LOADED, rows=(("globe", "www.mmmmmmmmmmmmmmmm.example"),))
    report = build_card.check_printability(spec=spec)
    assert not report["ok"]
    assert any(i["code"] in ("gap_closed", "stroke_thin") for i in report["issues"])


def test_every_issue_names_a_field_and_says_what_to_do():
    spec = build_card.Spec(qr_data="https://example.com/" + "x" * 140)
    for issue in build_card.check_printability(spec=spec)["issues"]:
        assert issue["level"] in ("error", "warn", "info")
        assert issue["field"] and issue["message"] and issue["hint"]


def test_catalog_describes_every_style():
    cat = build_card.catalog()
    assert len(cat["styles"]) == len(build_card.STYLES)
    known = set(build_card.STYLES)
    for entry in cat["styles"]:
        assert entry["id"] in known
        assert entry["label"]
        assert entry["category"] in ("basic", "developer", "generative",
                                     "machine", "retro", "pattern")
        assert entry["colors"]["base"].startswith("#")
        assert entry["preview"] == f"/previews/{entry['id']}.png"
    assert {d["id"] for d in cat["decors"]} == set(build_card.DECOR)
    assert cat["limits"]["rows"] >= 1
    # it has to survive a round trip, the web app reads it as a file
    assert json.loads(json.dumps(cat, sort_keys=True))["card"]["w"] == build_card.CARD_W


def test_catalog_previews_exist_on_disk():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for entry in build_card.catalog()["styles"]:
        path = os.path.join(root, "assets", "previews", f"{entry['id']}.png")
        assert os.path.exists(path), entry["id"]


def test_overrides_change_the_card_they_claim_to():
    base = build_card.build_shapes(spec=build_card.Spec(style="classic"))
    nodecor = build_card.build_shapes(
        spec=build_card.Spec(style="circuit", decor=None))
    withdecor = build_card.build_shapes(spec=build_card.Spec(style="circuit"))
    assert nodecor.feature.area < withdecor.feature.area

    square = build_card.build_shapes(spec=build_card.Spec(style="classic",
                                                          corners="square"))
    assert square.base.area > base.base.area

    embossed = build_card.build_shapes(spec=build_card.Spec(style="classic",
                                                            emboss=True))
    assert base.high.is_empty and not embossed.high.is_empty
