import { defineConfig } from "vite";
import path from "path";
import fs from "fs";
import { fileURLToPath } from "url";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const frontendRoot = __dirname;
const repoRoot = path.resolve(__dirname, "../..");
const srcRoot = path.join(repoRoot, "src");

/**
 * Lean Focus SPA — http://127.0.0.1:5180/
 * Entry: calt-focus/frontend/ (no Study plugins / mermaid graph).
 * Shared productivity code: repo src/ via @ alias.
 */
function caltDataMiddleware() {
  return {
    name: "calt-data-middleware",
    configureServer(server) {
      const serveRoot = (urlPrefix, absDir) => {
        server.middlewares.use((req, res, next) => {
          const url = (req.url || "").split("?")[0];
          if (!url.startsWith(urlPrefix)) return next();
          const rel = decodeURIComponent(url.slice(urlPrefix.length) || "");
          if (!rel || rel.includes("..")) {
            res.statusCode = 400;
            res.end("bad path");
            return;
          }
          const file = path.resolve(absDir, rel);
          if (!file.startsWith(absDir + path.sep) && file !== absDir) {
            res.statusCode = 400;
            res.end("bad path");
            return;
          }
          fs.readFile(file, (err, buf) => {
            if (err) {
              res.statusCode = 404;
              res.end("missing");
              return;
            }
            const ct = file.endsWith(".json")
              ? "application/json; charset=utf-8"
              : "application/octet-stream";
            res.setHeader("Content-Type", ct);
            res.setHeader(
              "Cache-Control",
              file.includes("structured") ? "public, max-age=3600" : "no-store",
            );
            res.end(buf);
          });
        });
      };
      // Live enforcer writes live in the standalone calt-focus repo. Study's
      // copy of data/ is a stale snapshot and hides today's blocks.
      const liveRoot = path.resolve(repoRoot, "..", "calt-focus", "data", "productivity");
      const dataRoot = fs.existsSync(path.join(liveRoot, "behavior"))
        ? liveRoot
        : path.join(repoRoot, "data", "productivity");
      serveRoot("/calt-data/", path.join(dataRoot, "behavior"));
      serveRoot("/calt-bible/", path.join(dataRoot, "bible"));
      // Math → ML offline SPA (same tree Focus maps as https://calt-learn.app)
      const learnRoot = path.resolve(repoRoot, "..", "calt-focus", "frontend", "jp-roadmap");
      const learnFallback = path.join(repoRoot, "frontend", "jp-roadmap");
      const learnDir = fs.existsSync(path.join(learnRoot, "index.html"))
        ? learnRoot
        : learnFallback;
      server.middlewares.use((req, res, next) => {
        const url = (req.url || "").split("?")[0];
        if (!url.startsWith("/calt-learn/")) return next();
        const rel = decodeURIComponent(url.slice("/calt-learn/".length) || "index.html");
        if (!rel || rel.includes("..")) {
          res.statusCode = 400;
          res.end("bad path");
          return;
        }
        const file = path.resolve(learnDir, rel || "index.html");
        if (!file.startsWith(learnDir + path.sep) && file !== learnDir) {
          res.statusCode = 400;
          res.end("bad path");
          return;
        }
        fs.readFile(file, (err, buf) => {
          if (err) {
            res.statusCode = 404;
            res.end("missing");
            return;
          }
          let ct = "application/octet-stream";
          if (file.endsWith(".html")) ct = "text/html; charset=utf-8";
          else if (file.endsWith(".js")) ct = "text/javascript; charset=utf-8";
          else if (file.endsWith(".css")) ct = "text/css; charset=utf-8";
          else if (file.endsWith(".json")) ct = "application/json; charset=utf-8";
          else if (file.endsWith(".svg")) ct = "image/svg+xml";
          else if (file.endsWith(".png")) ct = "image/png";
          else if (file.endsWith(".woff2")) ct = "font/woff2";
          res.setHeader("Content-Type", ct);
          res.setHeader("Cache-Control", "no-store");
          res.end(buf);
        });
      });
    },
  };
}

function figmaAssetResolver() {
  return {
    name: "figma-asset-resolver",
    resolveId(id) {
      if (id.startsWith("figma:asset/")) {
        return path.resolve(srcRoot, "assets", id.replace("figma:asset/", ""));
      }
    },
  };
}

export default defineConfig({
  root: frontendRoot,
  publicDir: path.join(repoRoot, "public"),
  server: {
    host: "127.0.0.1",
    port: 5180,
    strictPort: true,
    fs: {
      allow: [repoRoot],
    },
    preTransformRequests: false,
    watch: {
      ignored: [
        "**/dist-focus/**",
        "**/dist/**",
        "**/data/**",
        "**/calt-focus/backend/**/build/**",
        "**/native/**",
        "**/.tmp*/**",
        "**/.pytest_cache/**",
        "**/.superpowers/**",
        "**/calt-focus/extensions/**",
        "**/node_modules/**",
      ],
    },
  },
  build: {
    outDir: path.join(repoRoot, "dist-focus"),
    emptyOutDir: true,
    rollupOptions: {
      input: path.join(frontendRoot, "index.html"),
    },
  },
  optimizeDeps: {
    exclude: ["pyodide", "mermaid", "katex", "cytoscape", "react-super-mermaid"],
    holdUntilCrawlEnd: false,
  },
  plugins: [figmaAssetResolver(), caltDataMiddleware(), react(), tailwindcss()],
  resolve: {
    alias: { "@": srcRoot },
  },
  assetsInclude: ["**/*.svg", "**/*.csv"],
});
