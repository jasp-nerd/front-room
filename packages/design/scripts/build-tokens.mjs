// Compile tokens.json into tokens.css: one custom property per token, a class per type style,
// and @font-face for every font. tokens.json is the single source; never edit tokens.css by hand.
//
//   node scripts/build-tokens.mjs [--out dist/tokens.css] [--font-base fonts/]

import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { parseArgs } from "node:util";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const { values: args } = parseArgs({
  options: {
    out: { type: "string", default: "dist/tokens.css" },
    "font-base": { type: "string", default: "../fonts/" },
  },
});

const tokens = JSON.parse(readFileSync(join(root, "tokens.json"), "utf8"));
const themes = tokens.color.themes.map((t) => t.id);
const [firstTheme] = themes;

const cssValue = (value) => value.replace(/^\{(.+)\}$/, "var(--$1)");
const valueFor = (token, theme) =>
  typeof token.value === "string" ? token.value : (token.value[theme] ?? token.value[firstTheme]);

// Families that change per theme (colour, shadow) and families that don't (everything else).
const themed = [...tokens.color.tokens, ...(tokens.shadow?.tokens ?? [])];
const plainFamilies = Object.entries(tokens).filter(
  ([key, family]) =>
    !["name", "version", "color", "type", "shadow"].includes(key) && Array.isArray(family?.tokens),
);

function themeBlock(selector, theme, onlyChanged) {
  const lines = themed
    .filter((t) => !onlyChanged || valueFor(t, theme) !== valueFor(t, firstTheme))
    .map((t) => `  --${t.name}: ${cssValue(valueFor(t, theme))};`);
  const scheme = theme === "day" ? "light" : "dark";
  return `${selector} {\n  color-scheme: ${scheme};\n${lines.join("\n")}\n}`;
}

function staticBlock() {
  const lines = plainFamilies.flatMap(([, family]) => family.tokens.map((t) => `  --${t.name}: ${t.value};`));
  const fonts = Object.entries(tokens.type.families).map(([key, stack]) => `  --font-${key}: ${stack};`);
  return `:root {\n${[...lines, ...fonts].join("\n")}\n}`;
}

function typeClasses() {
  return tokens.type.groups
    .flatMap((group) =>
      group.styles.map((style) => {
        const family = style.family ?? group.family;
        const decls = [
          `font-family: var(--font-${family});`,
          `font-size: ${style.fontSize};`,
          `line-height: ${style.lineHeight};`,
          `font-weight: ${style.fontWeight};`,
          style.letterSpacing ? `letter-spacing: ${style.letterSpacing};` : null,
        ].filter(Boolean);
        return `.${style.name} {\n  ${decls.join("\n  ")}\n}`;
      }),
    )
    .join("\n\n");
}

function fontFaces() {
  return tokens.type.fonts
    .map((font) => {
      const file = font.file.replace(/^fonts\//, "");
      return [
        "@font-face {",
        `  font-family: "${font.family}";`,
        `  src: url("${args["font-base"]}${file}") format("woff2");`,
        `  font-weight: ${font.weight};`,
        ...(font.unicodeRange ? [`  unicode-range: ${font.unicodeRange};`] : []),
        "  font-display: swap;",
        "}",
      ].join("\n");
    })
    .join("\n\n");
}

const css = [
  `/* ${tokens.name} — generated from tokens.json */`,
  fontFaces(),
  themeBlock(`:root, [data-theme="${firstTheme}"]`, firstTheme, false),
  ...themes.slice(1).map((theme) => themeBlock(`[data-theme="${theme}"]`, theme, true)),
  staticBlock(),
  typeClasses(),
].join("\n\n");

const out = join(root, args.out);
mkdirSync(dirname(out), { recursive: true });
writeFileSync(out, `${css}\n`);
console.log(`wrote ${args.out}`);
