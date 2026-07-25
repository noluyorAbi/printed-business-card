"""The CardSpec, as the worker sees it.

This mirrors `web/lib/spec.ts`. Keeping two schemas in step by hand is the
likeliest way for this project to break, so `tests/test_contract.py` exports
the JSON Schema from both sides and compares them. Change one, change the
other, or the build fails.
"""

import sys
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import build_card  # noqa: E402

LIMITS = build_card.LIMITS
ICON_IDS = tuple(sorted(build_card.ICONS))
STYLE_IDS = frozenset(build_card.STYLES)
DECOR_IDS = frozenset(build_card.DECOR)
LAYOUT_IDS = frozenset(build_card.CODE_BLOCKS) | {
    st.get("layout", "default") for st in build_card.STYLES.values()}

HEX_COLOR = r"^#[0-9a-fA-F]{6}$"

# Latin-1 minus the control range. The card is drawn with real glyph outlines,
# so a character the font cannot draw would silently vanish from the print
# rather than fail loudly. Refusing it here is the honest option.
_PRINTABLE = set(range(0x20, 0x7F)) | set(range(0xA0, 0x100))


def _printable(value: str, field: str) -> str:
    bad = sorted({c for c in value if ord(c) not in _PRINTABLE})
    if bad:
        raise ValueError(
            f"{field} enthaelt Zeichen, die die Schrift nicht setzen kann: "
            + " ".join(bad))
    return value


class Row(BaseModel):
    model_config = ConfigDict(extra="forbid")

    icon: Literal["globe", "linkedin", "github", "mail", "none"] = "globe"
    label: str = Field(min_length=1, max_length=LIMITS["label"])

    @field_validator("label")
    @classmethod
    def _check(cls, v: str) -> str:
        return _printable(v.strip(), "label")


class Text(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=LIMITS["name"])
    tagline: list[str] = Field(default_factory=list, max_length=2)
    rows: list[Row] = Field(default_factory=list, max_length=LIMITS["rows"])

    @field_validator("name")
    @classmethod
    def _check_name(cls, v: str) -> str:
        return _printable(v.strip(), "name")

    @field_validator("tagline")
    @classmethod
    def _check_tagline(cls, v: list[str]) -> list[str]:
        out = [_printable(line.strip(), "tagline") for line in v]
        for line in out:
            if len(line) > LIMITS["tagline_line"]:
                raise ValueError(
                    f"tagline hoechstens {LIMITS['tagline_line']} Zeichen je Zeile")
        return out


class Qr(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: str = Field(min_length=1, max_length=LIMITS["qr_data"])
    mode: Literal["recess", "deep", "framed", "relief"] | None = None
    shape: Literal["square", "round", "dot"] | None = None


class Overrides(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decor: str | None = None
    decor_set: bool = False        # tells "no override" apart from "off"
    frame: Literal["band", "double", "none"] | None = None
    layout: str | None = None
    emboss: bool | None = None
    engrave: bool | None = None

    @field_validator("decor")
    @classmethod
    def _check_decor(cls, v):
        if v is not None and v not in DECOR_IDS:
            raise ValueError(f"unbekanntes Decor: {v}")
        return v

    @field_validator("layout")
    @classmethod
    def _check_layout(cls, v):
        if v is not None and v not in LAYOUT_IDS:
            raise ValueError(f"unbekanntes Layout: {v}")
        return v


class Colors(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base: str = Field(pattern=HEX_COLOR)
    feature: str = Field(pattern=HEX_COLOR)


class CardSpec(BaseModel):
    """What the editor sends. Everything but `style` and `text` is optional."""

    model_config = ConfigDict(extra="forbid")

    v: Literal[1] = 1
    style: str
    corners: Literal["round", "square"] | None = None
    text: Text
    qr: Qr
    overrides: Overrides = Field(default_factory=Overrides)
    colors: Colors | None = None

    @field_validator("style")
    @classmethod
    def _check_style(cls, v: str) -> str:
        if v not in STYLE_IDS:
            raise ValueError(f"unbekannter Style: {v}")
        return v

    def to_spec(self) -> build_card.Spec:
        """The generator's own Spec. This is the only place the two meet."""
        o = self.overrides
        return build_card.Spec(
            style=self.style,
            corners=self.corners,
            name=self.text.name,
            tagline=tuple(self.text.tagline),
            rows=tuple((r.icon, r.label) for r in self.text.rows),
            qr_data=self.qr.data,
            qr_mode=self.qr.mode,
            qr_shape=self.qr.shape,
            decor=o.decor if o.decor_set else build_card._KEEP,
            frame=o.frame,
            layout=o.layout,
            emboss=o.emboss,
            engrave=o.engrave,
            base_color=self.colors.base if self.colors else None,
            feature_color=self.colors.feature if self.colors else None,
        )


class ExportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    spec: CardSpec
    format: Literal["3mf", "stl-base", "stl-top", "svg"] = "3mf"


def default_spec(style: str = "classic") -> CardSpec:
    """The stock card as a CardSpec, which is what a preset resolves to."""
    return CardSpec(
        style=style,
        text=Text(name=build_card.NAME,
                  tagline=list(build_card.TAGLINE),
                  rows=[Row(icon=i, label=label)
                        for i, label in build_card.DEFAULT_ROWS]),
        qr=Qr(data=build_card.QR_DATA),
    )
