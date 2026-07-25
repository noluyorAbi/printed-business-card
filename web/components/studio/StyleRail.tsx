"use client";

import { catalog, CATEGORY_LABELS, type Category } from "@/lib/catalog";
import { CORNERS, type CardSpec } from "@/lib/spec";

/** Preset first, then the individual knobs that override it. */
export function StyleRail({
  spec,
  onChange,
}: {
  spec: CardSpec;
  onChange: (next: CardSpec) => void;
}) {
  const entry = catalog.styles.find((s) => s.id === spec.style);
  const patch = (part: Partial<CardSpec>) => onChange({ ...spec, ...part });
  const over = (part: Partial<CardSpec["overrides"]>) =>
    patch({ overrides: { ...spec.overrides, ...part } });

  const touched =
    spec.overrides.decor_set ||
    spec.overrides.frame != null ||
    spec.overrides.layout != null ||
    spec.overrides.emboss != null ||
    spec.overrides.engrave != null ||
    spec.corners != null ||
    spec.colors != null;

  const grouped = groupByCategory();

  return (
    <div className="space-y-4">
      <label className="block">
        <span className="num mb-1 block text-[11px] uppercase tracking-wider"
              style={{ color: "var(--muted)" }}>
          Vorlage
        </span>
        <select
          value={spec.style}
          onChange={(e) => patch({ style: e.target.value })}
          className="num w-full rounded px-2 py-1.5 text-[13px]"
        >
          {grouped.map(([category, styles]) => (
            <optgroup key={category} label={CATEGORY_LABELS[category]}>
              {styles.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.id}
                </option>
              ))}
            </optgroup>
          ))}
        </select>
        {entry && (
          <span className="mt-1 block text-[11px]" style={{ color: "var(--muted)" }}>
            {entry.label}
          </span>
        )}
      </label>

      <Select
        label="Textur"
        value={spec.overrides.decor_set ? (spec.overrides.decor ?? "") : "__keep"}
        onChange={(v) =>
          v === "__keep"
            ? over({ decor_set: false, decor: null })
            : over({ decor_set: true, decor: v || null })
        }
        options={[
          { value: "__keep", label: `wie ${spec.style}` },
          { value: "", label: "keine" },
          ...catalog.decors.map((d) => ({ value: d.id, label: d.id })),
        ]}
      />

      <Select
        label="Layout"
        value={spec.overrides.layout ?? "__keep"}
        onChange={(v) => over({ layout: v === "__keep" ? null : v })}
        options={[
          { value: "__keep", label: `wie ${spec.style}` },
          ...catalog.layouts.map((l) => ({
            value: l.id,
            label: l.mono ? `${l.id} (mono)` : l.id,
          })),
        ]}
      />

      <Select
        label="Rahmen"
        value={spec.overrides.frame ?? "__keep"}
        onChange={(v) =>
          over({ frame: v === "__keep" ? null : (v as "band" | "double" | "none") })
        }
        options={[
          { value: "__keep", label: `wie ${spec.style}` },
          { value: "band", label: "Band" },
          { value: "double", label: "Doppellinie" },
          { value: "none", label: "keiner" },
        ]}
      />

      <fieldset className="min-w-0">
        <span className="num mb-1 block text-[11px] uppercase tracking-wider"
              style={{ color: "var(--muted)" }}>
          Ecken
        </span>
        <div className="flex gap-1">
          {[{ value: null, label: `wie ${spec.style}` },
            ...CORNERS.map((c) => ({ value: c, label: c === "round" ? "rund" : "eckig" }))]
            .map((option) => (
              <button
                key={String(option.value)}
                type="button"
                aria-pressed={spec.corners === option.value}
                onClick={() => patch({ corners: option.value as CardSpec["corners"] })}
                className="num flex-1 rounded border px-2 py-1.5 text-[12px]"
                style={{
                  borderColor:
                    spec.corners === option.value ? "var(--accent)" : "var(--rule)",
                  color: spec.corners === option.value ? "var(--accent)" : "inherit",
                }}
              >
                {option.label}
              </button>
            ))}
        </div>
      </fieldset>

      <div className="space-y-1.5">
        <Toggle
          label="Erhabene Schrift"
          hint={`${catalog.card.high_z} mm ueber den Features, mit dem Daumen spuerbar`}
          value={spec.overrides.emboss}
          onChange={(v) => over({ emboss: v })}
        />
        <Toggle
          label="Gravur"
          hint={`${catalog.card.engrave_z} mm tief in die Basis, keine zweite Farbe`}
          value={spec.overrides.engrave}
          onChange={(v) => over({ engrave: v })}
        />
      </div>

      {touched && (
        <button
          type="button"
          onClick={() =>
            onChange({
              ...spec,
              corners: null,
              colors: null,
              overrides: { decor_set: false },
            })
          }
          className="num w-full rounded border rule py-1.5 text-[12px] hover:border-[var(--accent)]"
        >
          Auf {spec.style} zuruecksetzen
        </button>
      )}
    </div>
  );
}

function groupByCategory(): [Category, typeof catalog.styles][] {
  const map = new Map<Category, typeof catalog.styles>();
  for (const style of catalog.styles) {
    const list = map.get(style.category) ?? [];
    list.push(style);
    map.set(style.category, list);
  }
  return (Object.keys(CATEGORY_LABELS) as Category[])
    .filter((c) => map.has(c))
    .map((c) => [c, map.get(c)!]);
}

function Select({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
}) {
  return (
    <label className="block">
      <span className="num mb-1 block text-[11px] uppercase tracking-wider"
            style={{ color: "var(--muted)" }}>
        {label}
      </span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="num w-full rounded px-2 py-1.5 text-[13px]"
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  );
}

/**
 * Three states, not two: leave it to the style, force it on, force it off.
 * A plain checkbox would quietly turn every style's emboss off the moment the
 * editor loaded.
 */
function Toggle({
  label,
  hint,
  value,
  onChange,
}: {
  label: string;
  hint: string;
  value: boolean | null | undefined;
  onChange: (v: boolean | null) => void;
}) {
  const states: { value: boolean | null; label: string }[] = [
    { value: null, label: "auto" },
    { value: true, label: "an" },
    { value: false, label: "aus" },
  ];
  return (
    <div className="flex items-center gap-2">
      <div className="min-w-0 flex-1">
        <div className="text-[12px]">{label}</div>
        <div className="text-[10px]" style={{ color: "var(--muted)" }}>
          {hint}
        </div>
      </div>
      <div className="flex shrink-0 gap-0.5">
        {states.map((state) => (
          <button
            key={String(state.value)}
            type="button"
            aria-pressed={value === state.value || (value == null && state.value === null)}
            onClick={() => onChange(state.value)}
            className="num rounded border px-1.5 py-1 text-[11px]"
            style={{
              borderColor:
                value === state.value || (value == null && state.value === null)
                  ? "var(--accent)"
                  : "var(--rule)",
            }}
          >
            {state.label}
          </button>
        ))}
      </div>
    </div>
  );
}
