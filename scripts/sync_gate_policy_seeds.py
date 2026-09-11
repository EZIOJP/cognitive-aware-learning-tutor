#!/usr/bin/env python3
"""Generate offline gate_policy.js seed lists from browser_gate_policy.py.

Author domain/keyword seeds only in Python. Run before bundling service workers:

  python scripts/sync_gate_policy_seeds.py
  powershell -File scripts/build_extension_workers.ps1
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from backend.behavior.browser_gate_policy import (
    DEFAULT_ALLOW_DOMAINS,
    DEFAULT_BLOCK_KEYWORDS,
    DEFAULT_PORN_DOMAINS,
    DEFAULT_PORN_SUFFIXES,
    DEFAULT_SOCIAL_DOMAINS,
    DEFAULT_WATCH_DOMAINS,
    FORCE_WATCH_HOSTS,
    FREE_LIFE_ALLOW_DOMAINS,
)
from backend.paths import ROOT

BEGIN = "// BEGIN GENERATED_GATE_SEEDS (scripts/sync_gate_policy_seeds.py)"
END = "// END GENERATED_GATE_SEEDS"
BEGIN_CS = "// BEGIN GENERATED_CONTENT_SCORE (scripts/sync_gate_policy_seeds.py)"
END_CS = "// END GENERATED_CONTENT_SCORE"

TARGETS = (
    ROOT / "calt-focus" / "extensions" / "selftracker-extension" / "gate_policy.js",
    ROOT / "calt-focus" / "extensions" / "calt-gate-extension" / "gate_policy.js",
)
CALT_GATE_POLICY = (
    ROOT / "calt-focus" / "extensions" / "calt-gate-extension" / "gate_policy.js"
)


def _js_str_list(name: str, values: tuple[str, ...] | list[str], *, comment: str = "") -> str:
    lines = []
    if comment:
        lines.append(f"/** {comment} */")
    lines.append(f"var {name} = [")
    for v in values:
        lines.append(f'  "{v}",')
    lines.append("];")
    return "\n".join(lines)


def generated_block() -> str:
    # FORCE_PORN_* mirrors DEFAULT_PORN for fail-closed offline (same as prior JS).
    porn = tuple(dict.fromkeys(DEFAULT_PORN_DOMAINS))
    social = tuple(d for d in DEFAULT_SOCIAL_DOMAINS if not d.startswith("www."))
    parts = [
        BEGIN,
        "/** Offline seeds — generated from backend.behavior.browser_gate_policy. Do not edit by hand. */",
        _js_str_list(
            "FREE_LIFE_ALLOW_DOMAINS",
            FREE_LIFE_ALLOW_DOMAINS,
            comment="Shopping / house / errands — allowed in free mode (and errands-lite).",
        ),
        "",
        _js_str_list(
            "DISTRACTION_DOMAINS",
            DEFAULT_WATCH_DOMAINS,
            comment="@deprecated Prefer gateCache.browser.watch_domains — offline fallback.",
        ),
        "",
        _js_str_list("FALLBACK_ALLOW_DOMAINS", DEFAULT_ALLOW_DOMAINS),
        "",
        _js_str_list("FALLBACK_WATCH_DOMAINS", DEFAULT_WATCH_DOMAINS),
        "",
        _js_str_list(
            "FORCE_WATCH_HOSTS",
            FORCE_WATCH_HOSTS,
            comment="Always blocked in bible / planning / study — even if server flags are stale.",
        ),
        'var STRICT_DAY_MODES = ["bible", "planning", "study"];',
        "",
        _js_str_list(
            "FORCE_PORN_HOSTS",
            porn,
            comment="Always blocked (every mode including free) when offline / stale.",
        ),
        _js_str_list("FORCE_PORN_SUFFIXES", DEFAULT_PORN_SUFFIXES),
        "var FALLBACK_PORN_DOMAINS = FORCE_PORN_HOSTS.slice();",
        "var FALLBACK_PORN_SUFFIXES = FORCE_PORN_SUFFIXES.slice();",
        "",
        _js_str_list("FALLBACK_SOCIAL_DOMAINS", social),
        "",
        "/** Temporary per-host soft-allow from locked.html (extension chrome.storage.local). */",
        "var TEMP_ALLOW_MS = 60000;",
        'var TEMP_ALLOW_STORAGE_KEY = "tempAllows";',
        "",
        _js_str_list(
            "FALLBACK_BLOCK_KEYWORDS",
            DEFAULT_BLOCK_KEYWORDS,
            comment="Offline keyword seed — prefer server block_keywords_list.",
        ),
        END,
    ]
    return "\n".join(parts) + "\n"


def content_score_block() -> str:
    from backend.behavior.content_score import (
        CONTENT_SCORE_WEIGHTS,
        THRESHOLDS_FREE,
        THRESHOLDS_STUDY,
    )

    lines = [
        BEGIN_CS,
        "/** Weighted page-text score — generated from backend.behavior.content_score. */",
        "var CONTENT_SCORE_WEIGHTS = {",
    ]
    for term, weight in CONTENT_SCORE_WEIGHTS.items():
        key = json_js_key(term)
        lines.append(f"  {key}: {int(weight)},")
    lines.append("};")
    lines.append("")
    lines.append("var CONTENT_SCORE_THRESHOLDS = {")
    lines.append(
        "  free: { warn: %d, lock: %d, maxSamples: %d },"
        % (
            THRESHOLDS_FREE["warn"],
            THRESHOLDS_FREE["lock"],
            THRESHOLDS_FREE["max_samples"],
        )
    )
    lines.append(
        "  study: { warn: %d, lock: %d, maxSamples: %d },"
        % (
            THRESHOLDS_STUDY["warn"],
            THRESHOLDS_STUDY["lock"],
            THRESHOLDS_STUDY["max_samples"],
        )
    )
    lines.append("};")
    lines.append(END_CS)
    return "\n".join(lines) + "\n"


def json_js_key(term: str) -> str:
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", term):
        return term
    return '"' + term.replace("\\", "\\\\").replace('"', '\\"') + '"'


_SEED_START_RE = re.compile(
    r"(?:/\*\* Shopping / house / errands[^*]*\*/\s*)?var FREE_LIFE_ALLOW_DOMAINS\s*=",
    re.MULTILINE,
)
_AFTER_KEYWORDS_RE = re.compile(
    r"var FALLBACK_BLOCK_KEYWORDS\s*=\s*\[[^\]]*\];",
    re.MULTILINE | re.DOTALL,
)


def patch_file(path: Path, block: str, *, check_only: bool = False) -> bool:
    text = path.read_text(encoding="utf-8")
    if BEGIN in text and END in text:
        new_text = re.sub(
            re.escape(BEGIN) + r".*?" + re.escape(END) + r"\n?",
            block,
            text,
            count=1,
            flags=re.DOTALL,
        )
    else:
        m0 = _SEED_START_RE.search(text)
        m1 = _AFTER_KEYWORDS_RE.search(text)
        if not m0 or not m1 or m1.start() < m0.start():
            raise SystemExit(f"Cannot locate seed region in {path}")
        # Keep header through GATE_POLL / CALT_ORIGIN; replace from FREE_LIFE through keywords.
        # Find line start of FREE_LIFE match
        start = m0.start()
        # If there's a doc comment immediately before, include it
        pre = text.rfind("\n", 0, start)
        chunk_before = text[max(0, pre - 200) : start]
        if "Shopping / house" in chunk_before or "FREE_LIFE" in chunk_before:
            comment_start = text.rfind("/**", 0, start)
            if comment_start != -1 and comment_start > start - 300:
                start = comment_start
        end = m1.end()
        new_text = text[:start].rstrip() + "\n\n" + block + text[end:].lstrip("\n")
        if not new_text.endswith("\n"):
            new_text += "\n"

    if new_text == text:
        return False
    if check_only:
        raise SystemExit(f"Out of date: {path} — run: python scripts/sync_gate_policy_seeds.py")
    path.write_text(new_text, encoding="utf-8")
    return True


def patch_content_score(path: Path, block: str, *, check_only: bool = False) -> bool:
    text = path.read_text(encoding="utf-8")
    if BEGIN_CS in text and END_CS in text:
        new_text = re.sub(
            re.escape(BEGIN_CS) + r".*?" + re.escape(END_CS) + r"\n?",
            block,
            text,
            count=1,
            flags=re.DOTALL,
        )
    else:
        # Replace hand-authored CONTENT_SCORE_WEIGHTS + THRESHOLDS block.
        m0 = re.search(
            r"(?:/\*\* Weighted page-text score[^*]*\*/\s*)?var CONTENT_SCORE_WEIGHTS\s*=\s*\{",
            text,
        )
        m1 = re.search(
            r"var CONTENT_SCORE_THRESHOLDS\s*=\s*\{.*?\n\};",
            text,
            flags=re.DOTALL,
        )
        if not m0 or not m1 or m1.start() < m0.start():
            raise SystemExit(f"Cannot locate CONTENT_SCORE region in {path}")
        start = m0.start()
        comment = text.rfind("/**", max(0, start - 120), start)
        if comment != -1:
            start = comment
        new_text = text[:start].rstrip() + "\n\n" + block + text[m1.end() :].lstrip("\n")
        if not new_text.endswith("\n"):
            new_text += "\n"
    if new_text == text:
        return False
    if check_only:
        raise SystemExit(f"Out of date content score: {path}")
    path.write_text(new_text, encoding="utf-8")
    return True


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="Exit 1 if JS seeds differ from Python")
    args = ap.parse_args()
    block = generated_block()
    cs_block = content_score_block()
    changed = False
    for path in TARGETS:
        if not path.is_file():
            raise SystemExit(f"Missing {path}")
        if patch_file(path, block, check_only=args.check):
            print(f"updated {path.relative_to(ROOT)}")
            changed = True
        else:
            print(f"ok      {path.relative_to(ROOT)}")
    if CALT_GATE_POLICY.is_file():
        if patch_content_score(CALT_GATE_POLICY, cs_block, check_only=args.check):
            print(f"updated {CALT_GATE_POLICY.relative_to(ROOT)} (content_score)")
            changed = True
        else:
            print(f"ok      {CALT_GATE_POLICY.relative_to(ROOT)} (content_score)")
    if args.check and not changed:
        print("gate_policy seeds in sync")
    elif not args.check:
        print("Next: powershell -File scripts/build_extension_workers.ps1")


if __name__ == "__main__":
    main()
