import { NextResponse } from "next/server";

import { catalog } from "@/lib/catalog";

export const runtime = "nodejs";
export const dynamic = "force-static";

/** The catalogue ships with the build, so this never touches the worker. */
export function GET() {
  return NextResponse.json(catalog, {
    headers: { "Cache-Control": "public, max-age=3600, s-maxage=86400" },
  });
}
