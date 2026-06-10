"""DSC intervention logging — CSV + PNG snapshots (never discard canvas)."""

from __future__ import annotations

import base64
import csv
import uuid
from datetime import UTC, datetime
from pathlib import Path

from backend.paths import DATA_LOGS_DIR

LOG_DIR = DATA_LOGS_DIR
INTERVENTIONS_DIR = LOG_DIR / "interventions"
INTERVENTIONS_DIR.mkdir(parents=True, exist_ok=True)

CSV_FIELDS = [
    "session_snapshot_id",
    "timestamp",
    "user_id",
    "status",
    "topic",
    "latex",
    "teacher_latex",
    "needs_review",
    "incomplete_step",
    "stuckness_score",
    "hint_given",
    "question",
    "detected_concept",
    "gamma",
    "attention",
    "canvas_idle_seconds",
    "eraser_events",
    "learner_recovered",
    "use_llm",
    "png_path",
    "notes",
]


def _csv_path(day: datetime | None = None) -> Path:
    d = (day or datetime.now(UTC)).strftime("%Y-%m-%d")
    return LOG_DIR / f"DSC_interventions_{d}.csv"


def save_canvas_png(canvas_image: str, snapshot_id: str) -> str | None:
    raw = (canvas_image or "").strip()
    if not raw:
        return None
    if "," in raw:
        raw = raw.split(",", 1)[1]
    try:
        data = base64.b64decode(raw, validate=True)
    except Exception:
        return None
    out = INTERVENTIONS_DIR / f"{snapshot_id}.png"
    out.write_bytes(data)
    return str(out.relative_to(LOG_DIR.parent)).replace("\\", "/")


def append_intervention_row(row: dict) -> None:
    path = _csv_path()
    write_header = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
        if write_header:
            writer.writeheader()
        writer.writerow({k: row.get(k, "") for k in CSV_FIELDS})


def new_snapshot_id() -> str:
    return str(uuid.uuid4())


def _find_snapshot_row(snapshot_id: str) -> dict | None:
    path = _csv_path()
    if not path.exists():
        return None
    last: dict | None = None
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("session_snapshot_id") == snapshot_id:
                last = row
    return last


def log_intervention(
    *,
    user_id: int,
    canvas_image: str,
    status: str = "spawned",
    topic: str = "",
    latex: str = "",
    teacher_latex: str = "",
    needs_review: bool = False,
    incomplete_step: bool = False,
    stuckness: float = 0.0,
    gamma: float = 0.0,
    attention: float = 0.0,
    idle_seconds: float = 0.0,
    eraser_events: int = 0,
    hint: str = "",
    question: str = "",
    detected_concept: str = "",
    use_llm: bool = False,
    learner_recovered: str | None = None,
    notes: str = "",
    snapshot_id: str | None = None,
) -> str:
    sid = snapshot_id or new_snapshot_id()
    png_rel = save_canvas_png(canvas_image, sid) or ""
    row = {
        "session_snapshot_id": sid,
        "timestamp": datetime.now(UTC).isoformat(),
        "user_id": user_id,
        "status": status,
        "topic": topic,
        "latex": latex,
        "teacher_latex": teacher_latex,
        "needs_review": needs_review,
        "incomplete_step": incomplete_step,
        "stuckness_score": round(stuckness, 3),
        "hint_given": hint,
        "question": question,
        "detected_concept": detected_concept,
        "gamma": gamma,
        "attention": attention,
        "canvas_idle_seconds": round(idle_seconds, 1),
        "eraser_events": eraser_events,
        "learner_recovered": learner_recovered if learner_recovered is not None else "",
        "use_llm": use_llm,
        "png_path": png_rel,
        "notes": notes,
    }
    append_intervention_row(row)
    return sid


def update_intervention_status(
    snapshot_id: str,
    status: str,
    notes: str = "",
    *,
    learner_recovered: bool | None = None,
) -> bool:
    """Append a follow-up row for recover/correct events (append-only log)."""
    last = _find_snapshot_row(snapshot_id)
    if not last:
        return False
    recovered_val = ""
    if learner_recovered is not None:
        recovered_val = "true" if learner_recovered else "false"
    elif status in ("recovered", "correct"):
        recovered_val = "true"
    append_intervention_row(
        {
            **last,
            "timestamp": datetime.now(UTC).isoformat(),
            "status": status,
            "learner_recovered": recovered_val or last.get("learner_recovered", ""),
            "notes": notes or last.get("notes", ""),
        }
    )
    return True


def log_intervention_correction(
    *,
    snapshot_id: str,
    correct_latex: str,
    user_id: int,
) -> bool:
    """Append intervention snapshot to DSC_handwriting_dataset.csv for model training."""
    last = _find_snapshot_row(snapshot_id)
    if not last:
        return False
    from backend.math.training_log import append_sample

    png_path = last.get("png_path") or f"data_logs/interventions/{snapshot_id}.png"
    predicted = last.get("latex") or ""
    teacher = last.get("teacher_latex") or ""
    append_sample(
        {
            "sample_id": snapshot_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "tier": "intervention",
            "prompt_id": last.get("topic") or "practice",
            "prompt_text": last.get("detected_concept") or "",
            "predicted_latex": predicted,
            "confirmed_latex": correct_latex,
            "teacher_latex": teacher,
            "agree": "true" if predicted.strip() == correct_latex.strip() else "corrected",
            "png_path": png_path,
            "user_id": user_id,
            "action": "intervention_correct",
        }
    )
    return True
