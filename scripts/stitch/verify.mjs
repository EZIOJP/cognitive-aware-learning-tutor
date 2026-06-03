import { createStitchClient } from "./lib/client.mjs";

try {
  const { stitch, toolClient } = await createStitchClient(120_000);
  const projects = await stitch.projects();
  console.log("OK: Stitch API connected");
  console.log(`Projects: ${projects.length}`);
  for (const p of projects.slice(0, 8)) {
    const title = p.data?.title ?? p.data?.name ?? p.projectId ?? p.id;
    console.log(`  - ${title}`);
  }
  await toolClient.close();
} catch (err) {
  console.error("FAIL:", err.message || err);
  process.exit(1);
}
