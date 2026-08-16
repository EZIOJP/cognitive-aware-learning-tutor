"""Repair broken ``` fences in lecture5 pandas notes.

Restores from .bak_fencefix if present, else from current file.
Writes fixed markdown back to data/notes/lecture5/lecture5_pandas_operations_notes.md
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "data" / "notes" / "data_foundations" / "lecture_5" / "lecture5_pandas_operations_notes.md"
BACKUP = PATH.with_suffix(".md.bak_fencefix")


def is_heading(line: str) -> bool:
    return bool(re.match(r"^#{1,6}\s+\S", line))


def is_topic_heading(line: str) -> bool:
    t = line.strip()
    if re.match(r"^##\s+`L5-", t):
        return True
    if re.match(
        r"^##\s+(Additional|Quick|Open|New Functions|Topic Index|A note)",
        t,
    ):
        return True
    if re.match(r"^##\s+[\U0001F4CC\U0001F5C2\U0001F195]", t):
        return True
    if re.match(r"^#\s+Pandas", t):
        return True
    return False


def is_codey(line: str) -> bool:
    t = line.strip()
    if not t:
        return False
    if t.startswith("```") or t.startswith(">") or t.startswith("---"):
        return False
    if t.startswith("|") or t.startswith("- "):
        return False
    if is_topic_heading(line):
        return False
    if t.startswith("**") and len(t) > 20:
        return False
    if re.match(
        r"^(import |from |def |class |print\(|return |for |while |with |"
        r"if |elif |else:|try:|except|@)",
        t,
    ):
        return True
    if re.match(r"^[A-Za-z_][\w\.\[\]\"']*\s*=", t):
        return True
    if re.match(
        r"^(df|pd|np|series|data|column_names|name_series|age_series|"
        r"department_series|samples_|rest_type)\b",
        t,
    ):
        return True
    if re.match(r"^\w+\(.*\)", t):
        return True
    if t.startswith("#") and not is_topic_heading(line):
        return True
    return False


def normalize_code_line(line: str) -> str:
    if re.match(r"^##\s+", line) and not is_topic_heading(line):
        return "# " + line.lstrip("#").strip()
    return line


def repair(text: str) -> str:
    lines = text.splitlines()

    # Drop orphan bare ``` before another fence / heading / hr
    cleaned: list[str] = []
    i = 0
    while i < len(lines):
        if lines[i].strip() == "```":
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if (
                j >= len(lines)
                or lines[j].startswith("```")
                or is_heading(lines[j])
                or lines[j].strip() == "---"
            ):
                i += 1
                continue
        cleaned.append(lines[i])
        i += 1
    lines = cleaned

    out: list[str] = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        s = line.strip()
        m = re.match(r"^```(\w+)\s*$", s)
        if m:
            lang = m.group(1)
            i += 1
            body: list[str] = []
            while i < n:
                cur = lines[i]
                cs = cur.strip()
                if cs == "```":
                    k = i + 1
                    while k < n and not lines[k].strip():
                        k += 1
                    if k < n and is_codey(lines[k]) and not is_topic_heading(lines[k]):
                        i += 1
                        continue
                    i += 1
                    break
                if cs.startswith("```"):
                    break
                if is_topic_heading(cur):
                    break
                if cs.startswith(">") or cs == "---" or (
                    cs.startswith("|") and "|" in cs[1:]
                ):
                    break
                if (
                    not is_codey(cur)
                    and cs
                    and not cs.startswith("#")
                    and len(cs) > 60
                    and " " in cs
                    and not re.search(r"[=\[\(]", cs)
                ):
                    break
                body.append(normalize_code_line(cur))
                i += 1
            while body and not body[-1].strip():
                body.pop()
            if body:
                out.append("```" + lang)
                out.extend(body)
                out.append("```")
            continue

        if s == "```":
            i += 1
            continue

        if is_codey(line):
            chunk: list[str] = []
            while i < n:
                if (
                    is_topic_heading(lines[i])
                    or lines[i].strip().startswith("```")
                    or lines[i].strip().startswith(">")
                    or lines[i].strip() == "---"
                    or lines[i].strip().startswith("|")
                ):
                    break
                if not lines[i].strip():
                    k = i + 1
                    while k < n and not lines[k].strip():
                        k += 1
                    if k < n and is_codey(lines[k]):
                        chunk.append(lines[i])
                        i += 1
                        continue
                    break
                if is_codey(lines[i]):
                    chunk.append(normalize_code_line(lines[i]))
                    i += 1
                    continue
                break
            while chunk and not chunk[-1].strip():
                chunk.pop()
            if chunk:
                out.append("```python")
                out.extend(chunk)
                out.append("```")
            continue

        out.append(line)
        i += 1

    fixed = "\n".join(out) + "\n"
    fixed = re.sub(r"```\w*\n```\n", "", fixed)
    return fixed


def main() -> int:
    src = BACKUP if BACKUP.exists() else PATH
    text = src.read_text(encoding="utf-8")
    if not BACKUP.exists():
        BACKUP.write_text(text, encoding="utf-8")

    fixed = repair(text)
    PATH.write_text(fixed, encoding="utf-8")

    fences = len(re.findall(r"^```", fixed, re.M))
    lines = fixed.splitlines()
    outside = 0
    in_f = False
    for line in lines:
        if line.startswith("```"):
            in_f = not in_f
            continue
        if not in_f and re.match(r"^(df\.|pd\.|print\(|np\.|import )", line.strip()):
            outside += 1

    print(f"source={src.name}")
    print(f"lines={len(lines)} fences={fences} even={fences % 2 == 0} outside={outside}")
    return 0 if fences % 2 == 0 and outside == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
