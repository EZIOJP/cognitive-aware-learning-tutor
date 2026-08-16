"""Food search + macro resolve: custom → IFCT → local MACRO_DB → Open Food Facts."""

from __future__ import annotations

import csv
import json
import logging
import re
from functools import lru_cache
from typing import Any

from backend.paths import ROOT

log = logging.getLogger("nutrition.foods")

IFCT_PATH = ROOT / "data" / "nutrition" / "ifct2017_compositions.csv"
CUSTOM_PATH = ROOT / "data" / "nutrition" / "custom_foods.json"

LOCAL_MACRO_DB: dict[str, dict[str, float]] = {
    "chicken biryani": {"kcal": 1.85, "p": 0.10, "c": 0.18, "f": 0.08, "fiber": 0.01},
    "vegetable biryani": {"kcal": 1.50, "p": 0.04, "c": 0.22, "f": 0.05, "fiber": 0.02},
    "masala dosa": {"kcal": 1.97, "p": 0.04, "c": 0.25, "f": 0.08, "fiber": 0.01},
    "plain dosa": {"kcal": 1.68, "p": 0.04, "c": 0.27, "f": 0.04, "fiber": 0.01},
    "idli": {"kcal": 0.58, "p": 0.02, "c": 0.12, "f": 0.00, "fiber": 0.01},
    "sambar": {"kcal": 0.52, "p": 0.03, "c": 0.08, "f": 0.01, "fiber": 0.02},
    "dal tadka": {"kcal": 0.99, "p": 0.07, "c": 0.12, "f": 0.03, "fiber": 0.04},
    "paneer butter masala": {"kcal": 1.50, "p": 0.09, "c": 0.07, "f": 0.10, "fiber": 0.01},
    "roti": {"kcal": 2.97, "p": 0.09, "c": 0.53, "f": 0.04, "fiber": 0.05},
    "chapati": {"kcal": 2.97, "p": 0.09, "c": 0.53, "f": 0.04, "fiber": 0.05},
    "naan": {"kcal": 3.10, "p": 0.09, "c": 0.56, "f": 0.07, "fiber": 0.02},
    "rice (cooked)": {"kcal": 1.30, "p": 0.03, "c": 0.28, "f": 0.00, "fiber": 0.00},
    "cooked rice": {"kcal": 1.30, "p": 0.03, "c": 0.28, "f": 0.00, "fiber": 0.00},
    "chole": {"kcal": 1.64, "p": 0.09, "c": 0.27, "f": 0.03, "fiber": 0.08},
    "palak paneer": {"kcal": 1.25, "p": 0.08, "c": 0.05, "f": 0.09, "fiber": 0.02},
    "aloo gobi": {"kcal": 0.85, "p": 0.02, "c": 0.12, "f": 0.04, "fiber": 0.02},
    "poha": {"kcal": 1.80, "p": 0.03, "c": 0.34, "f": 0.05, "fiber": 0.01},
    "upma": {"kcal": 1.50, "p": 0.04, "c": 0.27, "f": 0.04, "fiber": 0.02},
    "egg": {"kcal": 1.55, "p": 0.13, "c": 0.01, "f": 0.11, "fiber": 0.00},
    "omelette": {"kcal": 1.54, "p": 0.10, "c": 0.01, "f": 0.12, "fiber": 0.00},
    "apple": {"kcal": 0.52, "p": 0.00, "c": 0.14, "f": 0.00, "fiber": 0.02},
    "banana": {"kcal": 0.89, "p": 0.01, "c": 0.23, "f": 0.00, "fiber": 0.03},
    "salad": {"kcal": 0.20, "p": 0.01, "c": 0.03, "f": 0.00, "fiber": 0.02},
    "burger": {"kcal": 2.50, "p": 0.12, "c": 0.25, "f": 0.13, "fiber": 0.01},
    "pizza": {"kcal": 2.66, "p": 0.11, "c": 0.33, "f": 0.10, "fiber": 0.02},
    "french fries": {"kcal": 3.12, "p": 0.04, "c": 0.41, "f": 0.15, "fiber": 0.04},
    "unknown": {"kcal": 1.50, "p": 0.05, "c": 0.20, "f": 0.07, "fiber": 0.02},
}

DEFAULT_SERVING_G = {
    "roti": 40.0,
    "chapati": 40.0,
    "idli": 40.0,
    "egg": 50.0,
    "banana": 120.0,
    "apple": 150.0,
}


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def _load_custom() -> list[dict[str, Any]]:
    if not CUSTOM_PATH.is_file():
        return []
    try:
        data = json.loads(CUSTOM_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_custom_food(entry: dict[str, Any]) -> dict[str, Any]:
    CUSTOM_PATH.parent.mkdir(parents=True, exist_ok=True)
    rows = _load_custom()
    name = _norm(str(entry.get("name") or ""))
    per_g = entry.get("per_g") or {}
    row = {
        "name": name,
        "display_name": entry.get("display_name") or name,
        "per_g": {
            "kcal": float(per_g.get("kcal") or 0),
            "p": float(per_g.get("p") or 0),
            "c": float(per_g.get("c") or 0),
            "f": float(per_g.get("f") or 0),
            "fiber": float(per_g.get("fiber") or 0),
        },
        "default_serving_g": float(entry.get("default_serving_g") or 100),
        "source": "custom",
    }
    rows = [r for r in rows if _norm(r.get("name", "")) != name]
    rows.append(row)
    CUSTOM_PATH.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    load_food_index.cache_clear()
    return row


def _header_code(h: str) -> str:
    parts = h.replace('"', "").split(";")
    return parts[-1].strip().lower() if parts else h.lower()


@lru_cache(maxsize=1)
def load_food_index() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []

    for c in _load_custom():
        out.append(
            {
                "id": f"custom:{c['name']}",
                "name": c.get("display_name") or c["name"],
                "name_key": _norm(c["name"]),
                "group": "Custom",
                "source": "custom",
                "per_g": c["per_g"],
                "default_serving_g": float(c.get("default_serving_g") or 100),
            }
        )

    for name, m in LOCAL_MACRO_DB.items():
        if name == "unknown":
            continue
        out.append(
            {
                "id": f"local:{name}",
                "name": name,
                "name_key": name,
                "group": "Local favourites",
                "source": "local",
                "per_g": m,
                "default_serving_g": DEFAULT_SERVING_G.get(name, 100.0),
            }
        )

    if IFCT_PATH.is_file():
        try:
            with IFCT_PATH.open("r", encoding="utf-8", errors="replace", newline="") as f:
                reader = csv.reader(f)
                headers = next(reader)
                codes = [_header_code(h) for h in headers]
                idx = {c: i for i, c in enumerate(codes)}

                def col(*keys: str) -> int | None:
                    for k in keys:
                        if k in idx:
                            return idx[k]
                    return None

                i_name = col("name")
                i_lang = col("lang")
                i_grup = col("grup")
                i_enerc = col("enerc")
                i_prot = col("protcnt")
                i_cho = col("choavldf", "cho")
                i_fat = col("fatce")
                i_fiber = col("fibtg")
                if i_name is not None and i_enerc is not None:
                    for row in reader:
                        if len(row) <= i_name:
                            continue
                        name = (row[i_name] or "").strip()
                        if not name:
                            continue

                        def num(i: int | None) -> float:
                            if i is None or i >= len(row):
                                return 0.0
                            try:
                                return float(str(row[i]).replace(",", "") or 0)
                            except ValueError:
                                return 0.0

                        kj100 = num(i_enerc)
                        kcal100 = kj100 / 4.184 if kj100 else 0.0
                        per_g = {
                            "kcal": kcal100 / 100.0,
                            "p": num(i_prot) / 100.0,
                            "c": num(i_cho) / 100.0,
                            "f": num(i_fat) / 100.0,
                            "fiber": num(i_fiber) / 100.0,
                        }
                        lang = (row[i_lang] if i_lang is not None and i_lang < len(row) else "") or ""
                        grup = (row[i_grup] if i_grup is not None and i_grup < len(row) else "") or "IFCT"
                        out.append(
                            {
                                "id": f"ifct:{_norm(name)}",
                                "name": name,
                                "name_key": _norm(name),
                                "aliases": _norm(lang),
                                "group": grup,
                                "source": "ifct",
                                "per_g": per_g,
                                "default_serving_g": 100.0,
                            }
                        )
            log.info("Food index ready: %s entries", len(out))
        except Exception as e:
            log.warning("IFCT load failed: %s", e)

    return out


def search_foods(q: str, limit: int = 20) -> list[dict[str, Any]]:
    query = _norm(q)
    if not query:
        return []
    tokens = query.split()
    scored: list[tuple[int, dict[str, Any]]] = []
    for food in load_food_index():
        key = food["name_key"]
        aliases = food.get("aliases") or ""
        hay = f"{key} {aliases}"
        if query not in hay and not all(t in hay for t in tokens):
            continue
        score = 0
        if key.startswith(query):
            score += 100
        if query == key:
            score += 200
        if query in key:
            score += 50
        score += max(0, 30 - abs(len(key) - len(query)))
        if food["source"] == "custom":
            score += 40
        elif food["source"] == "local":
            score += 20
        scored.append((score, food))
    scored.sort(key=lambda x: (-x[0], x[1]["name"]))
    results = []
    for _, food in scored[:limit]:
        pg = food["per_g"]
        results.append(
            {
                "id": food["id"],
                "name": food["name"],
                "group": food["group"],
                "source": food["source"],
                "default_serving_g": food["default_serving_g"],
                "per_100g": {
                    "kcal": round(pg["kcal"] * 100, 1),
                    "protein_g": round(pg["p"] * 100, 1),
                    "carbs_g": round(pg["c"] * 100, 1),
                    "fat_g": round(pg["f"] * 100, 1),
                    "fiber_g": round(pg.get("fiber", 0) * 100, 1),
                },
            }
        )
    return results


def find_food_exact(name: str) -> dict[str, Any] | None:
    key = _norm(name)
    best = None
    for food in load_food_index():
        if food["name_key"] == key:
            return food
        if key in food["name_key"] or key in (food.get("aliases") or ""):
            best = best or food
    return best


def macros_for_weight(per_g: dict[str, float], weight_g: float) -> dict[str, float]:
    w = max(0.0, float(weight_g))
    return {
        "total_kcal": round(w * float(per_g.get("kcal") or 0), 1),
        "protein_g": round(w * float(per_g.get("p") or 0), 1),
        "carbs_g": round(w * float(per_g.get("c") or 0), 1),
        "fat_g": round(w * float(per_g.get("f") or 0), 1),
        "fiber_g": round(w * float(per_g.get("fiber") or 0), 1),
    }


async def resolve_item_nutrition(
    food_name: str,
    weight_g: float,
    *,
    allow_off: bool = True,
    ai_per_g: dict[str, float] | None = None,
) -> dict[str, Any]:
    from backend.plugins.nutrinode_plugin import lookup_open_food_facts

    food = find_food_exact(food_name)
    if food:
        macros = macros_for_weight(food["per_g"], weight_g)
        return {**macros, "macros_source": food["source"], "matched_name": food["name"]}

    if ai_per_g:
        macros = macros_for_weight(ai_per_g, weight_g)
        return {**macros, "macros_source": "ai", "matched_name": food_name}

    if allow_off:
        off = await lookup_open_food_facts(food_name)
        if off:
            macros = macros_for_weight(off, weight_g)
            return {**macros, "macros_source": "open_food_facts", "matched_name": food_name}

    macros = macros_for_weight(LOCAL_MACRO_DB["unknown"], weight_g)
    return {**macros, "macros_source": "fallback", "matched_name": food_name}
