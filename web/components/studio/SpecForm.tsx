"use client";

import { catalog } from "@/lib/catalog";
import { ICONS, LIMITS, type CardSpec, type Issue, type Row } from "@/lib/spec";

const ICON_LABELS: Record<(typeof ICONS)[number], string> = {
  globe: "Web",
  linkedin: "LinkedIn",
  github: "GitHub",
  mail: "Mail",
  none: "kein Icon",
};

/** Every input that changes what the card says. */
export function SpecForm({
  spec,
  onChange,
  issues,
}: {
  spec: CardSpec;
  onChange: (next: CardSpec) => void;
  issues: Issue[];
}) {
  const patch = (part: Partial<CardSpec>) => onChange({ ...spec, ...part });
  const patchText = (part: Partial<CardSpec["text"]>) =>
    patch({ text: { ...spec.text, ...part } });

  const issueFor = (field: string) => issues.find((i) => i.field === field);

  function setRow(index: number, part: Partial<Row>) {
    const rows = spec.text.rows.map((r, i) => (i === index ? { ...r, ...part } : r));
    patchText({ rows });
  }

  return (
    <div className="space-y-5">
      <Field
        label="Name"
        value={spec.text.name}
        max={LIMITS.name}
        issue={issueFor("text.name")}
        onChange={(name) => patchText({ name })}
      />

      <fieldset className="min-w-0">
        <Legend>Untertitel</Legend>
        <div className="space-y-2">
          {[0, 1].map((i) => (
            <Field
              key={i}
              label={`Zeile ${i + 1}`}
              hideLabel
              value={spec.text.tagline[i] ?? ""}
              max={LIMITS.tagline_line}
              issue={issueFor(`text.tagline.${i}`)}
              placeholder={i === 0 ? "erste Zeile" : "zweite Zeile"}
              onChange={(line) => {
                const next = [spec.text.tagline[0] ?? "", spec.text.tagline[1] ?? ""];
                next[i] = line;
                // a trailing empty line is not a line, so it goes away
                while (next.length && !next[next.length - 1]) next.pop();
                patchText({ tagline: next });
              }}
            />
          ))}
        </div>
      </fieldset>

      <fieldset className="min-w-0">
        <Legend>
          Kontakt
          <span className="num ml-2 text-[10px]" style={{ color: "var(--muted)" }}>
            {spec.text.rows.length} / {LIMITS.rows}
          </span>
        </Legend>

        <div className="space-y-2">
          {spec.text.rows.map((row, i) => {
            const issue = issueFor(`text.rows.${i}`);
            return (
              <div key={i} className="flex gap-1.5">
                <select
                  aria-label={`Icon der Zeile ${i + 1}`}
                  value={row.icon}
                  onChange={(e) => setRow(i, { icon: e.target.value as Row["icon"] })}
                  className="num w-[96px] shrink-0 rounded px-1 py-1.5 text-[12px]"
                >
                  {ICONS.map((icon) => (
                    <option key={icon} value={icon}>
                      {ICON_LABELS[icon]}
                    </option>
                  ))}
                </select>
                <input
                  type="text"
                  aria-label={`Text der Zeile ${i + 1}`}
                  value={row.label}
                  maxLength={LIMITS.label}
                  onChange={(e) => setRow(i, { label: e.target.value })}
                  className="num min-w-0 flex-1 rounded px-2 py-1.5 text-[13px]"
                  style={issue ? { borderColor: "var(--flag)" } : undefined}
                />
                <button
                  type="button"
                  aria-label={`Zeile ${i + 1} entfernen`}
                  onClick={() =>
                    patchText({ rows: spec.text.rows.filter((_, x) => x !== i) })
                  }
                  className="num shrink-0 rounded border rule px-2 text-[13px] hover:border-[var(--flag)]"
                >
                  &minus;
                </button>
              </div>
            );
          })}
        </div>

        {spec.text.rows.length < LIMITS.rows && (
          <button
            type="button"
            onClick={() =>
              patchText({
                rows: [...spec.text.rows, { icon: "globe", label: "" }],
              })
            }
            className="mt-2 w-full rounded border border-dashed rule py-1.5 text-[12px] hover:border-[var(--accent)]"
          >
            Zeile hinzufuegen
          </button>
        )}
      </fieldset>

      <Field
        label="QR-Ziel"
        value={spec.qr.data}
        max={LIMITS.qr_data}
        issue={issueFor("qr.data")}
        mono
        onChange={(data) => patch({ qr: { ...spec.qr, data } })}
      />

      <fieldset className="min-w-0">
        <Legend>Farben</Legend>
        <div className="flex gap-2">
          <Swatch
            label="Basis"
            value={spec.colors?.base ?? currentColors(spec).base}
            onChange={(base) =>
              patch({
                colors: { base, feature: spec.colors?.feature ?? currentColors(spec).feature },
              })
            }
          />
          <Swatch
            label="Features"
            value={spec.colors?.feature ?? currentColors(spec).feature}
            onChange={(feature) =>
              patch({
                colors: { base: spec.colors?.base ?? currentColors(spec).base, feature },
              })
            }
          />
          {spec.colors && (
            <button
              type="button"
              onClick={() => patch({ colors: null })}
              className="num self-end rounded border rule px-2 py-1.5 text-[11px]"
            >
              zuruecksetzen
            </button>
          )}
        </div>
      </fieldset>
    </div>
  );
}

function currentColors(spec: CardSpec) {
  const entry = catalog.styles.find((s) => s.id === spec.style);
  return entry?.colors ?? { base: "#111111", feature: "#ffffff" };
}

function Legend({ children }: { children: React.ReactNode }) {
  return (
    <legend className="num mb-1.5 text-[11px] uppercase tracking-wider"
            style={{ color: "var(--muted)" }}>
      {children}
    </legend>
  );
}

function Field({
  label,
  value,
  onChange,
  max,
  issue,
  placeholder,
  hideLabel,
  mono,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  max: number;
  issue?: Issue;
  placeholder?: string;
  hideLabel?: boolean;
  mono?: boolean;
}) {
  const near = value.length > max * 0.85;
  return (
    <label className="block">
      <span
        className={`num mb-1 flex items-center text-[11px] uppercase tracking-wider ${hideLabel ? "sr-only" : ""}`}
        style={{ color: "var(--muted)" }}
      >
        {label}
        {!hideLabel && near && (
          <span className="ml-auto normal-case tracking-normal">
            {value.length} / {max}
          </span>
        )}
      </span>
      <input
        type="text"
        value={value}
        maxLength={max}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        className={`w-full rounded px-2 py-1.5 text-[13px] ${mono ? "num" : ""}`}
        style={issue ? { borderColor: "var(--flag)" } : undefined}
        aria-invalid={Boolean(issue)}
      />
      {issue && (
        <span className="mt-1 block text-[11px]" style={{ color: "var(--flag)" }}>
          {issue.message}
        </span>
      )}
    </label>
  );
}

function Swatch({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <label className="flex-1">
      <span className="num mb-1 block text-[10px]" style={{ color: "var(--muted)" }}>
        {label}
      </span>
      <span className="flex items-center gap-1.5 rounded border rule px-1.5 py-1">
        <input
          type="color"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="h-6 w-6 cursor-pointer border-0 bg-transparent p-0"
          aria-label={`${label} Farbe`}
        />
        <span className="num text-[11px]">{value}</span>
      </span>
    </label>
  );
}
