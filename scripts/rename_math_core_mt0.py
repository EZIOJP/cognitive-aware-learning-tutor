"""One-shot: rename Math Core worksheets MT1-T16..T24 → MT0 basics-first."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "data" / "notes" / "math-core" / "MT1_aptitude_interview_notes.md"
text = path.read_text(encoding="utf-8")

for a, b in [
    ("MT1-T19", "MT0-T01"),
    ("MT1-T21", "MT0-T02"),
    ("MT1-T20", "MT0-T03"),
    ("MT1-T16", "MT0-T04"),
    ("MT1-T17", "MT0-T05"),
    ("MT1-T18", "MT0-T06"),
    ("MT1-T22", "MT0-T07"),
    ("MT1-T23", "MT0-T08"),
    ("MT1-T24", "MT0-T09"),
]:
    text = text.replace(a, b)

old_ws_rows = """| `MT1-T01` | Number systems & divisibility | primes, divisibility rules (Math Core reference) |
| `MT0-T04` | Math Core · squares | squares 1–50 + fast-square shortcuts |
| `MT0-T05` | Math Core · cubes | cubes 1–30 + cube-root last-digit map |
| `MT0-T06` | Math Core · powers | bases 2/3/5/7 raw values + last-digit cyclicity |
| `MT0-T01` | Math Core · tables 2–25 | classic rote tables; random-cell recall target |
| `MT0-T03` | Math Core · fraction ↔ % | 1/2–1/30 + common multiples |
| `MT0-T02` | Math Core · primes & factorization | primes <200, ID methods, factor trees |
| `MT0-T07` | Math Core · calculation shortcuts | near-base mul, complements, ×5/25/125 |
| `MT0-T08` | Math Core · unit conversions | km/hr↔m/s, minute fractions of an hour |
| `MT0-T09` | Math Core · approximation & estimation | magnitude / MCQ elimination without exact calc |
| `MT1-T02` | LCM & HCF | prime-factor + Euclidean; word-problem cues |"""

new_ws_rows = """| `MT1-T01` | Number systems & divisibility | primes, divisibility rules (Math Core reference) |
| `MT0-T01` | Math Core · tables 2–25 | classic rote tables; random-cell recall target |
| `MT0-T02` | Math Core · primes & factorization | primes <200, ID methods, factor trees |
| `MT0-T03` | Math Core · fraction ↔ % | 1/2–1/30 + common multiples |
| `MT0-T04` | Math Core · squares | squares 1–50 + fast-square shortcuts |
| `MT0-T05` | Math Core · cubes | cubes 1–30 + cube-root last-digit map |
| `MT0-T06` | Math Core · powers | bases 2/3/5/7 raw values + last-digit cyclicity |
| `MT0-T07` | Math Core · calculation shortcuts | near-base mul, complements, ×5/25/125 |
| `MT0-T08` | Math Core · unit conversions | km/hr↔m/s, minute fractions of an hour |
| `MT0-T09` | Math Core · approximation & estimation | magnitude / MCQ elimination without exact calc |
| `MT1-T02` | LCM & HCF | prime-factor + Euclidean; word-problem cues |"""

if old_ws_rows not in text:
    raise SystemExit("expected worksheet index block not found after id rewrite")
text = text.replace(old_ws_rows, new_ws_rows, 1)

text = text.replace(
    "Interview-style quantitative aptitude. Tags: **`MT1-Txx`**.",
    "Interview-style quantitative aptitude. "
    "Fluency worksheets: **`MT0-Txx`** (basics first). Interview topics: **`MT1-Txx`**.",
)

# Scope paragraph under MT1-T01 (ids already rewritten; tidy leftovers like –`T18`)
needle = "**Scope (Math Core · optional skim):**"
idx = text.find(needle)
if idx < 0:
    raise SystemExit("scope needle missing")
end = text.find("\n\n### Number systems", idx)
if end < 0:
    raise SystemExit("scope end missing")
new_scope = (
    "**Scope (Math Core · optional skim):** Integer fluency for aptitude — place value, "
    "primes/factors, and **divisibility rules**. Learn worksheets in order: "
    "tables (`MT0-T01`) → primes (`MT0-T02`) → fraction↔% (`MT0-T03`) → "
    "squares/cubes/powers (`MT0-T04`–`MT0-T06`) → shortcuts/units/estimation "
    "(`MT0-T07`–`MT0-T09`). Skim the worksheet cards, then drill ~20 questions."
)
text = text[:idx] + new_scope + text[end:]

# Takeaway line
text = text.replace(
    "Continue to the Math Core worksheet cards (`MT0-T04`–`T24`), then practice.",
    "Continue to the Math Core worksheet cards (`MT0-T01`–`MT0-T09`), then practice.",
)
text = text.replace(
    "Continue to the Math Core worksheet cards (`MT0-T04`–`MT0-T09`), then practice.",
    "Continue to the Math Core worksheet cards (`MT0-T01`–`MT0-T09`), then practice.",
)

path.write_text(text, encoding="utf-8")
print("updated", path)
