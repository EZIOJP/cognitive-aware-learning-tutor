/**
 * Download HTML + screenshot for Stitch screens.
 * Usage:
 *   node scripts/stitch/download_project.mjs <projectId> <projectSlug> <screenId> <screenSlug> [screenTitle]
 *
 * Example:
 *   node scripts/stitch/download_project.mjs 1712560460820716 lemillion-phasing-motivator e3291ec7086c463893ddead2f6a76c35 lemillion-animated-assistant-pro "Lemillion Animated Assistant - Pro Edition"
 */
import fs from "node:fs";
import path from "node:path";
import { createStitchClient } from "./lib/client.mjs";

const ROOT = path.resolve(import.meta.dirname, "../..");

async function downloadUrl(url, destPath) {
  if (!url) return false;
  const res = await fetch(url, { redirect: "follow" });
  if (!res.ok) throw new Error(`HTTP ${res.status} for ${destPath}`);
  const buf = Buffer.from(await res.arrayBuffer());
  fs.mkdirSync(path.dirname(destPath), { recursive: true });
  fs.writeFileSync(destPath, buf);
  return true;
}

async function downloadTextUrl(url, destPath) {
  if (!url) return false;
  const res = await fetch(url, { redirect: "follow" });
  if (!res.ok) throw new Error(`HTTP ${res.status} for ${destPath}`);
  const text = await res.text();
  fs.mkdirSync(path.dirname(destPath), { recursive: true });
  fs.writeFileSync(destPath, text, "utf8");
  return true;
}

async function downloadScreen({ projectId, projectSlug, projectTitle, screen }) {
  const { stitch, toolClient } = await createStitchClient(300_000);
  const OUT_ROOT = path.join(ROOT, "docs", "stitch-export", projectSlug);
  const dir = path.join(OUT_ROOT, screen.slug);
  fs.mkdirSync(dir, { recursive: true });

  const entry = {
    projectId,
    projectTitle,
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
      if (isHtml) {
        await downloadTextUrl(htmlUrl, htmlPath);
      } else {
        await downloadUrl(htmlUrl, htmlPath);
      }
      entry.html = path.relative(ROOT, htmlPath).replace(/\\/g, "/");
    }

    if (imageUrl?.startsWith("http")) {
      const ext = imageUrl.includes(".png") ? "png" : imageUrl.includes(".webp") ? "webp" : "jpg";
      const imgPath = path.join(dir, `screenshot.${ext}`);
      await downloadUrl(imageUrl, imgPath);
      entry.screenshot = path.relative(ROOT, imgPath).replace(/\\/g, "/");
    }
  } catch (err) {
    entry.errors.push(String(err.message || err));
    console.error(`  Error: ${err.message || err}`);
  }

  const manifestPath = path.join(OUT_ROOT, "index.json");
  let manifest = {
    projectId,
    projectTitle,
    exportedAt: new Date().toISOString(),
    outputDir: path.relative(ROOT, OUT_ROOT).replace(/\\/g, "/"),
    screens: [],
  };
  if (fs.existsSync(manifestPath)) {
    try {
      manifest = JSON.parse(fs.readFileSync(manifestPath, "utf8"));
    } catch {
      /* fresh manifest */
    }
  }
  manifest.exportedAt = new Date().toISOString();
  manifest.screens = manifest.screens.filter((s) => s.screenId !== screen.id);
  manifest.screens.push(entry);
  fs.mkdirSync(OUT_ROOT, { recursive: true });
  fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2));

  console.log(`  → html: ${entry.html || "—"}  screenshot: ${entry.screenshot || "—"}`);
  if (entry.errors.length) console.log(`  → errors: ${entry.errors.join("; ")}`);
  console.log(`\nDone. Output: ${path.relative(ROOT, dir)}`);
  console.log(`Manifest: ${path.relative(ROOT, manifestPath)}`);

  await toolClient.close();
  return entry;
}

const [projectId, projectSlug, screenId, screenSlug, ...titleParts] = process.argv.slice(2);
if (!projectId || !projectSlug || !screenId || !screenSlug) {
  console.error(
    "Usage: node download_project.mjs <projectId> <projectSlug> <screenId> <screenSlug> [title]"
  );
  process.exit(1);
}

const screenTitle = titleParts.join(" ") || screenSlug;

downloadScreen({
  projectId,
  projectSlug,
  projectTitle: projectSlug.replace(/-/g, " "),
  screen: { id: screenId, slug: screenSlug, title: screenTitle },
}).catch((err) => {
  console.error(err);
  process.exit(1);
});
