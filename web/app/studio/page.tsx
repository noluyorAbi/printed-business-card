import type { Metadata } from "next";

import { StudioClient } from "@/components/studio/StudioClient";

export const metadata: Metadata = {
  title: "Studio · Card Studio",
  description:
    "Put your own name on one of the 163 cards, check it against a 0.2 mm nozzle, and download the print file.",
};

export default function StudioPage() {
  return <StudioClient />;
}
