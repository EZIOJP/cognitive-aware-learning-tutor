"""Handwriting training dataset — DSC_handwriting_dataset.csv + PNG snapshots."""

from __future__ import annotations

import base64
import csv
import uuid
from datetime import UTC, datetime
from pathlib import Path

from backend.paths import DATA_LOGS_DIR

LOG_DIR = DATA_LOGS_DIR
TRAINING_DIR = LOG_DIR / "training"
TRAINING_DIR.mkdir(parents=True, exist_ok=True)
DATASET_CSV = LOG_DIR / "DSC_handwriting_dataset.csv"

CSV_FIELDS = [
    "sample_id",
    "timestamp",
    "tier",
    "prompt_id",
    "prompt_text",
    "predicted_latex",
    "confirmed_latex",
    "teacher_latex",
    "agree",
    "png_path",
    "user_id",
    "action",
]


def _save_png(canvas_image: str, sample_id: str) -> str:
    raw = (canvas_image or "").strip()
    if "," in raw:
        raw = raw.split(",", 1)[1]
    data = base64.b64decode(raw, validate=True)
    out = TRAINING_DIR / f"{sample_id}.png"
    out.write_bytes(data)
    return str(out.relative_to(LOG_DIR.parent)).replace("\\", "/")


def append_sample(row: dict) -> str:
    sample_id = row.get("sample_id") or str(uuid.uuid4())
    write_header = not DATASET_CSV.exists()
    with open(DATASET_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
        if write_header:
            writer.writeheader()
        writer.writerow({k: row.get(k, "") for k in CSV_FIELDS})
    return sample_id


def log_training_sample(
    *,
    user_id: int,
    tier: str,
    prompt_id: str,
    prompt_text: str,
    canvas_image: str,
    predicted_latex: str,
    confirmed_latex: str,
    teacher_latex: str = "",
    action: str,
) -> str:
    sample_id = str(uuid.uuid4())
    png_path = _save_png(canvas_image, sample_id)
    agree = _latex_agree(predicted_latex, confirmed_latex, teacher_latex)
    append_sample(
        {
            "sample_id": sample_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "tier": tier,
            "prompt_id": prompt_id,
            "prompt_text": prompt_text,
            "predicted_latex": predicted_latex,
            "confirmed_latex": confirmed_latex,
            "teacher_latex": teacher_latex,
            "agree": agree,
            "png_path": png_path,
            "user_id": user_id,
            "action": action,
        }
    )
    return sample_id


def _latex_agree(predicted: str, confirmed: str, teacher: str) -> str:
    p = (predicted or "").strip()
    c = (confirmed or "").strip()
    t = (teacher or "").strip()
    if c and p == c:
        return "true"
    if c and t and t == c:
        return "teacher_match"
    if c and p != c:
        return "corrected"
    return "false"


def _read_rows(user_id: int | None = None) -> list[dict]:
    if not DATASET_CSV.exists():
        return []
    rows: list[dict] = []
    with open(DATASET_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if user_id is not None and str(row.get("user_id")) != str(user_id):
                continue
            rows.append(row)
    return rows


def training_progress(user_id: int) -> dict:
    rows = _read_rows(user_id)
    by_tier: dict[str, dict] = {}
    agree_count = 0
    for row in rows:
        tier = row.get("tier") or "unknown"
        bucket = by_tier.setdefault(
            tier,
            {"samples": 0, "agree": 0, "prompts": {}},
        )
        bucket["samples"] += 1
        if row.get("agree") in ("true", "teacher_match"):
            bucket["agree"] += 1
            agree_count += 1
        pid = row.get("prompt_id") or ""
        bucket["prompts"][pid] = bucket["prompts"].get(pid, 0) + 1

    total = len(rows)
    accuracy = round(agree_count / total, 3) if total else 0.0
    return {
        "total_samples": total,
        "accuracy": accuracy,
        "retrain_threshold": 50,
        "samples_until_retrain": max(0, 50 - (total % 50)) if total else 50,
        "by_tier": {
            k: {
                "samples": v["samples"],
                "agree": v["agree"],
                "accuracy": round(v["agree"] / v["samples"], 3) if v["samples"] else 0,
                "prompt_counts": v["prompts"],
            }
            for k, v in by_tier.items()
        },
    }


def training_stats_for_hub(user_id: int) -> dict:
    prog = training_progress(user_id)
    return {
        "ocr_samples": prog["total_samples"],
        "ocr_accuracy": prog["accuracy"],
    }
