import type { Metadata } from "next";

import { StudioClient } from "@/components/studio/StudioClient";

export const metadata: Metadata = {
  title: "Studio · Card Studio",
  description:
    "Setz deinen Namen auf eine der 163 Karten, pruef sie gegen eine 0.2 mm Duese und lade die Druckdatei.",
};

export default function StudioPage() {
  return <StudioClient />;
}
