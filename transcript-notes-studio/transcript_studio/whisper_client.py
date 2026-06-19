"""Whisper speech-to-text — Hugging Face Transformers or faster-whisper."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Literal

from transcript_studio.snapshots import TranscriptSegment

log = logging.getLogger(__name__)

WhisperEngine = Literal["transformers", "faster-whisper"]

MODEL_ALIASES: dict[str, str] = {
    "xkeyc/whisper-large-v3-turbo-gguf": "openai/whisper-large-v3-turbo",
    "xkeyC/whisper-large-v3-turbo-gguf": "openai/whisper-large-v3-turbo",
}

WHISPER_PRESETS: list[tuple[str, WhisperEngine, str]] = [
    ("openai/whisper-large-v3-turbo (Hugging Face)", "transformers", "openai/whisper-large-v3-turbo"),
    ("openai/whisper-large-v3", "transformers", "openai/whisper-large-v3"),
    ("openai/whisper-medium", "transformers", "openai/whisper-medium"),
    ("openai/whisper-small", "transformers", "openai/whisper-small"),
    ("faster-whisper · large-v3-turbo (lighter)", "faster-whisper", "large-v3-turbo"),
    ("faster-whisper · large-v3", "faster-whisper", "large-v3"),
    ("faster-whisper · medium", "faster-whisper", "medium"),
    ("Custom model ID…", "transformers", ""),
]


@dataclass
class TranscribeResult:
    text: str
    segments: list[TranscriptSegment]


def resolve_model_id(model_id: str) -> str:
    key = model_id.strip()
    if not key:
        return "openai/whisper-large-v3-turbo"
    return MODEL_ALIASES.get(key, MODEL_ALIASES.get(key.lower(), key))


def check_whisper_deps(engine: WhisperEngine) -> tuple[bool, str]:
    if engine == "faster-whisper":
        try:
            import faster_whisper  # noqa: F401

            return True, "faster-whisper installed"
        except ImportError:
            return False, "Install Whisper extras: pip install -r requirements-whisper.txt"
    try:
        import torch  # noqa: F401
        import transformers  # noqa: F401

        return True, "transformers + torch installed"
    except ImportError:
        return False, "Install Whisper extras: pip install -r requirements-whisper.txt"


def _resolve_torch_device(device: str) -> tuple[str, object]:
    import torch

    if device == "auto":
        dev = "cuda:0" if torch.cuda.is_available() else "cpu"
    else:
        dev = device
    dtype = torch.float16 if str(dev).startswith("cuda") else torch.float32
    return dev, dtype


def _transcribe_transformers(
    audio_path: Path,
    *,
    model_id: str,
    device: str,
    language: str | None,
    task: str,
    on_progress: Callable[[str], None] | None,
) -> TranscribeResult:
    import torch
    from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline

    resolved = resolve_model_id(model_id)
    if on_progress:
        on_progress(f"Loading {resolved}…")

    dev, dtype = _resolve_torch_device(device)
    model = AutoModelForSpeechSeq2Seq.from_pretrained(
        resolved,
        torch_dtype=dtype,
        low_cpu_mem_usage=True,
        use_safetensors=True,
    )
    model.to(dev)
    processor = AutoProcessor.from_pretrained(resolved)

    if on_progress:
        on_progress(f"Transcribing on {dev}…")

    pipe = pipeline(
        "automatic-speech-recognition",
        model=model,
        tokenizer=processor.tokenizer,
        feature_extractor=processor.feature_extractor,
        torch_dtype=dtype,
        device=dev,
        chunk_length_s=30,
    )

    generate_kwargs: dict = {}
    if language and language.strip():
        generate_kwargs["language"] = language.strip().lower()
    if task == "translate":
        generate_kwargs["task"] = "translate"

    result = pipe(
        str(audio_path),
        return_timestamps=True,
        generate_kwargs=generate_kwargs if generate_kwargs else {},
    )
    if not isinstance(result, dict):
        text = str(result).strip()
        return TranscribeResult(text=text, segments=[])

    text = (result.get("text") or "").strip()
    segments: list[TranscriptSegment] = []
    for chunk in result.get("chunks") or []:
        ts = chunk.get("timestamp") or (0.0, 0.0)
        seg_text = (chunk.get("text") or "").strip()
        if not seg_text:
            continue
        start = float(ts[0] if ts[0] is not None else 0.0)
        end = float(ts[1] if ts[1] is not None else start)
        segments.append(TranscriptSegment(start=start, end=end, text=seg_text))

    if not text and segments:
        text = " ".join(s.text for s in segments)
    return TranscribeResult(text=text, segments=segments)


def _transcribe_faster_whisper(
    audio_path: Path,
    *,
    model_id: str,
    device: str,
    language: str | None,
    task: str,
    on_progress: Callable[[str], None] | None,
) -> TranscribeResult:
    from faster_whisper import WhisperModel

    if device == "auto":
        try:
            import torch

            dev = "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            dev = "cpu"
    else:
        dev = "cuda" if device.startswith("cuda") else "cpu"

    compute_type = "float16" if dev == "cuda" else "int8"
    resolved = resolve_model_id(model_id) if "/" in model_id else model_id

    if on_progress:
        on_progress(f"Loading faster-whisper {resolved} ({dev})…")

    model = WhisperModel(resolved, device=dev, compute_type=compute_type)
    lang = language.strip().lower() if language and language.strip() else None

    if on_progress:
        on_progress("Transcribing…")

    raw_segments, _info = model.transcribe(
        str(audio_path),
        language=lang,
        task="translate" if task == "translate" else "transcribe",
    )
    segments: list[TranscriptSegment] = []
    parts: list[str] = []
    for seg in raw_segments:
        t = seg.text.strip()
        if not t:
            continue
        segments.append(TranscriptSegment(start=seg.start, end=seg.end, text=t))
        parts.append(t)
    text = " ".join(parts)
    return TranscribeResult(text=text, segments=segments)


def transcribe_audio(
    audio_path: Path,
    *,
    engine: WhisperEngine = "transformers",
    model_id: str = "openai/whisper-large-v3-turbo",
    device: str = "auto",
    language: str | None = None,
    task: str = "transcribe",
    on_progress: Callable[[str], None] | None = None,
) -> TranscribeResult:
    if not audio_path.is_file():
        raise FileNotFoundError(f"Audio not found: {audio_path}")

    ok, msg = check_whisper_deps(engine)
    if not ok:
        raise RuntimeError(msg)

    if engine == "faster-whisper":
        return _transcribe_faster_whisper(
            audio_path,
            model_id=model_id,
            device=device,
            language=language,
            task=task,
            on_progress=on_progress,
        )
    return _transcribe_transformers(
        audio_path,
        model_id=model_id,
        device=device,
        language=language,
        task=task,
        on_progress=on_progress,
    )


def save_transcript(text: str, *, output_dir: Path, stem: str | None = None) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    base = stem or "whisper_transcript"
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in base)[:50]
    path = output_dir / f"{safe}_{stamp}.txt"
    path.write_text(text.strip() + "\n", encoding="utf-8")
    return path
