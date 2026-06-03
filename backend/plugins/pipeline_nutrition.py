"""
NutriNode Data Pipeline — pipeline.py

Runs as a daily cron job or manually.
Reads all DSC_nutrition_log_*.csv files and:
  1. Aggregates into weekly/monthly summaries
  2. Detects anomalies (calorie spikes, protein deficits)
  3. Generates insights JSON for the dashboard
  4. Outputs DSC_weekly_summary_*.csv and DSC_insights_*.json

Run:
  python pipeline.py
  python pipeline.py --days 30
  python pipeline.py --export-json insights.json
"""

import os
import csv
import json
import argparse
from pathlib import Path
from datetime import datetime, date, timedelta
from collections import defaultdict
from statistics import mean, stdev

from backend.paths import DATA_LOGS_DIR, ROOT

LOG_DIR = DATA_LOGS_DIR
OUTPUT_DIR = ROOT / "data" / "pipeline_output"
OUTPUT_DIR.mkdir(exist_ok=True)

# ── Daily targets (WHO / ICMR Indian adult averages) ──────────────────────────
DAILY_TARGETS = {
    "total_kcal": 2000,
    "protein_g":  50,
    "carbs_g":    275,
    "fat_g":      65,
    "fiber_g":    25,
}

# ─────────────────────────────────────────────────────────────────────────────
def load_csv(path: Path) -> list[dict]:
    rows = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                rows.append(row)
    except Exception as e:
        print(f"⚠️  Could not read {path}: {e}")
    return rows


def safe_float(val, default=0.0) -> float:
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def load_all_logs(days: int = 30) -> list[dict]:
    """Load all log files from the past N days."""
    cutoff = date.today() - timedelta(days=days)
    all_rows = []
    for csv_file in sorted(LOG_DIR.glob("DSC_nutrition_log_*.csv")):
        date_str = csv_file.stem.replace("DSC_nutrition_log_", "")
        try:
            file_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            continue
        if file_date >= cutoff:
            rows = load_csv(csv_file)
            for r in rows:
                r["_date"] = date_str
            all_rows.extend(rows)
    return all_rows


# ── Aggregation ───────────────────────────────────────────────────────────────
def aggregate_by_day(rows: list[dict]) -> dict:
    days = defaultdict(lambda: {
        "total_kcal": 0, "protein_g": 0, "carbs_g": 0, "fat_g": 0, "fiber_g": 0,
        "meal_count": 0, "healthy_count": 0, "cuisine_types": [], "foods": []
    })
    for row in rows:
        d = row["_date"]
        days[d]["total_kcal"]    += safe_float(row.get("total_kcal"))
        days[d]["protein_g"]     += safe_float(row.get("protein_g"))
        days[d]["carbs_g"]       += safe_float(row.get("carbs_g"))
        days[d]["fat_g"]         += safe_float(row.get("fat_g"))
        days[d]["fiber_g"]       += safe_float(row.get("fiber_g"))
        days[d]["meal_count"]    += 1
        if str(row.get("is_healthy")).lower() == "true":
            days[d]["healthy_count"] += 1
        if row.get("cuisine_type"):
            days[d]["cuisine_types"].append(row["cuisine_type"])
        if row.get("food_item"):
            days[d]["foods"].append(row["food_item"])
    return dict(sorted(days.items()))


def compute_week_summary(day_data: dict) -> dict:
    if not day_data:
        return {}
    vals = list(day_data.values())
    kcals = [v["total_kcal"] for v in vals]
    return {
        "days_tracked":     len(vals),
        "avg_kcal":         round(mean(kcals), 1),
        "max_kcal":         round(max(kcals), 1),
        "min_kcal":         round(min(kcals), 1),
        "std_kcal":         round(stdev(kcals), 1) if len(kcals) > 1 else 0,
        "avg_protein_g":    round(mean(v["protein_g"] for v in vals), 1),
        "avg_carbs_g":      round(mean(v["carbs_g"] for v in vals), 1),
        "avg_fat_g":        round(mean(v["fat_g"] for v in vals), 1),
        "avg_fiber_g":      round(mean(v["fiber_g"] for v in vals), 1),
        "total_meals":      sum(v["meal_count"] for v in vals),
        "avg_meals_per_day":round(mean(v["meal_count"] for v in vals), 1),
    }


# ── Anomaly detection ─────────────────────────────────────────────────────────
def detect_anomalies(day_data: dict) -> list[dict]:
    anomalies = []
    for day, data in day_data.items():
        kcal = data["total_kcal"]
        protein = data["protein_g"]
        fiber = data["fiber_g"]
        meals = data["meal_count"]

        if kcal > DAILY_TARGETS["total_kcal"] * 1.5:
            anomalies.append({"date": day, "type": "calorie_spike",    "severity": "high",   "value": kcal,   "message": f"Consumed {kcal:.0f} kcal — {(kcal/DAILY_TARGETS['total_kcal']-1)*100:.0f}% above target"})
        if kcal < DAILY_TARGETS["total_kcal"] * 0.5 and meals > 0:
            anomalies.append({"date": day, "type": "calorie_deficit",  "severity": "medium", "value": kcal,   "message": f"Only {kcal:.0f} kcal recorded — possible under-eating or missed logging"})
        if protein < DAILY_TARGETS["protein_g"] * 0.6 and meals > 0:
            anomalies.append({"date": day, "type": "protein_deficit",  "severity": "medium", "value": protein,"message": f"Low protein: {protein:.0f}g vs {DAILY_TARGETS['protein_g']}g target"})
        if fiber < 10 and meals > 1:
            anomalies.append({"date": day, "type": "low_fiber",        "severity": "low",    "value": fiber,  "message": f"Fiber intake {fiber:.0f}g — aim for {DAILY_TARGETS['fiber_g']}g/day"})
        if meals > 6:
            anomalies.append({"date": day, "type": "high_meal_freq",   "severity": "info",   "value": meals,  "message": f"{meals} meals logged — unusually high meal frequency"})

    return sorted(anomalies, key=lambda x: x["date"], reverse=True)


# ── Insight generation ────────────────────────────────────────────────────────
def generate_insights(rows: list[dict], day_data: dict, week_summary: dict) -> list[dict]:
    insights = []

    # Most common foods
    food_counts = defaultdict(int)
    for r in rows:
        if r.get("food_item") and r["food_item"] != "unknown":
            food_counts[r["food_item"]] += 1
    top_foods = sorted(food_counts.items(), key=lambda x: x[1], reverse=True)[:5]

    # Most common cuisine
    cuisine_counts = defaultdict(int)
    for r in rows:
        if r.get("cuisine_type"):
            cuisine_counts[r["cuisine_type"]] += 1
    top_cuisine = max(cuisine_counts, key=cuisine_counts.get) if cuisine_counts else "Unknown"

    # Healthy ratio
    total_meals = sum(v["meal_count"] for v in day_data.values())
    healthy_meals = sum(v["healthy_count"] for v in day_data.values())
    healthy_pct = round((healthy_meals / total_meals * 100) if total_meals else 0, 1)

    # Protein adequacy
    avg_protein = week_summary.get("avg_protein_g", 0)
    protein_status = "✅ Adequate" if avg_protein >= DAILY_TARGETS["protein_g"] else "⚠️ Below target"

    insights.append({
        "category": "eating_pattern",
        "title": "Your Most Frequent Foods",
        "data": [{"food": f, "count": c} for f, c in top_foods],
        "recommendation": f"Your diet is primarily {top_cuisine}. Diversifying cuisine types improves micronutrient variety."
    })
    insights.append({
        "category": "health_score",
        "title": "Healthy Meal Rate",
        "value": healthy_pct,
        "unit": "%",
        "recommendation": "Healthy" if healthy_pct > 60 else "Try replacing one processed meal per day with whole foods."
    })
    insights.append({
        "category": "macros",
        "title": "Protein Status",
        "value": avg_protein,
        "unit": "g/day avg",
        "target": DAILY_TARGETS["protein_g"],
        "status": protein_status,
        "recommendation": "Good protein intake supports muscle repair and satiety." if avg_protein >= 50 else "Add protein sources: dal, paneer, eggs, chicken, or legumes to each meal."
    })

    # Calorie trend
    if len(day_data) >= 3:
        dates = sorted(day_data.keys())
        recent_kcal = mean(day_data[d]["total_kcal"] for d in dates[-3:])
        earlier_kcal = mean(day_data[d]["total_kcal"] for d in dates[:3])
        trend = "increasing" if recent_kcal > earlier_kcal * 1.1 else "decreasing" if recent_kcal < earlier_kcal * 0.9 else "stable"
        insights.append({
            "category": "calorie_trend",
            "title": "Calorie Trend",
            "trend": trend,
            "recent_avg": round(recent_kcal, 0),
            "earlier_avg": round(earlier_kcal, 0),
            "recommendation": {
                "increasing": "Calorie intake trending up — monitor portion sizes.",
                "decreasing": "Calorie intake trending down — ensure you're not under-fueling.",
                "stable": "Consistent calorie intake — great discipline!"
            }[trend]
        })

    return insights


# ── Write outputs ─────────────────────────────────────────────────────────────
def write_weekly_csv(day_data: dict):
    out_path = OUTPUT_DIR / f"DSC_weekly_summary_{date.today().isoformat()}.csv"
    headers = ["date", "total_kcal", "protein_g", "carbs_g", "fat_g", "fiber_g", "meal_count", "healthy_count"]
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        w.writeheader()
        for day, data in day_data.items():
            w.writerow({"date": day, **{k: round(data[k], 1) for k in headers[1:] if k in data}})
    print(f"✅ Weekly CSV → {out_path}")


def write_insights_json(insights: list, anomalies: list, week_summary: dict, export_path: str = None):
    payload = {
        "generated_at": datetime.now().isoformat(),
        "week_summary": week_summary,
        "daily_targets": DAILY_TARGETS,
        "anomalies": anomalies,
        "insights": insights,
    }
    default_path = OUTPUT_DIR / f"DSC_insights_{date.today().isoformat()}.json"
    paths = [default_path]
    if export_path:
        paths.append(Path(export_path))
    for p in paths:
        p.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
        print(f"✅ Insights JSON → {p}")
    return payload


# ── Main ──────────────────────────────────────────────────────────────────────
def run(days: int = 30, export_json: str = None):
    print(f"\n📊 NutriNode Pipeline — analysing {days} days of data\n")

    rows = load_all_logs(days)
    if not rows:
        print("⚠️  No data found in data_logs/. Run the backend and log some meals first.")
        return

    print(f"   Loaded {len(rows)} meal records from {len(set(r['_date'] for r in rows))} days\n")

    day_data     = aggregate_by_day(rows)
    week_summary = compute_week_summary(day_data)
    anomalies    = detect_anomalies(day_data)
    insights     = generate_insights(rows, day_data, week_summary)

    # Print summary
    print("📈 Period Summary:")
    for k, v in week_summary.items():
        print(f"   {k:25s} {v}")

    print(f"\n🚨 Anomalies detected: {len(anomalies)}")
    for a in anomalies[:5]:
        print(f"   [{a['severity'].upper()}] {a['date']} — {a['message']}")

    print(f"\n💡 Insights generated: {len(insights)}")
    for i in insights:
        print(f"   {i['title']}: {i.get('recommendation','')[:80]}")

    # Write outputs
    write_weekly_csv(day_data)
    write_insights_json(insights, anomalies, week_summary, export_json)
    print("\n✅ Pipeline complete.\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NutriNode Data Pipeline")
    parser.add_argument("--days",        type=int, default=30, help="Days of history to analyse")
    parser.add_argument("--export-json", type=str, default=None, help="Additional JSON output path")
    args = parser.parse_args()
    run(days=args.days, export_json=args.export_json)
