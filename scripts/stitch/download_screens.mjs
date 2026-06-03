/**
 * Download HTML + screenshot for Stitch screens in a project.
 * Usage: node scripts/stitch/download_screens.mjs
 */
import fs from "node:fs";
import path from "node:path";
import { createStitchClient } from "./lib/client.mjs";

const PROJECT_ID = "7612682550096205798";
const PROJECT_SLUG = "cognitive-aware-learning-hub";

const SCREENS = [
  { slug: "01-design-system", id: "asset-stub-assets-65c69257c8314e81b6f7c5addc15f710-1780457292640", title: "Design System" },
  { slug: "02-study-hub-deep-lumina", id: "a658a8887ae5462990c656e50e2e4883", title: "Study Hub - Deep Lumina Dashboard" },
  { slug: "03-study-hub-dark", id: "e132d84de47f49779dfc360fdb4f3255", title: "Study Hub Dashboard (Dark)" },
  { slug: "04-gre-vocab-quiz-light", id: "b646e2d6436e47bd915b6a7dc10ccf52", title: "GRE Vocab Quiz (Light)" },
  { slug: "05-math-practice-dark", id: "cc05dee6385e48ab9cb0ec4baf4a6754", title: "Math Practice (Dark)" },
  { slug: "06-theme-settings-light", id: "ec20606a6d374b6d861acff674a14b6c", title: "Theme Settings (Light)" },
  { slug: "07-study-hub-linear-timeline", id: "cf9eda9f405a4f5ba4f99e9323880793", title: "Study Hub (Linear Bar Timeline)" },
  { slug: "08-study-hub-enhanced-controls", id: "93374bff73334b31a7b87e8698b88064", title: "Study Hub - Enhanced Dashboard with Controls" },
  { slug: "09-life-clock-infographic-spec", id: "6ec2a1ec0a7d497ab4320ea13a8d173d", title: "24-hour Life Clock Infographic Widget Spec" },
  { slug: "10-life-clock-oceanic-aurora", id: "d22db5e27072452d88b70300c785f28d", title: "Life Clock - Oceanic Aurora Variant" },
  { slug: "11-life-clock-midnight-amber", id: "fca1724f9b9a45d2b9b38a51a1b49650", title: "Life Clock - Midnight Amber Variant" },
  { slug: "12-math-practice-deep-lumina", id: "cb152e523c574a46870ddfbc77b77547", title: "Math Practice (Deep Lumina)" },
  { slug: "13-theme-settings-deep-lumina", id: "1d77ee324ab74517a939e95ae40c5c0c", title: "Theme Settings (Deep Lumina)" },
  { slug: "14-gre-vocab-quiz-deep-lumina", id: "57889a52877547839bbf944589498e98", title: "GRE Vocab Quiz (Deep Lumina)" },
];

const ROOT = path.resolve(import.meta.dirname, "../..");
const OUT_ROOT = path.join(ROOT, "docs", "stitch-export", PROJECT_SLUG);

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

async function main() {
  const { stitch, toolClient } = await createStitchClient(300_000);
  const project = stitch.project(PROJECT_ID);

  fs.mkdirSync(OUT_ROOT, { recursive: true });

  const manifest = {
    projectId: PROJECT_ID,
    projectTitle: "Cognitive-Aware Learning Hub",
    exportedAt: new Date().toISOString(),
    outputDir: path.relative(ROOT, OUT_ROOT).replace(/\\/g, "/"),
    screens: [],
  };

  for (const spec of SCREENS) {
    const dir = path.join(OUT_ROOT, spec.slug);
    fs.mkdirSync(dir, { recursive: true });

    const entry = {
      slug: spec.slug,
      title: spec.title,
      screenId: spec.id,
      html: null,
      screenshot: null,
      errors: [],
    };

    console.log(`Fetching: ${spec.title}…`);

    try {
      const screen = project.screen(spec.id);
      const raw = await toolClient.callTool("get_screen", {
        projectId: PROJECT_ID,
        screenId: spec.id,
        name: `projects/${PROJECT_ID}/screens/${spec.id}`,
      });

      fs.writeFileSync(
        path.join(dir, "metadata.json"),
        JSON.stringify(raw, null, 2),
        "utf8"
      );

      const htmlUrl = raw?.htmlCode?.downloadUrl || (await screen.getHtml());
      const imageUrl = raw?.screenshot?.downloadUrl || (await screen.getImage());

      if (htmlUrl) {
        const htmlPath = path.join(dir, "screen.html");
        const isHtml = htmlUrl.includes(".html") || !htmlUrl.match(/\.(png|jpg|webp)/i);
        if (isHtml && htmlUrl.startsWith("http")) {
          await downloadTextUrl(htmlUrl, htmlPath);
        } else if (htmlUrl.startsWith("http")) {
          await downloadUrl(htmlUrl, htmlPath);
        }
        entry.html = path.relative(ROOT, htmlPath).replace(/\\/g, "/");
      }

      if (imageUrl && imageUrl.startsWith("http")) {
        const ext = imageUrl.includes(".png") ? "png" : imageUrl.includes(".webp") ? "webp" : "jpg";
        const imgPath = path.join(dir, `screenshot.${ext}`);
        await downloadUrl(imageUrl, imgPath);
        entry.screenshot = path.relative(ROOT, imgPath).replace(/\\/g, "/");
      }
    } catch (err) {
      entry.errors.push(String(err.message || err));
      console.error(`  Error: ${err.message || err}`);
    }

    manifest.screens.push(entry);
    console.log(`  → ${entry.html ? "html " : ""}${entry.screenshot ? "img " : ""}${entry.errors.length ? "ERR" : "ok"}`);
  }

  fs.writeFileSync(path.join(OUT_ROOT, "index.json"), JSON.stringify(manifest, null, 2));
  console.log(`\nDone. Manifest: ${path.join(OUT_ROOT, "index.json")}`);
  await toolClient.close();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
