// Assemble the folder that is published as the Front Room design system artifact.
// Everything comes from this package: tokens.json, BRAND.md, the fonts, the component bundle and previews.
//
//   node scripts/build-artifact.mjs            -> .artifact/project/...
//
// The asset records (logos uploaded to the artifact's store) live in src/artifact/assets.json.

import { execFileSync } from "node:child_process";
import {
  cpSync,
  existsSync,
  mkdirSync,
  readdirSync,
  readFileSync,
  rmSync,
  statSync,
  writeFileSync,
} from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const out = join(root, ".artifact", "project");
const src = (...p) => join(root, ...p);

rmSync(join(root, ".artifact"), { recursive: true, force: true });
mkdirSync(out, { recursive: true });

// Tokens, compiled the way the artifact page expects (fonts next to tokens.css).
cpSync(src("tokens.json"), join(out, "tokens.json"));
execFileSync(
  "node",
  [src("scripts/build-tokens.mjs"), "--out", ".artifact/project/tokens.css", "--font-base", "fonts/"],
  {
    cwd: root,
    stdio: "inherit",
  },
);

// The brand book is the README every reader starts from.
cpSync(src("BRAND.md"), join(out, "README.md"));

for (const file of readdirSync(src("fonts")).filter((f) => f.endsWith(".woff2"))) {
  mkdirSync(join(out, "fonts"), { recursive: true });
  cpSync(src("fonts", file), join(out, "fonts", file));
}

// Brand files, under assets/: the same files that are uploaded to the artifact's asset store.
const assets = JSON.parse(readFileSync(src("src/artifact/assets.json"), "utf8"));
for (const [group, spec] of Object.entries(assets.groups)) {
  mkdirSync(join(out, "assets", group), { recursive: true });
  for (const f of spec.files) cpSync(src(spec.dir, f.name), join(out, "assets", group, f.name));
}
cpSync(src("src/artifact/logos-readme.md"), join(out, "assets", "Logos", "README.md"));

// Component bundle (`node scripts/build-bundle.mjs`) and each component's preview and README.
const dist = src("dist");
for (const file of ["bundle.js", "bundle.css"]) {
  if (existsSync(join(dist, file))) {
    mkdirSync(join(out, "components"), { recursive: true });
    cpSync(join(dist, file), join(out, "components", file));
  }
}
const previews = src("src/components");
for (const name of existsSync(previews) ? readdirSync(previews) : []) {
  const dir = join(previews, name);
  if (!statSync(dir).isDirectory()) continue;
  for (const file of ["preview.html", "README.md"]) {
    if (existsSync(join(dir, file))) {
      mkdirSync(join(out, "components", name), { recursive: true });
      cpSync(join(dir, file), join(out, "components", name, file));
    }
  }
}
mkdirSync(join(out, "components", "Cover"), { recursive: true });
cpSync(src("src/artifact/cover.html"), join(out, "components", "Cover", "preview.html"));

const mediaTypes = {
  ".jpg": "image/jpeg",
  ".png": "image/png",
  ".webp": "image/webp",
  ".svg": "image/svg+xml",
};
const mediaType = (name) => mediaTypes[name.slice(name.lastIndexOf("."))];

// The index. Written last when publishing; its asset records point at uploads already in the store.
const assetGroups = Object.fromEntries(
  Object.entries(assets.groups).map(([group, spec]) => [
    group,
    {
      name: group,
      tile: spec.tile,
      order: spec.files.map((f) => f.name),
      files: Object.fromEntries(
        spec.files.map((f) => {
          const size = statSync(src(spec.dir, f.name)).size;
          return [f.name, { name: f.name, blob: f.blob, size, type: mediaType(f.name) }];
        }),
      ),
    },
  ]),
);

const createdAt = process.env.DS_CREATED_AT ?? new Date().toISOString();
const index = {
  v: 3,
  layout: "files",
  createdOnFiles: { v: 1, at: createdAt },
  title: "Front Room",
  namespace: "FrontRoom",
  libraries: existsSync(join(dist, "bundle.js"))
    ? [
        { name: "react", version: "18" },
        { name: "react-dom", version: "18" },
      ]
    : [],
  sections: {},
  groups: Object.keys(assetGroups),
  assetGroups,
  blobs: {},
  docs: { readme: "project/README.md", sections: [] },
  lastChange: {
    by: "Front Room",
    at: new Date().toISOString(),
    via: "scripts/build-artifact.mjs",
    note: process.env.DS_NOTE ?? "Build from packages/design",
  },
};
writeFileSync(join(out, "design-system.json"), `${JSON.stringify(index, null, 2)}\n`);

const listFiles = (dir, base = "") =>
  readdirSync(dir).flatMap((f) =>
    statSync(join(dir, f)).isDirectory() ? listFiles(join(dir, f), `${base}${f}/`) : [`${base}${f}`],
  );
console.log(
  listFiles(out)
    .map((f) => `project/${f}`)
    .join("\n"),
);
