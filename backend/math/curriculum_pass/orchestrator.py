from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.math.curriculum_pass.constants import META_DIR, NOTES_MATH, QUESTIONS_MATH
from backend.math.curriculum_pass.curriculum import (
    all_curriculum_mt_ids,
    build_reverse_index,
    load_curriculum,
)
from backend.math.curriculum_pass.language import decide_english
from backend.math.curriculum_pass.map_packs import map_pack
from backend.math.curriculum_pass.seed import seed_mapped_questions
from backend.math.curriculum_pass.stubs import ensure_note_stubs
from backend.math.curriculum_pass.summary import (
    PassSummary,
    append_dropped_non_en,
    write_needs_topic,
    write_normalized_log,
)
from backend.quiz.atomic_io import atomic_write_text


def _iter_pack_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in sorted(root.rglob("*.json")):
        parts = set(path.parts)
        if "_meta" in parts:
            continue
        if path.name == "curriculum.json":
            continue
        files.append(path)
    return files


def _filter_pack_english(
    pack: dict[str, Any],
    *,
    meta_dir: Path,
    summary: PassSummary,
) -> dict[str, Any]:
    kept_q: list[dict[str, Any]] = []
    drop_path = meta_dir / "dropped_non_en.jsonl"
    for q in pack.get("questions") or []:
        problem = str(q.get("problem") or "")
        lang = q.get("language")
        if lang is None:
            lang = (q.get("provenance") or {}).get("language") if isinstance(q.get("provenance"), dict) else None
        keep, reason = decide_english(problem, language_field=str(lang) if lang else None)
        if not keep:
            summary.dropped_non_en += 1
            append_dropped_non_en(
                {
                    "source": q.get("source"),
                    "source_id": q.get("source_id"),
                    "id": q.get("id"),
                    "reason": reason,
                    "snippet": problem[:200],
                },
                drop_path,
            )
            continue
        kept_q.append(q)
    out = dict(pack)
    out["questions"] = kept_q
    return out


def run_pass(
    *,
    curriculum_path: Path | None = None,
    questions_root: Path | None = None,
    notes_dir: Path | None = None,
    meta_dir: Path | None = None,
    skip_import: bool = True,
    skip_seed: bool = True,
    user_id: int = 1,
    db: Any = None,
) -> dict[str, Any]:
    """Curriculum-first English math bank pass.

    ``skip_import=True`` (default for library use) maps the on-disk bank only.
    Full multi-source import remains available via the CLI when datasets are present.
    """
    _ = skip_import  # import wiring is CLI-side; library maps existing packs
    qroot = questions_root or QUESTIONS_MATH
    ndir = notes_dir or NOTES_MATH
    mdir = meta_dir or META_DIR
    mdir.mkdir(parents=True, exist_ok=True)

    # Fresh drop log each run
    drop_log = mdir / "dropped_non_en.jsonl"
    if drop_log.is_file():
        drop_log.unlink()

    curriculum = load_curriculum(curriculum_path)
    reverse = build_reverse_index(curriculum)
    mt_rows = all_curriculum_mt_ids(curriculum)
    curriculum_mts = {mt for mt, _ in mt_rows}

    summary = PassSummary()
    needs: list[dict[str, Any]] = []
    mapped_packs: list[dict[str, Any]] = []

    for path in _iter_pack_files(qroot):
        try:
            pack = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(pack, dict) or "topic" not in pack:
            continue

        pack = _filter_pack_english(pack, meta_dir=mdir, summary=summary)
        result = map_pack(pack, reverse, curriculum_mts)
        topic = (pack.get("topic") or {})
        topic_id = str(topic.get("topic_id") or "")

        if result.status == "quarantined":
            summary.quarantined_unmapped += 1
            needs.append(
                {
                    "topic_id": topic_id,
                    "path": str(path.as_posix()),
                    "question_count": len(pack.get("questions") or []),
                    "reason": "no_curriculum_prefer",
                }
            )
            continue

        if result.removed_note_topic_ids:
            summary.note_topic_ids_normalized += len(result.removed_note_topic_ids)
            summary.removed_note_topic_log.append(
                {
                    "topic_id": topic_id,
                    "path": str(path.as_posix()),
                    "removed": result.removed_note_topic_ids,
                }
            )
        if result.multi_topic:
            summary.packs_multi_topic += 1

        summary.mapped_packs += 1
        summary.kept += len(result.pack.get("questions") or [])
        mapped_packs.append(result.pack)
        atomic_write_text(
            path,
            json.dumps(result.pack, indent=2, ensure_ascii=False) + "\n",
        )

    write_needs_topic(needs, mdir / "needs_topic.json")
    write_normalized_log(
        summary.removed_note_topic_log,
        mdir / "note_topic_ids_normalized.json",
    )

    stub_stats = ensure_note_stubs(mt_rows, notes_dir=ndir)
    summary.stubs_created = stub_stats["stubs_created"]
    summary.stubs_skipped_nonempty = stub_stats["stubs_skipped_nonempty"]

    if not skip_seed and db is not None:
        summary.cards_seeded = seed_mapped_questions(
            db, user_id=user_id, packs=mapped_packs
        )

    return summary.as_dict()
