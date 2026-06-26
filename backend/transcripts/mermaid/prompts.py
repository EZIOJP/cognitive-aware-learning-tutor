"""Mermaid LLM prompts for note generation and block regeneration."""

MERMAID_GENERATION_RULES = """

Mermaid syntax (strict — diagrams must render without errors):
- Start every diagram with `flowchart TD` or `flowchart LR` on the first line.
- One node or edge per line; use simple node IDs (A, B, step1) — no braces in IDs (never `n_{-1}`).
- Node labels with parentheses, brackets [i], ampersands, colons, arrows, or function calls MUST use quoted rectangles: id["label text"].
- Never use stadium syntax id(label) — always id["label"] instead (e.g. B["np.all"], not B(np.all)).
- Edge labels MUST use pipe form only: A -->|Yes| B or A -->|No (Blank)| B — never `A -- text --> B`.
- Never merge sources with ampersand: not `F & G --> H` — use two lines: F --> H and G --> H.
- Do not put colons after unquoted ] labels (wrong: P[Title]: text — use P["Title: text"]).
- Do not use malformed pipe edges like `-->|: label :|` — use `-->|label|`.
- Prefer short subgraph titles without special characters; avoid colons inside subgraph names.
- Diamond decision nodes: use id{Question?} without parentheses inside — or id["Question?"] if punctuation is needed.
- Layout: keep node labels under 40 characters; edge labels under 14 characters.
- Never use ellipsis `...` in labels — write "etc" instead (ellipsis breaks Mermaid layout).
- Inside labels write "index -1" or "len-1" — never W[-1] or W[len-1] (breaks layout).
- Prefer short edge labels: |L to R| not |Left to Right|.
- Diamond nodes use braces without inner quotes: B{Direction} — never B{"Direction"}.
- Output ONLY the diagram source. No reasoning, no explanation, no markdown fences.
- Output EXACTLY ONE diagram. Never repeat the flowchart/graph header. Stop immediately after the final edge line.

""".strip()

MERMAID_SYSTEM_PROMPT = """
You are a strict Mermaid.js code generator.
Output EXACTLY ONE valid Mermaid diagram.
Do not include any explanations, reasoning, or conversational preamble.
Do not wrap your output in markdown code fences (```mermaid).
End your response immediately after the final diagram node or edge.
""".strip()
