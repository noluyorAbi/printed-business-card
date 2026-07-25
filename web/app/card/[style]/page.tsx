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
  if (!entry) return { title: "Karte nicht gefunden" };
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
        <Link href="/" className="underline underline-offset-4">
          Galerie
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
            Im Studio oeffnen
          </Link>

          <dl className="num mt-6 space-y-0 text-[12px]">
            <Spec k="Kategorie" v={CATEGORY_LABELS[entry.category]} />
            <Spec k="Layout" v={entry.layout} />
            <Spec k="Textur" v={entry.decor ?? "keine"} />
            <Spec k="Rahmen" v={entry.frame} />
            <Spec k="QR" v={`${entry.qr} · ${entry.qr_shape}`} />
            <Spec k="Emboss" v={entry.emboss ?? "keiner"} />
            <Spec k="Gravur" v={entry.engrave ? "ja" : "nein"} />
            <Spec k="Basis" v={entry.filaments.base} swatch={entry.colors.base} />
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
      ? `Die Flaeche traegt die Textur "${s.decor}", die ueberall dort ausgespart wird, wo Text oder QR-Code stehen.`
      : "Die Flaeche bleibt leer, die Karte lebt allein von der Typografie.",
  );
  if (s.engrave)
    bits.push(
      `Ein Teil davon ist ${catalog.card.engrave_z} mm tief in die Basis gefraest, also nur als Tiefe spuerbar, nicht als Farbe.`,
    );
  if (s.emboss)
    bits.push(
      `${s.emboss === "text" ? "Die Schrift" : "Ein Teil der Features"} steht ${catalog.card.high_z} mm hoeher als der Rest und laesst sich mit dem Daumen ertasten.`,
    );
  bits.push(
    s.qr === "relief"
      ? "Der QR-Code steht erhaben auf der Basis."
      : "Der QR-Code ist in ein Feld aus dem zweiten Filament gesenkt, damit der Kontrast auch bei dunkler Basis stimmt.",
  );
  return bits.join(" ");
}
