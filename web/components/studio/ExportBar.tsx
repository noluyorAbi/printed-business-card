"use client";

import { useState } from "react";

import { canonicalSpec, type CardSpec, type PrintCheck } from "@/lib/spec";

const FORMATS = [
  { id: "3mf", label: "3MF", hint: "beide Farben, fuer Bambu Studio" },
  { id: "stl-base", label: "STL Basis", hint: "erstes Filament" },
  { id: "stl-top", label: "STL Top", hint: "zweites Filament" },
] as const;

export function ExportBar({
  spec,
  check,
}: {
  spec: CardSpec;
  check: PrintCheck | null;
}) {
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const blocked = check ? !check.ok : false;

  async function download(format: string) {
    setBusy(format);
    setError(null);
    try {
      const response = await fetch("/api/export", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: `{"spec":${canonicalSpec(spec)},"format":"${format}"}`,
      });

      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        setError(
          payload?.detail?.detail ??
            (typeof payload?.detail === "string"
              ? payload.detail
              : "Der Download hat nicht geklappt."),
        );
        return;
      }

      const blob = await response.blob();
      const name =
        response.headers
          .get("content-disposition")
          ?.match(/filename="([^"]+)"/)?.[1] ?? `card.${format}`;

      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = name;
      link.click();
      URL.revokeObjectURL(url);
    } catch {
      setError("Keine Verbindung.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <section className="rounded-lg border rule p-3" style={{ background: "var(--panel)" }}>
      <div className="num mb-2 text-[11px] uppercase tracking-wider"
           style={{ color: "var(--muted)" }}>
        Herunterladen
      </div>

      <div className="grid grid-cols-3 gap-1.5">
        {FORMATS.map((format) => (
          <button
            key={format.id}
            type="button"
            disabled={blocked || busy !== null}
            title={format.hint}
            onClick={() => download(format.id)}
            className="rounded px-2 py-2 text-[12px] font-semibold transition-opacity disabled:cursor-not-allowed disabled:opacity-40"
            style={
              format.id === "3mf"
                ? { background: "var(--accent)", color: "#fff" }
                : { border: "1px solid var(--rule)" }
            }
          >
            {busy === format.id ? "…" : format.label}
          </button>
        ))}
      </div>

      {blocked && (
        <p className="mt-2 text-[11px]" style={{ color: "var(--flag)" }}>
          Der Druck-Check meldet einen Fehler. Behebe ihn oben, dann gibt es die
          Datei.
        </p>
      )}
      {error && (
        <p className="mt-2 text-[11px]" style={{ color: "var(--flag)" }}>
          {error}
        </p>
      )}
    </section>
  );
}
