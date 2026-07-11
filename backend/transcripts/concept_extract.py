"""Lightweight concept extraction for notes retrieve queries and quiz generation."""

from __future__ import annotations

import json
import re
from typing import Any

from backend.core.ollama_client import LlmOptions, ollama_available, ollama_generate

_JSON_BLOCK = re.compile(r"\{[\s\S]*\}|\[[\s\S]*\]")


def _parse_concepts_blob(text: str) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []
    try:
        if text.startswith("["):
            data = json.loads(text)
        elif text.startswith("{"):
            data = json.loads(text)
        else:
            match = _JSON_BLOCK.search(text)
            if not match:
                return []
            data = json.loads(match.group())
    except json.JSONDecodeError:
        return []
    if isinstance(data, dict):
        raw = data.get("concepts") or data.get("topics") or []
    else:
        raw = data
    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        if isinstance(item, dict):
            name = str(item.get("name") or item.get("concept") or "").strip()
        else:
            name = str(item).strip()
        if not name:
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(name[:120])
    return out


def extract_concepts(
    material: str,
    *,
    topic: str = "",
    max_concepts: int = 8,
    llm: LlmOptions | None = None,
    confirm_heavy_budget: bool = False,
    seed: list[str] | None = None,
) -> list[str]:
    """
    Return atomic concept names for retrieval / quiz targeting.

    Uses task=concept_extract (light tier). Falls back to heading heuristics if LLM unavailable.
    """
    seeds = [s.strip() for s in (seed or []) if s and str(s).strip()]
    if not ollama_available(llm):
        return _heuristic_concepts(material, topic=topic, max_concepts=max_concepts, seed=seeds)

    prompt = f"""Extract up to {max_concepts} atomic study CONCEPTS / TOPICS from the material.
Topic focus: {topic or "general"}

Rules:
- Concepts only (definitions, properties, algorithms, formulas) — not classroom logistics.
- Prefer short noun phrases (2–6 words).
- Deduplicate near-synonyms.

Return JSON only:
{{"concepts": ["concept one", "concept two"]}}

Material:
{material[:12000]}"""

    raw = ollama_generate(
        prompt,
        timeout=60.0,
        llm=llm,
        task="concept_extract",
        confirm_heavy_budget=confirm_heavy_budget,
    )
    concepts = _parse_concepts_blob(raw or "")
    if not concepts:
        concepts = _heuristic_concepts(material, topic=topic, max_concepts=max_concepts, seed=seeds)
    # Merge seeds first
    merged: list[str] = []
    seen: set[str] = set()
    for name in seeds + concepts:
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        merged.append(name)
        if len(merged) >= max_concepts:
            break
    return merged


def _heuristic_concepts(
    material: str,
    *,
    topic: str = "",
    max_concepts: int = 8,
    seed: list[str] | None = None,
) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for name in seed or []:
        key = name.lower()
        if key not in seen:
            seen.add(key)
            out.append(name)
    if topic.strip():
        key = topic.strip().lower()
        if key not in seen:
            seen.add(key)
            out.append(topic.strip()[:120])
    for line in material.splitlines():
        s = line.strip()
        if s.startswith("##"):
            name = re.sub(r"^#+\s*", "", s).strip()
            if name and name.lower() not in seen and name.lower() not in {
                "topics covered",
                "semantic glossary",
            }:
                seen.add(name.lower())
                out.append(name[:120])
        if len(out) >= max_concepts:
            break
    return out[:max_concepts]


def concepts_to_retrieval_query(concepts: list[str], *, topic: str = "") -> str:
    parts = [topic.strip()] if topic.strip() else []
    parts.extend(c for c in concepts if c.strip())
    query = " — ".join(parts)
    return re.sub(r"\s+", " ", query).strip()[:280]
