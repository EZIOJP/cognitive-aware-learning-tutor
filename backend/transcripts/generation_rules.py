"""Permanent rules for lecture notes + per-topic quiz generation.

Canonical topic IDs: ``L{n}-Txx`` (e.g. ``L5-T05`` for Lecture 5, topic 5).
Decimal outline ``1.1``, ``2.3`` is a fallback when L-IDs are absent.

Used by:
- ``study_intel._quiz_role_prompt`` (quiz_gen task)
- ``notes_generator`` refine / structure pass
- ``.cursor/rules/notes-generation.mdc`` and ``quiz-generation.mdc``

Human-readable mirror: ``docs/generation-rules.md``
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Notes structure (Lecture 5 pattern)
# ---------------------------------------------------------------------------

NOTES_TOPIC_INDEX_HEADING = "## 🗂️ Topic Index (quiz-gen lookup table)"

NOTES_STRUCTURE_RULES = """
Notes must be quiz-ready with explicit topic IDs:

1. After the title, include a Topic Index table:
   | ID | Topic | One-line scope |
   | `L5-T05` | Unique values | unique, nunique, value_counts |
   | `MT1-T01` | Number systems | divisibility, tables (math modules) |

2. Each teachable section uses a heading:
   ## `L5-T05` — Unique values: unique(), nunique(), value_counts()
   ## `MT0-T04` — Math Core · squares (worksheet)   ← separate cards for Study Loop

3. Skip meta sections (never quiz these):
   Topic Index, New Functions, Quick Lookup, Quick Reference, Cheat-Sheet,
   Open Items, Recap, Today's Agenda, Math Roadmap, Module Overview.

4. Each topic body needs ≥40 chars of grounded content (code snippets + explanation).

5. Prefer one concept per L-ID / MT-ID section; do not merge unrelated APIs into one topic.

6. Math Core: keep warm-up reference (`MT1-T01`) separate from fluency worksheet cards
   (`MT0-T01` tables … `MT0-T09` estimation; basics first). Do not bury olympiad/competition
   stretch inside day-1 fluency headings.
""".strip()


def notes_structure_prompt_block(*, lecture_num: int | None = None) -> str:
    n = lecture_num or 5
    return f"""{NOTES_STRUCTURE_RULES}

Example IDs for this lecture: `L{n}-T01`, `L{n}-T02`, … (two-digit suffix, lecture order).
"""


# ---------------------------------------------------------------------------
# Quiz generation — per-topic loop
# ---------------------------------------------------------------------------

QUIZ_TOPIC_LOOP_RULES = """
Quiz generation walks topics IN ORDER (not one blob for the whole note):

1. Parse topics from the note (`L{n}-Txx` preferred; decimal `2.1` fallback).
2. For each topic: generate a fixed quota of MCQs using ONLY that topic's body.
3. Tag every item: topic_id, note_path, concept, tags[].
4. Combine into one deck; seed SRS as one ReviewCard per topic (topic_pack).
5. Walk ALL topics even when the user requests a small count — at least 2 Q/topic.

Do NOT generate quiz items from the Topic Index table or meta cheat-sheet sections.
""".strip()


# ---------------------------------------------------------------------------
# MCQ quality — good vs bad (Lecture 5 Pandas examples)
# ---------------------------------------------------------------------------

GOOD_MCQ_EXAMPLES: list[dict[str, Any]] = [
    {
        "topic_id": "L5-T05",
        "question": "You need the count of distinct values in a Series — which call is correct?",
        "options": [
            "s.nunique()",
            "s.unique().count()",
            "len(s.unique()) only when there are no NaNs",
            "s.value_counts().sum()",
        ],
        "answer_index": 0,
        "concept": "nunique vs unique",
        "why": "Grounded in notes; plausible distractors; tests API choice not trivia.",
    },
    {
        "topic_id": "L5-T08",
        "question": "After df.drop_duplicates(subset=['email'], keep='last'), what happens to rows with the same email?",
        "options": [
            "Only the last occurrence per email remains",
            "All duplicates are removed including first and last",
            "Rows are sorted by email before dropping",
            "NaN emails are always kept twice",
        ],
        "answer_index": 0,
        "concept": "drop_duplicates keep",
        "why": "Scenario-style; uses parameters actually taught in the topic body.",
    },
    {
        "topic_id": "L5-T02",
        "question": "Why does fancy indexing with a boolean mask on a NumPy array often return a copy?",
        "options": [
            "Non-contiguous selection cannot share the original buffer as a view",
            "Boolean masks always sort the array first",
            "NumPy disables views for arrays smaller than 100 elements",
            "copy=True is the default for every NumPy operator",
        ],
        "answer_index": 0,
        "concept": "fancy indexing copy",
        "why": "Tests understanding (why), not 'which statement best matches'.",
    },
]

BAD_MCQ_EXAMPLES: list[dict[str, Any]] = [
    {
        "question": "Which statement best matches the note section Pandas?",
        "options": [
            "It relates to: Pandas",
            "NumPy",
            "EDA",
            "Indexing",
        ],
        "why": "Bland stem; 'It relates to:' distractor; not grounded in a specific fact.",
    },
    {
        "question": "What topic is covered in this lecture?",
        "options": ["Pandas", "Python", "Data", "Lecture 5"],
        "why": "Meta question about the file, not the material.",
    },
    {
        "question": "unique() completes this claim: ____",
        "options": ["returns distinct values", "sorts the Series", "drops NaN always", "counts rows"],
        "why": "Cloze/template stem banned by quality lint.",
    },
    {
        "question": "What did the lecturer say about duplicates?",
        "options": ["A", "B", "C", "D"],
        "why": "Classroom logistics / speaker diary — not in revision notes.",
    },
]

BANNED_MCQ_STEMS: tuple[str, ...] = (
    "which statement best matches",
    "which statement best describes the note section",
    "what topic is covered",
    "completes this claim",
    "note section",
    "what did the lecturer",
    "what did the speaker",
    "according to the filename",
    "which of the following is true about",
)

BANNED_MCQ_OPTION_PREFIXES: tuple[str, ...] = (
    "it relates to:",
    "mainly about:",
)


def quiz_good_bad_examples_block() -> str:
    """Compact good/bad few-shot block for quiz_gen prompts."""
    good_lines = []
    for i, ex in enumerate(GOOD_MCQ_EXAMPLES[:3], 1):
        good_lines.append(
            f"GOOD {i} [{ex.get('topic_id', '')}]: {ex['question'][:120]}… "
            f"({ex.get('why', '')})"
        )
    bad_lines = []
    for i, ex in enumerate(BAD_MCQ_EXAMPLES[:4], 1):
        bad_lines.append(f"BAD {i}: {ex['question'][:100]}… ({ex.get('why', '')})")
    return (
        "Quality examples (match GOOD, never write BAD):\n"
        + "\n".join(good_lines)
        + "\n"
        + "\n".join(bad_lines)
    )


def quiz_prompt_rules_block(*, section_title: str = "") -> str:
    """Rules injected into every quiz_gen role prompt."""
    topic_line = (
        f"\nSCOPE: Generate questions ONLY for topic «{section_title}». "
        "Ignore all other headings in the material block.\n"
        if section_title
        else ""
    )
    return f"""{QUIZ_TOPIC_LOOP_RULES}
{topic_line}
{quiz_good_bad_examples_block()}

Output JSON only. Each question MUST include: question, options (4 strings),
answer_index (0-based), explanation, hint, concept, source_chunk_id (optional).
"""


def banned_stems_for_lint() -> tuple[str, ...]:
    return BANNED_MCQ_STEMS


def banned_option_prefixes_for_lint() -> tuple[str, ...]:
    return BANNED_MCQ_OPTION_PREFIXES


def rules_summary_for_api() -> dict[str, Any]:
    """Expose rules metadata to the web UI / diagnostics."""
    return {
        "topic_id_format": "L{n}-Txx",
        "quiz_engine": "topic_loop",
        "min_questions_per_topic": 2,
        "notes_structure_rules": NOTES_STRUCTURE_RULES,
        "quiz_topic_loop_rules": QUIZ_TOPIC_LOOP_RULES,
        "good_examples": GOOD_MCQ_EXAMPLES,
        "bad_examples": BAD_MCQ_EXAMPLES,
        "banned_stems": list(BANNED_MCQ_STEMS),
    }
