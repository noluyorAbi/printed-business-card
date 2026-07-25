import type { NextConfig } from "next";

const config: NextConfig = {
  reactStrictMode: true,
  images: {
    // the previews are pre rendered PNGs of a fixed size, so there is nothing
    // for the optimiser to do that the CDN does not already do
    unoptimized: true,
  },
};

export default config;
