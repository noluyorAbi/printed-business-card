import { catalog } from "@/lib/catalog";

/**
 * The card seen from its edge.
 *
 * This is the one thing a printed card has that a paper card does not: it is
 * built out of four stacked layers, and you can feel three of them with a
 * thumb. Every view in the app carries this strip, drawn at the true ratio of
 * 0.6 / 0.4 / 0.3 mm with a scale beside it, so the depth is never an
 * abstraction.
 */

const { base_z, top_z, high_z, engrave_z } = catalog.card;
const TOTAL = base_z + top_z + high_z;

type Props = {
  base: string;
  feature: string;
  engraved?: boolean;
  embossed?: boolean;
  /** Compact drops the scale and the labels, for a gallery tile. */
  compact?: boolean;
  className?: string;
};

function pct(mm: number) {
  return `${(mm / TOTAL) * 100}%`;
}

export function ZStack({
  base,
  feature,
  engraved = false,
  embossed = false,
  compact = false,
  className = "",
}: Props) {
  const height = compact ? 34 : 64;

  return (
    <figure className={className} aria-hidden={compact}>
      <div className="flex items-end gap-2">
        {!compact && (
          <div
            className="num flex flex-col justify-between text-right text-[10px] leading-none"
            style={{ height, color: "var(--muted)" }}
          >
            <span>{TOTAL.toFixed(1)}</span>
            <span>{base_z.toFixed(1)}</span>
            <span>0.0</span>
          </div>
        )}

        {/* Air is hatched, material is solid with a hairline around it. The
            user picks the filament colours, and a near white filament on a
            near white page would otherwise vanish. */}
        <div
          className="relative flex-1 overflow-hidden rounded-[2px]"
          style={{
            height,
            background:
              "repeating-linear-gradient(45deg, transparent 0 3px, var(--rule) 3px 4px)",
            opacity: 0.999,
          }}
        >
          {/* base, full width, minus the engraved notch */}
          <div
            className="zbar absolute inset-x-0 bottom-0"
            style={{
              height: pct(base_z),
              background: base,
              outline: "1px solid var(--rule)",
              outlineOffset: "-1px",
            }}
          />
          <div
            className="zbar absolute"
            style={{
              left: "26%",
              width: "13%",
              bottom: pct(base_z - engrave_z),
              height: pct(engrave_z),
              background:
                "repeating-linear-gradient(45deg, var(--bg) 0 3px, var(--rule) 3px 4px)",
              outline: "1px solid var(--rule)",
              outlineOffset: "-1px",
              opacity: engraved ? 1 : 0,
            }}
          />

          {/* features, in the second filament, only where there is geometry */}
          {[
            { left: "8%", width: "16%" },
            { left: "46%", width: "38%" },
          ].map((run) => (
            <div
              key={run.left}
              className="zbar absolute"
              style={{
                ...run,
                bottom: pct(base_z),
                height: pct(top_z),
                background: feature,
                outline: "1px solid var(--rule)",
                outlineOffset: "-1px",
              }}
            />
          ))}

          {/* emboss, stacked on top of one of the feature runs */}
          <div
            className="zbar absolute"
            style={{
              left: "46%",
              width: "18%",
              bottom: pct(base_z + top_z),
              height: pct(high_z),
              background: feature,
              filter: "brightness(1.15)",
              outline: "1px solid var(--rule)",
              outlineOffset: "-1px",
              opacity: embossed ? 1 : 0,
            }}
          />
        </div>
      </div>

      {!compact && (
        <figcaption
          className="num mt-1.5 flex flex-wrap gap-x-3 text-[10px]"
          style={{ color: "var(--muted)" }}
        >
          <span>base {base_z.toFixed(1)} mm</span>
          <span>features {top_z.toFixed(1)} mm</span>
          <span style={{ opacity: embossed ? 1 : 0.4 }}>
            emboss {high_z.toFixed(1)} mm
          </span>
          <span style={{ opacity: engraved ? 1 : 0.4 }}>
            engraved {engrave_z.toFixed(1)} mm deep
          </span>
        </figcaption>
      )}
    </figure>
  );
}
