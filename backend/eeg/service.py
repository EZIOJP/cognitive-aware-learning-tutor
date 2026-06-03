"""ESP32 UDP EEG ingest + WebSocket broadcast (optional; enable with EEG_ENABLED=1)."""

from __future__ import annotations

import asyncio
import struct
import time
from collections import deque
from typing import Set

try:
    import numpy as np
    from scipy.fft import fft, fftfreq
except ImportError:
    np = None  # type: ignore

eeg_buffer: deque = deque(maxlen=512)
_ws_clients: Set = set()
_udp_transport = None


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


class EEGUDPProtocol(asyncio.DatagramProtocol):
    def datagram_received(self, data: bytes, addr) -> None:
        try:
            if len(data) >= 4:
                voltage = struct.unpack("f", data[:4])[0]
                eeg_buffer.append(voltage)
        except Exception:
            pass


async def start_udp_server(port: int = 5005):
    global _udp_transport
    loop = asyncio.get_event_loop()
    _udp_transport, _ = await loop.create_datagram_endpoint(
        lambda: EEGUDPProtocol(),
        local_addr=("0.0.0.0", port),
    )


async def broadcast_loop():
    while True:
        if len(eeg_buffer) >= 128:
            alpha, beta, gamma = extract_frequency_bands(list(eeg_buffer))
        else:
            alpha = beta = gamma = 0.0
        payload = {
            "type": "eeg_data",
            "alpha": round(alpha, 2),
            "beta": round(beta, 2),
            "gamma": round(gamma, 2),
            "timestamp": time.time() * 1000,
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
