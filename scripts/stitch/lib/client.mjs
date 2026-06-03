import { Stitch, StitchToolClient } from "@google/stitch-sdk";
import { loadStitchApiKey } from "./apiKey.mjs";

export async function createStitchClient(timeout = 600_000) {
  const apiKey = loadStitchApiKey();
  if (!apiKey) {
    throw new Error(
      "No Stitch API key. Add X-Goog-Api-Key in ~/.cursor/mcp.json or set STITCH_API_KEY."
    );
  }
  const toolClient = new StitchToolClient({ apiKey, timeout });
  await toolClient.connect();
  const stitch = new Stitch(toolClient);
  return { stitch, toolClient };
}
