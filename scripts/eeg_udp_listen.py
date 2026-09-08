#!/usr/bin/env python3
"""Listen for ESP32 EEG UDP float32 samples on port 5005 (no FastAPI required).

Usage:
  python scripts/eeg_udp_listen.py
  python scripts/eeg_udp_listen.py --port 5005

Shows live voltage + detects snap-like spikes (self-test or real transients).
"""

from __future__ import annotations

import argparse
import socket
import struct
import time


def main() -> None:
    p = argparse.ArgumentParser(description="CALT EEG UDP listener")
    p.add_argument("--port", type=int, default=5005)
    p.add_argument("--host", default="0.0.0.0")
    args = p.parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((args.host, args.port))
    sock.settimeout(1.0)

    print(f"[eeg-listen] waiting on udp://{args.host}:{args.port}")
    print("[eeg-listen] flash ESP32 with SELF_TEST_MODE=1 — expect SNAP every ~2s")
    print()

    n = 0
    snaps = 0
    baseline = 1.65
    last_snap = 0.0
    t0 = time.time()

    while True:
        try:
            data, addr = sock.recvfrom(64)
        except socket.timeout:
            age = time.time() - t0
            if n == 0 and int(age) % 5 == 0:
                print(f"[eeg-listen] still waiting… ({int(age)}s) check WiFi + UDP_TARGET_IP")
            continue

        if len(data) < 4:
            continue
        (voltage,) = struct.unpack("<f", data[:4])
        n += 1
        baseline = baseline * 0.999 + voltage * 0.001
        now = time.time()
        is_snap = voltage > baseline + 0.4 and (now - last_snap) > 0.4
        if is_snap:
            last_snap = now
            snaps += 1
            print(
                f"SNAP #{snaps}  v={voltage:.3f}V  from={addr[0]}  "
                f"packets={n}  t={time.strftime('%H:%M:%S')}"
            )
        elif n % 250 == 0:
            print(f"… live  v={voltage:.3f}V  baseline≈{baseline:.3f}  packets={n}  snaps={snaps}")


if __name__ == "__main__":
    main()
