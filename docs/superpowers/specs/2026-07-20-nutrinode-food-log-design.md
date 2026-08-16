# NutriNode food log v1 — search + AI + multi-item

**Date:** 2026-07-20  
**Status:** Implemented (v1)  
**Scope:** Browser NutriNode only (no ESP32)

## Goals

1. Search food (IFCT CSV + local MACRO_DB) → weight / servings → add to meal draft  
2. No match → AI nutrition estimate → optional **Save custom**  
3. Optional camera → AI suggests names → same confirm path  
4. Multi-item meal → **Send** once  
5. Full metrics: kcal, protein, carbs, fat, fiber, weight_g, servings, source, meal_type  
6. Today list edit/delete + daily goal remaining strip  

## Lookup order

`custom foods` → `IFCT` → `MACRO_DB` → Open Food Facts → **AI**

## APIs

| Method | Path | Role |
|--------|------|------|
| GET | `/api/nutrition/foods/search?q=` | Fuzzy search |
| POST | `/api/nutrition/foods/estimate` | AI macros for name+grams |
| POST | `/api/nutrition/foods/custom` | Save custom food |
| POST | `/api/nutrition/analyze-photo` | Vision → draft item names |
| POST | `/api/nutrition/meals` | Confirm multi-item meal |
| GET | `/api/nutrition/today` | Extended with meal_type |
| DELETE | `/api/nutrition/meals/{id}` | Soft delete / filter row |

## Out of scope

ESP32, barcode, Bluetooth scale.
