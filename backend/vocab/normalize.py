"""Word list normalization — shared by JSON file and DB repository."""

from typing import Any

GROUP_SIZE = 30


def normalize_words(words: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered = sorted(words, key=lambda w: int(w.get("id", 0)))
    normalized: list[dict[str, Any]] = []
    for i, w in enumerate(ordered):
        nw = dict(w)
        nw["group_number"] = (i // GROUP_SIZE) + 1
        normalized.append(nw)
    return normalized
