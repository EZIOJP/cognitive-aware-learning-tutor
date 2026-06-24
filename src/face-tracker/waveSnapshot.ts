import { captureMainAreaPng, uploadSnapshot } from "../api/transcriptsClient";
import { getActiveTranscript } from "./activeTranscript";

/** Capture main study area and append [SNAPSHOT N] to the active transcript file. */
export async function triggerWaveSnapshot(): Promise<string | null> {
  const transcript = getActiveTranscript();
  if (!transcript) return null;

  const blob = await captureMainAreaPng();
  if (!blob) return null;

  const result = await uploadSnapshot(transcript, blob);
  return result.marker;
}
