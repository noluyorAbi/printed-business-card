"""The worker's HTTP surface: auth, limits, render, export, refusals."""

import json
import os
import sys

import pytest
from fastapi.testclient import TestClient

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "worker"))

os.environ.setdefault("WORKER_TOKEN", "test-token")

import build_card  # noqa: E402
from worker import app as worker_app  # noqa: E402
from worker.models import CardSpec, Qr, Row, Text, default_spec  # noqa: E402

AUTH = {"Authorization": f"Bearer {os.environ['WORKER_TOKEN']}"}


@pytest.fixture(scope="module")
def client():
    with TestClient(worker_app.app) as c:
        yield c


def body(spec: CardSpec) -> dict:
    return json.loads(spec.model_dump_json(exclude_none=True))


def test_health_needs_no_token(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["styles"] == len(build_card.STYLES)


def test_everything_else_needs_a_token(client):
    assert client.get("/styles").status_code == 401
    assert client.post("/render", json=body(default_spec())).status_code == 401
    assert client.post("/export",
                       json={"spec": body(default_spec())}).status_code == 401


def test_a_wrong_token_is_not_close_enough(client):
    r = client.get("/styles", headers={"Authorization": "Bearer test-tokeX"})
    assert r.status_code == 401


def test_styles_matches_the_catalog(client):
    r = client.get("/styles", headers=AUTH)
    assert r.status_code == 200
    assert r.json() == build_card.catalog()


def test_render_returns_four_layers_and_a_check(client):
    r = client.post("/render", json=body(default_spec()), headers=AUTH)
    assert r.status_code == 200, r.text
    out = r.json()
    assert [layer["id"] for layer in out["layers"]] == \
        ["engrave", "base", "feature", "high"]
    assert out["card"]["w"] == build_card.CARD_W
    assert out["check"]["ok"]
    assert out["check"]["issues"] == []
    assert len(out["hash"]) == 16
    assert out["style"]["id"] == "classic"
    assert out["ms"] >= 0


def test_the_same_spec_always_hashes_the_same(client):
    spec = default_spec("terminal")
    first = client.post("/render", json=body(spec), headers=AUTH).json()["hash"]
    second = client.post("/render", json=body(spec), headers=AUTH).json()["hash"]
    assert first == second

    other = default_spec("terminal")
    other.text.name = "Someone Else"
    third = client.post("/render", json=body(other), headers=AUTH).json()["hash"]
    assert third != first


def test_render_carries_free_text_through(client):
    spec = CardSpec(
        style="terminal",
        text=Text(name="Mira Halvorsen", tagline=["Distributed systems"],
                  rows=[Row(icon="mail", label="mira@halvorsen.dev"),
                        Row(icon="github", label="git.halvorsen.dev")]),
        qr=Qr(data="https://halvorsen.dev"),
    )
    out = client.post("/render", json=body(spec), headers=AUTH).json()
    assert out["check"]["ok"], out["check"]["issues"]
    assert out["layers"][2]["d"].startswith("M")


def test_unknown_style_is_refused(client):
    payload = body(default_spec())
    payload["style"] = "does-not-exist"
    r = client.post("/render", json=payload, headers=AUTH)
    assert r.status_code == 422


def test_unknown_field_is_refused(client):
    payload = body(default_spec())
    payload["surprise"] = True
    assert client.post("/render", json=payload, headers=AUTH).status_code == 422


def test_a_character_the_font_cannot_draw_is_refused(client):
    payload = body(default_spec())
    payload["text"]["name"] = "Alperen 中文"
    r = client.post("/render", json=payload, headers=AUTH)
    assert r.status_code == 422
    assert "Schrift" in r.text


def test_an_oversized_body_is_refused(client):
    """The size gate fires before anything parses the JSON."""
    payload = body(default_spec())
    payload["text"]["name"] = "x" * 20_000
    r = client.post("/render", json=payload, headers=AUTH)
    assert r.status_code == 413


def test_export_gives_a_3mf_a_slicer_can_open(client):
    r = client.post("/export", json={"spec": body(default_spec()), "format": "3mf"},
                    headers=AUTH)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "model/3mf"
    assert "attachment" in r.headers["content-disposition"]
    assert r.content[:2] == b"PK"                       # it is a zip

    import io
    import zipfile

    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        names = set(z.namelist())
    assert "3D/3dmodel.model" in names
    assert "Metadata/model_settings.config" in names


def test_export_gives_both_stl_parts(client):
    for fmt in ("stl-base", "stl-top"):
        r = client.post("/export", json={"spec": body(default_spec()), "format": fmt},
                        headers=AUTH)
        assert r.status_code == 200, fmt
        assert r.headers["content-type"] == "model/stl"
        assert len(r.content) > 1000


def test_export_gives_an_svg(client):
    r = client.post("/export", json={"spec": body(default_spec()), "format": "svg"},
                    headers=AUTH)
    assert r.status_code == 200
    assert r.content.startswith(b"<svg ")


def test_export_refuses_a_card_that_cannot_be_printed(client):
    spec = default_spec()
    spec.qr.data = "https://example.com/" + "x" * 90
    r = client.post("/export", json={"spec": body(spec), "format": "3mf"},
                    headers=AUTH)
    assert r.status_code == 422
    assert "qr_dense" in r.text


def test_a_warning_does_not_block_the_download(client):
    """Warn, do not silently repair, and do not block on a warning either."""
    spec = default_spec()
    spec.qr.data = "https://linkedin.com/in/mirahalvorsen"
    check = client.post("/render", json=body(spec), headers=AUTH).json()["check"]
    assert check["ok"]
    assert any(i["level"] == "warn" for i in check["issues"])

    r = client.post("/export", json={"spec": body(spec), "format": "3mf"},
                    headers=AUTH)
    assert r.status_code == 200


def test_parallel_renders_do_not_kill_the_service(client):
    """The endpoint has to survive what a browser test actually does to it."""
    from concurrent.futures import ThreadPoolExecutor

    def once(i):
        spec = default_spec("terminal")
        spec.text.name = f"Client {i}"
        return client.post("/render", json=body(spec), headers=AUTH).status_code

    with ThreadPoolExecutor(max_workers=6) as pool:
        codes = list(pool.map(once, range(6)))
    assert codes == [200] * 6
    assert client.get("/health").json()["ok"] is True


def test_overrides_reach_the_generator(client):
    spec = default_spec("circuit")
    with_decor = client.post("/render", json=body(spec), headers=AUTH).json()

    spec.overrides.decor_set = True
    spec.overrides.decor = None
    without = client.post("/render", json=body(spec), headers=AUTH).json()
    assert len(without["layers"][2]["d"]) < len(with_decor["layers"][2]["d"])

    spec.corners = "square"
    square = client.post("/render", json=body(spec), headers=AUTH).json()
    assert square["card"]["corners"] == "square"
