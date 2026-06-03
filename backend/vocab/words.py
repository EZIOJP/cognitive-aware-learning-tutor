import json
from pathlib import Path
from typing import Any

from backend.paths import WORDS_PATH

GROUP_SIZE = 30


def normalize_words(words: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered = sorted(words, key=lambda w: int(w.get("id", 0)))
    normalized: list[dict[str, Any]] = []
    for i, w in enumerate(ordered):
        nw = dict(w)
        nw["group_number"] = (i // GROUP_SIZE) + 1
        normalized.append(nw)
    return normalized


def load_words() -> list[dict[str, Any]]:
    if not WORDS_PATH.exists():
        return []
    with open(WORDS_PATH, encoding="utf-8") as f:
        data = json.load(f)
    words = data if isinstance(data, list) else data.get("words", [])
    return normalize_words(words)


def save_words(words: list[dict[str, Any]]) -> None:
    normalized = normalize_words(words)
    with open(WORDS_PATH, "w", encoding="utf-8") as f:
        json.dump(normalized, f, ensure_ascii=False, indent=2)
