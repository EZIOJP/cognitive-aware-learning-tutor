"""LLM enrichment for GRE vocab cards via AI handler (funny examples + mnemonics)."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from sqlalchemy.orm import Session

from backend.vocab.gref_import import has_usable_meaning, is_thin_card
from backend.vocab.repository import load_words, save_words

log = logging.getLogger(__name__)

_JSON_BLOCK = re.compile(r"\{[\s\S]*\}")

_SYSTEM = """You are a witty GRE vocab coach who writes flashcard content people actually remember.
Reply with JSON only — no markdown fences, no commentary."""

_ENRICH_PROMPT = """Write GRE flashcard fields for this word. Keep the definition accurate; make memory hooks FUNNY and sticky.

Word: {word}
Existing meaning (keep accurate; you may polish slightly): {hint}

Style rules:
- connotation: short English tone/feel of the word (e.g. "formal, slightly negative", "playful praise"). Not the definition. Prefer plain English connotations.
- story_mnemonic: ONE short funny story or word-play (1–2 sentences). Clever, easy to picture, tied to the meaning. Not dry textbook. Not crude.
- examples: exactly 3 short sentences. Funny or absurd everyday scenes that still use the word correctly. Each sentence must include the word naturally.
- meaning: clear GRE-style definition (1–2 sentences). Keep sense of the hint if present.
- pronunciation: simple English respelling (how it sounds), or ""
- etymology: one short root note, or ""
- synonyms / antonyms: up to 5 each, or []

Return JSON only with keys:
meaning, connotation, pronunciation, story_mnemonic, etymology, examples, synonyms, antonyms
(examples = array of 3 strings)
"""

_EMPTY_TEXT_KEYS = (
    "meaning",
    "connotation",
    "pronunciation",
    "story_mnemonic",
    "etymology",
)


def _is_empty_text(value: object) -> bool:
    return len(str(value or "").strip()) < 2


def needs_card_polish(word: dict[str, Any]) -> bool:
    """True when any enrichable field is empty/thin — good fill-empty target."""
    if not has_usable_meaning(word) or is_thin_card(word):
        return True
    if _is_empty_text(word.get("story_mnemonic")) or len(str(word.get("story_mnemonic") or "").strip()) < 12:
        return True
    if _is_empty_text(word.get("connotation")):
        return True
    if _is_empty_text(word.get("pronunciation")):
        return True
    examples = word.get("examples") or []
    if len(examples) < 2:
        return True
    if not (word.get("synonyms") or []):
        return True
    return False


def enrich_queue(db: Session, *, limit: int = 50) -> list[dict[str, Any]]:
    words = load_words(db)
    thin = [w for w in words if needs_card_polish(w)]
    thin.sort(
        key=lambda w: (
            -int(w.get("priority") or 0),
            0 if _is_empty_text(w.get("story_mnemonic")) else 1,
            int(w.get("id") or 0),
        )
    )
    return [
        {
            "id": int(w["id"]),
            "word": w.get("word"),
            "meaning": w.get("meaning") or "",
            "thin": is_thin_card(w),
            "has_meaning": has_usable_meaning(w),
            "has_mnemonic": not _is_empty_text(w.get("story_mnemonic")),
            "has_connotation": not _is_empty_text(w.get("connotation")),
            "priority": int(w.get("priority") or 0),
        }
        for w in thin[: max(1, min(limit, 200))]
    ]


def _parse_enrich_json(raw: str) -> dict[str, Any]:
    text = (raw or "").strip()
    if text.startswith("{"):
        return json.loads(text)
    match = _JSON_BLOCK.search(text)
    if not match:
        raise ValueError("No JSON object in enrich response")
    return json.loads(match.group())


def enrich_word_payload(word: str, hint: str = "") -> dict[str, Any]:
    from backend.core.ollama_client import ollama_available, ollama_generate

    if not ollama_available():
        raise RuntimeError("Local LLM is not available for vocab enrich (start LM Studio / enable gateway)")

    prompt = _ENRICH_PROMPT.format(word=word, hint=(hint or "(none)")[:500])
    raw = ollama_generate(
        prompt,
        system_prompt=_SYSTEM,
        task="vocab_enrich",
        timeout=90.0,
    )
    if not raw:
        raise ValueError("Empty enrich response")
    data = _parse_enrich_json(raw)
    meaning = str(data.get("meaning") or "").strip()
    if len(meaning) < 3:
        raise ValueError("Enrich response missing meaning")
    examples_raw = data.get("examples") or []
    examples: list[dict[str, str]] = []
    for ex in examples_raw[:5]:
        if isinstance(ex, dict):
            text = str(ex.get("text") or "").strip()
        else:
            text = str(ex).strip()
        if text:
            examples.append({"text": text})
    mnemonic = str(data.get("story_mnemonic") or "").strip()
    return {
        "meaning": meaning[:800],
        "connotation": str(data.get("connotation") or "").strip()[:200],
        "pronunciation": str(data.get("pronunciation") or "")[:120],
        "story_mnemonic": mnemonic[:500],
        "etymology": str(data.get("etymology") or "")[:400],
        "examples": examples[:3] if examples else [],
        "synonyms": [str(s)[:80] for s in (data.get("synonyms") or [])[:5] if s],
        "antonyms": [str(s)[:80] for s in (data.get("antonyms") or [])[:5] if s],
    }


def apply_enrichment(word: dict[str, Any], payload: dict[str, Any], *, overwrite: bool = False) -> dict[str, Any]:
    """
    Merge AI fields onto the card.
    overwrite=False (default): fill ONLY empty fields — never clobber existing content.
    overwrite=True: replace content fields (full AI rewrite).
    """
    out = dict(word)

    for key in _EMPTY_TEXT_KEYS:
        new_val = str(payload.get(key) or "").strip()
        if not new_val:
            continue
        old_val = str(out.get(key) or "").strip()
        if overwrite or _is_empty_text(old_val):
            out[key] = new_val

    if payload.get("examples"):
        if overwrite or len(out.get("examples") or []) < 2:
            out["examples"] = payload["examples"]

    for key in ("synonyms", "antonyms"):
        if payload.get(key) and (overwrite or not out.get(key)):
            out[key] = payload[key]

    tags = list(out.get("tags") or [])
    lower = {str(t).lower() for t in tags}
    if "enriched" not in lower:
        tags.append("enriched")
    if "funny" not in lower:
        tags.append("funny")
    out["tags"] = tags
    return out


def enrich_word_by_id(db: Session, word_id: int, *, overwrite: bool = False) -> dict[str, Any]:
    """Default overwrite=False: generate into empty fields only."""
    words = load_words(db)
    target = None
    for w in words:
        if int(w["id"]) == word_id:
            target = w
            break
    if target is None:
        raise KeyError(f"Word id {word_id} not found")
    payload = enrich_word_payload(str(target.get("word") or ""), str(target.get("meaning") or ""))
    # For fill-empty, still require a usable meaning in payload if card has none
    if not overwrite and _is_empty_text(payload.get("story_mnemonic")) and _is_empty_text(target.get("story_mnemonic")):
        # soft: allow missing mnemonic if other fields filled
        pass
    updated = apply_enrichment(target, payload, overwrite=overwrite)
    for i, w in enumerate(words):
        if int(w["id"]) == word_id:
            words[i] = updated
            break
    save_words(db, words)
    return updated


def enrich_batch(db: Session, *, limit: int = 10, overwrite: bool = False) -> dict[str, Any]:
    queue = enrich_queue(db, limit=limit)
    enriched = 0
    errors: list[dict[str, str]] = []
    results: list[dict[str, Any]] = []
    for item in queue:
        try:
            updated = enrich_word_by_id(db, int(item["id"]), overwrite=overwrite)
            enriched += 1
            results.append(
                {
                    "id": updated["id"],
                    "word": updated.get("word"),
                    "ok": True,
                    "mnemonic": str(updated.get("story_mnemonic") or "")[:80],
                    "connotation": str(updated.get("connotation") or "")[:60],
                }
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("enrich failed for %s: %s", item.get("word"), exc)
            errors.append({"id": str(item.get("id")), "word": str(item.get("word")), "error": str(exc)})
    return {
        "requested": len(queue),
        "enriched": enriched,
        "errors": errors,
        "results": results,
        "remaining": len(enrich_queue(db, limit=200)),
    }
