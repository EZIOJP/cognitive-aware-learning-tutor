"""ESP32 UDP EEG ingest + WebSocket broadcast (optional; enable with EEG_ENABLED=1).

Soft-fail design: quiet/missing stream is a status, never an API hard failure.
"""

from __future__ import annotations

import asyncio
import struct
import time
from collections import deque
from typing import Any, Set

try:
    import numpy as np
    from scipy.fft import fft, fftfreq
except ImportError:
    np = None  # type: ignore

eeg_buffer: deque = deque(maxlen=512)
_ws_clients: Set = set()
_udp_transport = None
_last_packet_monotonic: float | None = None
_packet_count: int = 0
_enabled: bool = False
_last_voltage: float | None = None
_last_from: str | None = None
_snap_count: int = 0
_last_snap_monotonic: float | None = None
_baseline_v: float = 1.65
_SNAP_DELTA_V = 0.4
_SNAP_COOLDOWN_S = 0.4


def _band_power(freqs, power, low: float, high: float) -> float:
    mask = (freqs >= low) & (freqs < high)
    return float(np.sum(power[mask]))


def extract_frequency_bands(samples: list[float], sample_rate: int = 250) -> tuple[float, float, float]:
    if np is None or len(samples) < 128:
        return 0.0, 0.0, 0.0
    signal = np.array(samples) - np.mean(samples)
    window = np.hamming(len(signal))
    signal = signal * window
    yf = fft(signal)
    xf = fftfreq(len(signal), 1 / sample_rate)[: len(signal) // 2]
    power = np.abs(yf[: len(signal) // 2]) ** 2
    alpha = _band_power(xf, power, 8, 13)
    beta = _band_power(xf, power, 13, 30)
    gamma = _band_power(xf, power, 30, 100)
    total = alpha + beta + gamma
    if total <= 0:
        return 0.0, 0.0, 0.0
    return (alpha / total) * 100, (beta / total) * 100, (gamma / total) * 100


def _note_sample(voltage: float, addr: tuple | None = None) -> None:
    """Update live voltage + detect SELF_TEST / transient snaps."""
    global _last_packet_monotonic, _packet_count, _last_voltage, _last_from
    global _snap_count, _last_snap_monotonic, _baseline_v

    eeg_buffer.append(voltage)
    _last_packet_monotonic = time.monotonic()
    _packet_count += 1
    _last_voltage = float(voltage)
    if addr:
        _last_from = str(addr[0])

    _baseline_v = _baseline_v * 0.999 + voltage * 0.001
    now = time.monotonic()
    cooled = _last_snap_monotonic is None or (now - _last_snap_monotonic) > _SNAP_COOLDOWN_S
    if cooled and voltage > _baseline_v + _SNAP_DELTA_V:
        _last_snap_monotonic = now
        _snap_count += 1


class EEGUDPProtocol(asyncio.DatagramProtocol):
    def datagram_received(self, data: bytes, addr) -> None:
        try:
            if len(data) >= 4:
                voltage = struct.unpack("f", data[:4])[0]
                _note_sample(voltage, addr)
        except Exception:
            # Soft-fail: bad packet ignored
            pass


async def start_udp_server(port: int = 5005):
    global _udp_transport, _enabled
    _enabled = True
    loop = asyncio.get_event_loop()
    _udp_transport, _ = await loop.create_datagram_endpoint(
        lambda: EEGUDPProtocol(),
        local_addr=("0.0.0.0", port),
    )


def stream_status(*, stale_after_s: float = 2.0) -> str:
    """offline | warming | streaming — never raises."""
    if not _enabled:
        return "disabled"
    if _last_packet_monotonic is None:
        return "offline"
    age = time.monotonic() - _last_packet_monotonic
    if age > stale_after_s:
        return "offline"
    if len(eeg_buffer) < 64:
        return "warming"
    return "streaming"


def status_payload() -> dict[str, Any]:
    """Safe for /health and UI — absence is informational."""
    age = None
    if _last_packet_monotonic is not None:
        age = round(time.monotonic() - _last_packet_monotonic, 3)
    snap_age = None
    if _last_snap_monotonic is not None:
        snap_age = round(time.monotonic() - _last_snap_monotonic, 3)
    return {
        "enabled": _enabled,
        "status": stream_status(),
        "buffer_size": len(eeg_buffer),
        "packet_count": _packet_count,
        "last_packet_age_s": age,
        "last_voltage": round(_last_voltage, 4) if _last_voltage is not None else None,
        "last_from": _last_from,
        "snap_count": _snap_count,
        "last_snap_age_s": snap_age,
        "ok": True,  # EEG never fails the stack
        "reliable_without_device": True,
    }


async def broadcast_loop():
    while True:
        status = stream_status()
        if status == "streaming" and len(eeg_buffer) >= 128:
            alpha, beta, gamma = extract_frequency_bands(list(eeg_buffer))
            source = "hardware"
        elif status in ("warming", "streaming"):
            alpha = beta = gamma = 0.0
            source = "hardware"
        else:
            # No live stream — do not invent load; clients use sim or ignore
            alpha = beta = gamma = 0.0
            source = "none"

        snap_age = None
        if _last_snap_monotonic is not None:
            snap_age = round(time.monotonic() - _last_snap_monotonic, 3)

        payload = {
            "type": "eeg_data",
            "alpha": round(alpha, 2),
            "beta": round(beta, 2),
            "gamma": round(gamma, 2),
            "timestamp": time.time() * 1000,
            "recv_ms": int(time.time() * 1000),
            "source": source,
            "status": status,
            "voltage": round(_last_voltage, 4) if _last_voltage is not None else None,
            "snap_count": _snap_count,
            "last_snap_age_s": snap_age,
            "packet_count": _packet_count,
        }
        dead = set()
        for ws in list(_ws_clients):
            try:
                await ws.send_json(payload)
            except Exception:
                dead.add(ws)
        _ws_clients -= dead
        await asyncio.sleep(0.1)


def register_ws(ws) -> None:
    _ws_clients.add(ws)


def unregister_ws(ws) -> None:
    _ws_clients.discard(ws)
