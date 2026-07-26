"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { CardTile } from "@/components/gallery/CardTile";
import {
  CATEGORY_LABELS,
  catalog,
  search,
  type Category,
} from "@/lib/catalog";

const CATEGORIES = Object.keys(CATEGORY_LABELS) as Category[];

export function Gallery() {
  const [term, setTerm] = useState("");
  const [category, setCategory] = useState<Category | "all">("all");
  const searchRef = useRef<HTMLInputElement>(null);
  const gridRef = useRef<HTMLDivElement>(null);

  const counts = useMemo(() => {
    const out = new Map<Category, number>();
    for (const s of catalog.styles) out.set(s.category, (out.get(s.category) ?? 0) + 1);
    return out;
  }, []);

  const shown = useMemo(() => {
    const pool =
      category === "all"
        ? catalog.styles
        : catalog.styles.filter((s) => s.category === category);
    return search(term, pool);
  }, [term, category]);

  /** `/` jumps to the search box, the way every tool with a list does it. */
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key !== "/" || event.metaKey || event.ctrlKey) return;
      const active = document.activeElement;
      if (active instanceof HTMLInputElement) return;
      event.preventDefault();
      searchRef.current?.focus();
    }
    addEventListener("keydown", onKey);
    return () => removeEventListener("keydown", onKey);
  }, []);

  /** Arrow keys walk the grid, using the real column count from layout. */
  const onGridKey = useCallback((event: React.KeyboardEvent) => {
    const keys = ["ArrowRight", "ArrowLeft", "ArrowDown", "ArrowUp"];
    if (!keys.includes(event.key)) return;
    const grid = gridRef.current;
    const tiles = grid ? Array.from(grid.querySelectorAll<HTMLElement>("[data-tile]")) : [];
    const index = tiles.indexOf(document.activeElement as HTMLElement);
    if (index < 0) return;

    // count how many tiles share the first row's top edge
    const top = tiles[0].offsetTop;
    const columns = Math.max(1, tiles.filter((t) => t.offsetTop === top).length);
    const step =
      event.key === "ArrowRight" ? 1
      : event.key === "ArrowLeft" ? -1
      : event.key === "ArrowDown" ? columns
      : -columns;

    const next = tiles[index + step];
    if (next) {
      event.preventDefault();
      next.focus();
    }
  }, []);

  return (
    <main className="mx-auto max-w-[1400px] px-4 pb-16 sm:px-6">
      <section className="py-8 sm:py-12">
        <h1
          className="display text-[30px] sm:text-[40px]"
          style={{ fontFamily: "var(--font-display-loaded), var(--font-display)" }}
        >
          Every card
        </h1>
        <p className="mt-3 max-w-[58ch]" style={{ color: "var(--muted)" }}>
          All {catalog.styles.length} of them, {catalog.card.w} by{" "}
          {catalog.card.h} mm, two filaments each. Hover a card to see its
          cross section.
        </p>
      </section>

      <div
        className="sticky top-[53px] z-20 -mx-4 mb-6 border-y rule px-4 py-3 backdrop-blur sm:-mx-6 sm:px-6"
        style={{ background: "color-mix(in srgb, var(--bg) 90%, transparent)" }}
      >
        <div className="flex flex-wrap items-center gap-2">
          <label className="relative">
            <span className="sr-only">Search the cards</span>
            <input
              ref={searchRef}
              type="text"
              value={term}
              onChange={(e) => setTerm(e.target.value)}
              placeholder="search"
              className="num w-[190px] rounded px-2.5 py-1.5 text-[13px]"
            />
            <kbd
              className="num pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 text-[10px]"
              style={{ color: "var(--muted)" }}
            >
              /
            </kbd>
          </label>

          <div className="flex flex-wrap gap-1">
            <Chip
              active={category === "all"}
              onClick={() => setCategory("all")}
              label="all"
              count={catalog.styles.length}
            />
            {CATEGORIES.map((c) => (
              <Chip
                key={c}
                active={category === c}
                onClick={() => setCategory(c)}
                label={CATEGORY_LABELS[c]}
                count={counts.get(c) ?? 0}
              />
            ))}
          </div>

          <span
            className="num ml-auto text-[12px]"
            style={{ color: "var(--muted)" }}
            aria-live="polite"
          >
            {shown.length} of {catalog.styles.length}
          </span>
        </div>
      </div>

      {shown.length === 0 ? (
        <div className="rounded-lg border rule py-20 text-center">
          <p className="num text-[14px]">No card matches {term}</p>
          <button
            type="button"
            onClick={() => {
              setTerm("");
              setCategory("all");
            }}
            className="mt-3 rounded px-3 py-1.5 text-[13px] underline underline-offset-4"
          >
            Clear the filters
          </button>
        </div>
      ) : (
        <div
          ref={gridRef}
          onKeyDown={onGridKey}
          className="grid grid-cols-1 gap-3 min-[420px]:grid-cols-2 md:grid-cols-3 xl:grid-cols-4"
        >
          {shown.map((style, i) => (
            <CardTile key={style.id} style={style} priority={i < 8} />
          ))}
        </div>
      )}
    </main>
  );
}

function Chip({
  active,
  onClick,
  label,
  count,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
  count: number;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className="rounded px-2.5 py-1.5 text-[13px] transition-colors"
      style={{
        background: active ? "var(--accent)" : "transparent",
        color: active ? "#fff" : "var(--fg)",
        border: `1px solid ${active ? "var(--accent)" : "var(--rule)"}`,
      }}
    >
      {label}
      <span className="num ml-1.5 text-[11px] opacity-70">{count}</span>
    </button>
  );
}
