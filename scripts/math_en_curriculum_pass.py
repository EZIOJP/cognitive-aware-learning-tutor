#!/usr/bin/env python3
"""Curriculum-first English math bank pass.

See docs/superpowers/specs/2026-09-03-math-en-curriculum-pass-design.md
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-import",
        action="store_true",
        default=True,
        help="Map/tag existing bank only (default). Multi-source re-import is opt-in.",
    )
    parser.add_argument(
        "--with-import",
        action="store_true",
        help="Attempt multi-source refresh via import_math_aptitude_datasets helpers (no --clean-out).",
    )
    parser.add_argument("--skip-seed", action="store_true", help="Do not seed ReviewCards")
    parser.add_argument("--user-id", type=int, default=1, help="User id for ReviewCard seed")
    parser.add_argument(
        "--curriculum",
        type=Path,
        default=None,
        help="Override curriculum.json path",
    )
    args = parser.parse_args(argv)

    if args.with_import:
        try:
            from scripts import import_math_aptitude_datasets as importers

            # Best-effort refresh without wiping authored / existing packs.
            if hasattr(importers, "main"):
                # Call library entrypoints if present; ignore failures for missing datasets.
                for name in (
                    "import_sat",
                    "import_mathqa",
                    "import_hendrycks",
                    "import_saket",
                    "import_mathgenerator",
                    "import_deepmind",
                    "import_mathnet",
                ):
                    fn = getattr(importers, name, None)
                    if callable(fn):
                        try:
                            fn()
                        except Exception as exc:  # noqa: BLE001 — dataset optional
                            print(f"import skip {name}: {exc}")
        except Exception as exc:  # noqa: BLE001
            print(f"with-import unavailable: {exc}")

    from backend.math.curriculum_pass.orchestrator import run_pass

    db = None
    skip_seed = bool(args.skip_seed)
    if not skip_seed:
        from backend.db.session import SessionLocal

        db = SessionLocal()

    try:
        summary = run_pass(
            curriculum_path=args.curriculum,
            skip_import=not args.with_import,
            skip_seed=skip_seed,
            user_id=args.user_id,
            db=db,
        )
    finally:
        if db is not None:
            db.close()

    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
