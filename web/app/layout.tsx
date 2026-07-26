import type { Metadata } from "next";
import Link from "next/link";
import { Archivo, IBM_Plex_Mono, IBM_Plex_Sans } from "next/font/google";

import { ThemeToggle } from "@/components/ThemeToggle";
import "./globals.css";

/**
 * Three faces, three jobs. Archivo Expanded is the machine lettering on the
 * page titles, Plex Sans carries the reading, Plex Mono carries every number
 * that has a unit attached. Plex has engineering in its bones and the mono
 * matches the code layouts the cards themselves use.
 */
const display = Archivo({
  subsets: ["latin"],
  // the width axis is the point: Archivo Expanded is the machine lettering
  // look, and it only exists as a variable axis
  axes: ["wdth"],
  variable: "--font-display-loaded",
});

const sans = IBM_Plex_Sans({
  subsets: ["latin"],
  weight: ["400", "600"],
  variable: "--font-sans-loaded",
});

const mono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-mono-loaded",
});

export const metadata: Metadata = {
  title: { default: "Card Studio", template: "%s" },
  description:
    "163 3D printable business cards. Put your own name on one, check it against a 0.2 mm nozzle, and download the 3MF.",
  metadataBase: new URL("https://printed-business-card.vercel.app"),
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script
          // read the stored choice before first paint, so a dark reader never
          // gets a white flash on the way in
          dangerouslySetInnerHTML={{
            __html: `try{var t=localStorage.getItem("theme");if(t)document.documentElement.dataset.theme=t}catch(e){}`,
          }}
        />
      </head>
      <body
        className={`${display.variable} ${sans.variable} ${mono.variable} min-h-dvh`}
        style={{
          fontFamily: "var(--font-sans-loaded), var(--font-sans)",
        }}
      >
        <header className="sticky top-0 z-30 border-b backdrop-blur rule"
                style={{ background: "color-mix(in srgb, var(--bg) 88%, transparent)" }}>
          <div className="mx-auto flex max-w-[1400px] items-center gap-4 px-4 py-3 sm:px-6">
            <Link
              href="/"
              className="display text-[15px] tracking-[0.14em]"
              style={{ fontFamily: "var(--font-display-loaded), var(--font-display)" }}
            >
              Card Studio
            </Link>
            <span
              className="num hidden text-[11px] sm:block"
              style={{ color: "var(--muted)" }}
            >
              84.0 &times; 52.0 mm
            </span>
            <nav className="ml-auto flex items-center gap-1 text-[13px]">
              <Link
                href="/gallery"
                className="rounded px-2.5 py-1.5 hover:bg-[var(--shade)]"
              >
                Gallery
              </Link>
              <Link
                href="/studio"
                className="rounded px-2.5 py-1.5 hover:bg-[var(--shade)]"
              >
                Studio
              </Link>
              <ThemeToggle />
            </nav>
          </div>
        </header>
        {children}
        <footer
          className="mt-24 border-t rule px-4 py-8 text-[12px] sm:px-6"
          style={{ color: "var(--muted)" }}
        >
          <div className="mx-auto flex max-w-[1400px] flex-wrap gap-x-6 gap-y-2">
            <span>
              Two filaments, one change. Base 0.6 mm, features 0.4 mm.
            </span>
            <a
              className="underline underline-offset-2 hover:text-[var(--fg)]"
              href="https://github.com/noluyorAbi/printed-business-card"
            >
              Source
            </a>
          </div>
        </footer>
      </body>
    </html>
  );
}
