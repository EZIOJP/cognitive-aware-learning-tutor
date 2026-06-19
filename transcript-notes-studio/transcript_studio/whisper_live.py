"""Live audio → Whisper transcription in timed chunks (mic or system loopback)."""

from __future__ import annotations

import platform
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Literal

import numpy as np

from transcript_studio.snapshots import TranscriptSegment
from transcript_studio.whisper_client import resolve_model_id

AudioSource = Literal["mic", "system"]
SAMPLE_RATE = 16_000

_FASTER_MODEL_IDS = {
    "openai/whisper-large-v3-turbo": "large-v3-turbo",
    "openai/whisper-large-v3": "large-v3",
    "openai/whisper-medium": "medium",
    "openai/whisper-small": "small",
}


def faster_whisper_model_id(model_id: str) -> str:
    resolved = resolve_model_id(model_id) if model_id.strip() else "large-v3-turbo"
    if resolved in _FASTER_MODEL_IDS:
        return _FASTER_MODEL_IDS[resolved]
    if "/" not in resolved:
        return resolved
    return "large-v3-turbo"


def check_live_whisper_deps() -> tuple[bool, str]:
    try:
        import sounddevice  # noqa: F401
        import soundfile  # noqa: F401
    except ImportError:
        return False, "Install live extras: pip install faster-whisper sounddevice soundfile"
    try:
        import faster_whisper  # noqa: F401

        return True, "faster-whisper + sounddevice ready"
    except ImportError:
        return False, "Needs faster-whisper (pip install faster-whisper sounddevice soundfile)"


def check_system_audio_available() -> tuple[bool, str]:
    if platform.system() != "Windows":
        return False, "System audio capture requires Windows (WASAPI loopback)."
    try:
        import sounddevice as sd
    except ImportError:
        return False, "Install sounddevice for system audio capture."

    hostapis = sd.query_hostapis()
    if not any("wasapi" in (h.get("name") or "").lower() for h in hostapis):
        return False, "WASAPI not available on this system."

    out_idx = sd.default.device[1]
    if out_idx is None or int(out_idx) < 0:
        return False, "No default speakers/output device found."

    name = sd.query_devices(out_idx).get("name", "speakers")
    return True, f"System audio ready — will capture from: {name}"


def _to_mono(frames: np.ndarray) -> np.ndarray:
    audio = np.squeeze(frames)
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    return audio.astype(np.float32)


@dataclass
class LiveWhisperSession:
    """Record live audio and transcribe every N seconds with faster-whisper."""

    model_id: str = "large-v3-turbo"
    device: str = "auto"
    language: str | None = None
    task: str = "transcribe"
    chunk_seconds: float = 10.0
    audio_source: AudioSource = "system"
    silence_threshold: float = 0.008
    segments: list[str] = field(default_factory=list)
    transcript_segments: list[TranscriptSegment] = field(default_factory=list)
    _elapsed: float = 0.0
    _model: object | None = field(default=None, repr=False)

    def _resolve_device(self) -> str:
        if self.device == "auto":
            try:
                import torch

                return "cuda" if torch.cuda.is_available() else "cpu"
            except ImportError:
                return "cpu"
        return "cuda" if self.device.startswith("cuda") else "cpu"

    def _ensure_model(self, on_progress: Callable[[str], None] | None) -> None:
        if self._model is not None:
            return
        from faster_whisper import WhisperModel

        dev = self._resolve_device()
        compute = "float16" if dev == "cuda" else "int8"
        resolved = faster_whisper_model_id(self.model_id)
        if on_progress:
            on_progress(f"Loading faster-whisper {resolved} ({dev})…")
        self._model = WhisperModel(resolved, device=dev, compute_type=compute)

    def _record_chunk(self, n_samples: int) -> np.ndarray:
        import sounddevice as sd

        if self.audio_source == "system":
            ok, msg = check_system_audio_available()
            if not ok:
                raise RuntimeError(msg)
            out_idx = int(sd.default.device[1])
            loopback = sd.WasapiSettings(loopback=True)
            frames = sd.rec(
                n_samples,
                samplerate=SAMPLE_RATE,
                channels=2,
                dtype="float32",
                device=(out_idx, loopback),
                blocking=True,
            )
            return _to_mono(frames)

        frames = sd.rec(
            n_samples,
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="float32",
            blocking=True,
        )
        return _to_mono(frames)

    def _transcribe_chunk(
        self,
        audio: np.ndarray,
        *,
        chunk_start: float,
        on_text: Callable[[str], None] | None,
    ) -> None:
        import soundfile as sf
        from faster_whisper import WhisperModel

        assert isinstance(self._model, WhisperModel)
        lang = self.language.strip().lower() if self.language and self.language.strip() else None

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = Path(tmp.name)
        try:
            sf.write(str(tmp_path), audio, SAMPLE_RATE)
            raw_segments, _info = self._model.transcribe(
                str(tmp_path),
                language=lang,
                task="translate" if self.task == "translate" else "transcribe",
                vad_filter=True,
            )
            for seg in raw_segments:
                text = seg.text.strip()
                if not text:
                    continue
                self.segments.append(text)
                self.transcript_segments.append(
                    TranscriptSegment(
                        start=chunk_start + seg.start,
                        end=chunk_start + seg.end,
                        text=text,
                    )
                )
                if on_text:
                    on_text(text)
        finally:
            tmp_path.unlink(missing_ok=True)

    def run(
        self,
        *,
        stop_event: threading.Event,
        on_text: Callable[[str], None] | None = None,
        on_progress: Callable[[str], None] | None = None,
        max_seconds: float | None = None,
    ) -> list[str]:
        ok, msg = check_live_whisper_deps()
        if not ok:
            raise RuntimeError(msg)
        if self.audio_source == "system":
            ok, sys_msg = check_system_audio_available()
            if not ok:
                raise RuntimeError(sys_msg)

        self._ensure_model(on_progress)
        chunk_samples = max(int(self.chunk_seconds * SAMPLE_RATE), SAMPLE_RATE)
        deadline = time.monotonic() + max_seconds if max_seconds and max_seconds > 0 else None

        source_label = (
            "system audio (speakers / browser)"
            if self.audio_source == "system"
            else "microphone"
        )
        if on_progress:
            on_progress(
                f"Listening on {source_label} — transcribing every {self.chunk_seconds:.0f}s "
                f"(~{self.chunk_seconds:.0f}s lag vs real time)"
            )

        threshold = self.silence_threshold
        if self.audio_source == "system":
            threshold = min(threshold, 0.004)

        self._elapsed = 0.0
        while not stop_event.is_set():
            if deadline is not None and time.monotonic() >= deadline:
                break

            try:
                audio = self._record_chunk(chunk_samples)
            except Exception as exc:
                raise RuntimeError(f"Audio capture failed: {exc}") from exc

            if stop_event.is_set():
                break

            if float(np.max(np.abs(audio))) < threshold:
                self._elapsed += self.chunk_seconds
                continue

            chunk_start = self._elapsed
            try:
                self._transcribe_chunk(audio, chunk_start=chunk_start, on_text=on_text)
            except Exception:
                break
            self._elapsed += self.chunk_seconds

        return self.segments

    @property
    def full_text(self) -> str:
        return " ".join(self.segments)
