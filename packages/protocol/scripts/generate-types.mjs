// Generate src/types.ts from the JSON Schemas. The schemas are the contract; never edit the output by hand.

import { readdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { compileFromFile } from "json-schema-to-typescript";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const schemaDir = join(root, "schema");

const options = {
  cwd: schemaDir,
  bannerComment: "",
  additionalProperties: false,
  declareExternallyReferenced: true,
  style: { semi: true, singleQuote: false },
};

// common.schema.json only holds shared $defs; they are inlined where referenced.
const files = readdirSync(schemaDir).filter((f) => f.endsWith(".schema.json") && f !== "common.schema.json");
const chunks = [];
for (const file of files) {
  chunks.push(await compileFromFile(join(schemaDir, file), options));
}

// Shared definitions are emitted once per schema that references them; keep the first declaration of each.
const seen = new Set();
const declarations = chunks
  .join("\n")
  .split(/\n(?=export )/)
  .filter((block) => {
    const name = block.match(/^export (?:interface|type) (\w+)/)?.[1];
    if (!name || seen.has(name)) return false;
    seen.add(name);
    return true;
  });

const header = "// Generated from packages/protocol/schema by scripts/generate-types.mjs. Do not edit.\n\n";
writeFileSync(join(root, "src", "types.ts"), `${header}${declarations.join("\n").trim()}\n`);
console.log(`wrote src/types.ts (${seen.size} declarations)`);
