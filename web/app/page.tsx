import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";

import { HeroCard } from "@/components/landing/HeroCard";
import { ZStack } from "@/components/ZStack";
import { byId, catalog } from "@/lib/catalog";
import { encodeSpec, specForStyle } from "@/lib/spec";

export const metadata: Metadata = {
  title: "Card Studio, business cards you print",
  description:
    "163 3D printable business card designs. Put your own name on one, check it against a 0.2 mm nozzle, and download the print file.",
};

const { base_z, top_z, high_z, engrave_z, w, h } = catalog.card;

/** A handful that show the range, for the strip above the gallery link. */
const SAMPLER = ["tree", "blueprint", "signet", "conway", "punchcard", "poster"];

export default function Landing() {
  const studio = `/studio?s=${encodeSpec(specForStyle("classic"))}`;

  return (
    <main>
      {/* ---------------------------------------------------------- hero */}
      <section className="mx-auto grid max-w-[1400px] items-center gap-10 px-4 py-12 sm:px-6 lg:grid-cols-[1fr_620px] lg:py-20">
        <div>
          <p
            className="num mb-5 text-[11px] uppercase tracking-[0.18em]"
            style={{ color: "var(--muted)" }}
          >
            {w} &times; {h} mm &middot; two filaments &middot; one colour change
          </p>

          <h1
            className="display text-[38px] leading-[1.02] sm:text-[56px]"
            style={{ fontFamily: "var(--font-display-loaded), var(--font-display)" }}
          >
            A business card
            <br />
            you print
          </h1>

          <p className="mt-6 max-w-[54ch] text-[17px]" style={{ color: "var(--muted)" }}>
            Pick one of {catalog.styles.length} designs, put your own name and
            link on it, and download a file your printer understands. It costs
            a few cents of filament and it fits a wallet.
          </p>

          <div className="mt-8 flex flex-wrap items-center gap-3">
            <Link
              href={studio}
              className="rounded px-5 py-3 text-[15px] font-semibold text-white"
              style={{ background: "var(--accent)" }}
            >
              Open the studio
            </Link>
            <Link
              href="/gallery"
              className="rounded border rule px-5 py-3 text-[15px] hover:border-[var(--accent)]"
            >
              Browse all {catalog.styles.length}
            </Link>
          </div>

          <p className="num mt-5 text-[12px]" style={{ color: "var(--muted)" }}>
            No account. Nothing stored. A card lives in its own URL.
          </p>
        </div>

        <HeroCard />
      </section>

      {/* --------------------------------------------------------- depth */}
      <section className="border-y rule" style={{ background: "var(--panel)" }}>
        <div className="mx-auto grid max-w-[1400px] gap-10 px-4 py-14 sm:px-6 lg:grid-cols-2 lg:py-20">
          <div>
            <h2
              className="display text-[26px] sm:text-[34px]"
              style={{ fontFamily: "var(--font-display-loaded), var(--font-display)" }}
            >
              Paper cards
              <br />
              have no thickness
            </h2>
            <p className="mt-5 max-w-[52ch]" style={{ color: "var(--muted)" }}>
              These are built from four stacked layers, and you can feel three
              of them. The base carries the colour, the type sits on top in the
              second filament, an emboss can lift it further, and a groove can
              be cut into the base so a pattern reads as depth rather than as
              ink.
            </p>
            <p className="mt-4 max-w-[52ch]" style={{ color: "var(--muted)" }}>
              All of it stays inside two filaments and a single colour change,
              so the print is one job and no manual swap beyond the one.
            </p>
          </div>

          <div className="self-center">
            {/* the card seen edge on, at the true ratio, which is the only
                honest way to show a tenth of a millimetre */}
            <div
              className="num mb-3 flex items-baseline gap-2 text-[11px] uppercase tracking-wider"
              style={{ color: "var(--muted)" }}
            >
              Cross section
              <span className="normal-case tracking-normal">
                {(base_z + top_z + high_z).toFixed(1)} mm at its tallest
              </span>
            </div>
            <ZStack base="#17181a" feature="#f2f0ec" engraved embossed />

            <dl className="mt-8 grid grid-cols-2 gap-x-6 gap-y-5 sm:grid-cols-4">
              <Figure k="Base" v={base_z} note="first filament" />
              <Figure k="Features" v={top_z} note="second filament" />
              <Figure k="Emboss" v={high_z} note="raised further" />
              <Figure k="Groove" v={engrave_z} note="cut into the base" />
            </dl>
          </div>
        </div>
      </section>

      {/* ---------------------------------------------------------- check */}
      <section className="mx-auto max-w-[1400px] px-4 py-14 sm:px-6 lg:py-20">
        <div className="grid gap-10 lg:grid-cols-[1fr_380px]">
          <div>
            <h2
              className="display text-[26px] sm:text-[34px]"
              style={{ fontFamily: "var(--font-display-loaded), var(--font-display)" }}
            >
              It measures your text
              <br />
              before you spend filament
            </h2>
            <p className="mt-5 max-w-[58ch]" style={{ color: "var(--muted)" }}>
              A long name gets scaled to fit the column, and past a point the
              strokes get too thin for a 0.2 mm nozzle and the letters fuse on
              the print. That happened here once, on a real card, which is why
              every edit is measured: thinnest stroke, tightest gap between
              letters, QR module size, and whether the type still clears the QR
              panel.
            </p>
            <p className="mt-4 max-w-[58ch]" style={{ color: "var(--muted)" }}>
              The numbers are checked against the design you picked rather than
              an abstract threshold, because a third of these styles set type
              tighter than any fixed rule on purpose. The check tells you when
              your text made a card worse, and refuses the download only when
              the file would be unprintable.
            </p>
          </div>

          {/* a real reading from the reference card, not an invented one */}
          <div
            className="self-start rounded-lg border rule p-4"
            style={{ background: "var(--panel)" }}
          >
            <div className="flex items-center gap-2">
              <span
                className="inline-block h-2 w-2 rounded-full"
                style={{ background: "var(--accent)", opacity: 0.5 }}
              />
              <span className="num text-[11px] uppercase tracking-wider">
                Print check
              </span>
              <span
                className="num ml-auto text-[11px]"
                style={{ color: "var(--muted)" }}
              >
                clean
              </span>
            </div>
            <dl className="num mt-3 grid grid-cols-2 gap-x-4 gap-y-1 text-[11px]">
              <Reading k="Stroke" v="0.49 mm" />
              <Reading k="Gap" v="0.26 mm" />
              <Reading k="QR module" v="0.88 mm" />
              <Reading k="QR matrix" v="25 × 25" />
            </dl>
            <p className="mt-3 text-[11px]" style={{ color: "var(--muted)" }}>
              The reference card, the one that was printed and held.
            </p>
          </div>
        </div>
      </section>

      {/* --------------------------------------------------------- steps */}
      <section className="border-y rule" style={{ background: "var(--panel)" }}>
        <div className="mx-auto max-w-[1400px] px-4 py-14 sm:px-6 lg:py-20">
          <ol className="grid gap-8 sm:grid-cols-3">
            <Step
              n="01"
              title="Pick a design"
              body={`${catalog.styles.length} of them, from a plain black card to a Hilbert curve to a barcode that actually scans.`}
            />
            <Step
              n="02"
              title="Put your name on it"
              body="Name, tagline, up to four contact lines, and whatever the QR code should point at. Watch it in 2D or 3D as you type."
            />
            <Step
              n="03"
              title="Print it"
              body="Download a 3MF that opens two-coloured in Bambu Studio, or two STL files if you slice it yourself."
            />
          </ol>
        </div>
      </section>

      {/* ------------------------------------------------------- sampler */}
      <section className="mx-auto max-w-[1400px] px-4 py-14 sm:px-6 lg:py-20">
        <div className="flex flex-wrap items-baseline gap-x-4 gap-y-2">
          <h2
            className="display text-[26px] sm:text-[34px]"
            style={{ fontFamily: "var(--font-display-loaded), var(--font-display)" }}
          >
            A few of them
          </h2>
          <Link
            href="/gallery"
            className="num text-[13px] underline underline-offset-4"
          >
            all {catalog.styles.length}
          </Link>
        </div>

        <div className="mt-6 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
          {SAMPLER.map((id) => {
            const entry = byId.get(id);
            if (!entry) return null;
            return (
              <Link
                key={id}
                href={`/card/${id}`}
                className="block rounded-lg border rule p-2 transition-colors hover:border-[var(--accent)]"
                style={{ background: "var(--panel)" }}
              >
                <div
                  className="relative overflow-hidden rounded"
                  style={{ aspectRatio: "84 / 52", background: entry.colors.base }}
                >
                  <Image
                    src={entry.preview}
                    alt={entry.label}
                    fill
                    sizes="(max-width: 768px) 50vw, 220px"
                    className="object-cover"
                  />
                </div>
                <div className="num px-1 pt-2 text-[12px]">{entry.id}</div>
              </Link>
            );
          })}
        </div>
      </section>

      {/* ----------------------------------------------------------- cta */}
      <section className="mx-auto max-w-[1400px] px-4 pb-8 sm:px-6">
        <div
          className="flex flex-wrap items-center gap-x-6 gap-y-4 rounded-lg border rule px-6 py-8"
          style={{ background: "var(--panel)" }}
        >
          <div className="min-w-0">
            <h2
              className="display text-[22px]"
              style={{ fontFamily: "var(--font-display-loaded), var(--font-display)" }}
            >
              Make one
            </h2>
            <p className="mt-1 text-[14px]" style={{ color: "var(--muted)" }}>
              It takes about a minute, and the file is yours.
            </p>
          </div>
          <Link
            href={studio}
            className="ml-auto rounded px-5 py-3 text-[15px] font-semibold text-white"
            style={{ background: "var(--accent)" }}
          >
            Open the studio
          </Link>
        </div>
      </section>
    </main>
  );
}

function Figure({ k, v, note }: { k: string; v: number; note: string }) {
  return (
    <div>
      <dt className="num text-[11px] uppercase tracking-wider"
          style={{ color: "var(--muted)" }}>
        {k}
      </dt>
      <dd className="num mt-1 text-[26px] leading-none">
        {v.toFixed(1)}
        <span className="ml-1 text-[13px]" style={{ color: "var(--muted)" }}>
          mm
        </span>
      </dd>
      <dd className="mt-1 text-[12px]" style={{ color: "var(--muted)" }}>
        {note}
      </dd>
    </div>
  );
}

function Reading({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex justify-between gap-2">
      <dt style={{ color: "var(--muted)" }}>{k}</dt>
      <dd>{v}</dd>
    </div>
  );
}

function Step({ n, title, body }: { n: string; title: string; body: string }) {
  return (
    <li>
      <div className="num text-[11px]" style={{ color: "var(--accent)" }}>
        {n}
      </div>
      <h3 className="mt-2 text-[17px] font-semibold">{title}</h3>
      <p className="mt-2 text-[14px]" style={{ color: "var(--muted)" }}>
        {body}
      </p>
    </li>
  );
}
