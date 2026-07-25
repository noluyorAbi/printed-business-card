"use client";

import { useMemo } from "react";

import type { Layer, RenderResult } from "@/lib/spec";
import type { RenderError } from "@/lib/useRender";

/**
 * The card in 2D, drawn from the worker's layer paths.
 *
 * Coordinates arrive in millimetres with y pointing up, the way the generator
 * works. One transform at the top flips it, so nothing below has to think
 * about which way a browser draws.
 */

function shade(hex: string, amount: number): string {
  const n = parseInt(hex.slice(1), 16);
  const to = amount > 0 ? 255 : 0;
  const f = Math.abs(amount);
  const mix = (c: number) => Math.round(c + (to - c) * f);
  return `rgb(${mix((n >> 16) & 255)} ${mix((n >> 8) & 255)} ${mix(n & 255)})`;
}

export function Stage({
  render,
  pending,
  error,
}: {
  render: RenderResult | null;
  pending: boolean;
  error?: RenderError | null;
}) {
  const fills = useMemo(() => {
    if (!render) return null;
    const { base, feature } = render.colors;
    return {
      engrave: shade(base, -0.55),
      base,
      feature,
      high: shade(feature, 0.22),
    } as Record<Layer["id"], string>;
  }, [render]);

  return (
    <div
      className="relative overflow-hidden rounded-lg border rule"
      style={{ aspectRatio: "84 / 52", background: "var(--shade)" }}
    >
      {/* a hairline that only says "working", instead of a spinner that
          replaces the card the user is looking at */}
      <div
        className="absolute inset-x-0 top-0 z-10 h-[2px] origin-left transition-opacity duration-150"
        style={{
          background: "var(--accent)",
          opacity: pending ? 1 : 0,
          animation: pending ? "card-in 400ms ease-out" : undefined,
        }}
      />

      {render && fills && (
        <svg
          key={render.hash}
          viewBox={`0 0 ${render.card.w} ${render.card.h}`}
          className="card-in absolute inset-0 h-full w-full"
          role="img"
          aria-label={`Vorschau der Karte im Stil ${render.style.id}`}
        >
          <g transform={`translate(0,${render.card.h}) scale(1,-1)`}>
            {render.layers.map((layer) =>
              layer.d ? (
                <path
                  key={layer.id}
                  d={layer.d}
                  fill={fills[layer.id]}
                  fillRule="evenodd"
                />
              ) : null,
            )}
          </g>
        </svg>
      )}

      {/* Nothing has ever rendered and the service is unreachable. Say what
          is missing rather than spinning forever: the gallery still works,
          and this is the one page that genuinely needs the worker. */}
      {!render && error?.offline && (
        <div className="absolute inset-0 grid place-items-center p-6 text-center">
          <div className="max-w-[42ch]">
            <p className="num text-[13px]" style={{ color: "var(--flag)" }}>
              Der Geometrie-Dienst ist nicht verbunden
            </p>
            <p className="mt-2 text-[13px]" style={{ color: "var(--muted)" }}>
              Die Karten werden von einem Python-Worker gerechnet, nicht von
              dieser Seite. Ohne ihn bleibt der Editor leer. Die Galerie
              funktioniert weiterhin.
            </p>
            <a
              href="https://github.com/noluyorAbi/printed-business-card/blob/main/DEPLOY.md"
              className="num mt-3 inline-block text-[12px] underline underline-offset-4"
            >
              DEPLOY.md
            </a>
          </div>
        </div>
      )}

      {!render && !error?.offline && (
        <div
          className="num absolute inset-0 grid place-items-center text-[12px]"
          style={{ color: "var(--muted)" }}
        >
          wird gerechnet
        </div>
      )}
    </div>
  );
}
