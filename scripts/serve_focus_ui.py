"""Serve prebuilt Focus UI (dist-focus/) on 127.0.0.1:5174 — no Vite.

Used by calt_focus.exe when WebView2 virtual-host mapping is unavailable.
"""

from __future__ import annotations

import http.server
import os
import socketserver
import sys
from pathlib import Path

PORT = 5174
ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist-focus"


def main() -> int:
    if not (DIST / "index.html").is_file():
        print(f"[serve_focus_ui] Missing {DIST / 'index.html'} — run: npm run build:focus")
        return 1
    os.chdir(DIST)
    handler = http.server.SimpleHTTPRequestHandler
    # Allow reuse so Focus can restart quickly
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("127.0.0.1", PORT), handler) as httpd:
        print(f"[serve_focus_ui] http://127.0.0.1:{PORT}/  (cwd={DIST})")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
