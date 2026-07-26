import raw from "@/data/catalog.json";

export type StyleEntry = {
  id: string;
  label: string;
  category: Category;
  decor: string | null;
  frame: string;
  layout: string;
  qr: string;
  qr_shape: string;
  emboss: string | null;
  engrave: boolean;
  colors: { base: string; feature: string };
  filaments: { base: string; feature: string };
  preview: string;
};

export type Catalog = {
  card: {
    w: number;
    h: number;
    corner_r: number;
    base_z: number;
    top_z: number;
    high_z: number;
    engrave_z: number;
  };
  limits: Record<string, number>;
  icons: string[];
  styles: StyleEntry[];
  decors: { id: string; bottom: boolean }[];
  layouts: { id: string; mono: boolean }[];
  qr_modes: string[];
  qr_shapes: string[];
  frames: string[];
};

export type Category =
  | "basic"
  | "developer"
  | "generative"
  | "machine"
  | "retro"
  | "pattern";

export const catalog = raw as unknown as Catalog;

export const CATEGORY_LABELS: Record<Category, string> = {
  basic: "Plain",
  developer: "Developer",
  generative: "Generative",
  machine: "Machine readable",
  retro: "Retro",
  pattern: "Pattern",
};

export const byId = new Map(catalog.styles.map((s) => [s.id, s]));

export function styleOr404(id: string): StyleEntry {
  const entry = byId.get(id);
  if (!entry) throw new Error(`unknown style: ${id}`);
  return entry;
}

/**
 * The line under each tile. It reads like a parts list because that is what
 * it is: which texture, which frame, which depth trick, at what module size.
 */
export function partsLine(s: StyleEntry): string[] {
  const parts = [s.layout === "default" ? "standard" : s.layout];
  if (s.decor) parts.push(s.decor);
  if (s.frame !== "none") parts.push(s.frame === "double" ? "double frame" : "frame");
  if (s.engrave) parts.push("engraved");
  if (s.emboss) parts.push("embossed");
  if (s.qr !== "recess") parts.push(`qr ${s.qr}`);
  return parts;
}

/** Fuzzy enough to be useful, cheap enough to run on every keystroke. */
export function search(term: string, styles: StyleEntry[]): StyleEntry[] {
  const q = term.trim().toLowerCase();
  if (!q) return styles;
  const words = q.split(/\s+/);
  return styles.filter((s) => {
    const hay = [
      s.id,
      s.label,
      s.category,
      s.decor ?? "",
      s.layout,
      s.frame,
      s.emboss ?? "",
    ]
      .join(" ")
      .toLowerCase();
    return words.every((w) => hay.includes(w));
  });
}
