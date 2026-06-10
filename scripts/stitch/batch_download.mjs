/**
 * Batch-download Stitch screens from a JSON config.
 * Usage: node scripts/stitch/batch_download.mjs <config.json>
 */
import fs from "node:fs";
import path from "node:path";
import { createStitchClient } from "./lib/client.mjs";

const ROOT = path.resolve(import.meta.dirname, "../..");

async function downloadUrl(url, destPath) {
  const res = await fetch(url, { redirect: "follow" });
  if (!res.ok) throw new Error(`HTTP ${res.status} for ${destPath}`);
  fs.mkdirSync(path.dirname(destPath), { recursive: true });
  fs.writeFileSync(destPath, Buffer.from(await res.arrayBuffer()));
}

async function downloadTextUrl(url, destPath) {
  const res = await fetch(url, { redirect: "follow" });
  if (!res.ok) throw new Error(`HTTP ${res.status} for ${destPath}`);
  fs.mkdirSync(path.dirname(destPath), { recursive: true });
  fs.writeFileSync(destPath, await res.text(), "utf8");
}

async function fetchScreen(toolClient, stitch, projectId, screen) {
  const dir = screen._dir;
  const entry = {
    slug: screen.slug,
    title: screen.title,
    screenId: screen.id,
    html: null,
    screenshot: null,
    htmlUrl: null,
    screenshotUrl: null,
    errors: [],
  };

  console.log(`Fetching: ${screen.title}…`);

  try {
    const project = stitch.project(projectId);
    const stitchScreen = project.screen(screen.id);
    const raw = await toolClient.callTool("get_screen", {
      projectId,
      screenId: screen.id,
      name: `projects/${projectId}/screens/${screen.id}`,
    });

    fs.writeFileSync(path.join(dir, "metadata.json"), JSON.stringify(raw, null, 2), "utf8");

    const htmlUrl = raw?.htmlCode?.downloadUrl || (await stitchScreen.getHtml());
    const imageUrl = raw?.screenshot?.downloadUrl || (await stitchScreen.getImage());
    entry.htmlUrl = htmlUrl || null;
    entry.screenshotUrl = imageUrl || null;

    if (htmlUrl?.startsWith("http")) {
      const htmlPath = path.join(dir, "screen.html");
      const isHtml = htmlUrl.includes(".html") || !htmlUrl.match(/\.(png|jpg|webp)/i);
      if (isHtml) await downloadTextUrl(htmlUrl, htmlPath);
      else await downloadUrl(htmlUrl, htmlPath);
      entry.html = path.relative(ROOT, htmlPath).replace(/\\/g, "/");
    }

    if (imageUrl?.startsWith("http")) {
      const ext = imageUrl.includes(".png") ? "png" : imageUrl.includes(".webp") ? "webp" : "jpg";
      const imgPath = path.join(dir, `screenshot.${ext}`);
      await downloadUrl(imageUrl, imgPath);
      entry.screenshot = path.relative(ROOT, imgPath).replace(/\\/g, "/");
    }

    console.log(`  → ${entry.html ? "html " : ""}${entry.screenshot ? "img " : ""}ok`);
  } catch (err) {
    entry.errors.push(String(err.message || err));
    console.error(`  Error: ${err.message || err}`);
  }

  return entry;
}

async function main() {
  const configPath = process.argv[2];
  if (!configPath) {
    console.error("Usage: node batch_download.mjs <config.json>");
    process.exit(1);
  }

  const config = JSON.parse(fs.readFileSync(path.resolve(configPath), "utf8"));
  const { projectId, projectSlug, projectTitle, screens } = config;
  const OUT_ROOT = path.join(ROOT, "docs", "stitch-export", projectSlug);
  fs.mkdirSync(OUT_ROOT, { recursive: true });

  const { stitch, toolClient } = await createStitchClient(300_000);
  const results = [];

  for (const spec of screens) {
    const dir = path.join(OUT_ROOT, spec.slug);
    fs.mkdirSync(dir, { recursive: true });
    results.push(
      await fetchScreen(toolClient, stitch, projectId, { ...spec, _dir: dir })
    );
  }

  const manifest = {
    projectId,
    projectTitle,
    exportedAt: new Date().toISOString(),
    outputDir: path.relative(ROOT, OUT_ROOT).replace(/\\/g, "/"),
    note: config.note || null,
    screens: results,
  };

  const manifestPath = path.join(OUT_ROOT, "index.json");
  fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2));
  console.log(`\nDone — ${results.filter((r) => !r.errors.length).length}/${results.length} screens`);
  console.log(`Manifest: ${path.relative(ROOT, manifestPath)}`);

  await toolClient.close();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
