"""
NutriNode Backend — main.py
FastAPI server that handles:
  - ESP32-CAM multipart uploads (image + weight)
  - Claude Vision AI food identification
  - Open Food Facts API fallback lookup
  - WebSocket live feed to dashboard
  - REST API for your existing website
  - DSC_ CSV data pipeline output
"""

import os
import csv
import json
import base64
import asyncio
import httpx
import logging
from datetime import datetime, date
from pathlib import Path
from typing import Optional, List
from contextlib import asynccontextmanager

from fastapi import APIRouter, File, UploadFile, Form, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel
from .pipeline_nutrition import main as run_pipeline

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("nutrinode")

# ── Config ────────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")   # set in .env
from backend.paths import DATA_LOGS_DIR, PLATE_IMAGES_DIR

LOG_DIR = DATA_LOGS_DIR
IMG_DIR = PLATE_IMAGES_DIR
LOG_DIR.mkdir(exist_ok=True)
IMG_DIR.mkdir(exist_ok=True)

# ── WebSocket connection manager ──────────────────────────────────────────────
class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)
        log.info(f"WS client connected. Total: {len(self.active)}")

    def disconnect(self, ws: WebSocket):
        self.active.remove(ws)

    async def broadcast(self, data: dict):
        dead = []
        for ws in self.active:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.active.remove(ws)

manager = ConnectionManager()

# ── Extended Indian + Global Macro DB ─────────────────────────────────────────
# Per gram: kcal, protein_g, carbs_g, fat_g, fiber_g
MACRO_DB = {
    # Indian staples
    "chicken biryani":    {"kcal": 1.85, "p": 0.10, "c": 0.18, "f": 0.08, "fiber": 0.01},
    "vegetable biryani":  {"kcal": 1.50, "p": 0.04, "c": 0.22, "f": 0.05, "fiber": 0.02},
    "masala dosa":        {"kcal": 1.97, "p": 0.04, "c": 0.25, "f": 0.08, "fiber": 0.01},
    "plain dosa":         {"kcal": 1.68, "p": 0.04, "c": 0.27, "f": 0.04, "fiber": 0.01},
    "idli":               {"kcal": 0.58, "p": 0.02, "c": 0.12, "f": 0.00, "fiber": 0.01},
    "sambar":             {"kcal": 0.52, "p": 0.03, "c": 0.08, "f": 0.01, "fiber": 0.02},
    "dal tadka":          {"kcal": 0.99, "p": 0.07, "c": 0.12, "f": 0.03, "fiber": 0.04},
    "paneer butter masala":{"kcal": 1.50, "p": 0.09, "c": 0.07, "f": 0.10, "fiber": 0.01},
    "roti":               {"kcal": 2.97, "p": 0.09, "c": 0.53, "f": 0.04, "fiber": 0.05},
    "naan":               {"kcal": 3.10, "p": 0.09, "c": 0.56, "f": 0.07, "fiber": 0.02},
    "rice (cooked)":      {"kcal": 1.30, "p": 0.03, "c": 0.28, "f": 0.00, "fiber": 0.00},
    "chole":              {"kcal": 1.64, "p": 0.09, "c": 0.27, "f": 0.03, "fiber": 0.08},
    "palak paneer":       {"kcal": 1.25, "p": 0.08, "c": 0.05, "f": 0.09, "fiber": 0.02},
    "aloo gobi":          {"kcal": 0.85, "p": 0.02, "c": 0.12, "f": 0.04, "fiber": 0.02},
    "poha":               {"kcal": 1.80, "p": 0.03, "c": 0.34, "f": 0.05, "fiber": 0.01},
    "upma":               {"kcal": 1.50, "p": 0.04, "c": 0.27, "f": 0.04, "fiber": 0.02},
    "egg":                {"kcal": 1.55, "p": 0.13, "c": 0.01, "f": 0.11, "fiber": 0.00},
    "omelette":           {"kcal": 1.54, "p": 0.10, "c": 0.01, "f": 0.12, "fiber": 0.00},
    # Fruits & Veg
    "apple":              {"kcal": 0.52, "p": 0.00, "c": 0.14, "f": 0.00, "fiber": 0.02},
    "banana":             {"kcal": 0.89, "p": 0.01, "c": 0.23, "f": 0.00, "fiber": 0.03},
    "salad":              {"kcal": 0.20, "p": 0.01, "c": 0.03, "f": 0.00, "fiber": 0.02},
    # Fast food
    "burger":             {"kcal": 2.50, "p": 0.12, "c": 0.25, "f": 0.13, "fiber": 0.01},
    "pizza":              {"kcal": 2.66, "p": 0.11, "c": 0.33, "f": 0.10, "fiber": 0.02},
    "french fries":       {"kcal": 3.12, "p": 0.04, "c": 0.41, "f": 0.15, "fiber": 0.04},
    # Fallback
    "unknown":            {"kcal": 1.50, "p": 0.05, "c": 0.20, "f": 0.07, "fiber": 0.02},
}

# ── Food identification via Claude Vision ─────────────────────────────────────
async def identify_food_claude(image_bytes: bytes) -> dict:
    """
    Sends image to Claude claude-sonnet-4-20250514 vision model.
    Returns {food_name, confidence, description, allergens, is_healthy}
    """
    if not ANTHROPIC_API_KEY:
        log.warning("No ANTHROPIC_API_KEY set — using mock identification")
        return {"food_name": "unknown", "confidence": 0.0, "description": "API key not configured", "allergens": [], "is_healthy": None}

    b64 = base64.standard_b64encode(image_bytes).decode("utf-8")
    prompt = """You are a professional nutritionist and food identification AI.
Look at this plate/food image carefully and respond ONLY in valid JSON with these exact keys:
{
  "food_name": "<common lowercase name matching standard food database, e.g. 'chicken biryani', 'masala dosa'>",
  "confidence": <0.0 to 1.0>,
  "description": "<one sentence describing what you see>",
  "estimated_portions": "<e.g. 'one serving', 'half plate'>",
  "allergens": ["<list any: gluten, dairy, eggs, nuts, soy>"],
  "is_healthy": <true or false>,
  "cuisine_type": "<e.g. South Indian, North Indian, Western, Chinese>"
}
If you cannot identify the food, use "unknown" as food_name."""

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 512,
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}},
                        {"type": "text", "text": prompt}
                    ]
                }]
            }
        )
        resp.raise_for_status()
        raw = resp.json()["content"][0]["text"].strip()
        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip())


# ── Open Food Facts fallback ──────────────────────────────────────────────────
async def lookup_open_food_facts(food_name: str) -> Optional[dict]:
    """Tries Open Food Facts API for macros by food name."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://world.openfoodfacts.org/cgi/search.pl",
                params={"search_terms": food_name, "search_simple": 1, "action": "process", "json": 1, "page_size": 1}
            )
            data = resp.json()
            if data.get("products"):
                p = data["products"][0]
                n = p.get("nutriments", {})
                return {
                    "kcal": n.get("energy-kcal_100g", 0) / 100,
                    "p":    n.get("proteins_100g", 0) / 100,
                    "c":    n.get("carbohydrates_100g", 0) / 100,
                    "f":    n.get("fat_100g", 0) / 100,
                    "fiber":n.get("fiber_100g", 0) / 100,
                }
    except Exception as e:
        log.warning(f"OpenFoodFacts lookup failed: {e}")
    return None


# ── Macro calculation ─────────────────────────────────────────────────────────
async def calculate_macros(food_name: str, weight_g: float) -> dict:
    macros = MACRO_DB.get(food_name.lower())
    source = "local_db"

    if not macros:
        # Try Open Food Facts
        macros = await lookup_open_food_facts(food_name)
        source = "open_food_facts" if macros else "fallback"
        if not macros:
            macros = MACRO_DB["unknown"]

    return {
        "total_kcal":   round(weight_g * macros["kcal"], 1),
        "protein_g":    round(weight_g * macros["p"], 1),
        "carbs_g":      round(weight_g * macros["c"], 1),
        "fat_g":        round(weight_g * macros["f"], 1),
        "fiber_g":      round(weight_g * macros.get("fiber", 0), 1),
        "macros_source": source,
    }


# ── DSC CSV Logger ────────────────────────────────────────────────────────────
def log_to_csv(entry: dict):
    date_str = datetime.now().strftime("%Y-%m-%d")
    csv_path = LOG_DIR / f"DSC_nutrition_log_{date_str}.csv"
    headers = [
        "timestamp", "meal_id", "source", "location_tag",
        "food_item", "weight_g",
        "total_kcal", "protein_g", "carbs_g", "fat_g", "fiber_g",
        "confidence", "is_healthy", "cuisine_type", "allergens",
        "macros_source", "description"
    ]
    file_exists = csv_path.exists()
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        if not file_exists:
            writer.writeheader()
        writer.writerow({h: entry.get(h, "") for h in headers})
    log.info(f"📝 Logged to {csv_path.name}")


def _hub_log_calories(kcal: float) -> None:
    try:
        from backend.db.base import SessionLocal
        from backend.hub.services.ingest import insert_reading

        db = SessionLocal()
        try:
            insert_reading(
                db,
                user_id=1,
                slug="calories",
                value_numeric=float(kcal),
                source_device="nutrinode",
            )
        finally:
            db.close()
    except Exception:
        pass


# ── Router ───────────────────────────────────────────────────────────────
router = APIRouter(tags=["nutrition"])

# ── ENDPOINT: ESP32-CAM Upload ────────────────────────────────────────────────
@router.post("/api/nutrition/log")
async def log_nutrition(
    weight_grams: float = Form(...),
    image: UploadFile = File(...),
    location_tag: str = Form("home"),      # e.g. "restaurant_xyz", "home", "office"
    source: str = Form("esp32_cam"),
):
    timestamp = datetime.now()
    meal_id = f"MEAL_{timestamp.strftime('%Y%m%d_%H%M%S')}"

    # 1. Read image bytes
    image_bytes = await image.read()

    # 2. Optionally save plate image
    img_path = IMG_DIR / f"{meal_id}.jpg"
    img_path.write_bytes(image_bytes)
    log.info(f"📷 Image saved: {img_path.name} ({len(image_bytes)/1024:.1f} KB)")

    # 3. AI identification
    ai_result = await identify_food_claude(image_bytes)
    food_name = ai_result.get("food_name", "unknown")
    log.info(f"🤖 Identified: {food_name} (confidence: {ai_result.get('confidence', 0):.0%})")

    # 4. Calculate macros
    macros = await calculate_macros(food_name, weight_grams)

    # 5. Build full entry
    entry = {
        "timestamp":    timestamp.isoformat(),
        "meal_id":      meal_id,
        "source":       source,
        "location_tag": location_tag,
        "food_item":    food_name,
        "weight_g":     weight_grams,
        "confidence":   ai_result.get("confidence", 0),
        "is_healthy":   ai_result.get("is_healthy"),
        "cuisine_type": ai_result.get("cuisine_type", ""),
        "allergens":    json.dumps(ai_result.get("allergens", [])),
        "description":  ai_result.get("description", ""),
        **macros,
    }

    # 6. Log to CSV
    log_to_csv(entry)

    _hub_log_calories(macros.get("total_kcal", 0))

    # 7. Broadcast to WebSocket dashboards
    await manager.broadcast({"event": "new_meal", "data": entry})

    log.info(f"🍽️  {weight_grams}g of {food_name} → {macros['total_kcal']} kcal")
    return {"status": "logged", "meal_id": meal_id, **entry}


# ── ENDPOINT: Manual log (no hardware) ───────────────────────────────────────
class ManualMealLog(BaseModel):
    food_item: str
    weight_grams: float
    location_tag: str = "manual"

@router.post("/api/nutrition/manual")
async def manual_log(body: ManualMealLog):
    timestamp = datetime.now()
    meal_id = f"MEAL_{timestamp.strftime('%Y%m%d_%H%M%S')}"
    macros = await calculate_macros(body.food_item, body.weight_grams)
    entry = {
        "timestamp":    timestamp.isoformat(),
        "meal_id":      meal_id,
        "source":       "manual",
        "location_tag": body.location_tag,
        "food_item":    body.food_item,
        "weight_g":     body.weight_grams,
        "confidence":   1.0,
        "is_healthy":   None,
        "cuisine_type": "",
        "allergens":    "[]",
        "description":  "Manually logged",
        **macros,
    }
    log_to_csv(entry)
    _hub_log_calories(macros.get("total_kcal", 0))
    await manager.broadcast({"event": "new_meal", "data": entry})
    return {"status": "logged", **entry}


# ── ENDPOINT: Get today's summary ─────────────────────────────────────────────
@router.get("/api/nutrition/today")
async def today_summary():
    date_str = date.today().strftime("%Y-%m-%d")
    csv_path = LOG_DIR / f"DSC_nutrition_log_{date_str}.csv"
    if not csv_path.exists():
        return {"meals": [], "totals": {}, "date": date_str}

    meals = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            meals.append(row)

    totals = {
        "total_kcal":  round(sum(float(m.get("total_kcal", 0)) for m in meals), 1),
        "protein_g":   round(sum(float(m.get("protein_g", 0)) for m in meals), 1),
        "carbs_g":     round(sum(float(m.get("carbs_g", 0)) for m in meals), 1),
        "fat_g":       round(sum(float(m.get("fat_g", 0)) for m in meals), 1),
        "fiber_g":     round(sum(float(m.get("fiber_g", 0)) for m in meals), 1),
        "meal_count":  len(meals),
    }
    return {"meals": meals, "totals": totals, "date": date_str}


# ── ENDPOINT: Get N-day history ───────────────────────────────────────────────
@router.get("/api/nutrition/history")
async def history(days: int = 7):
    all_days = []
    for csv_file in sorted(LOG_DIR.glob("DSC_nutrition_log_*.csv"), reverse=True)[:days]:
        date_label = csv_file.stem.replace("DSC_nutrition_log_", "")
        meals = []
        with open(csv_file, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                meals.append(row)
        all_days.append({
            "date": date_label,
            "meals": meals,
            "totals": {
                "total_kcal": round(sum(float(m.get("total_kcal", 0)) for m in meals), 1),
                "protein_g":  round(sum(float(m.get("protein_g", 0)) for m in meals), 1),
                "carbs_g":    round(sum(float(m.get("carbs_g", 0)) for m in meals), 1),
                "fat_g":      round(sum(float(m.get("fat_g", 0)) for m in meals), 1),
                "meal_count": len(meals),
            }
        })
    return {"history": all_days}


# ── ENDPOINT: Export CSV ──────────────────────────────────────────────────────
@router.get("/api/nutrition/export/{date_str}")
async def export_csv(date_str: str):
    csv_path = LOG_DIR / f"DSC_nutrition_log_{date_str}.csv"
    if not csv_path.exists():
        raise HTTPException(status_code=404, detail="No data for this date")
    return FileResponse(csv_path, media_type="text/csv", filename=csv_path.name)


# ── ENDPOINT: Run Pipeline ────────────────────────────────────────────────────
@router.post("/api/nutrition/pipeline/run")
async def trigger_pipeline():
    try:
        run_pipeline()
        # Read the latest insight file
        insight_files = sorted(LOG_DIR.glob("DSC_insights_*.json"), reverse=True)
        if insight_files:
            with open(insight_files[0], "r", encoding="utf-8") as f:
                return {"status": "success", "insights": json.load(f)}
        return {"status": "success", "insights": None}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ── WEBSOCKET: Live feed ──────────────────────────────────────────────────────
@router.websocket("/ws/nutrition/live")
async def websocket_live(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        # Send current day summary on connect
        summary = await today_summary()
        await websocket.send_json({"event": "init", "data": summary})
        while True:
            # Keep alive ping
            await asyncio.sleep(30)
            await websocket.send_json({"event": "ping"})
    except WebSocketDisconnect:
        manager.disconnect(websocket)
