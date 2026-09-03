from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class PassSummary:
    kept: int = 0
    dropped_non_en: int = 0
    quarantined_unmapped: int = 0
    packs_multi_topic: int = 0
    note_topic_ids_normalized: int = 0
    stubs_created: int = 0
    stubs_skipped_nonempty: int = 0
    cards_seeded: int = 0
    mapped_packs: int = 0
    removed_note_topic_log: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "kept": self.kept,
            "dropped_non_en": self.dropped_non_en,
            "quarantined_unmapped": self.quarantined_unmapped,
            "packs_multi_topic": self.packs_multi_topic,
            "note_topic_ids_normalized": self.note_topic_ids_normalized,
            "stubs_created": self.stubs_created,
            "stubs_skipped_nonempty": self.stubs_skipped_nonempty,
            "cards_seeded": self.cards_seeded,
            "mapped_packs": self.mapped_packs,
        }


def write_needs_topic(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def append_dropped_non_en(row: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_normalized_log(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
