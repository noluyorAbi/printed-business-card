"use client";

import { useCallback, useSyncExternalStore } from "react";

type Theme = "light" | "dark";

/**
 * The theme lives on the document element, not in React.
 *
 * An inline script in the head stamps `data-theme` before first paint so a
 * dark reader never gets a white flash. React then reads that attribute
 * rather than keeping a second copy of the truth, which is what
 * `useSyncExternalStore` is for. Mirroring it into state inside an effect
 * would render once with the wrong answer and correct itself a frame later.
 */

const listeners = new Set<() => void>();

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function current(): Theme {
  const stamped = document.documentElement.dataset.theme;
  if (stamped === "dark" || stamped === "light") return stamped;
  return matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function ThemeToggle() {
  // the server has no theme to report, so it renders the button empty and the
  // client fills the label in on hydration
  const theme = useSyncExternalStore(subscribe, current, () => null);

  const flip = useCallback(() => {
    const next: Theme = current() === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try {
      localStorage.setItem("theme", next);
    } catch {
      // private mode, or storage is full. The choice just will not persist.
    }
    for (const listener of listeners) listener();
  }, []);

  return (
    <button
      type="button"
      onClick={flip}
      aria-label={theme === "dark" ? "Auf hell wechseln" : "Auf dunkel wechseln"}
      className="ml-1 rounded px-2.5 py-1.5 text-[13px] hover:bg-[var(--shade)]"
    >
      {/* fixed width, so the header does not shift when the label appears */}
      <span className="num inline-block w-[42px] text-center">
        {theme === null ? "" : theme === "dark" ? "hell" : "dunkel"}
      </span>
    </button>
  );
}
