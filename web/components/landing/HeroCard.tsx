"use client";

import Image from "next/image";
import { useEffect, useState } from "react";

import { ZStack } from "@/components/ZStack";
import { byId, partsLine } from "@/lib/catalog";

/**
 * The hero shows a card, and then another one.
 *
 * The claim on this page is range: 163 of these exist and they do not look
 * like variations of one template. A single still cannot say that and a grid
 * of thumbnails says it too quietly, so the hero cross fades through a few of
 * the most different ones. It is the only motion on the page, it is slow, and
 * it stops for anyone who asked their system to stop animations.
 */

const ROTATION = ["classic", "terminal", "neon", "hilbert", "bauhaus", "code39"];
const HOLD_MS = 3200;

export function HeroCard() {
  const cards = ROTATION.map((id) => byId.get(id)).filter(
    (entry): entry is NonNullable<typeof entry> => Boolean(entry),
  );
  const [index, setIndex] = useState(0);

  useEffect(() => {
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    if (cards.length < 2) return;
    const timer = setInterval(
      () => setIndex((i) => (i + 1) % cards.length),
      HOLD_MS,
    );
    return () => clearInterval(timer);
  }, [cards.length]);

  const current = cards[index];
  if (!current) return null;

  return (
    <figure className="w-full">
      <div
        className="relative overflow-hidden rounded-lg border rule"
        style={{ aspectRatio: "84 / 52", background: current.colors.base }}
      >
        {cards.map((entry, i) => (
          <Image
            key={entry.id}
            src={entry.preview}
            alt={i === index ? entry.label : ""}
            fill
            priority={i === 0}
            sizes="(max-width: 1024px) 100vw, 620px"
            className="object-cover transition-opacity duration-700"
            style={{ opacity: i === index ? 1 : 0 }}
          />
        ))}
      </div>

      <figcaption className="mt-3 flex items-baseline gap-3">
        <span className="num text-[12px]">{current.id}</span>
        <span
          className="num truncate text-[11px]"
          style={{ color: "var(--muted)" }}
        >
          {partsLine(current).join(" · ")}
        </span>
        <span
          className="num ml-auto shrink-0 text-[11px]"
          style={{ color: "var(--muted)" }}
        >
          {index + 1} / {cards.length}
        </span>
      </figcaption>

      <ZStack
        className="mt-4"
        base={current.colors.base}
        feature={current.colors.feature}
        engraved={current.engrave}
        embossed={Boolean(current.emboss)}
      />
    </figure>
  );
}
