"""Export DSC_handwriting_dataset.csv → TexTeller fine-tune layout; optional train launch."""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from backend.math.training_log import DATASET_CSV, _read_rows
from backend.math.training_service import load_curriculum
from backend.paths import ROOT

logger = logging.getLogger(__name__)

FINETUNE_ROOT = ROOT / "data" / "math" / "texteller_finetune"


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


TRAIN_DIR = FINETUNE_ROOT / "train"
IMAGES_DIR = TRAIN_DIR / "images"
FORMULAS_JSONL = TRAIN_DIR / "formulas.jsonl"
VAL_DIR = FINETUNE_ROOT / "val"
VAL_IMAGES_DIR = VAL_DIR / "images"
VAL_FORMULAS_JSONL = VAL_DIR / "formulas.jsonl"
MANIFEST_JSON = FINETUNE_ROOT / "manifest.json"
LAST_RETRAIN_JSON = FINETUNE_ROOT / "last_retrain.json"


@dataclass
class RetrainExportResult:
    status: str
    message: str
    total_samples: int
    exported: int
    skipped: int
    skip_reasons: dict[str, int] = field(default_factory=dict)
    export_dir: str = ""
    formulas_jsonl: str = ""
    min_samples: int = 50
    retrain_threshold: int = 50
    holdout_count: int = 0
    val_exported: int = 0
    val_dir: str = ""
    val_formulas_jsonl: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def retrain_threshold() -> int:
    try:
        return int(load_curriculum().get("retrain_threshold", 50))
    except Exception:
        return 50


def ground_truth_latex(row: dict) -> str:
    """Prefer human-confirmed label, then teacher, then curriculum target."""
    for key in ("confirmed_latex", "teacher_latex", "target_latex"):
        text = (row.get(key) or "").strip()
        if text:
            return text
    return ""


def resolve_png_path(row: dict) -> Path | None:
    rel = (row.get("png_path") or "").strip()
    if not rel:
        return None
    path = Path(rel)
    if not path.is_absolute():
        path = ROOT / path
    return path if path.is_file() else None


def _skip(reasons: dict[str, int], reason: str) -> None:
    reasons[reason] = reasons.get(reason, 0) + 1


def _copy_rows_to(
    rows: list[dict],
    images_dir: Path,
    *,
    require_paths_json: bool,
    skip_reasons: dict[str, int],
) -> list[dict[str, str]]:
    """Copy each usable row's PNG into ``images_dir``; return its JSONL records."""
    images_dir.mkdir(parents=True, exist_ok=True)
    out: list[dict[str, str]] = []
    seen_ids: set[str] = set()

    for row in rows:
        sample_id = (row.get("sample_id") or "").strip()
        if not sample_id:
            _skip(skip_reasons, "missing_sample_id")
            continue
        if sample_id in seen_ids:
            _skip(skip_reasons, "duplicate_sample_id")
            continue

        if require_paths_json and not (row.get("paths_json_path") or "").strip():
            _skip(skip_reasons, "missing_paths_json")
            continue

        latex = ground_truth_latex(row)
        if not latex:
            _skip(skip_reasons, "missing_label")
            continue

        src = resolve_png_path(row)
        if src is None:
            _skip(skip_reasons, "missing_png")
            continue

        dest_name = f"{sample_id}.png"
        shutil.copy2(src, images_dir / dest_name)
        out.append({"image": dest_name, "formula": latex, "sample_id": sample_id})
        seen_ids.add(sample_id)

    return out


def _write_jsonl(path: Path, records: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for item in records:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")


def export_texteller_dataset(
    *,
    min_samples: int | None = None,
    user_id: int | None = None,
    rows: list[dict] | None = None,
    clean: bool = True,
    require_paths_json: bool = False,
    exclude_holdout: bool = True,
) -> RetrainExportResult:
    """
    Copy PNGs + write ``train/formulas.jsonl`` for TexTeller ``examples/train_texteller``.

    Each JSONL line: ``{"image": "<sample_id>.png", "formula": "<latex>"}``.

    Held-out rows go to ``val/`` instead of ``train/`` so the fine-tune never sees the
    samples it will be judged on. ``min_samples`` is checked against the *trainable*
    count, not the raw row count.
    """
    from backend.math.artifacts import snapshot_artifact
    from backend.math.holdout import holdout_fraction, split_rows

    threshold = min_samples if min_samples is not None else retrain_threshold()
    data = rows if rows is not None else _read_rows(user_id)
    total = len(data)

    if exclude_holdout:
        train_rows, holdout_rows = split_rows(data)
    else:
        train_rows, holdout_rows = data, []

    if len(train_rows) < threshold:
        return RetrainExportResult(
            status="insufficient_samples",
            message=(
                f"Need at least {threshold} trainable samples; have {len(train_rows)} "
                f"({total} total, {len(holdout_rows)} held out)."
            ),
            total_samples=total,
            exported=0,
            skipped=total,
            min_samples=threshold,
            retrain_threshold=threshold,
            holdout_count=len(holdout_rows),
        )

    # Keep the small metadata from the previous export; the images are reproducible.
    snapshot_artifact(FORMULAS_JSONL)
    snapshot_artifact(MANIFEST_JSON)

    if clean:
        for stale in (TRAIN_DIR, VAL_DIR):
            if stale.exists():
                shutil.rmtree(stale)

    skip_reasons: dict[str, int] = {}
    jsonl_rows = _copy_rows_to(
        train_rows,
        IMAGES_DIR,
        require_paths_json=require_paths_json,
        skip_reasons=skip_reasons,
    )
    exported = len(jsonl_rows)

    if exported < threshold:
        return RetrainExportResult(
            status="insufficient_valid_samples",
            message=(
                f"Only {exported} trainable rows had PNG + label (need {threshold}). "
                f"Skipped: {skip_reasons or 'none'}."
            ),
            total_samples=total,
            exported=exported,
            skipped=total - exported,
            skip_reasons=skip_reasons,
            min_samples=threshold,
            retrain_threshold=threshold,
            holdout_count=len(holdout_rows),
        )

    val_skip: dict[str, int] = {}
    val_rows = _copy_rows_to(
        holdout_rows,
        VAL_IMAGES_DIR,
        require_paths_json=require_paths_json,
        skip_reasons=val_skip,
    )

    _write_jsonl(FORMULAS_JSONL, jsonl_rows)
    _write_jsonl(VAL_FORMULAS_JSONL, val_rows)

    manifest = {
        "exported_at": datetime.now(UTC).isoformat(),
        "source_csv": _display_path(DATASET_CSV),
        "total_csv_rows": total,
        "exported": exported,
        "skipped": total - exported,
        "skip_reasons": skip_reasons,
        "train_dir": _display_path(TRAIN_DIR),
        "images_dir": _display_path(IMAGES_DIR),
        "formulas_jsonl": _display_path(FORMULAS_JSONL),
        "holdout_fraction": holdout_fraction() if exclude_holdout else 0.0,
        "holdout_rows": len(holdout_rows),
        "val_exported": len(val_rows),
        "val_dir": _display_path(VAL_DIR),
        "val_formulas_jsonl": _display_path(VAL_FORMULAS_JSONL),
        "val_skip_reasons": val_skip,
        "texteller_instructions": (
            "Clone https://github.com/OleehyO/TexTeller, pip install texteller[train], "
            "point examples/train_texteller/dataset/train at this export, then: "
            "cd examples/train_texteller && accelerate launch train.py"
        ),
    }
    FINETUNE_ROOT.mkdir(parents=True, exist_ok=True)
    MANIFEST_JSON.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    return RetrainExportResult(
        status="exported",
        message=(
            f"Exported {exported} samples to {_display_path(TRAIN_DIR)}; "
            f"{len(val_rows)} held out in {_display_path(VAL_DIR)}."
        ),
        total_samples=total,
        exported=exported,
        skipped=total - exported,
        skip_reasons=skip_reasons,
        export_dir=_display_path(TRAIN_DIR),
        formulas_jsonl=_display_path(FORMULAS_JSONL),
        min_samples=threshold,
        retrain_threshold=threshold,
        holdout_count=len(holdout_rows),
        val_exported=len(val_rows),
        val_dir=_display_path(VAL_DIR),
        val_formulas_jsonl=_display_path(VAL_FORMULAS_JSONL),
    )


def _texteller_train_repo() -> Path | None:
    raw = os.environ.get("TEXTELLER_TRAIN_REPO", "").strip()
    if raw:
        path = Path(raw)
        return path if path.is_dir() else None
    candidate = ROOT / "vendor" / "TexTeller"
    return candidate if candidate.is_dir() else None


def _accelerate_available() -> bool:
    try:
        import accelerate  # noqa: F401

        return True
    except ImportError:
        return False


def launch_texteller_training(*, export_result: RetrainExportResult) -> dict[str, Any]:
    """Optional GPU fine-tune via cloned TexTeller repo + accelerate."""
    repo = _texteller_train_repo()
    if repo is None:
        return {
            "ok": False,
            "reason": "no_repo",
            "message": (
                "Set TEXTELLER_TRAIN_REPO to a TexTeller clone "
                "(git clone https://github.com/OleehyO/TexTeller). "
                "Export is ready; run training manually or install texteller[train]."
            ),
        }
    if not _accelerate_available():
        return {
            "ok": False,
            "reason": "no_accelerate",
            "message": "pip install texteller[train] (includes accelerate) before --train.",
        }

    train_dir = repo / "examples" / "train_texteller"
    train_py = train_dir / "train.py"
    if not train_py.is_file():
        return {
            "ok": False,
            "reason": "train_script_missing",
            "message": f"Expected {train_py} — update TexTeller clone.",
        }

    # Symlink or copy our export into TexTeller's expected dataset/train folder.
    dest_train = train_dir / "dataset" / "train"
    if dest_train.exists():
        shutil.rmtree(dest_train)
    shutil.copytree(TRAIN_DIR, dest_train)

    cmd = [sys.executable, "-m", "accelerate.commands.launch", "train.py"]
    logger.info("Launching TexTeller fine-tune: %s (cwd=%s)", " ".join(cmd), train_dir)
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(train_dir),
            capture_output=True,
            text=True,
            timeout=int(os.environ.get("TEXTELLER_TRAIN_TIMEOUT_SEC", "7200")),
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "reason": "timeout",
            "message": "Training exceeded TEXTELLER_TRAIN_TIMEOUT_SEC.",
        }
    except Exception as e:
        return {"ok": False, "reason": "spawn_failed", "message": str(e)}

    ok = proc.returncode == 0
    tail = (proc.stdout or "")[-4000:] + "\n" + (proc.stderr or "")[-4000:]
    finetuned_hint = ""
    if ok:
        # Common TexTeller output locations — set TEXTELLER_FINETUNED_MODEL after manual export to ONNX.
        for cand in [
            train_dir / "output",
            train_dir / "checkpoints",
            repo / "output",
        ]:
            if cand.is_dir():
                finetuned_hint = str(cand)
                break
    return {
        "ok": ok,
        "reason": "completed" if ok else "failed",
        "returncode": proc.returncode,
        "log_tail": tail.strip(),
        "message": "Fine-tune finished." if ok else f"Fine-tune failed (exit {proc.returncode}).",
        "finetuned_checkpoint_hint": finetuned_hint,
        "next_step": (
            "Export checkpoint to ONNX, set TEXTELLER_FINETUNED_MODEL, POST /train/reload-model"
            if ok
            else ""
        ),
    }


def run_retrain_job(
    *,
    mode: Literal["export", "train"] = "export",
    min_samples: int | None = None,
    user_id: int | None = None,
) -> dict[str, Any]:
    export_result = export_texteller_dataset(min_samples=min_samples, user_id=user_id)
    out: dict[str, Any] = export_result.to_dict()

    if export_result.status not in ("exported",):
        return out

    if mode == "export":
        _write_last_retrain(out, train=None)
        return out

    train_info = launch_texteller_training(export_result=export_result)
    out["train"] = train_info
    out["status"] = "training_completed" if train_info.get("ok") else "export_only_train_failed"
    if train_info.get("ok"):
        out["message"] = "Export + fine-tune completed."
    else:
        out["message"] = export_result.message + " " + train_info.get("message", "")
    _write_last_retrain(out, train=train_info)
    return out


def _write_last_retrain(export: dict[str, Any], train: dict[str, Any] | None) -> None:
    FINETUNE_ROOT.mkdir(parents=True, exist_ok=True)
    payload = {
        "at": datetime.now(UTC).isoformat(),
        "export": export,
        "train": train,
    }
    LAST_RETRAIN_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
