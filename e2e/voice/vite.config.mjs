// Bundles e2e/voice/harness (the real voice components) into plain static files for the browser test.
//   node frontend/node_modules/vite/bin/vite.js build --config e2e/voice/vite.config.mjs --outDir <dir>
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const frontend = path.resolve(here, "../../frontend");

export default {
  root: path.join(here, "harness"),
  base: "./",
  // No React plugin: the automatic JSX runtime is enough, and a plugin cannot be resolved from outside frontend/.
  oxc: { jsx: { runtime: "automatic" } },
  resolve: { alias: { "@": frontend } },
  define: { "process.env.NEXT_PUBLIC_API_URL": JSON.stringify(process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"), "process.env.NODE_ENV": JSON.stringify("production") },
  build: { emptyOutDir: true, minify: false, sourcemap: false },
  server: { fs: { allow: [path.resolve(here, "../..")] } },
};
