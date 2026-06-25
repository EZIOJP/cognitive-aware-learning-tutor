"""Strict Mermaid generation rules + sanitization for lecture-note diagrams."""

from __future__ import annotations

import re

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
""".strip()

_MAX_NODE_LABEL_LEN = 42
_MAX_EDGE_LABEL_LEN = 14
_EDGE_LABEL_SHORT: dict[str, str] = {
    "Left to Right": "L to R",
    "Right to Left": "R to L",
}

_MERMAID_HEADER_RE = re.compile(
    r"^(flowchart|graph|sequenceDiagram|classDiagram|stateDiagram|erDiagram|gantt|pie)\b",
    re.I,
)


def _quote_mermaid_label(node_id: str, label: str) -> str:
    safe = label.strip().replace('"', "'")
    return f'{node_id.strip()}["{safe}"]'


def _find_balanced_paren(s: str, open_pos: int) -> int:
    if open_pos < 0 or open_pos >= len(s) or s[open_pos] != "(":
        return -1
    depth = 0
    for i in range(open_pos, len(s)):
        if s[i] == "(":
            depth += 1
        elif s[i] == ")":
            depth -= 1
            if depth == 0:
                return i
    return -1


def _inside_bracket_region(line: str, index: int) -> bool:
    in_square = False
    in_diamond = False
    in_quote = False
    for i, c in enumerate(line[:index]):
        if c == '"' and (i == 0 or line[i - 1] != "\\"):
            in_quote = not in_quote
        if in_quote:
            continue
        if c == "[":
            in_square = True
        elif c == "]" and in_square:
            in_square = False
        elif c == "{":
            in_diamond = True
        elif c == "}" and in_diamond:
            in_diamond = False
    return in_square or in_diamond


def _inside_pipe_region(line: str, index: int) -> bool:
    in_pipe = False
    for i, c in enumerate(line[:index]):
        if c == "|":
            in_pipe = not in_pipe
    return in_pipe


def _brace_id_suffix(raw: str) -> str:
    """Turn {-1} style suffix into a safe id fragment."""
    cleaned = re.sub(r"[^\w]+", "_", raw.strip()).strip("_")
    return cleaned or "x"


def _fix_brace_node_ids(line: str) -> str:
    """n_{-1}(Index -1) → n_neg1["Index -1"]."""

    def repl(match: re.Match[str]) -> str:
        prefix, inner, label = match.group(1), match.group(2), match.group(3)
        node_id = f"{prefix}_{_brace_id_suffix(inner)}"
        return _quote_mermaid_label(node_id, label)

    return re.sub(
        r"\b([A-Za-z0-9_]+)_\{([^}]+)\}\s*\(([^)]+)\)",
        repl,
        line,
    )


def _fix_colon_after_square_label(line: str) -> str:
    """P[Title]: extra text → P["Title: extra text"]."""
    return re.sub(
        r"\b([A-Za-z0-9_]+)\s*\[([^\]\"]+)\]\s*:\s*(.+)$",
        lambda m: _quote_mermaid_label(m.group(1), f"{m.group(2).strip()}: {m.group(3).strip()}"),
        line,
    )


def _fix_malformed_pipe_edges(line: str) -> str:
    """-->|: label :| → -->|label|."""
    line = re.sub(
        r"-->\s*\|:\s*([^:|]+?)\s*:\s*\|",
        lambda m: f"-->|{m.group(1).strip()}|",
        line,
    )
    line = re.sub(
        r"-->\s*\|\s*:\s*([^:|]+?)\s*:\s*\|",
        lambda m: f"-->|{m.group(1).strip()}|",
        line,
    )
    return line


def _fix_edge_labels(line: str) -> str:
    return re.sub(
        r"\s--\s+(.+?)\s+-->",
        lambda m: f" -->|{m.group(1).strip().replace('|', '/')}|",
        line,
    )


def _fix_ampersand_links(line: str) -> str:
    return re.sub(
        r"\b([A-Za-z0-9_]+)\s*&\s*([A-Za-z0-9_]+)\s*(-->|---)\s*(.+)$",
        lambda m: f"{m.group(1)} {m.group(3)} {m.group(4).strip()}\n    {m.group(2)} {m.group(3)} {m.group(4).strip()}",
        line,
    )


def _inside_quoted_string(line: str, index: int) -> bool:
    in_quote = False
    for i, c in enumerate(line[:index]):
        if c == '"' and (i == 0 or line[i - 1] != "\\"):
            in_quote = not in_quote
    return in_quote


def _fix_quoted_diamond_nodes(line: str) -> str:
    """B{\"Direction\"} → B{Direction} (invalid LLM output)."""
    return re.sub(
        r'(\b[A-Za-z0-9_]+)\{"([^"]+)"\}',
        r"\1{\2}",
        line,
    )


def _fix_stadium_nodes(line: str) -> str:
    out: list[str] = []
    pos = 0
    for m in re.finditer(r"\b([A-Za-z0-9_]+)\s*\(", line):
        if m.start() < pos:
            continue
        if (
            _inside_bracket_region(line, m.start())
            or _inside_pipe_region(line, m.start())
            or _inside_quoted_string(line, m.start())
        ):
            out.append(line[pos : m.end()])
            pos = m.end()
            continue
        out.append(line[pos : m.start()])
        node_id = m.group(1)
        open_paren = m.end() - 1
        close_idx = _find_balanced_paren(line, open_paren)
        if close_idx < 0:
            out.append(line[m.start() : m.end()])
            pos = m.end()
            continue
        inner = line[open_paren + 1 : close_idx]
        out.append(_quote_mermaid_label(node_id, inner))
        pos = close_idx + 1
    out.append(line[pos:])
    return "".join(out)


def _fix_square_bracket_nodes(line: str) -> str:
    line = re.sub(
        r"(\b[A-Za-z0-9_]+\s*)\[([^\]]*\[[^\]]+\][^\]]*)\]",
        lambda m: _quote_mermaid_label(m.group(1), m.group(2)),
        line,
    )
    line = re.sub(
        r"(\b[A-Za-z0-9_]+\s*)\[([^\]\"]+)\]",
        lambda m: _quote_mermaid_label(m.group(1), m.group(2))
        if re.search(r"[\[\]&():]", m.group(2))
        else m.group(0),
        line,
    )
    return line


def _split_merged_nodes(line: str) -> str:
    return re.sub(
        r"\](\s+)(?=[A-Za-z0-9_]+\s*[\[({])",
        "]\n    ",
        line,
    )


def _fix_diamond_nodes(line: str) -> str:
    def fix_diamond(match: re.Match[str]) -> str:
        node_id, inner = match.group(1), match.group(2)
        if "(" not in inner and ")" not in inner:
            return match.group(0)
        label = re.sub(r"\s*\(([^)]*)\)", r" - \1", inner)
        label = label.replace("{", "").replace("}", "").strip()
        return _quote_mermaid_label(node_id, label)

    return re.sub(
        r"(\b[A-Za-z0-9_]+\s*)\{([^{}]+)\}",
        fix_diamond,
        line,
    )


def _soften_layout_label(text: str, *, max_len: int = _MAX_NODE_LABEL_LEN) -> str:
    """Shorten labels that break Mermaid's layout engine (not the parser)."""
    t = text.strip()
    t = _EDGE_LABEL_SHORT.get(t, t)
    t = re.sub(r"\.{2,}", " etc", t)
    t = t.replace("W[-1]", "index -1").replace("W[len-1]", "len-1 index")
    t = t.replace("(W[-1])", "index -1").replace("(index -1)", "at index -1")
    t = re.sub(r"(\w+)\[([^\]]+)\]", r"\1(\2)", t)
    if len(t) > max_len:
        t = t[: max_len - 4].rstrip(", ") + " etc"
    return t


def _fix_layout_labels(line: str) -> str:
    line = re.sub(
        r'\["([^"]+)"\]',
        lambda m: f'["{_soften_layout_label(m.group(1))}"]',
        line,
    )
    line = re.sub(
        r"-->\|([^|]+)\|",
        lambda m: f'-->|{_soften_layout_label(m.group(1), max_len=_MAX_EDGE_LABEL_LEN)}|',
        line,
    )
    return line


def _fix_mermaid_line(line: str) -> str:
    stripped = line.rstrip().rstrip(";")
    if not stripped.strip():
        return stripped
    if stripped.lstrip().startswith("subgraph ") or stripped.strip() == "end":
        return stripped

    stripped = _fix_layout_labels(stripped)
    stripped = _fix_quoted_diamond_nodes(stripped)
    stripped = _fix_malformed_pipe_edges(stripped)
    stripped = _fix_edge_labels(stripped)
    stripped = _fix_ampersand_links(stripped)
    stripped = _fix_brace_node_ids(stripped)
    stripped = _fix_colon_after_square_label(stripped)
    stripped = _fix_square_bracket_nodes(stripped)
    stripped = _split_merged_nodes(stripped)
    stripped = _fix_stadium_nodes(stripped)
    stripped = re.sub(
        r"(\b[A-Za-z0-9_]+\s*)\[([^\]\"]+)\]",
        lambda m: _quote_mermaid_label(m.group(1), m.group(2))
        if re.search(r"[\[\]&():]", m.group(2))
        else m.group(0),
        stripped,
    )
    stripped = _fix_diamond_nodes(stripped)
    return stripped

def _ensure_diagram_header(lines: list[str]) -> list[str]:
    for line in lines:
        if line.strip():
            if _MERMAID_HEADER_RE.match(line.strip()):
                return lines
            break
    return ["flowchart TD", *lines]


def sanitize_mermaid_source(source: str) -> str:
    """Apply strict line fixes to raw Mermaid (not fenced)."""
    lines = _ensure_diagram_header(source.splitlines())
    fixed: list[str] = []
    for line in lines:
        for part in _fix_mermaid_line(line).splitlines():
            fixed.append(part)
    return "\n".join(fixed)


def aggressive_sanitize_mermaid_source(source: str) -> str:
    """Second pass when layout still breaks: strip W[i], shorten labels, canonical indexing flow."""
    out = sanitize_mermaid_source(source)
    out = re.sub(r"\bW\s*\[[^\]]*\]", "index -1", out)
    out = re.sub(
        r'\b([A-Za-z0-9_]+)\[([^"\]\{\}]+)\]',
        lambda m: f'{m.group(1)}["{_soften_layout_label(m.group(2), max_len=34)}"]',
        out,
    )
    out = re.sub(
        r'\["([^"]+)"\]',
        lambda m: f'["{_soften_layout_label(m.group(1), max_len=34)}"]',
        out,
    )
    if re.search(r"\bDirection\b", out) and re.search(r"Index|index", out):
        return (
            "flowchart TD\n"
            "    A[Start] --> B{Direction}\n"
            "    B -->|L to R| C[Positive indices]\n"
            "    B -->|R to L| D[Negative indices]\n"
            "    D --> E[Last at index -1]\n"
            "    C --> F[Length minus one]"
        )
    return out


def _without_pipe_edge_labels(source: str) -> str:
    """Remove pipe edge label text so lint does not treat (parens) inside labels as stadium nodes."""
    return re.sub(r"-->\|[^|]*\|", "-->|", source)


def _without_quoted_label_text(source: str) -> str:
    """Strip quoted node labels so lint does not mis-read parentheses inside labels."""
    return re.sub(r'\["[^"]*"\]', '["…"]', source)


def mermaid_lint_issues(source: str) -> list[str]:
    """Heuristic lint — returns human-readable issue strings."""
    issues: list[str] = []
    s = source.strip()
    if not s:
        return ["empty diagram"]
    if not _MERMAID_HEADER_RE.match(s.splitlines()[0].strip()):
        issues.append("missing flowchart/graph header")
    lint_body = _without_pipe_edge_labels(s)
    lint_body = _without_quoted_label_text(lint_body)
    if re.search(r'\{"[^"]+"\}', s):
        issues.append("quoted text inside diamond braces")
    if re.search(r"\s--\s+[^|>\n][^>]*\s+-->", lint_body):
        issues.append("legacy edge label syntax (-- text -->)")
    if re.search(r"\b[A-Za-z0-9_]+\s*\(", lint_body):
        issues.append("stadium node id(label)")
    if re.search(r"\s&\s*[A-Za-z0-9_]+\s*(-->|---)", s):
        issues.append("ampersand-merged edges")
    if re.search(r"-->\s*\|:", s):
        issues.append("malformed pipe edge (-->|:)")
    if re.search(r"\[[^\]\"]+\]\s*:", s):
        issues.append("colon after unquoted ] label")
    if re.search(r"_\{[^}]+\}", s):
        issues.append("brace characters in node id")
    return issues


def is_mermaid_likely_broken(source: str) -> bool:
    return bool(mermaid_lint_issues(source))
