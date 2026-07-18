import mermaid from "mermaid";

let initialized = false;
let renderChain: Promise<unknown> = Promise.resolve();
let runCounter = 0;

/** Allow HMR / config changes to re-initialize Mermaid. */
export function resetMermaidInitialized(): void {
  initialized = false;
}

function runSerialized<T>(fn: () => Promise<T>): Promise<T> {
  const next = renderChain.then(fn, fn);
  renderChain = next.then(
    () => undefined,
    () => undefined,
  );
  return next;
}

/** Single init for all study-library Mermaid use. */
export function ensureMermaidInitialized(): void {
  if (initialized) return;
  mermaid.initialize({
    startOnLoad: false,
    theme: "dark",
    securityLevel: "loose",
    maxTextSize: 100_000,
    fontFamily: "ui-sans-serif, system-ui, sans-serif",
    logLevel: "fatal",
    suppressErrorRendering: true,
    flowchart: {
      useMaxWidth: true,
      htmlLabels: false,
      curve: "basis",
      padding: 12,
    },
    themeVariables: {
      darkMode: true,
      background: "transparent",
      primaryColor: "#16352c",
      primaryTextColor: "#e7f5ef",
      primaryBorderColor: "#3d7a64",
      lineColor: "#8fbc9f",
      secondaryColor: "#1c3f35",
      tertiaryColor: "#102820",
      fontFamily: "ui-sans-serif, system-ui, sans-serif",
    },
  });
  initialized = true;
}

export function isMermaidErrorSvg(svg: string): boolean {
  if (svg.includes("Syntax error in text")) return true;
  if (/<[^>]*\bclass="[^"]*\berror-icon\b[^"]*"/.test(svg)) return true;
  if (/<[^>]*\bclass="[^"]*\berror-text\b[^"]*"/.test(svg)) return true;
  return false;
}

function isCollapsedSvg(svg: SVGSVGElement): boolean {
  const viewBox = svg.getAttribute("viewBox") || "";
  const width = svg.getAttribute("width") || "";
  if (viewBox === "-8 -8 16 16" || width === "16") return true;
  const rect = svg.getBoundingClientRect();
  return rect.width > 0 && rect.width <= 16 && rect.height <= 16;
}

function friendlyMermaidError(err: unknown): string {
  const msg = err instanceof Error ? err.message : String(err);
  const compact = msg.replace(/\s+/g, " ").trim();
  if (compact.length > 180) return `${compact.slice(0, 180)}…`;
  return compact || "Diagram could not be rendered";
}

/** Parse only (no layout). */
export async function validateMermaidSource(source: string): Promise<string | null> {
  const trimmed = source.trim();
  if (!trimmed) return "Empty diagram source";
  ensureMermaidInitialized();
  try {
    await mermaid.parse(trimmed, { suppressErrors: false });
    return null;
  } catch (err) {
    return friendlyMermaidError(err);
  }
}

/**
 * Render Mermaid source into a visible DOM container via mermaid.run().
 * Avoids mermaid.render()'s off-DOM measure path that collapses to 16×16.
 */
export async function renderMermaidInto(container: HTMLElement, source: string): Promise<void> {
  const trimmed = source.trim();
  if (!trimmed) throw new Error("Empty diagram source");

  return runSerialized(async () => {
    ensureMermaidInitialized();
    container.replaceChildren();

    const node = document.createElement("pre");
    node.className = "mermaid";
    node.textContent = trimmed;
    // Unique id helps Mermaid avoid collisions across blocks.
    node.id = `mermaid-live-${++runCounter}`;
    container.appendChild(node);

    try {
      await mermaid.run({ nodes: [node] });
    } catch (err) {
      container.replaceChildren();
      throw new Error(friendlyMermaidError(err));
    }

    const svg = container.querySelector("svg");
    if (!svg) {
      container.replaceChildren();
      throw new Error("Diagram could not be rendered");
    }
    if (isMermaidErrorSvg(svg.outerHTML) || isCollapsedSvg(svg)) {
      container.replaceChildren();
      throw new Error("Diagram layout collapsed — try Fix with AI or simplify labels");
    }

    svg.classList.add("study-mermaid-svg", "size-mermaid");
  });
}

/** @deprecated Prefer renderMermaidInto for Study Library. Kept for any leftover callers. */
export async function renderMermaidSvg(diagramId: string, source: string): Promise<string> {
  const host = document.createElement("div");
  host.style.cssText =
    "position:absolute;left:-99999px;top:0;width:640px;visibility:hidden;pointer-events:none;";
  document.body.appendChild(host);
  try {
    await renderMermaidInto(host, source);
    const svg = host.querySelector("svg");
    if (!svg) throw new Error("Diagram could not be rendered");
    svg.setAttribute("id", diagramId.replace(/[^a-zA-Z0-9_-]/g, "") || "mermaid");
    return svg.outerHTML;
  } finally {
    host.remove();
  }
}

// HMR: drop stale initialize() flags when this module reloads.
resetMermaidInitialized();
