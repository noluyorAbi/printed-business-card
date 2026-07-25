"""Zod and Pydantic have to describe the same CardSpec.

Two schemas maintained by hand in two languages is the likeliest way for this
project to break, and the failure is silent: the editor sends something the
worker quietly rejects, or worse, accepts and misreads. So both sides export
JSON Schema and this test walks the two trees.

It compares the things that change behaviour: which fields exist, which are
required, their types, their enum members and their length limits. It does
not compare error messages, key order, or the wrapper each library puts
around a nullable field.
"""

import json
import os
import shutil
import subprocess

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "web")


def _zod_schema():
    if not os.path.isdir(os.path.join(WEB, "node_modules")):
        pytest.skip("web dependencies are not installed")
    if shutil.which("npx") is None:
        pytest.skip("npx is not on PATH")
    out = subprocess.run(
        ["npx", "--no-install", "tsx", "scripts/dump-schema.ts"],
        cwd=WEB, capture_output=True, text=True, timeout=180,
    )
    if out.returncode != 0:
        pytest.fail(f"dump-schema failed:\n{out.stderr[-2000:]}")
    return json.loads(out.stdout)


def _pydantic_schema():
    import sys

    sys.path.insert(0, os.path.join(ROOT, "worker"))
    from worker.models import CardSpec

    return CardSpec.model_json_schema()


def _unwrap(node, defs):
    """Follow a $ref, and look through the anyOf a nullable field becomes."""
    while isinstance(node, dict) and "$ref" in node:
        node = defs[node["$ref"].rsplit("/", 1)[-1]]
    if isinstance(node, dict) and "anyOf" in node:
        real = [b for b in node["anyOf"] if b.get("type") != "null"]
        if len(real) == 1:
            merged = dict(node)
            merged.pop("anyOf")
            merged.update(_unwrap(real[0], defs))
            return merged
    return node


def _facts(node, defs, path="", out=None):
    """Flatten a schema into {path: comparable facts}."""
    out = {} if out is None else out
    node = _unwrap(node, defs)
    if not isinstance(node, dict):
        return out

    fact = {}
    for key in ("type", "minLength", "maxLength", "maxItems", "minItems",
                "pattern", "const"):
        if key in node:
            fact[key] = node[key]
    if "enum" in node:
        fact["enum"] = sorted(map(str, node["enum"]))
    if path:
        out[path] = fact

    if "properties" in node:
        out[path + "/required"] = sorted(node.get("required", []))
        out[path + "/fields"] = sorted(node["properties"])
        for name, child in node["properties"].items():
            _facts(child, defs, f"{path}/{name}", out)
    if "items" in node:
        _facts(node["items"], defs, path + "[]", out)
    return out


@pytest.fixture(scope="module")
def trees():
    zod = _zod_schema()
    pyd = _pydantic_schema()
    return (_facts(zod, zod.get("$defs", zod.get("definitions", {}))),
            _facts(pyd, pyd.get("$defs", pyd.get("definitions", {}))))


def test_both_sides_know_the_same_fields(trees):
    zod, pyd = trees
    for path in sorted(set(zod) | set(pyd)):
        if not path.endswith("/fields"):
            continue
        assert zod.get(path) == pyd.get(path), path


def test_both_sides_require_the_same_fields(trees):
    zod, pyd = trees
    for path in sorted(set(zod) | set(pyd)):
        if not path.endswith("/required"):
            continue
        assert zod.get(path) == pyd.get(path), path


def test_both_sides_agree_on_limits_and_enums(trees):
    zod, pyd = trees
    interesting = ("maxLength", "minLength", "maxItems", "enum", "pattern")
    for path in sorted(set(zod) | set(pyd)):
        if path.endswith(("/fields", "/required")):
            continue
        a, b = zod.get(path, {}), pyd.get(path, {})
        for key in interesting:
            assert a.get(key) == b.get(key), (path, key, a.get(key), b.get(key))


def test_the_limits_come_from_one_place():
    """The numbers in the schemas are build_card's, not hand copied twice."""
    import re
    import sys

    sys.path.insert(0, ROOT)
    import build_card

    source = open(os.path.join(WEB, "lib", "spec.ts")).read()
    block = re.search(r"export const LIMITS = \{(.*?)\}", source, re.S).group(1)
    limits = dict(re.findall(r"(\w+):\s*(\d+)", block))
    assert {k: int(v) for k, v in limits.items()} == build_card.LIMITS
