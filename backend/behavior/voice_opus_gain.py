"""Optional digital gain for Zepp OS voice Opus clips (16 kHz mono).

Zepp stores Opus in a length-prefixed container (see Zepp FAQ opus-to-mp3).
When opuslib is installed, we decode → amplify PCM → re-encode so speech
recordings land louder on the PC without changing the watch firmware.
"""

from __future__ import annotations

import logging
import struct
from typing import Callable

log = logging.getLogger("desktop_tracker.voice_opus_gain")

SAMPLE_RATE = 16000
CHANNELS = 1
# Opus frame sizes at 16 kHz (samples); try largest first for Zepp clips.
_FRAME_SIZES = (960, 640, 480, 320, 160, 80, 40)


def _clamp_gain(gain: float) -> float:
    try:
        g = float(gain)
    except (TypeError, ValueError):
        return 1.0
    return max(0.25, min(8.0, g))


def _decode_zepp_opus(data: bytes, decode_fn: Callable[[bytes, int], bytes]) -> bytes:
    """Parse Zepp's length-prefixed Opus container into interleaved PCM s16le."""
    chunks: list[bytes] = []
    pos = 0
    size = len(data)
    while pos + 8 <= size:
        length = struct.unpack(">I", data[pos : pos + 4])[0]
        if length <= 0 or pos + 8 + length > size:
            break
        payload = data[pos + 8 : pos + 8 + length]
        pos += 8 + length
        if not payload:
            continue
        decoded = None
        for frame_size in _FRAME_SIZES:
            try:
                decoded = decode_fn(payload, frame_size)
                if decoded:
                    break
            except Exception:  # noqa: BLE001
                continue
        if decoded:
            chunks.append(decoded)
    if not chunks:
        raise ValueError("no_pcm_decoded")
    return b"".join(chunks)


def _encode_zepp_opus(pcm: bytes, encode_fn: Callable[[bytes, int], bytes]) -> bytes:
    """Pack PCM back into Zepp's length-prefixed Opus container."""
    out = bytearray()
    # 20 ms @ 16 kHz mono s16le
    frame_bytes = 640
    pos = 0
    while pos < len(pcm):
        piece = pcm[pos : pos + frame_bytes]
        pos += frame_bytes
        if len(piece) < frame_bytes:
            piece = piece + b"\x00" * (frame_bytes - len(piece))
        packet = encode_fn(piece, 320)
        if not packet:
            continue
        out.extend(struct.pack(">I", len(packet)))
        out.extend(b"\x00\x00\x00\x00")
        out.extend(packet)
    if not out:
        raise ValueError("no_opus_encoded")
    return bytes(out)


def _amplify_pcm_s16le(pcm: bytes, gain: float) -> bytes:
    import numpy as np

    g = _clamp_gain(gain)
    if abs(g - 1.0) < 0.01:
        return pcm
    arr = np.frombuffer(pcm, dtype=np.int16).astype(np.float32)
    arr *= g
    # Soft limiter — keep peaks below full scale to reduce harsh clipping.
    peak = float(np.max(np.abs(arr))) if arr.size else 0.0
    if peak > 30000.0:
        arr *= 30000.0 / peak
    return arr.clip(-32768, 32767).astype(np.int16).tobytes()


def amplify_zepp_opus(data: bytes, gain: float) -> bytes:
    """Return gain-adjusted Opus bytes, or the original blob if processing fails."""
    g = _clamp_gain(gain)
    if abs(g - 1.0) < 0.01 or not data:
        return data
    try:
        import opuslib  # type: ignore
    except ImportError:
        log.debug("voice gain skipped (pip install opuslib for PC amplification)")
        return data

    try:
        decoder = opuslib.Decoder(SAMPLE_RATE, CHANNELS)
        encoder = opuslib.Encoder(SAMPLE_RATE, CHANNELS, opuslib.APPLICATION_AUDIO)

        def decode(payload: bytes, frame_size: int) -> bytes:
            return decoder.decode(payload, frame_size)

        def encode(piece: bytes, frame_size: int) -> bytes:
            return encoder.encode(piece, frame_size)

        pcm = _decode_zepp_opus(data, decode)
        boosted = _amplify_pcm_s16le(pcm, g)
        return _encode_zepp_opus(boosted, encode)
    except Exception as exc:  # noqa: BLE001
        log.warning("voice opus gain failed (%s) — storing original", exc)
        return data
