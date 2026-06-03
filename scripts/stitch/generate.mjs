/**
 * Generate Stitch screens from repo prompts (uses API key from env or ~/.cursor/mcp.json).
 * Usage:
 *   node scripts/stitch/generate.mjs life-clock
 *   node scripts/stitch/generate.mjs study-hub
 *   node scripts/stitch/generate.mjs all
 */
import fs from "node:fs";
import path from "node:path";
import { createStitchClient } from "./lib/client.mjs";

const ROOT = path.resolve(import.meta.dirname, "../..");
const OUT_DIR = path.join(ROOT, "docs", "stitch-output");
const PROJECT_TITLE = "Cognitive-Aware Learning Tutor";

const JOBS = {
  "life-clock": {
    name: "Life Clock — 24h infographic",
    promptFile: "docs/STITCH_LIFE_CLOCK_PROMPT.txt",
    deviceType: "DESKTOP",
  },
  "study-hub": {
    name: "Study Hub dashboard shell",
    promptFile: "docs/STITCH_PROMPT.txt",
    deviceType: "DESKTOP",
  },
};

function readPrompt(relPath) {
  const full = path.join(ROOT, relPath);
  if (!fs.existsSync(full)) throw new Error(`Missing prompt file: ${relPath}`);
  return fs.readFileSync(full, "utf8").trim();
}

async function ensureProject(stitch) {
  const projects = await stitch.projects();
  const existing = projects.find((p) => {
    const title = (p.data?.title ?? p.data?.name ?? "").toLowerCase();
    return title.includes("cognitive-aware") || title.includes("study hub");
  });
  if (existing) {
    const title = existing.data?.title ?? existing.data?.name ?? existing.projectId;
    console.log(`Using project: ${title}`);
    return existing;
  }
  console.log(`Creating project: ${PROJECT_TITLE}`);
  return stitch.createProject(PROJECT_TITLE);
}

async function runJob(project, job) {
  const prompt = readPrompt(job.promptFile);
  console.log(`\nGenerating: ${job.name} (${job.deviceType})…`);
  console.log("This can take several minutes on Stitch servers.\n");

  const result = await project.generate(prompt, job.deviceType);
  const screens = result?.screens ?? result?.screen ?? [];
  const list = Array.isArray(screens) ? screens : screens ? [screens] : [];

  return {
    job: job.name,
    promptFile: job.promptFile,
    deviceType: job.deviceType,
    screenIds: list.map((s) => s.id || s.screenId || s.name).filter(Boolean),
    raw: result,
  };
}

async function main() {
  const arg = (process.argv[2] || "life-clock").toLowerCase();
  const { stitch, toolClient } = await createStitchClient(600_000);
  const project = await ensureProject(stitch);

  fs.mkdirSync(OUT_DIR, { recursive: true });

  const keys =
    arg === "all" ? Object.keys(JOBS) : JOBS[arg] ? [arg] : null;
  if (!keys) {
    console.error(`Unknown job "${arg}". Use: ${Object.keys(JOBS).join(", ")}, all`);
    process.exit(1);
  }

  const manifest = {
    generatedAt: new Date().toISOString(),
    projectId: project.projectId || project.id,
    projectTitle: PROJECT_TITLE,
    stitchUrl: "https://stitch.withgoogle.com",
    runs: [],
  };

  for (const key of keys) {
    try {
      const run = await runJob(project, JOBS[key]);
      manifest.runs.push(run);
      console.log(`Done: ${run.job} → screen ids: ${run.screenIds.join(", ") || "(see Stitch UI)"}`);
    } catch (err) {
      console.error(`Failed: ${JOBS[key].name}`, err.message || err);
      manifest.runs.push({ job: JOBS[key].name, error: String(err.message || err) });
    }
  }

  const outPath = path.join(OUT_DIR, `manifest-${Date.now()}.json`);
  fs.writeFileSync(outPath, JSON.stringify(manifest, null, 2));
  console.log(`\nManifest saved: ${outPath}`);
  console.log("Open Stitch to review and export screens.");
  await toolClient.close();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
