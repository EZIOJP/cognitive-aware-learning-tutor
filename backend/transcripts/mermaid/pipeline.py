"""Mermaid sanitize pipeline: extract, dedupe, syntax, layout for lecture-note diagrams."""

from __future__ import annotations

import re

from backend.transcripts.mermaid.prompts import MERMAID_GENERATION_RULES  # noqa: F401

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


_MERMAID_REPEAT_HEADER_RE = re.compile(
    r"(?:flowchart|graph)\s+(?:TD|TB|BT|RL|LR)\b",
    re.I,
)


def dedupe_repeated_mermaid_diagram(source: str) -> str:
    """Keep first diagram when small LLMs glue or repeat flowchart/graph headers."""
    s = source.strip()
    if not s:
        return s
    starts = [m.start() for m in _MERMAID_REPEAT_HEADER_RE.finditer(s)]
    if len(starts) <= 1:
        return s
    return s[starts[0] : starts[1]].strip()


_EXTRACT_DIAGRAM_RE = re.compile(
    r"((?:flowchart|graph)\s+(?:TD|TB|BT|RL|LR)\b[\s\S]*)",
    re.I,
)


def extract_mermaid_from_llm_output(raw: str) -> str:
    """Strip reasoning preamble from small LLMs; keep first diagram declaration onward."""
    text = raw.strip()
    if not text:
        return text
    text = re.sub(r"^```(?:mermaid)?\s*\n?", "", text, flags=re.I)
    text = re.sub(r"\n?```\s*$", "", text).strip()
    first_line = next((ln.strip() for ln in text.splitlines() if ln.strip()), "")
    if first_line and _MERMAID_HEADER_RE.match(first_line):
        return text
    match = _EXTRACT_DIAGRAM_RE.search(text)
    if match:
        return match.group(1).strip()
    return text




def aggressive_sanitize_mermaid_source(source: str) -> str:
    """No-op rewrite — Mermaid.js renders diagrams as-is. Kept for API compatibility."""
    return sanitize_mermaid_source(source)


def _without_pipe_edge_labels(source: str) -> str:
    """Remove pipe edge label text so lint does not treat (parens) inside labels as stadium nodes."""
    return re.sub(r"-->\|[^|]*\|", "-->|", source)


def _without_quoted_label_text(source: str) -> str:
    """Strip quoted node labels so lint does not mis-read parentheses inside labels."""
    return re.sub(r'\["[^"]*"\]', '["…"]', source)


def mermaid_lint_issues(source: str) -> list[str]:
    """Minimal lint — only flag empty / missing diagram header."""
    s = source.strip()
    if not s:
        return ["empty diagram"]
    first = next((ln.strip() for ln in s.splitlines() if ln.strip()), "")
    if not first or not _MERMAID_HEADER_RE.match(first):
        return ["missing flowchart/graph header"]
    return []


def is_mermaid_likely_broken(source: str) -> bool:
    return bool(mermaid_lint_issues(source))


def extract_from_llm(raw: str) -> str:
    return extract_mermaid_from_llm_output(raw)


def dedupe_headers(source: str) -> str:
    return dedupe_repeated_mermaid_diagram(source)


def _fix_syntax_lines_only(source: str) -> str:
    # Legacy helpers retained but unused by sanitize — identity path.
    return source


def fix_syntax_lines(source: str) -> str:
    return source.strip()


def layout_canonical(source: str) -> str:
    """Identity — do not replace diagrams with hardcoded templates."""
    return source.strip()


def sanitize_mermaid_source(raw: str) -> str:
    """Extract fence wrappers + dedupe repeated headers only. No syntax rewrites."""
    if not raw or not raw.strip():
        return ""
    s = extract_from_llm(raw)
    s = dedupe_headers(s)
    return s.strip()


def layout_safe_mermaid_source(source: str) -> str:
    """Alias of sanitize_mermaid_source (no layout rewriting)."""
    return sanitize_mermaid_source(source)