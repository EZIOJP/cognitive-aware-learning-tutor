"""Local study coach via LM Studio / Ollama — daily review + chat."""

from __future__ import annotations

import json
import re

from backend.core.ollama_client import ollama_available, ollama_generate

_JSON_BLOCK = re.compile(r"\{[\s\S]*\}")

COACH_SYSTEM = """You are the AI study coach for the Cognitive-Aware Learning Tutor app.

You receive JSON context about:
- project: what this app is and its study loops
- student: logged-in user
- today: hub metrics for today (life score, study minutes, vocab/math events)
- vocab: GRE progress (mastered, due, low mastery)
- life_last_7_days: sleep, mood, study trends
- math: practice attempts
- lecture_notes: recent topics and titles
- focus: Pomodoro distraction events from the face tracker
- plugins_enabled: active features
- face_tracker: latest webcam attention snapshot (if running)
- suggested_priorities: rule-based next steps (use as hints, not gospel)
- knowledge_base: on-demand retrieval from their database and files — weak/due GRE words with meanings,
  lecture note excerpts (markdown), recent math attempts, matching live-caption transcript lines,
  browser_activity from the SelfTracker extension (page titles, YouTube video titles/channels,
  domains, rough category guesses, Scalar progress when available)

Use knowledge_base when they ask about a topic, word, lecture, browser habits, or what they were watching.
Trust YouTube video_title and page_title over coarse category labels (Video/Streaming is not always entertainment).
If knowledge_base is empty for a topic, say what is missing and suggest logging a lecture or running a quiz.

Your job: help the student be productive in a sustainable way — concrete next actions, not lectures.
Speak like a warm, direct friend. Never say "optimize" or use hollow productivity jargon.
When they ask about the app, explain relevant features and routes from the project overview.
When they ask about their progress, cite their actual numbers from the context.
Keep answers concise unless they ask for depth."""


def local_llm_available() -> bool:
    return bool(ollama_available())


def _parse_json_blob(text: str) -> dict:
    text = text.strip()
    if text.startswith("{"):
        return json.loads(text)
    match = _JSON_BLOCK.search(text)
    if match:
        return json.loads(match.group())
    raise ValueError("No JSON object in coach response")


def _context_block(hub_context: dict) -> str:
    return json.dumps(hub_context, indent=2, default=str)


def generate_local_review(hub_payload: dict) -> dict:
    if not local_llm_available():
        raise RuntimeError("Local LLM is not enabled")

    prompt = f"""Based on the full student context below, write a short daily review.
Return JSON only with keys: comments (string), next_steps (array of strings), goals (array of strings).
Prefer suggested_priorities when they fit.

Context:
{_context_block(hub_payload)}"""

    raw = ollama_generate(prompt, system_prompt=COACH_SYSTEM, timeout=90.0)
    if not raw:
        raise ValueError("Empty local LLM review")

    parsed = _parse_json_blob(raw)
    comments = str(parsed.get("comments", "")).strip()
    if not comments:
        raise ValueError("Empty comments in review JSON")

    return {
        "comments": comments[:800],
        "next_steps": [str(s)[:200] for s in (parsed.get("next_steps") or [])[:5]],
        "goals": [str(g)[:120] for g in (parsed.get("goals") or [])[:5]],
        "overall_performance": hub_payload.get("today", {}).get(
            "overall_performance",
            hub_payload.get("overall_performance", "good"),
        ),
        "source": "gemma",
    }


def chat_with_coach(
    messages: list[dict[str, str]],
    *,
    hub_context: dict,
) -> str:
    if not local_llm_available():
        raise RuntimeError("Local LLM is not enabled. Set OLLAMA_ENABLED=1 and start LM Studio.")

    history_lines: list[str] = []
    for msg in messages[-16:]:
        role = msg.get("role", "user")
        content = (msg.get("content") or "").strip()
        if not content:
            continue
        label = "Coach" if role == "assistant" else "Student"
        history_lines.append(f"{label}: {content}")

    prompt = "\n".join(history_lines)
    if not prompt.endswith("Coach:"):
        prompt = f"{prompt}\nCoach:" if prompt else "Student: Hello\nCoach:"

    struggle_topics = (
        hub_context.get("knowledge_base", {})
        .get("graph_context", {})
        .get("struggle_topics", [])
    )
    extra = ""
    if struggle_topics:
        topics_str = ", ".join(str(t) for t in struggle_topics[:5])
        extra = f"\n\nPROACTIVE HINT: Student has struggled recently with: {topics_str}. Prioritize clarifying these concepts if the topic is relevant."

    system = f"{COACH_SYSTEM}{extra}\n\nFull student + app context (use on demand):\n{_context_block(hub_context)}"

    raw = ollama_generate(prompt, system_prompt=system, timeout=120.0)
    if not raw:
        raise ValueError("Empty chat response from local LLM")
    return raw.strip()[:4000]
