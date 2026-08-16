"""Occasional lightweight NSFW screen scan for the desktop tracker.

Honesty
-------
- Keywords in browser_gate_policy: ~0 cost (text only).
- This module: every N seconds (default 60), one downscaled screenshot on
  **CPU** → short spike, **~0 VRAM** when using onnxruntime CPU / NudeNet CPU.
- Continuous video GPU NSFW: **not implemented** (heavy on 8GB GPUs).

Enable / disable
----------------
- Default **on while hard-block Armed** (and morning enforce via tracker gate).
- ``NSFW_SCREEN_SCAN=0`` → always off.
- ``NSFW_SCREEN_SCAN=1`` → force on even if not Armed (still respects gaming silence).
- Gaming silence: ``VOICE_AGENT_ENABLED=0`` (same kill-switch as voice) → skip scan.
- Interval: ``NSFW_SCREEN_INTERVAL_S`` (default 60, clamp 30–180).

Classifier backends (first available wins; missing deps never crash tracker)
---------------------------------------------------------------------------
1. Optional ``nudenet`` if installed.
2. Optional onnxruntime + ``data/nsfw/*.onnx`` if present.
3. Else weak skin-tone heuristic (default CPU path; ``NSFW_SCREEN_HEURISTIC=0`` to disable).
   When heuristic is off and no model → inactive status on Today's rules + speak once.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

log = logging.getLogger("calt.nsfw_screen")

_ROOT = Path(__file__).resolve().parent.parent.parent
NSFW_DIR = _ROOT / "data" / "nsfw"
DEFAULT_INTERVAL_S = 60.0
DEFAULT_THRESHOLD = 0.55
_DOWNSCALE = (224, 224)

_logged_backend: str | None = None
_last_scan_at = 0.0
_classifier: Callable[[Any], float] | None = None
_classifier_name = "none"
_init_attempted = False


@dataclass
class NsfwScanResult:
    ran: bool
    positive: bool
    score: float
    backend: str
    reason: str = ""


def _env_flag(name: str, default: str = "0") -> bool:
    raw = (os.environ.get(name) or default).strip().lower()
    return raw in {"1", "true", "yes", "on"}


def gaming_silence_active() -> bool:
    """True when user set voice/gaming silence kill-switch."""
    raw = (os.environ.get("VOICE_AGENT_ENABLED") or "1").strip().lower()
    return raw in {"0", "false", "off", "no"}


def scan_interval_s() -> float:
    try:
        v = float(os.environ.get("NSFW_SCREEN_INTERVAL_S") or DEFAULT_INTERVAL_S)
    except ValueError:
        v = DEFAULT_INTERVAL_S
    return max(30.0, min(180.0, v))


def score_threshold() -> float:
    try:
        v = float(os.environ.get("NSFW_SCREEN_THRESHOLD") or DEFAULT_THRESHOLD)
    except ValueError:
        v = DEFAULT_THRESHOLD
    return max(0.35, min(0.95, v))


def should_run_scan(*, hard_block_armed: bool, day_enforce: bool = False) -> bool:
    """Whether a scan pass is allowed right now (ignores interval)."""
    raw = (os.environ.get("NSFW_SCREEN_SCAN") or "").strip().lower()
    if raw in {"0", "false", "off", "no"}:
        return False
    if gaming_silence_active():
        return False
    if raw in {"1", "true", "yes", "on"}:
        return True
    # Default (unset): on when Armed or day-mode browser enforce (study/free/…)
    return bool(hard_block_armed) or bool(day_enforce)


def scan_status() -> dict[str, Any]:
    """UI-facing status for Today's rules / tray (never throws)."""
    raw = (os.environ.get("NSFW_SCREEN_SCAN") or "").strip().lower()
    if raw in {"0", "false", "off", "no"}:
        return {
            "active": False,
            "backend": "off",
            "message": "NSFW scan off (NSFW_SCREEN_SCAN=0)",
        }
    if gaming_silence_active():
        return {
            "active": False,
            "backend": "silence",
            "message": "NSFW scan paused (gaming silence)",
        }
    _try_init_classifier()
    name = _classifier_name or "none"
    if name == "none" or _classifier is None:
        return {
            "active": False,
            "backend": "none",
            "message": "NSFW scan inactive: install nudenet / set model",
        }
    if name == "skin_heuristic":
        return {
            "active": True,
            "backend": name,
            "message": "NSFW scan: weak skin heuristic - install nudenet for better detection",
        }
    return {
        "active": True,
        "backend": name,
        "message": f"NSFW scan: {name}",
    }


def _log_backend_once(name: str, detail: str = "") -> None:
    global _logged_backend
    if _logged_backend == name:
        return
    _logged_backend = name
    if detail:
        log.info("[nsfw_screen] backend=%s (%s)", name, detail)
    else:
        log.info("[nsfw_screen] backend=%s", name)


def _try_init_classifier() -> None:
    global _classifier, _classifier_name, _init_attempted
    if _init_attempted:
        return
    _init_attempted = True

    # 1) NudeNet (optional pip)
    try:
        from nudenet import NudeDetector  # type: ignore[import-untyped]

        det = NudeDetector()

        def _nudenet_score(pil_img: Any) -> float:
            import tempfile

            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                path = tmp.name
            try:
                pil_img.convert("RGB").save(path, format="JPEG", quality=75)
                dets = det.detect(path) or []
            finally:
                try:
                    os.unlink(path)
                except OSError:
                    pass
            # Labels vary by version; take max NSFW-ish score
            nsfw_labels = {
                "FEMALE_GENITALIA_EXPOSED",
                "MALE_GENITALIA_EXPOSED",
                "FEMALE_BREAST_EXPOSED",
                "BUTTOCKS_EXPOSED",
                "ANUS_EXPOSED",
                "BELLY_EXPOSED",
            }
            best = 0.0
            for d in dets:
                label = str(d.get("class") or d.get("label") or "").upper()
                score = float(d.get("score") or d.get("confidence") or 0.0)
                if label in nsfw_labels or "EXPOSED" in label:
                    best = max(best, score)
            return best

        _classifier = _nudenet_score
        _classifier_name = "nudenet"
        _log_backend_once("nudenet", "optional package")
        return
    except Exception as exc:  # noqa: BLE001
        log.debug("nudenet unavailable: %s", exc)

    # 2) ONNX model under data/nsfw/
    onnx_paths = sorted(NSFW_DIR.glob("*.onnx")) if NSFW_DIR.is_dir() else []
    if onnx_paths:
        try:
            import numpy as np
            import onnxruntime as ort  # type: ignore[import-untyped]

            model_path = onnx_paths[0]
            sess = ort.InferenceSession(
                str(model_path),
                providers=["CPUExecutionProvider"],
            )
            input_meta = sess.get_inputs()[0]
            in_name = input_meta.name

            def _onnx_score(pil_img: Any) -> float:
                img = pil_img.convert("RGB").resize(_DOWNSCALE)
                arr = np.asarray(img, dtype=np.float32) / 255.0
                # NCHW batch
                tensor = arr.transpose(2, 0, 1)[None, ...]
                outs = sess.run(None, {in_name: tensor})
                out = outs[0]
                flat = np.asarray(out).reshape(-1).astype(float)
                if flat.size == 1:
                    return float(flat[0])
                # Assume [sfw, nsfw] or similar — take max / last
                if flat.size >= 2:
                    return float(max(flat[1], flat[-1]))
                return float(flat.max())

            _classifier = _onnx_score
            _classifier_name = f"onnx:{model_path.name}"
            _log_backend_once(_classifier_name, "CPUExecutionProvider")
            return
        except Exception as exc:  # noqa: BLE001
            log.debug("onnx nsfw unavailable: %s", exc)

    # 3) Weak heuristic — default CPU path when no model (opt-out via NSFW_SCREEN_HEURISTIC=0)
    heuristic_raw = (os.environ.get("NSFW_SCREEN_HEURISTIC") or "1").strip().lower()
    if heuristic_raw not in {"0", "false", "off", "no"}:

        def _heuristic_score(pil_img: Any) -> float:
            return _skin_tone_ratio(pil_img)

        _classifier = _heuristic_score
        _classifier_name = "skin_heuristic"
        _log_backend_once(
            "skin_heuristic",
            "weak default CPU path — prefer nudenet or data/nsfw/*.onnx",
        )
        return

    _classifier = None
    _classifier_name = "none"
    _log_backend_once(
        "none",
        "install nudenet or place *.onnx in data/nsfw/ — scans skipped until then",
    )


def _skin_tone_ratio(pil_img: Any) -> float:
    """Very weak proxy — high threshold required. Not a real NSFW detector."""
    import numpy as np

    img = pil_img.convert("RGB").resize((160, 90))
    arr = np.asarray(img, dtype=np.float32)
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    # Rough YCbCr-ish skin band
    skin = (
        (r > 95)
        & (g > 40)
        & (b > 20)
        & (r > g)
        & (r > b)
        & ((r - g) > 15)
    )
    return float(skin.mean())


def capture_downscaled_screenshot() -> Any | None:
    """Grab primary screen, downscale. Returns PIL Image or None."""
    try:
        from PIL import ImageGrab
    except Exception as exc:  # noqa: BLE001
        log.debug("Pillow ImageGrab missing: %s", exc)
        return None
    try:
        shot = ImageGrab.grab(all_screens=False)
    except Exception as exc:  # noqa: BLE001
        log.debug("screenshot failed: %s", exc)
        return None
    try:
        return shot.convert("RGB").resize(_DOWNSCALE)
    except Exception:  # noqa: BLE001
        return shot


def classify_image(pil_img: Any) -> tuple[float, str]:
    """Return (score, backend_name)."""
    _try_init_classifier()
    if _classifier is None:
        return 0.0, "none"
    try:
        score = float(_classifier(pil_img))
        return max(0.0, min(1.0, score)), _classifier_name
    except Exception as exc:  # noqa: BLE001
        log.warning("[nsfw_screen] classify failed: %s", exc)
        return 0.0, _classifier_name


def maybe_scan_screen(
    *,
    hard_block_armed: bool,
    day_enforce: bool = False,
    force: bool = False,
    now: float | None = None,
) -> NsfwScanResult:
    """Interval-gated scan. Safe no-op when disabled / no backend."""
    global _last_scan_at
    t = time.time() if now is None else now
    if not should_run_scan(hard_block_armed=hard_block_armed, day_enforce=day_enforce):
        return NsfwScanResult(False, False, 0.0, "off", "disabled")
    interval = scan_interval_s()
    if not force and (t - _last_scan_at) < interval:
        return NsfwScanResult(False, False, 0.0, "skip", "interval")
    _last_scan_at = t

    img = capture_downscaled_screenshot()
    if img is None:
        return NsfwScanResult(True, False, 0.0, "none", "capture_failed")

    score, backend = classify_image(img)
    if backend == "none":
        return NsfwScanResult(True, False, 0.0, backend, "no_classifier")

    thr = score_threshold()
    # Heuristic needs a higher bar
    if backend == "skin_heuristic":
        thr = max(thr, 0.72)
    positive = score >= thr
    if positive:
        log.warning(
            "[nsfw_screen] positive score=%.3f thr=%.3f backend=%s",
            score,
            thr,
            backend,
        )
    else:
        log.debug(
            "[nsfw_screen] ok score=%.3f thr=%.3f backend=%s",
            score,
            thr,
            backend,
        )
    return NsfwScanResult(True, positive, score, backend, "scanned")


def reset_scan_state_for_tests() -> None:
    """Test helper — clear caches."""
    global _last_scan_at, _classifier, _classifier_name, _init_attempted, _logged_backend
    _last_scan_at = 0.0
    _classifier = None
    _classifier_name = "none"
    _init_attempted = False
    _logged_backend = None
