"""Write data/exports/productivity_snapshot_YYYY-MM-DD.json (+ docs pointer).

Usage (repo root):
  python scripts/export_productivity_snapshot.py
  python scripts/export_productivity_snapshot.py --days 3 --user-id 1
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.behavior.distraction_gate import compute_distraction_gate  # noqa: E402
from backend.db.base import SessionLocal  # noqa: E402
from backend.models.timetable import TrackedSession  # noqa: E402
from backend.models.user import User  # noqa: E402
from backend.models.wearable_daily import WearableDaily  # noqa: E402
from backend.planner.service import local_day_bounds_utc, local_tz  # noqa: E402
from backend.planner.week_export import build_productivity_week_export  # noqa: E402
from backend.timetable.tracker_query import primary_tracker_user_id  # noqa: E402
from backend.wearables.sleep_window import parse_sleep_dict, sleep_bouts  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Export productivity snapshot JSON")
    parser.add_argument("--days", type=int, default=3, help="Calendar days ending today (1-14)")
    parser.add_argument("--user-id", type=int, default=None)
    parser.add_argument("--sessions-per-day", type=int, default=40)
    args = parser.parse_args()

    days = max(1, min(14, int(args.days)))
    db = SessionLocal()
    try:
        uid = args.user_id or primary_tracker_user_id(db)
        user = db.query(User).filter(User.id == uid).first()
        if not user:
            print("No user found", file=sys.stderr)
            return 1

        today = datetime.now(local_tz()).date()
        payload = build_productivity_week_export(db, user, days=days, end_day=today)

        samples: dict = {}
        sleep_info: dict = {}
        for offset in range(days):
            d = today - timedelta(days=offset)
            start, end = local_day_bounds_utc(d)
            rows = (
                db.query(TrackedSession)
                .filter(
                    TrackedSession.user_id == uid,
                    TrackedSession.start_time < end,
                    TrackedSession.end_time > start,
                    TrackedSession.source.in_(("desktop_tracker", "extension", "calt_spa")),
                )
                .order_by(TrackedSession.start_time)
                .limit(args.sessions_per_day)
                .all()
            )
            samples[d.isoformat()] = [
                {
                    "session_id": r.session_id,
                    "source": r.source,
                    "category": r.category,
                    "app_name": r.app_name,
                    "window_title": (r.window_title or "")[:120],
                    "start_time": r.start_time.isoformat() if r.start_time else None,
                    "end_time": r.end_time.isoformat() if r.end_time else None,
                    "category_source": r.category_source,
                    "override_productive": r.override_productive,
                }
                for r in rows
            ]

            wd = (
                db.query(WearableDaily)
                .filter(WearableDaily.user_id == uid, WearableDaily.local_date == d)
                .first()
            )
            if not wd:
                sleep_info[d.isoformat()] = None
                continue
            sleep = parse_sleep_dict(wd.payload_json)
            bouts = sleep_bouts(local_date=wd.local_date, sleep=sleep)
            sleep_info[d.isoformat()] = {
                "sleep_hours": wd.sleep_hours,
                "sleep_score": wd.sleep_score,
                "start_min": sleep.get("start_min"),
                "end_min": sleep.get("end_min"),
                "total_min": sleep.get("total_min"),
                "naps": sleep.get("naps") or [],
                "resolved_bouts": [
                    {
                        "start": s.isoformat(),
                        "end": e.isoformat(),
                        "hours": round((e - s).total_seconds() / 3600, 2),
                    }
                    for s, e in bouts
                ],
            }

        gate = compute_distraction_gate(db, uid)
        out = {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "local_tz": str(local_tz()),
            "user_id": uid,
            "days_covered": days,
            "end_day": today.isoformat(),
            "docs": "docs/PRODUCTIVITY_SYSTEM.md",
            "distraction_gate_today": {
                "productive_minutes": gate.get("productive_minutes"),
                "goal_minutes": gate.get("goal_minutes") or gate.get("daily_goal_minutes"),
                "unlocked": gate.get("unlocked"),
                "enabled": gate.get("enabled"),
                "browser_mode": (gate.get("browser") or {}).get("mode"),
            },
            "week_export_summary": {
                "keys": list(payload.keys()),
                "by_day": payload.get("by_day"),
                "summary": payload.get("summary"),
            },
            "full_week_export": payload,
            "sample_tracked_sessions": samples,
            "sleep": sleep_info,
        }

        out_dir = ROOT / "data" / "exports"
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"productivity_snapshot_{today.isoformat()}.json"
        path.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
        print(f"Wrote {path} ({path.stat().st_size} bytes)")
        print(f"Guide: docs/PRODUCTIVITY_SYSTEM.md")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
