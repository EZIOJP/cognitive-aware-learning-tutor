"""Background scraper for Windows 11 Live Captions (Win+Ctrl+L).

Usage:
  1. Start a lesson video (e.g. Scaler) in Chrome or any player.
  2. Press Win+Ctrl+L to enable Windows Live Captions.
  3. Run: python -m backend.scripts.live_captions_scraper
  4. Stop with Ctrl+C — transcript saves to data/transcripts/

Requires: pip install -r backend/requirements-captions.txt
"""

from __future__ import annotations

import argparse
import signal
import sys

from backend.transcripts.live_captions import LiveCaptionsScraper, ensure_windows


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Capture Windows Live Captions into a text transcript."
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default="",
        help="Output .txt path (default: data/transcripts/live_captions_<timestamp>.txt)",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=0.5,
        help="Poll interval in seconds (default: 0.5)",
    )
    parser.add_argument(
        "--method",
        choices=("uia", "ocr"),
        default="uia",
        help="uia = read UI element (recommended); ocr = screenshot fallback",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=0,
        help="Stop after N seconds (0 = run until Ctrl+C)",
    )
    return parser.parse_args()


def main() -> None:
    ensure_windows()
    args = _parse_args()

    scraper = LiveCaptionsScraper(
        poll_interval=args.interval,
        method=args.method,
        on_segment=lambda text: print(f"Captured: {text}"),
    )

    out_path = args.output.strip() or None
    duration = args.duration if args.duration > 0 else None

    def _save_and_exit(*_args) -> None:
        if scraper.segments:
            saved = scraper.save(out_path)
            print(f"\nTranscript saved ({len(scraper.segments)} segments): {saved}")
        else:
            print("\nNo captions captured.")
        sys.exit(0)

    signal.signal(signal.SIGINT, _save_and_exit)
    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, _save_and_exit)

    print("Connecting to LiveCaptions.exe …")
    print("Start captions with Win+Ctrl+L if needed. Press Ctrl+C to stop.\n")

    try:
        scraper.run(max_seconds=duration)
    except (ImportError, OSError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    _save_and_exit()


if __name__ == "__main__":
    main()
