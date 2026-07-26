"use client";

import { useEffect, useRef, useState } from "react";

import { canonicalSpec, type CardSpec, type RenderResult } from "@/lib/spec";

/**
 * Keep a render in step with the spec.
 *
 * Three rules, all of them about not making the preview jump:
 *   the request is debounced, because a keystroke is not an intent;
 *   an older request is aborted the moment a newer one starts;
 *   the last good result stays on screen while the next one is computed.
 */
export type RenderError = { message: string; offline: boolean };

export function useRender(spec: CardSpec, delay = 200) {
  const [result, setResult] = useState<RenderResult | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<RenderError | null>(null);
  const inFlight = useRef<AbortController | null>(null);
  const key = canonicalSpec(spec);

  useEffect(() => {
    let cancelled = false;
    const timer = setTimeout(async () => {
      inFlight.current?.abort();
      const controller = new AbortController();
      inFlight.current = controller;
      setPending(true);

      try {
        const response = await fetch("/api/render", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: key,
          signal: controller.signal,
        });
        const payload = await response.json();
        if (cancelled || controller.signal.aborted) return;

        if (!response.ok) {
          setError({
            message:
              typeof payload?.detail === "string"
                ? payload.detail
                : "The card could not be computed.",
            // 502 and 503 mean the geometry service is not reachable at all,
            // which is a different thing to tell someone than a bad spec
            offline: response.status === 502 || response.status === 503,
          });
        } else {
          setResult(payload as RenderResult);
          setError(null);
        }
      } catch (caught) {
        if ((caught as Error).name === "AbortError" || cancelled) return;
        setError({ message: "No connection to the renderer.", offline: true });
      } finally {
        if (!cancelled && inFlight.current === controller) setPending(false);
      }
    }, delay);

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [key, delay]);

  return { result, pending, error };
}
