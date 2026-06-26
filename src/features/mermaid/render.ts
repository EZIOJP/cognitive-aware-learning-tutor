import mermaid from "mermaid";
import { aggressiveSanitizeMermaidSource, sanitizeMermaidSource } from "./pipeline";

let initialized = false;
let renderChain: Promise<unknown> = Promise.resolve();

const MERMAID_CONSOLE_NOISE = [
  "translate(undefined, NaN)",
  "attribute transform",
  "Syntax error in text",
  "mermaid version",
];

/** Swallow d3/Mermaid DOM noise that still logs even when errors are caught. */
async function withQuietMermaidConsole<T>(fn: () => Promise<T>): Promise<T> {
  const prevError = console.error;
  console.error = (...args: unknown[]) => {
    const msg = args.map((a) => String(a)).join(" ");
    if (MERMAID_CONSOLE_NOISE.some((bit) => msg.includes(bit))) return;
    prevError.apply(console, args);
  };
  try {
    return await fn();
  } finally {
    console.error = prevError;
  }
}

function cleanupMermaidDomArtifacts() {
  document
    .querySelectorAll<HTMLElement>('div[id^="dmermaid-"], div[id^="d3-mermaid-"]')
    .forEach((el) => el.remove());
}

function runSerializedRender<T>(fn: () => Promise<T>): Promise<T> {
  const next = renderChain.then(fn, fn);
  renderChain = next.then(
    () => undefined,
    () => undefined,
  );
  return next;
}

/** Single init for all study-library Mermaid use (render + parse). */
export function ensureMermaidInitialized(): void {
  if (initialized) return;
  mermaid.initialize({
    startOnLoad: false,
    theme: "neutral",
    securityLevel: "strict",
    maxTextSize: 100_000,
    fontFamily: "ui-sans-serif, system-ui, sans-serif",
    logLevel: "fatal",
    suppressErrorRendering: true,
    flowchart: {
      useMaxWidth: true,
      htmlLabels: true,
      curve: "basis",
      padding: 12,
    },
  });
  initialized = true;
}

export function isMermaidErrorSvg(svg: string): boolean {
  return (
    svg.includes("Syntax error in text") ||
    svg.includes('class="error-text"') ||
    svg.includes("error-icon") ||
    /\bNaN\b/.test(svg) ||
    svg.includes("translate(undefined")
  );
}

function friendlyMermaidError(err: unknown): string {
  const msg = err instanceof Error ? err.message : String(err);
  const compact = msg.replace(/\s+/g, " ").trim();
  if (
    compact.includes("NaN") ||
    compact.includes("undefined") ||
    compact.includes("transform") ||
    compact.includes("suitable point")
  ) {
    return "Diagram layout failed — shorten labels or use Fix with AI";
  }
  if (compact.length > 180) return `${compact.slice(0, 180)}…`;
  return compact || "Diagram could not be rendered";
}

/** Parse only (no layout). For issue scanning — does not call render. */
export async function validateMermaidSource(source: string): Promise<string | null> {
  const trimmed = sanitizeMermaidSource(source).trim();
  if (!trimmed) return "Empty diagram source";
  ensureMermaidInitialized();
  try {
    await withQuietMermaidConsole(async () => {
      await mermaid.parse(trimmed, { suppressErrors: false });
    });
    return null;
  } catch (err) {
    return friendlyMermaidError(err);
  }
}

async function renderOnce(diagramId: string, source: string): Promise<string> {
  ensureMermaidInitialized();
  try {
    const { svg } = await mermaid.render(diagramId, source);
    if (isMermaidErrorSvg(svg)) {
      throw new Error("Diagram could not be rendered");
    }
    return svg;
  } finally {
    cleanupMermaidDomArtifacts();
  }
}

/** Render to SVG; retries with aggressive layout sanitize on failure. */
export async function renderMermaidSvg(diagramId: string, source: string): Promise<string> {
  const sanitized = sanitizeMermaidSource(source).trim();
  return runSerializedRender(() =>
    withQuietMermaidConsole(async () => {
      try {
        return await renderOnce(diagramId, sanitized);
      } catch (firstErr) {
        const aggressive = aggressiveSanitizeMermaidSource(sanitized).trim();
        if (aggressive !== sanitized) {
          try {
            return await renderOnce(`${diagramId}-agg`, aggressive);
          } catch {
            /* fall through */
          }
        }
        throw new Error(friendlyMermaidError(firstErr));
      }
    }),
  );
}
