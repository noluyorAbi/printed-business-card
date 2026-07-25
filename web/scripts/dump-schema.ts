/**
 * Write the CardSpec's JSON Schema, so the Python side can compare it to its
 * own. Keeping two schemas in step by hand is the likeliest way for this
 * project to break; this is how the build notices instead of the user.
 */

import { writeFileSync } from "node:fs";
import { z } from "zod";

import { cardSpecSchema } from "../lib/spec";

const target = process.argv[2] ?? "-";
// "input" is the shape a client actually posts: fields with defaults are
// optional, which is what the Pydantic model says too
const schema = z.toJSONSchema(cardSpecSchema, { io: "input" });
const text = JSON.stringify(schema, null, 2) + "\n";

if (target === "-") process.stdout.write(text);
else writeFileSync(target, text);
