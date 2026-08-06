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


def test_every_code_layout_that_shows_a_name_follows_an_edit():
    """Editing the name has to change the card, in every layout that shows one.

    The code layouts are literal text with the stock name written into them,
    and each one writes it differently: the ANSI box shouts it in capitals,
    the assembly listing labels it `_alperen`, the man page heads a section
    with `ADATEPE(1)`. Substituting only the exact spelling left eleven of
    them frozen: you could retype your name and nothing moved.

    makefile, sql and tracker are the honest exceptions. They print a link and
    no name at all, so there is nothing for an edit to change.
    """
    nameless = {"makefile", "sql", "tracker"}
    for layout in sorted(build_card.CODE_BLOCKS):
        stock = build_card.build_content(layout, build_card.Spec())
        edited = build_card.build_content(
            layout, build_card.Spec(name="Mira Halvorsen"))
        moved = stock.symmetric_difference(edited).area > 1e-6
        assert moved is (layout not in nameless), layout


def test_a_frame_does_not_shift_when_the_name_changes():
    """The stock name happened to fit the art; somebody else's will not.

    A shorter name has to leave the frame exactly where it was. A longer one
    gives back whatever slack the line has and may still overrun, which
    `place_text` then scales to the column; what it may never do is lose
    characters off the end.
    """
    shorter = build_card._subst_table(build_card.Spec(name="Bo"))
    longer = build_card._subst_table(
        build_card.Spec(name="Bartholomew Fitzwilliam"))

    for layout in sorted(build_card.CODE_BLOCKS):
        for stock, _ in build_card.CODE_BLOCKS[layout]:
            if not stock or stock[-1] not in build_card._ART_EDGE:
                continue

            out = build_card._keep_width(stock, build_card._subst(stock, shorter))
            assert len(out) == len(stock), (layout, stock, out)

            out = build_card._keep_width(stock, build_card._subst(stock, longer))
            assert out.endswith(stock[-1]), (layout, stock, out)
            assert len(out) >= len(stock), (layout, stock, out)


def test_a_one_word_name_stays_where_the_long_one_started():
    stock = "║  ALPEREN ADATEPE  ║"
    out = build_card._keep_width(
        stock, build_card._subst(stock, build_card._subst_table(
            build_card.Spec(name="Bo"))))
    assert len(out) == len(stock)
    # the padding lands on the right, so the type does not drift into the wall
    assert out.startswith("║  BO")


def test_a_substituted_row_is_not_rewritten_a_second_time():
    """One pass, or a later rule chews on what an earlier one just wrote."""
    spec = build_card.Spec(
        name="Mira Halvorsen",
        rows=(("globe", "adatepe.dev"),),        # deliberately the stock value
    )
    table = build_card._subst_table(spec)
    assert build_card._subst("adatepe.dev", table) == "adatepe.dev"


def test_building_from_several_threads_does_not_take_the_process_down():
    """matplotlib's font machinery is not thread safe, and it fails hard.

    Without the lock in build_card this does not raise, it kills the
    interpreter with SIGTRAP, which is how the worker died the first time a
    parallel browser test hit it. A test that only checked results would have
    passed right up until production.
    """
    import threading

    errors = []

    def work(i):
        try:
            spec = build_card.Spec(style="terminal", name=f"Thread {i}")
            for _ in range(2):
                card = build_card.build_shapes(spec=spec)
                build_card.check_printability(card=card, spec=spec)
        except BaseException as caught:      # noqa: BLE001
            errors.append(repr(caught))

    threads = [threading.Thread(target=work, args=(i,)) for i in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=180)
        assert not thread.is_alive()
    assert errors == []


def test_a_download_name_says_whose_card_it_is():
    spec = build_card.Spec(style="terminal", name="Mira Halvorsen")
    stem = build_card.export_basename(spec, "4eba8ade12345678")
    assert stem == "mira-halvorsen-terminal-4eba8ade"

    square = build_card.spec_replace(spec, corners="square")
    assert "square" in build_card.export_basename(square, "4eba8ade12345678")

    # two cards that differ only in something the name cannot show still get
    # different files, which is the whole reason the hash is there
    a = build_card.export_basename(spec, "aaaaaaaa")
    b = build_card.export_basename(spec, "bbbbbbbb")
    assert a != b


def test_a_name_from_a_text_box_cannot_escape_the_filename():
    """The stem is built from user text, so it is a whitelist, not a filter."""
    nasty = [
        '../../etc/passwd',
        'a"; rm -rf /; echo "',
        "line\nbreak",
        "..",
        ".hidden",
        "C:\\Windows\\System32",
        "a\x00b",
        "Ω≈ç√∫",
    ]
    for value in nasty:
        stem = build_card.export_basename(
            build_card.Spec(name=value), "0123456789abcdef")
        assert set(stem) <= set("abcdefghijklmnopqrstuvwxyz0123456789-"), (value, stem)
        assert not stem.startswith((".", "-"))
        assert "/" not in stem and "\\" not in stem and ".." not in stem

    # a name with nothing usable in it still produces a file, not an empty one
    assert build_card.export_basename(
        build_card.Spec(name="中文"), "abc").startswith("card-")


def test_a_name_keeps_its_shape_through_the_slug():
    assert build_card.slugify("Jörg Müller-Straße") == "joerg-mueller-strasse"
    assert build_card.slugify("  spaced   out  ") == "spaced-out"
    assert build_card.slugify("x" * 80, limit=10) == "x" * 10


def test_the_3mf_carries_what_the_file_needs_to_say_for_itself():
    """A print file that arrives alone should still explain itself."""
    import zipfile
    from xml.etree import ElementTree

    spec = build_card.Spec(style="depth", name="Mira Halvorsen",
                           qr_data="https://halvorsen.dev")
    card = build_card.build_shapes(spec=spec)
    meta, custom = build_card.card_metadata(spec, card, "0c08d567")
    base_mesh, feature_mesh = build_card.card_meshes(card)

    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".3mf") as fh:
        build_card.write_3mf(fh.name,
                             [("Basis", 1, base_mesh), ("Schrift", 2, feature_mesh)],
                             meta=meta, custom=custom, object_name=meta["Title"])
        with zipfile.ZipFile(fh.name) as z:
            names = set(z.namelist())
            model = z.read("3D/3dmodel.model").decode()
            config = z.read("Metadata/model_settings.config").decode()

    assert {"3D/3dmodel.model", "Metadata/model_settings.config",
            "[Content_Types].xml", "_rels/.rels"} <= names

    ns = {"c": "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"}
    root = ElementTree.fromstring(model)
    found = {m.get("name"): (m.text or "") for m in root.findall("c:metadata", ns)}

    assert found["Designer"] == "Mira Halvorsen"
    assert "depth" in found["Title"]
    assert "0.2 mm nozzle" in found["Description"]
    assert "colour change" in found["Description"]
    assert found["cardstudio:QrTarget"] == "https://halvorsen.dev"
    assert found["cardstudio:SpecHash"] == "0c08d567"
    # depth engraves and embosses, so both depths are stated
    assert found["cardstudio:EngraveDepth"] == "0.3 mm"
    assert found["cardstudio:EmbossHeight"] == "0.3 mm"

    # the custom names sit behind a declared namespace, or a strict reader may
    # reject the whole file
    assert 'xmlns:cardstudio=' in model
    assert meta["Title"] in config


def test_metadata_survives_a_name_full_of_xml():
    from xml.etree import ElementTree

    spec = build_card.Spec(name='Mira <b>"&" Halvorsen</b>')
    meta, custom = build_card.card_metadata(spec)
    card = build_card.build_shapes(spec=spec)
    base_mesh, feature_mesh = build_card.card_meshes(card)

    import tempfile
    import zipfile

    with tempfile.NamedTemporaryFile(suffix=".3mf") as fh:
        build_card.write_3mf(fh.name,
                             [("Basis", 1, base_mesh), ("Schrift", 2, feature_mesh)],
                             meta=meta, custom=custom, object_name=meta["Title"])
        with zipfile.ZipFile(fh.name) as z:
            model = z.read("3D/3dmodel.model").decode()
            config = z.read("Metadata/model_settings.config").decode()

    ElementTree.fromstring(model)          # still well formed
    ElementTree.fromstring(config)
    root = ElementTree.fromstring(model)
    ns = {"c": "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"}
    found = {m.get("name"): (m.text or "") for m in root.findall("c:metadata", ns)}
    assert found["Designer"] == 'Mira <b>"&" Halvorsen</b>'


def test_the_3mf_names_the_colour_of_both_filaments():
    """A slot number says nothing about what is loaded in that slot.

    The card is drawn light on dark. Opened in a slicer that happens to hold
    two dark filaments it slices black on black, and the text disappears. So
    the file carries the two colours itself, twice: as 3MF core materials for
    any conformant reader, and as filament_colour for Bambu Studio and Orca,
    which read their slots from the project settings and nowhere else.
    """
    import json
    import tempfile
    import zipfile
    from xml.etree import ElementTree

    spec = build_card.Spec(style="classic")
    st = spec.resolved()
    card = build_card.build_shapes(spec=spec)
    base_mesh, feature_mesh = build_card.card_meshes(card)
    meta, custom = build_card.card_metadata(spec, card)

    with tempfile.NamedTemporaryFile(suffix=".3mf") as fh:
        build_card.write_3mf(fh.name,
                             [(st["base_name"], 1, base_mesh),
                              (st["feature_name"], 2, feature_mesh)],
                             meta=meta, custom=custom,
                             colors=[st["base_color"], st["feature_color"]])
        with zipfile.ZipFile(fh.name) as z:
            model = z.read("3D/3dmodel.model").decode()
            project = json.loads(z.read("Metadata/project_settings.config"))

    ns = {"c": "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"}
    root = ElementTree.fromstring(model)

    bases = root.findall("c:resources/c:basematerials/c:base", ns)
    assert [b.get("displaycolor") for b in bases] == ["#151515FF", "#ECECECFF"]
    assert [b.get("name") for b in bases] == [st["base_name"], st["feature_name"]]

    # both meshes point at a material, or there is nothing for a reader to paint
    meshes = [o for o in root.findall("c:resources/c:object", ns)
              if o.find("c:mesh", ns) is not None]
    assert [(o.get("pid"), o.get("pindex")) for o in meshes] == [("1", "0"), ("1", "1")]

    assert project["filament_colour"] == ["#151515", "#ECECEC"]
    # the printer and the print profile stay whatever the person opening the
    # file already had selected
    assert "printer_settings_id" not in project
    assert "print_settings_id" not in project


def test_the_stl_header_carries_a_description_and_stays_binary():
    card = build_card.build_shapes("classic")
    base_mesh, _ = build_card.card_meshes(card)

    plain = base_mesh.export(file_type="stl")
    tagged = build_card.stl_bytes(base_mesh, "Card Studio | base | z 0-0.6 mm")

    assert len(tagged) == len(plain)
    assert tagged[80:] == plain[80:]           # only the header differs
    assert tagged[:80].rstrip(b"\0").decode() == "Card Studio | base | z 0-0.6 mm"

    # a header starting with "solid" makes readers parse the binary as ascii
    sneaky = build_card.stl_bytes(base_mesh, "solid something")
    assert not sneaky[:5].lower().startswith(b"solid")

    # and it still loads
    import io

    import trimesh

    reloaded = trimesh.load(io.BytesIO(tagged), file_type="stl")
    assert len(reloaded.faces) == len(base_mesh.faces)
    assert reloaded.is_watertight


def test_the_svg_names_its_layers_and_says_what_it_is():
    spec = build_card.Spec(style="depth", name="Mira Halvorsen")
    card = build_card.build_shapes(spec=spec)
    doc = build_card.svg_document(card, spec=spec)

    assert "<title>Mira Halvorsen business card, depth</title>" in doc
    for layer in ("engrave", "base", "feature", "high"):
        assert f'<g id="{layer}"' in doc
    assert 'data-z0="0.6" data-z1="1"' in doc      # the feature layer's real z
    assert "https://github.com/noluyorAbi/printed-business-card" in doc


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
