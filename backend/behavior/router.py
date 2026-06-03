"""Browser behavior WebSocket + stats — persisted to hub readings."""

import asyncio
import csv
import json
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.db.base import SessionLocal
from backend.hub.services.ingest import insert_reading
from backend.paths import DATA_LOGS_DIR

router = APIRouter(tags=["behavior"])

LOG_DIR = DATA_LOGS_DIR
LOG_DIR.mkdir(exist_ok=True)


@router.websocket("/ws/behavior")
async def behavior_websocket(websocket: WebSocket):
    await websocket.accept()
    today_str = datetime.now(UTC).strftime("%Y-%m-%d")
    csv_path = LOG_DIR / f"DSC_browser_behavior_{today_str}.csv"
    write_header = not csv_path.exists()

    try:
        while True:
            data = await websocket.receive_json()
            enriched = {**data, "received_at": datetime.now(UTC).isoformat()}
            with open(csv_path, "a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=list(enriched.keys()))
                if write_header:
                    writer.writeheader()
                    write_header = False
                writer.writerow(enriched)

            db = SessionLocal()
            try:
                insert_reading(
                    db,
                    user_id=1,
                    slug="browser_event",
                    value_json=enriched,
                    source_device="extension",
                    client_event_id=enriched.get("event_id") or enriched.get("received_at"),
                )
            except (ValueError, Exception):
                pass
            finally:
                db.close()

            await websocket.send_json({"status": "ok"})
    except WebSocketDisconnect:
        pass


@router.get("/api/behavior/stats")
async def behavior_stats():
    today_str = datetime.now(UTC).strftime("%Y-%m-%d")
    csv_path = LOG_DIR / f"DSC_browser_behavior_{today_str}.csv"
    if not csv_path.exists():
        return {"events_today": 0, "domains": [], "message": "No behavior data yet"}

    rows: list[dict] = []
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    domains: dict[str, int] = {}
    for row in rows:
        domain = row.get("domain") or row.get("url", "unknown")[:30]
        domains[domain] = domains.get(domain, 0) + 1

    top = sorted(domains.items(), key=lambda x: -x[1])[:10]
    return {
        "events_today": len(rows),
        "domains": [{"domain": d, "count": c} for d, c in top],
    }
