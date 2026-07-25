"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useEffect, useState } from "react";

import { CheckPanel } from "@/components/studio/CheckPanel";
import { ExportBar } from "@/components/studio/ExportBar";
import { SpecForm } from "@/components/studio/SpecForm";
import { Stage } from "@/components/studio/Stage";
import { StyleRail } from "@/components/studio/StyleRail";
import { ZStack } from "@/components/ZStack";
import { catalog } from "@/lib/catalog";
import { DEFAULT_SPEC, decodeSpec, encodeSpec, type CardSpec } from "@/lib/spec";
import { useRender } from "@/lib/useRender";

/** three.js is a big download, so it arrives only when 3D is switched on. */
const Card3D = dynamic(() => import("@/components/viewer/Card3D"), {
  ssr: false,
  loading: () => (
    <div className="num grid h-full place-items-center text-[12px]"
         style={{ color: "var(--muted)" }}>
      3D wird geladen
    </div>
  ),
});

export function Studio({ initial }: { initial: CardSpec }) {
  const [spec, setSpec] = useState<CardSpec>(initial);
  const [view, setView] = useState<"2d" | "3d">("2d");
  const { result, pending, error } = useRender(spec);

  /**
   * The URL is the only place the card lives. No account, no database, and a
   * link is the whole card, so sharing one is just sharing the address.
   */
  useEffect(() => {
    const encoded = encodeSpec(spec);
    const next = `${location.pathname}?s=${encoded}`;
    if (encoded.length > 1800) return; // do not push a URL a mail client will break
    history.replaceState(null, "", next);
  }, [spec]);

  const entry = catalog.styles.find((s) => s.id === spec.style);
  const colors = result?.colors ??
    entry?.colors ?? { base: "#111111", feature: "#ffffff" };

  return (
    <main className="mx-auto max-w-[1400px] px-4 pb-16 sm:px-6">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 py-5">
        <h1
          className="display text-[22px]"
          style={{ fontFamily: "var(--font-display-loaded), var(--font-display)" }}
        >
          Studio
        </h1>
        {entry && (
          <Link
            href={`/card/${entry.id}`}
            className="num text-[12px] underline underline-offset-4"
            style={{ color: "var(--muted)" }}
          >
            {entry.id}
          </Link>
        )}
        {result && (
          <span className="num ml-auto text-[11px]" style={{ color: "var(--muted)" }}>
            {result.ms} ms · {result.hash}
          </span>
        )}
      </div>

      <div className="grid gap-5 lg:grid-cols-[300px_minmax(0,1fr)_300px]">
        {/* content */}
        <section className="order-2 lg:order-1">
          <Panel title="Inhalt">
            <SpecForm
              spec={spec}
              onChange={setSpec}
              issues={result?.check.issues ?? []}
            />
          </Panel>
        </section>

        {/* stage */}
        <section className="order-1 lg:order-2 lg:sticky lg:top-[70px] lg:self-start">
          <div className="mb-2 flex items-center gap-1">
            {(["2d", "3d"] as const).map((mode) => (
              <button
                key={mode}
                type="button"
                aria-pressed={view === mode}
                onClick={() => setView(mode)}
                className="num rounded border px-2.5 py-1 text-[12px] uppercase"
                style={{
                  borderColor: view === mode ? "var(--accent)" : "var(--rule)",
                  color: view === mode ? "var(--accent)" : "inherit",
                }}
              >
                {mode}
              </button>
            ))}
            {/* when the service is down the stage says so at length, so this
                line would just repeat it in smaller type */}
            {error && !error.offline && (
              <span className="ml-auto text-[11px]" style={{ color: "var(--flag)" }}>
                {error.message}
              </span>
            )}
          </div>

          {view === "2d" ? (
            <Stage render={result} pending={pending} error={error} />
          ) : (
            <div
              className="overflow-hidden rounded-lg border rule"
              style={{ aspectRatio: "84 / 52", background: "var(--shade)" }}
            >
              {result ? (
                <Card3D render={result} />
              ) : (
                <div
                  className="num grid h-full place-items-center px-6 text-center text-[12px]"
                  style={{ color: "var(--muted)" }}
                >
                  {error?.offline
                    ? "Ohne den Geometrie-Dienst gibt es nichts zu zeigen."
                    : "wird gerechnet"}
                </div>
              )}
            </div>
          )}

          <ZStack
            className="mt-4"
            base={colors.base}
            feature={colors.feature}
            engraved={Boolean(
              result?.solids.some((s) => s.id === "base-top") ??
                entry?.engrave,
            )}
            embossed={Boolean(
              result?.solids.some((s) => s.id === "high") ?? entry?.emboss,
            )}
          />
        </section>

        {/* style and output */}
        <section className="order-3 space-y-4">
          <Panel title="Stil">
            <StyleRail spec={spec} onChange={setSpec} />
          </Panel>
          <CheckPanel check={result?.check ?? null} />
          <ExportBar spec={spec} check={result?.check ?? null} />
        </section>
      </div>
    </main>
  );
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border rule p-3" style={{ background: "var(--panel)" }}>
      <div
        className="num mb-3 text-[11px] uppercase tracking-wider"
        style={{ color: "var(--muted)" }}
      >
        {title}
      </div>
      {children}
    </div>
  );
}

/** Read the card out of the URL on first paint, or start from the stock one. */
export function readInitial(encoded: string | undefined): CardSpec {
  if (!encoded) return DEFAULT_SPEC;
  return decodeSpec(encoded) ?? DEFAULT_SPEC;
}
