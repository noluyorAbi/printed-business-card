import { defineConfig } from "vitest/config";

/**
 * Unit tests only. `e2e/` is Playwright's, and its files end in .spec.ts too,
 * so without this vitest picks them up and fails on the first page.goto.
 */
export default defineConfig({
  test: {
    include: ["lib/**/*.test.ts", "components/**/*.test.tsx"],
    exclude: ["e2e/**", "node_modules/**", ".next/**"],
  },
});
