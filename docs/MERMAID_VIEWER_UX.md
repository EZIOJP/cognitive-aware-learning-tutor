# Mermaid viewer UX — zoom, fonts, and limits

**Route:** `/lecture-notes` · **Updated:** 2026-09-02  
**Related:** [MERMAID_RENDER_AND_REGEN_HANDOFF.md](./MERMAID_RENDER_AND_REGEN_HANDOFF.md)

---

## What shipped (2026-09-02)

| Feature | Where | Purpose |
|---------|-------|---------|
| **Zoom controls** | Mermaid block toolbar | − / + / Fit / Reset (40%–300%) |
| **Pan** | Diagram viewport | Drag to move when zoomed |
| **Ctrl+scroll zoom** | Diagram viewport | Pinch-style zoom on trackpad |
| **Text size S/M/L** | Toolbar (Type icon) | Re-renders with 11px / 13px / 15px labels; persisted in `localStorage` |
| **Init defaults** | `src/features/mermaid/render.ts` | Smaller default font, wider node spacing, `useMaxWidth: false` |
| **CSS** | `study-library.css` | Natural SVG width (no forced 42rem shrink) |

---

## How to use

1. Open a note with ` ```mermaid ` blocks on **Lecture Notes**.
2. **Fit** — scale diagram to the block width (good first step for wide flowcharts).
3. **− / +** — fine-tune scale; percentage shown between buttons.
4. **S / M / L** (Type icon) — cycle label font size; triggers re-render for all blocks using that preference.
5. **Drag** the diagram to pan when zoomed in.
6. **Ctrl+scroll** (or Cmd+scroll on Mac) over the diagram to zoom.

Edit mode hides zoom/font controls; preview stays live while editing source.

---

## Root causes (why diagrams looked misaligned)

1. **Double scaling** — Mermaid `useMaxWidth: true` fit the graph to a width, then CSS forced `width: 100%; max-width: 42rem`, shrinking boxes while label font sizes stayed fixed → text looked oversized in small nodes.
2. **No viewer controls** — layout is computed by Mermaid’s dagre engine; the only adjustment was editing source or AI fix.
3. **Default font** — Mermaid’s implicit ~16px labels are large for dense lecture flowcharts.
4. **Not a WYSIWYG editor** — Mermaid is text → SVG; node positions are automatic, not draggable handles.

---

## Limitations vs a graphical editor

| Need | This app | Full graphical editor (e.g. draw.io, Figma, Mermaid Live “visual”) |
|------|----------|---------------------------------------------------------------------|
| Drag nodes | No — edit `flowchart` source | Yes |
| Resize one box | No — shorten labels or adjust graph direction | Yes |
| Persist zoom per note | No — zoom/pan reset when source or font changes | Often yes |
| Export WYSIWYG layout | PNG export uses CLI defaults, not viewer zoom | Matches canvas |
| Fix broken syntax | **Fix with AI** + local sanitize | Manual |

**Practical workflow today:** use **Fit** + zoom for reading; use **Edit** / **Fix with AI** for structure; use **S/M/L** if labels feel cramped or oversized after Fit.

---

## Bigger-lift options (not implemented)

1. **Mermaid Chart editor embed** — hosted visual editor + export back to fence (license, sync, offline).
2. **ELK layout + `%%{init}%%` per block** — frontmatter in each fence for diagram-specific spacing (needs parser + save path).
3. **SVG post-process** — expose selected node labels for inline edit (fragile across Mermaid versions).
4. **Server PNG inline** — `mermaid_render.py` / `mmdc` with same theme JSON as browser for PDF/export parity.
5. **Per-note zoom persistence** — store scale in note metadata or sidecar JSON.

---

## Code map

| File | Role |
|------|------|
| `src/features/mermaid/render.ts` | `mermaid.initialize`, font size API, `renderMermaidInto` |
| `src/features/mermaid/MermaidBlockView.tsx` | Block UI, toolbar controls, viewport |
| `src/features/mermaid/MermaidDiagramViewport.tsx` | Pan/zoom hook + control buttons |
| `src/components/study/MermaidBlockShell.tsx` | Edit/regenerate shell |
| `src/styles/study-library.css` | Viewport + SVG sizing |
