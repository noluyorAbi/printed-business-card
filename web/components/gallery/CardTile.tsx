"use client";

import Image from "next/image";
import Link from "next/link";

import { ZStack } from "@/components/ZStack";
import { partsLine, type StyleEntry } from "@/lib/catalog";

/**
 * One card in the grid, at the real 84:52 ratio. The profile strip slides in
 * on hover and focus, so the depth of a style is one glance away without
 * opening it.
 */
export function CardTile({
  style,
  priority = false,
}: {
  style: StyleEntry;
  priority?: boolean;
}) {
  return (
    <Link
      href={`/card/${style.id}`}
      data-tile={style.id}
      className="group block rounded-lg border rule p-2 transition-colors hover:border-[var(--accent)] focus-visible:border-[var(--accent)]"
      style={{ background: "var(--panel)" }}
    >
      <div
        className="relative overflow-hidden rounded"
        style={{ aspectRatio: "84 / 52", background: style.colors.base }}
      >
        <Image
          src={style.preview}
          alt=""
          fill
          sizes="(max-width: 420px) 100vw, (max-width: 768px) 50vw, (max-width: 1280px) 33vw, 25vw"
          priority={priority}
          className="object-cover"
        />
        <div className="absolute inset-x-2 bottom-2 opacity-0 transition-opacity duration-150 group-hover:opacity-100 group-focus-visible:opacity-100">
          <ZStack
            compact
            base={style.colors.base}
            feature={style.colors.feature}
            engraved={style.engrave}
            embossed={Boolean(style.emboss)}
          />
        </div>
      </div>

      <div className="px-1 pt-2 pb-0.5">
        <div className="num text-[13px]">{style.id}</div>
        <div
          className="num mt-0.5 truncate text-[11px]"
          style={{ color: "var(--muted)" }}
          title={partsLine(style).join(" · ")}
        >
          {partsLine(style).join(" · ")}
        </div>
      </div>
    </Link>
  );
}
