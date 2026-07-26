"use client";

import type { PrintCheck } from "@/lib/spec";

/**
 * What the nozzle says about this card.
 *
 * Warn, do not silently repair. Every number carries its unit, every message
 * names the field that caused it and what to do about it. An error blocks the
 * download; a warning does not.
 */
export function CheckPanel({ check }: { check: PrintCheck | null }) {
  if (!check) {
    return (
      <div className="rounded-lg border rule p-3">
        <div className="num text-[11px]" style={{ color: "var(--muted)" }}>
          Print check
        </div>
      </div>
    );
  }

  const errors = check.issues.filter((i) => i.level === "error");
  const warnings = check.issues.filter((i) => i.level === "warn");
  const colour = errors.length
    ? "var(--flag)"
    : warnings.length
      ? "var(--flag)"
      : "var(--accent)";

  return (
    <section
      className="rounded-lg border rule p-3"
      aria-live="polite"
      style={{ background: "var(--panel)" }}
    >
      <div className="flex items-center gap-2">
        <span
          className="inline-block h-2 w-2 rounded-full"
          style={{ background: colour, opacity: errors.length || warnings.length ? 1 : 0.5 }}
        />
        <span className="num text-[11px] uppercase tracking-wider">
          Print check
        </span>
        <span className="num ml-auto text-[11px]" style={{ color: "var(--muted)" }}>
          {errors.length
            ? `${errors.length} error${errors.length > 1 ? "s" : ""}`
            : warnings.length
              ? `${warnings.length} warning${warnings.length > 1 ? "s" : ""}`
              : "clean"}
        </span>
      </div>

      <dl className="num mt-3 grid grid-cols-2 gap-x-4 gap-y-1 text-[11px]">
        <Metric
          k="Stroke"
          v={`${check.metrics.min_stroke_mm.toFixed(2)} mm`}
          low={check.metrics.min_stroke_mm < 0.45}
        />
        <Metric
          k="Gap"
          v={`${check.metrics.min_gap_mm.toFixed(2)} mm`}
          low={check.metrics.min_gap_mm < 0.25}
        />
        <Metric
          k="QR module"
          v={`${check.metrics.qr_module_mm.toFixed(2)} mm`}
          low={check.metrics.qr_module_mm < 0.8}
        />
        <Metric
          k="QR matrix"
          v={`${check.metrics.qr_modules} × ${check.metrics.qr_modules}`}
        />
      </dl>

      {check.issues.length > 0 && (
        <ul className="mt-3 space-y-2">
          {check.issues.map((issue, i) => (
            <li
              key={`${issue.code}-${issue.field}-${i}`}
              className="rounded border-l-2 pl-2.5 text-[12px]"
              style={{
                borderColor: issue.level === "error" ? "var(--flag)" : "var(--rule)",
              }}
            >
              <div className="num text-[10px]" style={{ color: "var(--muted)" }}>
                {issue.field}
              </div>
              <div>{issue.message}</div>
              {issue.hint && (
                <div className="mt-0.5" style={{ color: "var(--muted)" }}>
                  {issue.hint}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function Metric({ k, v, low }: { k: string; v: string; low?: boolean }) {
  return (
    <div className="flex justify-between gap-2">
      <dt style={{ color: "var(--muted)" }}>{k}</dt>
      <dd style={{ color: low ? "var(--flag)" : "inherit" }}>{v}</dd>
    </div>
  );
}
