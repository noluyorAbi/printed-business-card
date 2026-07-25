import { describe, expect, it } from "vitest";

import {
  DEFAULT_SPEC,
  canonicalSpec,
  cardSpecSchema,
  decodeSpec,
  encodeSpec,
  specForStyle,
  specHash,
  type CardSpec,
} from "./spec";

describe("canonicalisation", () => {
  it("gives two equal specs the same string, whatever the key order", () => {
    const a: CardSpec = { ...DEFAULT_SPEC };
    const b: CardSpec = {
      overrides: { decor_set: false },
      qr: { data: DEFAULT_SPEC.qr.data },
      text: DEFAULT_SPEC.text,
      style: DEFAULT_SPEC.style,
      v: 1,
    };
    expect(canonicalSpec(a)).toBe(canonicalSpec(b));
  });

  it("drops nulls, so an untouched override does not miss the cache", () => {
    const withNulls = { ...DEFAULT_SPEC, corners: null, colors: null };
    expect(canonicalSpec(withNulls)).toBe(canonicalSpec(DEFAULT_SPEC));
  });

  it("still notices a real change", () => {
    const other = {
      ...DEFAULT_SPEC,
      text: { ...DEFAULT_SPEC.text, name: "Someone Else" },
    };
    expect(canonicalSpec(other)).not.toBe(canonicalSpec(DEFAULT_SPEC));
  });
});

describe("hashing", () => {
  it("is stable across calls", async () => {
    const first = await specHash(DEFAULT_SPEC);
    const second = await specHash({ ...DEFAULT_SPEC });
    expect(first).toBe(second);
    expect(first).toHaveLength(16);
  });

  it("changes when the card changes", async () => {
    const other = specForStyle("terminal");
    expect(await specHash(other)).not.toBe(await specHash(DEFAULT_SPEC));
  });
});

describe("url state", () => {
  it("survives a round trip", () => {
    const spec = specForStyle("tree");
    const back = decodeSpec(encodeSpec(spec));
    expect(back).not.toBeNull();
    expect(canonicalSpec(back!)).toBe(canonicalSpec(spec));
  });

  it("carries non ascii text", () => {
    const spec: CardSpec = {
      ...DEFAULT_SPEC,
      text: { ...DEFAULT_SPEC.text, name: "Jörg Müller-Straße" },
    };
    expect(decodeSpec(encodeSpec(spec))?.text.name).toBe("Jörg Müller-Straße");
  });

  it("returns null on rubbish instead of throwing", () => {
    expect(decodeSpec("not-base64!!")).toBeNull();
    expect(decodeSpec(btoa("{}"))).toBeNull();
  });

  it("produces a url safe string", () => {
    const encoded = encodeSpec(specForStyle("hexdump"));
    expect(encoded).toMatch(/^[A-Za-z0-9_-]+$/);
  });
});

describe("validation", () => {
  it("refuses a character the card font cannot draw", () => {
    const spec = {
      ...DEFAULT_SPEC,
      text: { ...DEFAULT_SPEC.text, name: "Alperen 中文" },
    };
    expect(cardSpecSchema.safeParse(spec).success).toBe(false);
  });

  it("accepts the latin range the font does cover", () => {
    const spec = {
      ...DEFAULT_SPEC,
      text: { ...DEFAULT_SPEC.text, name: "Jörg Müller" },
    };
    expect(cardSpecSchema.safeParse(spec).success).toBe(true);
  });

  it("caps the rows, the name and the qr payload", () => {
    const tooMany = {
      ...DEFAULT_SPEC,
      text: {
        ...DEFAULT_SPEC.text,
        rows: Array.from({ length: 5 }, () => ({
          icon: "globe" as const,
          label: "x",
        })),
      },
    };
    expect(cardSpecSchema.safeParse(tooMany).success).toBe(false);

    const longName = {
      ...DEFAULT_SPEC,
      text: { ...DEFAULT_SPEC.text, name: "x".repeat(29) },
    };
    expect(cardSpecSchema.safeParse(longName).success).toBe(false);

    const longQr = { ...DEFAULT_SPEC, qr: { data: "x".repeat(121) } };
    expect(cardSpecSchema.safeParse(longQr).success).toBe(false);
  });

  it("fills in the defaults a bare spec leaves out", () => {
    const parsed = cardSpecSchema.parse({
      style: "classic",
      text: { name: "Kim" },
      qr: { data: "https://example.com" },
    });
    expect(parsed.v).toBe(1);
    expect(parsed.text.tagline).toEqual([]);
    expect(parsed.text.rows).toEqual([]);
    expect(parsed.overrides.decor_set).toBe(false);
  });
});
