import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const ROOT = path.resolve(import.meta.dirname, "../../..");

export function loadStitchApiKey() {
  if (process.env.STITCH_API_KEY?.trim()) {
    return process.env.STITCH_API_KEY.trim();
  }

  const localEnv = path.join(ROOT, ".env.stitch.local");
  if (fs.existsSync(localEnv)) {
    const line = fs
      .readFileSync(localEnv, "utf8")
      .split("\n")
      .find((l) => l.startsWith("STITCH_API_KEY="));
    if (line) {
      const val = line.slice("STITCH_API_KEY=".length).trim().replace(/^["']|["']$/g, "");
      if (val && !val.includes("YOUR_")) return val;
    }
  }

  const cursorMcp = path.join(os.homedir(), ".cursor", "mcp.json");
  if (fs.existsSync(cursorMcp)) {
    try {
      const cfg = JSON.parse(fs.readFileSync(cursorMcp, "utf8"));
      const key = cfg?.mcpServers?.stitch?.headers?.["X-Goog-Api-Key"];
      if (key && typeof key === "string" && !key.includes("YOUR_")) {
        return key.trim();
      }
    } catch {
      /* ignore */
    }
  }

  return null;
}
