"""Load curriculum JSON and merge user progress."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from backend.math.training_log import training_progress

_CURRICULUM_PATH = Path(__file__).resolve().parent / "training_curriculum.json"


@lru_cache(maxsize=1)
def load_curriculum() -> dict:
    with open(_CURRICULUM_PATH, encoding="utf-8") as f:
        return json.load(f)


def curriculum_with_progress(user_id: int) -> dict:
    base = load_curriculum()
    prog = training_progress(user_id)
    default_target = base.get("default_target_samples", 5)
    prompt_counts: dict[str, int] = {}
    for tier_data in prog.get("by_tier", {}).values():
        for pid, count in tier_data.get("prompt_counts", {}).items():
            prompt_counts[pid] = prompt_counts.get(pid, 0) + count

    tiers_out = []
    for tier in base.get("tiers", []):
        tier_id = tier["id"]
        tier_prog = prog.get("by_tier", {}).get(tier_id, {})
        prompts_out = []
        tier_target = 0
        for p in tier.get("prompts", []):
            pid = p["id"]
            samples = prompt_counts.get(pid, 0)
            target = p.get("target_samples", default_target)
            tier_target += target
            prompts_out.append(
                {
                    **p,
                    "samples": samples,
                    "target_samples": target,
                    "remaining": max(0, target - samples),
                    "grid_cells": p.get("grid_cells", 1),
                }
            )
        tiers_out.append(
            {
                "id": tier_id,
                "label": tier.get("label", tier_id),
                "samples": tier_prog.get("samples", 0),
                "target_samples": tier_target,
                "accuracy": tier_prog.get("accuracy", 0),
                "prompts": prompts_out,
            }
        )

    return {
        "format_version": base.get("format_version", 1),
        "min_samples_per_prompt": base.get("min_samples_per_prompt", 1),
        "default_target_samples": default_target,
        "retrain_threshold": base.get("retrain_threshold", 50),
        "progress": prog,
        "tiers": tiers_out,
    }
