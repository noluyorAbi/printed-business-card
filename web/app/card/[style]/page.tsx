import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { notFound } from "next/navigation";

import { ZStack } from "@/components/ZStack";
import {
  CATEGORY_LABELS,
  byId,
  catalog,
  partsLine,
  type StyleEntry,
} from "@/lib/catalog";
import { encodeSpec, specForStyle } from "@/lib/spec";

/** The previews are rendered at a fixed size by build_card.py. */
const PREVIEW_W = 1215;
const PREVIEW_H = 794;

/** All 163 pages are static: the previews already exist as files. */
export function generateStaticParams() {
  return catalog.styles.map((s) => ({ style: s.id }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ style: string }>;
}): Promise<Metadata> {
  const { style } = await params;
  const entry = byId.get(style);
  if (!entry) return { title: "Card not found" };
  return { title: `${entry.id} · Card Studio`, description: entry.label };
}

export default async function CardPage({
  params,
}: {
  params: Promise<{ style: string }>;
}) {
  const { style } = await params;
  const entry = byId.get(style);
  if (!entry) notFound();

  const index = catalog.styles.findIndex((s) => s.id === entry.id);
  const previous = catalog.styles[index - 1];
  const next = catalog.styles[index + 1];
  const href = `/studio?s=${encodeSpec(specForStyle(entry.id))}`;

  return (
    <main className="mx-auto max-w-[1100px] px-4 pb-20 sm:px-6">
      <nav className="num flex items-center gap-2 py-5 text-[12px]">
        <Link href="/gallery" className="underline underline-offset-4">
          Gallery
        </Link>
        <span style={{ color: "var(--muted)" }}>/</span>
        <span>{entry.id}</span>
      </nav>

      <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_300px]">
        <div>
          <div
            className="overflow-hidden rounded-lg border rule"
            style={{ aspectRatio: "84 / 52", background: entry.colors.base }}
          >
            <Image
              src={entry.preview}
              alt={entry.label}
              width={PREVIEW_W}
              height={PREVIEW_H}
              priority
              className="h-full w-full object-cover"
            />
          </div>

          <ZStack
            className="mt-5"
            base={entry.colors.base}
            feature={entry.colors.feature}
            engraved={entry.engrave}
            embossed={Boolean(entry.emboss)}
          />
        </div>

        <aside>
          <h1
            className="display text-[26px]"
            style={{ fontFamily: "var(--font-display-loaded), var(--font-display)" }}
          >
            {entry.id}
          </h1>
          <p className="mt-2 text-[14px]" style={{ color: "var(--muted)" }}>
            {entry.label}
          </p>

          <Link
            href={href}
            className="mt-5 block rounded px-4 py-2.5 text-center text-[14px] font-semibold text-white"
            style={{ background: "var(--accent)" }}
          >
            Open in Studio
          </Link>

          <dl className="num mt-6 space-y-0 text-[12px]">
            <Spec k="Category" v={CATEGORY_LABELS[entry.category]} />
            <Spec k="Layout" v={entry.layout} />
            <Spec k="Texture" v={entry.decor ?? "none"} />
            <Spec k="Frame" v={entry.frame} />
            <Spec k="QR" v={`${entry.qr} · ${entry.qr_shape}`} />
            <Spec k="Emboss" v={entry.emboss ?? "none"} />
            <Spec k="Engraving" v={entry.engrave ? "yes" : "no"} />
            <Spec k="Base" v={entry.filaments.base} swatch={entry.colors.base} />
            <Spec
              k="Features"
              v={entry.filaments.feature}
              swatch={entry.colors.feature}
            />
          </dl>

          <p className="mt-6 text-[13px]" style={{ color: "var(--muted)" }}>
            {describe(entry)}
          </p>
        </aside>
      </div>

      <nav className="mt-12 flex justify-between gap-4 border-t rule pt-5 text-[13px]">
        {previous ? (
          <Link href={`/card/${previous.id}`} className="num underline underline-offset-4">
            &larr; {previous.id}
          </Link>
        ) : (
          <span />
        )}
        {next && (
          <Link href={`/card/${next.id}`} className="num underline underline-offset-4">
            {next.id} &rarr;
          </Link>
        )}
      </nav>
    </main>
  );
}

function Spec({ k, v, swatch }: { k: string; v: string; swatch?: string }) {
  return (
    <div className="flex justify-between gap-3 border-b rule py-1.5">
      <dt style={{ color: "var(--muted)" }}>{k}</dt>
      <dd className="flex items-center gap-1.5 text-right">
        {swatch && (
          <span
            className="inline-block h-3 w-3 rounded-[2px] border rule"
            style={{ background: swatch }}
          />
        )}
        {v}
      </dd>
    </div>
  );
}

/** One honest sentence per card, assembled from what the style actually does. */
function describe(s: StyleEntry): string {
  const bits: string[] = [];
  bits.push(
    s.decor
      ? `The surface carries the "${s.decor}" texture, cut away wherever type or the QR code sits.`
      : "The surface stays empty; this card lives on its typography alone.",
  );
  if (s.engrave)
    bits.push(
      `Part of it is cut ${catalog.card.engrave_z} mm into the base, so it reads as depth under a thumb rather than as colour.`,
    );
  if (s.emboss)
    bits.push(
      `${s.emboss === "text" ? "The type" : "Part of the features"} stands ${catalog.card.high_z} mm above the rest, high enough to feel.`,
    );
  bits.push(
    s.qr === "relief"
      ? "The QR code stands raised on the base."
      : "The QR code is sunk into a panel of the second filament, so the contrast holds even on a dark base.",
  );
  return bits.join(" ");
}
