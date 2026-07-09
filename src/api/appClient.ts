import { resolveApiUrl } from "../utils/resolveBackendUrl";

export type CaltAndroidLatest = {
  app_id: string;
  package: string;
  version_name: string;
  version_code: number;
  release_notes: string;
  size_bytes: number;
  updated_at: string;
  download_url: string;
  filename: string;
};

export function caltAndroidDownloadUrl(): string {
  return resolveApiUrl("/api/app/calt-android/download");
}

export async function fetchCaltAndroidLatest(): Promise<CaltAndroidLatest> {
  const res = await fetch(resolveApiUrl("/api/app/calt-android/latest"));
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(
      typeof data.detail === "string" ? data.detail : `HTTP ${res.status}`,
    );
  }
  return data as CaltAndroidLatest;
}

export function formatApkSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
