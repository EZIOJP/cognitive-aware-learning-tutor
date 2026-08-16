"""Light DSP post-filter for Jarvis TTS mode (butler presence, not cartoon robot).

Chain (tasteful, subtle):
  1. Mild low-pass / moving-average (less bright)
  2. Soft presence shelf around ~1.2–2.5 kHz
  3. Very light soft-saturation (gentle compression feel)
  4. Tiny high-shelf cut + short wet/dry “room” (one-tap echo)

Uses numpy; optional scipy for a cleaner FIR. Fail soft: callers catch errors
and play unfiltered audio.
"""

from __future__ import annotations

import logging
import wave
from pathlib import Path

log = logging.getLogger("desktop_tracker.voice_agent")


def apply_jarvis_filter(wav_path: Path, *, out_path: Path | None = None) -> Path:
    """Read WAV, apply Jarvis chain, write WAV. Returns output path.

    Raises on hard I/O errors; DSP internals should not raise after load.
    """
    wav_path = Path(wav_path)
    dest = Path(out_path) if out_path else wav_path.with_name(wav_path.stem + "_jarvis.wav")
    with wave.open(str(wav_path), "rb") as wf:
        nch = wf.getnchannels()
        sw = wf.getsampwidth()
        sr = wf.getframerate()
        nframes = wf.getnframes()
        raw = wf.readframes(nframes)

    if sw != 2:
        # Only int16 PCM; leave unusual formats unchanged
        if dest != wav_path:
            dest.write_bytes(wav_path.read_bytes())
            return dest
        return wav_path

    import numpy as np

    samples = np.frombuffer(raw, dtype=np.int16).astype(np.float64)
    if nch > 1:
        samples = samples.reshape(-1, nch)
        mono = samples.mean(axis=1)
    else:
        mono = samples

    filtered = jarvis_process_mono(mono, sr)

    if nch > 1:
        # Replicate filtered mono to all channels (keeps layout)
        out = np.column_stack([filtered] * nch).reshape(-1)
    else:
        out = filtered

    out_i16 = np.clip(out, -32768, 32767).astype(np.int16)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(dest), "wb") as wf:
        wf.setnchannels(nch)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(out_i16.tobytes())
    return dest


def jarvis_process_mono(samples, sample_rate: int):
    """Apply Jarvis DSP to float64 mono samples. Pure numpy (+ optional scipy)."""
    import numpy as np

    x = np.asarray(samples, dtype=np.float64)
    if x.size == 0:
        return x

    # Normalize lightly for processing headroom
    peak = float(np.max(np.abs(x))) or 1.0
    x = x / peak

    # 1) Mild low-pass (moving average / FIR) — butler, less bright
    x = _lowpass(x, sample_rate, cutoff_hz=6200.0)

    # 2) Soft presence boost around ~1.8 kHz (narrow shelf via band emphasis)
    x = _presence_boost(x, sample_rate, center_hz=1800.0, gain=0.12)

    # 3) Soft saturation (very light)
    x = np.tanh(x * 1.15) / np.tanh(1.15)

    # 4) Mild high-shelf cut + tiny room (one-tap delayed wet)
    x = _high_shelf_cut(x, sample_rate, cutoff_hz=7500.0, amount=0.22)
    x = _tiny_room(x, sample_rate, delay_ms=28.0, mix=0.08)

    # Restore level (~−1 dB from peak)
    peak2 = float(np.max(np.abs(x))) or 1.0
    x = x / peak2 * (peak * 0.92)
    return x


def _lowpass(x, sr: int, cutoff_hz: float):
    import numpy as np

    # Window length ~ proportional to sr/cutoff; clamp for stability
    n = max(3, min(61, int(sr / max(cutoff_hz, 1.0) * 0.35) | 1))  # odd
    try:
        from scipy.signal import firwin, lfilter

        taps = firwin(n, cutoff_hz / (0.5 * sr))
        return lfilter(taps, [1.0], x)
    except Exception:
        kernel = np.ones(n, dtype=np.float64) / n
        return np.convolve(x, kernel, mode="same")


def _presence_boost(x, sr: int, center_hz: float, gain: float):
    import numpy as np

    # Crude resonant emphasis: bandpass residual mixed back
    # band ≈ center ± 600 Hz via two moving averages
    bw = 600.0
    n_lo = max(3, min(81, int(sr / max(center_hz - bw, 200.0) * 0.25) | 1))
    n_hi = max(3, min(41, int(sr / max(center_hz + bw, 400.0) * 0.25) | 1))
    lo = np.convolve(x, np.ones(n_lo) / n_lo, mode="same")
    hi = np.convolve(x, np.ones(n_hi) / n_hi, mode="same")
    band = lo - hi
    return x + gain * band


def _high_shelf_cut(x, sr: int, cutoff_hz: float, amount: float):
    import numpy as np

    n = max(3, min(51, int(sr / max(cutoff_hz, 1.0) * 0.3) | 1))
    smooth = np.convolve(x, np.ones(n) / n, mode="same")
    highs = x - smooth
    return smooth + highs * (1.0 - amount)


def _tiny_room(x, sr: int, delay_ms: float, mix: float):
    import numpy as np

    delay = max(1, int(sr * delay_ms / 1000.0))
    if delay >= x.size:
        return x
    wet = np.zeros_like(x)
    wet[delay:] = x[:-delay] * 0.55
    return (1.0 - mix) * x + mix * wet
