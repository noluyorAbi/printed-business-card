/**
 * The CardSpec.
 *
 * This file and `worker/models.py` describe the same thing in two languages.
 * `tests/test_contract.py` exports the JSON Schema from both and compares
 * them, so the two cannot drift apart without the build noticing.
 */

import { z } from "zod";

export const LIMITS = {
  name: 28,
  label: 24,
  rows: 4,
  qr_data: 120,
  tagline_line: 30,
} as const;

export const ICONS = ["globe", "linkedin", "github", "mail", "none"] as const;
export const CORNERS = ["round", "square"] as const;
export const QR_MODES = ["recess", "deep", "framed", "relief"] as const;
export const QR_SHAPES = ["square", "round", "dot"] as const;
export const FRAMES = ["band", "double", "none"] as const;

/**
 * Latin-1 minus the control ranges. The card is drawn from real glyph
 * outlines, so a character the font cannot draw would vanish from the print
 * instead of failing loudly. Refusing it here is the honest option, and the
 * worker refuses the same set.
 */
const PRINTABLE = /^[\x20-\x7E\xA0-\xFF]*$/;
const printable = (field: string) =>
  z.string().refine((v) => PRINTABLE.test(v), {
    message: `${field} contains characters the card font cannot draw`,
  });

export const rowSchema = z.object({
  icon: z.enum(ICONS).default("globe"),
  label: printable("label").min(1).max(LIMITS.label),
});

export const textSchema = z.object({
  name: printable("name").min(1).max(LIMITS.name),
  tagline: z.array(printable("tagline").max(LIMITS.tagline_line)).max(2).default([]),
  rows: z.array(rowSchema).max(LIMITS.rows).default([]),
});

export const qrSchema = z.object({
  data: z.string().min(1).max(LIMITS.qr_data),
  mode: z.enum(QR_MODES).nullish(),
  shape: z.enum(QR_SHAPES).nullish(),
});

export const overridesSchema = z.object({
  decor: z.string().nullish(),
  /** Tells "leave the style alone" apart from "turn the decor off". */
  decor_set: z.boolean().default(false),
  frame: z.enum(FRAMES).nullish(),
  layout: z.string().nullish(),
  emboss: z.boolean().nullish(),
  engrave: z.boolean().nullish(),
});

export const colorsSchema = z.object({
  base: z.string().regex(/^#[0-9a-fA-F]{6}$/),
  feature: z.string().regex(/^#[0-9a-fA-F]{6}$/),
});

export const cardSpecSchema = z.object({
  v: z.literal(1).default(1),
  style: z.string().min(1),
  corners: z.enum(CORNERS).nullish(),
  text: textSchema,
  qr: qrSchema,
  overrides: overridesSchema.default({ decor_set: false }),
  colors: colorsSchema.nullish(),
});

export type CardSpec = z.infer<typeof cardSpecSchema>;
export type Row = z.infer<typeof rowSchema>;
export type Overrides = z.infer<typeof overridesSchema>;

/* ------------------------------------------------------------------ hashing */

/**
 * Drop nulls and undefined, sort keys. Two specs that mean the same thing
 * have to produce the same string, or the cache misses on every keystroke.
 */
function canonical(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(canonical);
  if (value && typeof value === "object") {
    const out: Record<string, unknown> = {};
    for (const key of Object.keys(value as object).sort()) {
      const v = (value as Record<string, unknown>)[key];
      if (v === null || v === undefined) continue;
      out[key] = canonical(v);
    }
    return out;
  }
  return value;
}

export function canonicalSpec(spec: CardSpec): string {
  return JSON.stringify(canonical(spec));
}

/** Same digest the worker computes, so both sides name a card identically. */
export async function specHash(spec: CardSpec): Promise<string> {
  const bytes = new TextEncoder().encode(canonicalSpec(spec));
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("")
    .slice(0, 16);
}

/* -------------------------------------------------------------- url state */

const toBase64Url = (s: string) =>
  btoa(String.fromCharCode(...new TextEncoder().encode(s)))
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");

const fromBase64Url = (s: string) => {
  const padded = s.replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(padded + "=".repeat((4 - (padded.length % 4)) % 4));
  return new TextDecoder().decode(Uint8Array.from(raw, (c) => c.charCodeAt(0)));
};

/** Encoded state, so a link carries a whole card and nothing is stored. */
export function encodeSpec(spec: CardSpec): string {
  return toBase64Url(canonicalSpec(spec));
}

export function decodeSpec(encoded: string): CardSpec | null {
  try {
    return cardSpecSchema.parse(JSON.parse(fromBase64Url(encoded)));
  } catch {
    return null;
  }
}

/* --------------------------------------------------------------- defaults */

export const DEFAULT_SPEC: CardSpec = {
  v: 1,
  style: "classic",
  text: {
    name: "Alperen Adatepe",
    tagline: ["Creating powerful", "digital experiences"],
    rows: [
      { icon: "globe", label: "adatepe.dev" },
      { icon: "linkedin", label: "in.adatepe.dev" },
      { icon: "github", label: "git.adatepe.dev" },
    ],
  },
  qr: { data: "https://www.adatepe.dev" },
  overrides: { decor_set: false },
};

export function specForStyle(style: string): CardSpec {
  return { ...DEFAULT_SPEC, style, overrides: { decor_set: false } };
}

/* ----------------------------------------------------------- render types */

export type Layer = {
  id: "engrave" | "base" | "feature" | "high";
  z0: number;
  z1: number;
  cut: boolean;
  d: string;
};

/**
 * A printable body, matching what `card_meshes` extrudes. The 3D view uses
 * these rather than `layers`, because an engraved groove is material removed
 * and stacking it as a block would show a ridge where the print has a notch.
 */
export type Solid = {
  id: string;
  filament: "base" | "feature";
  z0: number;
  z1: number;
  d: string;
};

export type Issue = {
  level: "error" | "warn" | "info";
  code: string;
  field: string;
  message: string;
  hint: string;
};

export type PrintCheck = {
  ok: boolean;
  metrics: {
    min_stroke_mm: number;
    min_gap_mm: number;
    qr_module_mm: number;
    qr_modules: number;
    qr_quiet_modules: number;
    qr_decoded: boolean | null;
    text_within_column: boolean;
  };
  issues: Issue[];
};

export type RenderResult = {
  hash: string;
  card: { w: number; h: number; corners: "round" | "square" };
  layers: Layer[];
  solids: Solid[];
  colors: { base: string; feature: string };
  style: { id: string; label: string; category: string };
  check: PrintCheck;
  ms: number;
};
