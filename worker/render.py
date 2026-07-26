"""Adapter between the HTTP layer and `build_card`.

Everything expensive happens here, and everything here is pure: same spec in,
same bytes out. That is what lets the caller cache on a hash of the spec.
"""

import hashlib
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import build_card  # noqa: E402
from build_card import BASE_Z, TOP_Z  # noqa: E402

from models import CardSpec  # noqa: E402  isort: skip

MEDIA_TYPES = {
    "3mf": "model/3mf",
    "stl-base": "model/stl",
    "stl-top": "model/stl",
    "svg": "image/svg+xml",
}


def spec_hash(spec: CardSpec) -> str:
    """Stable id for a spec. Must match `specHash` in web/lib/spec.ts."""
    canonical = json.dumps(spec.model_dump(mode="json", exclude_none=True),
                           sort_keys=True, separators=(",", ":"),
                           ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


def _colors(spec: CardSpec, resolved: dict) -> dict:
    if spec.colors:
        return {"base": spec.colors.base, "feature": spec.colors.feature}
    return {"base": resolved["base_color"], "feature": resolved["feature_color"]}


def render(spec: CardSpec) -> dict:
    """Layer paths plus the print check. This is what the editor polls."""
    inner = spec.to_spec()
    resolved = inner.resolved()
    card = build_card.build_shapes(spec=inner)
    corners = spec.corners or resolved.get("corners", build_card.CORNERS)

    out = build_card.render_svg(card, _colors(spec, resolved), corners)
    out["hash"] = spec_hash(spec)
    out["style"] = {"id": spec.style, "label": resolved["label"],
                    "category": resolved.get("category", "pattern")}
    out["check"] = build_card.check_printability(card=card, spec=inner)
    return out


class CheckFailed(Exception):
    """The spec would produce a card that cannot be printed."""

    def __init__(self, issues):
        super().__init__("print check failed")
        self.issues = issues


def export(spec: CardSpec, fmt: str) -> tuple[bytes, str, str]:
    """Bytes, media type and file name for a download.

    The print check runs here rather than in the route, so the card is built
    once and the refusal can never disagree with the file that would have been
    handed out.
    """
    inner = spec.to_spec()
    resolved = inner.resolved()
    card = build_card.build_shapes(spec=inner)

    report = build_card.check_printability(card=card, spec=inner)
    if not report["ok"]:
        raise CheckFailed(report["issues"])

    digest = spec_hash(spec)
    name = build_card.export_basename(inner, digest)
    meta, custom = build_card.card_metadata(inner, card, digest)

    if fmt == "svg":
        doc = build_card.svg_document(card, _colors(spec, resolved),
                                      spec.corners, inner)
        return doc.encode(), MEDIA_TYPES[fmt], f"{name}.svg"

    base_mesh, feature_mesh = build_card.card_meshes(card)
    if fmt in ("stl-base", "stl-top"):
        top = fmt == "stl-top"
        mesh = feature_mesh if top else base_mesh
        filament = resolved["feature_name" if top else "base_name"]
        z0, z1 = (BASE_Z, BASE_Z + TOP_Z) if top else (0.0, BASE_Z)
        header = (f"{meta['Title']} | {'features' if top else 'base'} "
                  f"| {filament} | z {z0:g}-{z1:g} mm | {digest}")
        return (build_card.stl_bytes(mesh, header), MEDIA_TYPES[fmt],
                f"{name}-{'top' if top else 'base'}.stl")

    # 3MF: write_3mf takes a path, so hand it a scratch file and read it back
    with tempfile.NamedTemporaryFile(suffix=".3mf") as fh:
        build_card.write_3mf(
            fh.name,
            [(resolved["base_name"], 1, base_mesh),
             (resolved["feature_name"], 2, feature_mesh)],
            meta=meta, custom=custom,
            object_name=f"{spec.text.name} ({spec.style})",
        )
        data = Path(fh.name).read_bytes()
    return data, MEDIA_TYPES["3mf"], f"{name}.3mf"


def catalog() -> dict:
    return build_card.catalog()
