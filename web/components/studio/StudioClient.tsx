"use client";

import { useSearchParams } from "next/navigation";
import { Suspense } from "react";

import { Studio, readInitial } from "@/components/studio/Studio";

/**
 * Reading search params forces a client boundary, and Next wants that inside
 * a Suspense boundary so the rest of the page can still be prerendered.
 */
function FromUrl() {
  const params = useSearchParams();
  const encoded = params.get("s") ?? undefined;
  // keying on the encoded spec means a pasted link replaces the editor state
  // instead of merging into it
  return <Studio key={encoded ?? "default"} initial={readInitial(encoded)} />;
}

export function StudioClient() {
  return (
    <Suspense
      fallback={
        <div
          className="num mx-auto max-w-[1400px] px-4 py-20 text-[12px] sm:px-6"
          style={{ color: "var(--muted)" }}
        >
          loading studio
        </div>
      }
    >
      <FromUrl />
    </Suspense>
  );
}
