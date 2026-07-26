import type { Metadata } from "next";

import { Gallery } from "@/components/gallery/Gallery";
import { catalog } from "@/lib/catalog";

export const metadata: Metadata = {
  title: "Gallery · Card Studio",
  description: `All ${catalog.styles.length} card designs, filterable by category and searchable.`,
};

export default function GalleryPage() {
  return <Gallery />;
}
