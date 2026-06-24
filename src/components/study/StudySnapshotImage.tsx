import { useEffect, useState } from "react";
import { ImageIcon } from "lucide-react";
import { config } from "../../config";

const TOKEN_KEY = "vocab:auth-token";

function resolveFetchUrl(src: string): string {
  const trimmed = src.trim();
  if (trimmed.startsWith("http://") || trimmed.startsWith("https://")) {
    return trimmed;
  }
  const base = config.backend.apiUrl.replace(/\/$/, "");
  if (trimmed.startsWith("/")) {
    return `${base}${trimmed}`;
  }
  return `${base}/${trimmed}`;
}

function isSnapshotUrl(src: string): boolean {
  return src.includes("/api/transcripts/snapshots/");
}

type StudySnapshotImageProps = {
  src?: string;
  alt?: string;
};

/** Loads slide PNGs with JWT — plain img tags cannot send Authorization. */
export function StudySnapshotImage({ src, alt }: StudySnapshotImageProps) {
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!src) {
      setFailed(true);
      return;
    }

    let revoked = false;
    let objectUrl: string | null = null;

    const load = async () => {
      try {
        const headers: Record<string, string> = {};
        const token = localStorage.getItem(TOKEN_KEY);
        if (token) headers.Authorization = `Bearer ${token}`;

        const res = await fetch(resolveFetchUrl(src), { headers });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);

        const blob = await res.blob();
        objectUrl = URL.createObjectURL(blob);
        if (!revoked) {
          setBlobUrl(objectUrl);
          setFailed(false);
        }
      } catch {
        if (!revoked) setFailed(true);
      }
    };

    void load();

    return () => {
      revoked = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [src]);

  if (failed) {
    return (
      <span className="my-3 block rounded-lg border border-dashed border-border/60 bg-muted/20 px-3 py-4 text-center text-xs text-muted-foreground">
        {alt ?? "Slide"} unavailable — sign in and ensure the snapshot file exists.
      </span>
    );
  }

  if (!blobUrl) {
    return (
      <span
        className="my-3 block h-32 animate-pulse rounded-lg border border-border/40 bg-muted/30"
        aria-label="Loading slide"
      />
    );
  }

  return (
    <img
      src={blobUrl}
      alt={alt ?? "Lecture slide"}
      className="my-3 max-w-full rounded-lg border border-border/50 shadow-sm"
      loading="lazy"
    />
  );
}

export function StudyMarkdownImage({ src, alt }: StudySnapshotImageProps) {
  const isPlaceholder =
    !src ||
    src === "placeholder" ||
    src.startsWith("placeholder:") ||
    src.includes("placeholder.com");

  if (isPlaceholder) {
    return (
      <figure className="study-image-placeholder my-4">
        <div className="flex flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed border-emerald-600/40 bg-emerald-950/30 px-6 py-10 text-center">
          <ImageIcon className="h-8 w-8 text-emerald-500/50" aria-hidden />
          <p className="text-sm font-medium text-emerald-200/80">Image placeholder</p>
          <p className="text-[11px] text-muted-foreground max-w-sm">
            Edit this note and replace{" "}
            <code className="rounded bg-black/30 px-1 py-0.5 font-mono text-[10px]">placeholder:image</code> with a URL
            or use Insert → Slide for lecture snapshots.
          </p>
        </div>
        {alt && alt !== "Describe this image" && (
          <figcaption className="mt-2 text-center text-xs text-muted-foreground italic">{alt}</figcaption>
        )}
      </figure>
    );
  }

  if (src && isSnapshotUrl(src)) {
    return <StudySnapshotImage src={src} alt={alt} />;
  }

  const resolved = src ? resolveFetchUrl(src) : "";
  if (!resolved) return null;

  return (
    <img
      src={resolved}
      alt={alt ?? ""}
      className="my-3 max-w-full rounded-lg border border-border/50"
      loading="lazy"
    />
  );
}
