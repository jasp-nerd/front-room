// Bundle the component library for pages that load React from a script tag: the design system
// artifact's previews, and any page that isn't built with Vite.
//
//   node scripts/build-bundle.mjs   ->  dist/bundle.js (window.FrontRoom) + dist/bundle.css
//
// CSS modules stay CSS modules: esbuild's local-css loader scopes the class names exactly as Vite does in the
// web app, so one stylesheet per component works in both. SVGs and the drawings are inlined as data URLs so the bundle needs no
// other files, and React comes from the page's React and ReactDOM globals (UMD 18.3.1).

import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { build } from "esbuild";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");

/** Point react, react-dom and the automatic JSX runtime at the page's UMD globals. */
const reactFromGlobals = {
  name: "react-from-globals",
  setup(b) {
    b.onResolve({ filter: /^react(-dom)?(\/.*)?$/ }, (args) => ({ path: args.path, namespace: "globals" }));
    b.onLoad({ filter: /.*/, namespace: "globals" }, (args) => {
      if (args.path === "react/jsx-runtime") {
        return {
          contents: `
            const R = window.React;
            const jsx = (type, props, key) => R.createElement(type, key === undefined ? props : { ...props, key });
            export { jsx, jsx as jsxs };
            export const Fragment = R.Fragment;`,
          loader: "js",
        };
      }
      const global = args.path.startsWith("react-dom") ? "ReactDOM" : "React";
      return { contents: `module.exports = window.${global};`, loader: "js" };
    });
  },
};

await build({
  entryPoints: [join(root, "src/index.ts")],
  outfile: join(root, "dist/bundle.js"),
  bundle: true,
  format: "iife",
  globalName: "FrontRoom",
  platform: "browser",
  target: "es2022",
  jsx: "automatic",
  loader: { ".svg": "dataurl", ".webp": "dataurl", ".png": "dataurl" },
  plugins: [reactFromGlobals],
  // Keep identifiers so scoped class names stay readable (Button_button), and never collide with a host page.
  minifyWhitespace: true,
  minifySyntax: true,
  legalComments: "none",
  logLevel: "info",
});
