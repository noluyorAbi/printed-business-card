/**
 * Copy the generator's previews and catalogue into the Next.js public tree.
 *
 * The 163 PNGs live in assets/previews and weigh about 15 MB. Checking a
 * second copy into web/public would double that in git for no reason, so the
 * build makes the copy instead. Runs before dev and before build.
 */

import { cpSync, existsSync, mkdirSync, readdirSync, statSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const web = dirname(here);
const repo = dirname(web);

const from = join(repo, "assets", "previews");
const to = join(web, "public", "previews");

if (!existsSync(from)) {
  console.error(
    `previews missing at ${from}\n` +
      `run: python build_card.py --all`,
  );
  process.exit(1);
}

mkdirSync(to, { recursive: true });
cpSync(from, to, { recursive: true });

const count = readdirSync(to).filter((f) => f.endsWith(".png")).length;
const bytes = readdirSync(to).reduce(
  (sum, f) => sum + statSync(join(to, f)).size,
  0,
);
console.log(`previews: ${count} files, ${(bytes / 1e6).toFixed(1)} MB`);

const catalog = join(web, "data", "catalog.json");
if (!existsSync(catalog)) {
  console.error(
    `catalog missing at ${catalog}\n` +
      `run: python build_card.py --dump-catalog web/data/catalog.json`,
  );
  process.exit(1);
}
