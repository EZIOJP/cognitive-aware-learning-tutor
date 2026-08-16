import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { resolveApiUrl, resolveNutritionWsUrl } from "../../utils/resolveBackendUrl";
import {
  isNutritionLiveWsEnabled,
  NUTRINODE_LIVE_WS_EVENT,
  setNutritionLiveWsEnabled,
} from "./nutritionLive";

export interface MealEntry {
  meal_id: string;
  timestamp: string;
  food_item: string;
  weight_g: number;
  servings?: number;
  meal_type?: string;
  total_kcal: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
  fiber_g: number;
  confidence: number;
  is_healthy: boolean | null;
  location_tag: string;
  source: string;
  macros_source?: string;
}

export interface NutritionTotals {
  total_kcal: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
  fiber_g: number;
  meal_count: number;
}

export interface FoodSearchHit {
  id: string;
  name: string;
  group: string;
  source: string;
  default_serving_g: number;
  per_100g: {
    kcal: number;
    protein_g: number;
    carbs_g: number;
    fat_g: number;
    fiber_g: number;
  };
}

export interface NutritionEstimate {
  food_name: string;
  total_kcal: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
  fiber_g: number;
  macros_source: string;
  confidence?: number;
  notes?: string;
  per_g?: { kcal: number; p: number; c: number; f: number; fiber: number };
  per_100g?: FoodSearchHit["per_100g"];
}

export interface PhotoSuggestItem {
  suggested_name: string;
  estimated_weight_g: number | null;
  confidence: number;
}

export interface MealDraftItem {
  food_name: string;
  weight_g: number;
  servings: number;
  macros_source?: string;
  ai_per_g?: NutritionEstimate["per_g"];
  preview?: {
    total_kcal: number;
    protein_g: number;
    carbs_g: number;
    fat_g: number;
    fiber_g: number;
  };
}

interface NutritionState {
  status: "connected" | "disconnected" | "error" | "connecting" | "idle";
  liveWsEnabled: boolean;
  setLiveWsEnabled: (on: boolean) => void;
  todayTotals: NutritionTotals | null;
  todayMeals: MealEntry[];
  refreshToday: () => Promise<void>;
  logManualMeal: (foodItem: string, weightGrams: number, locationTag?: string) => Promise<void>;
  searchFoods: (q: string) => Promise<FoodSearchHit[]>;
  estimateFood: (foodName: string, weightG: number) => Promise<NutritionEstimate>;
  saveCustomFood: (payload: {
    name: string;
    display_name?: string;
    per_g: NonNullable<NutritionEstimate["per_g"]>;
    default_serving_g?: number;
  }) => Promise<void>;
  analyzePhoto: (file: File) => Promise<{ items: PhotoSuggestItem[]; description: string }>;
  confirmMeal: (items: MealDraftItem[], mealType: string) => Promise<void>;
  deleteMeal: (mealId: string) => Promise<void>;
  runPipeline: () => Promise<unknown>;
}

const NutritionContext = createContext<NutritionState | undefined>(undefined);

const MAX_WS_RETRIES = 3;
const WS_RETRY_MS = 5000;

function coerceMeal(row: Record<string, unknown>): MealEntry {
  return {
    meal_id: String(row.meal_id || ""),
    timestamp: String(row.timestamp || ""),
    food_item: String(row.food_item || ""),
    weight_g: Number(row.weight_g || 0),
    servings: row.servings != null ? Number(row.servings) : undefined,
    meal_type: row.meal_type != null ? String(row.meal_type) : undefined,
    total_kcal: Number(row.total_kcal || 0),
    protein_g: Number(row.protein_g || 0),
    carbs_g: Number(row.carbs_g || 0),
    fat_g: Number(row.fat_g || 0),
    fiber_g: Number(row.fiber_g || 0),
    confidence: Number(row.confidence || 0),
    is_healthy: row.is_healthy == null || row.is_healthy === "" ? null : Boolean(row.is_healthy),
    location_tag: String(row.location_tag || ""),
    source: String(row.source || ""),
    macros_source: row.macros_source != null ? String(row.macros_source) : undefined,
  };
}

export function NutritionProvider({ children }: { children: React.ReactNode }) {
  const [liveWsEnabled, setLiveWsEnabledState] = useState(isNutritionLiveWsEnabled);
  const [status, setStatus] = useState<NutritionState["status"]>("idle");
  const [todayTotals, setTodayTotals] = useState<NutritionTotals | null>(null);
  const [todayMeals, setTodayMeals] = useState<MealEntry[]>([]);
  const wsRef = useRef<WebSocket | null>(null);
  const retryCountRef = useRef(0);
  const gaveUpRef = useRef(false);

  const applyTodayPayload = useCallback((data: { totals?: NutritionTotals; meals?: Record<string, unknown>[] }) => {
    if (data.totals) setTodayTotals(data.totals);
    if (data.meals) setTodayMeals(data.meals.map(coerceMeal));
  }, []);

  const refreshToday = useCallback(async () => {
    try {
      const res = await fetch(`${resolveApiUrl()}/api/nutrition/today`);
      if (res.ok) {
        const data = await res.json();
        applyTodayPayload(data);
      }
    } catch {
      /* backend or plugin unavailable */
    }
  }, [applyTodayPayload]);

  const setLiveWsEnabled = useCallback((on: boolean) => {
    setNutritionLiveWsEnabled(on);
    setLiveWsEnabledState(on);
    if (!on) {
      gaveUpRef.current = false;
      retryCountRef.current = 0;
      wsRef.current?.close();
      wsRef.current = null;
      setStatus("idle");
    }
  }, []);

  useEffect(() => {
    void refreshToday();
  }, [refreshToday]);

  useEffect(() => {
    const onPrefChange = () => {
      const on = isNutritionLiveWsEnabled();
      setLiveWsEnabledState(on);
      if (!on) {
        gaveUpRef.current = false;
        retryCountRef.current = 0;
        wsRef.current?.close();
        wsRef.current = null;
        setStatus("idle");
      }
    };
    window.addEventListener(NUTRINODE_LIVE_WS_EVENT, onPrefChange);
    window.addEventListener("storage", onPrefChange);
    return () => {
      window.removeEventListener(NUTRINODE_LIVE_WS_EVENT, onPrefChange);
      window.removeEventListener("storage", onPrefChange);
    };
  }, []);

  useEffect(() => {
    if (!liveWsEnabled) {
      return;
    }

    let reconnectTimeout: ReturnType<typeof setTimeout> | undefined;
    let cancelled = false;

    const scheduleReconnect = () => {
      if (cancelled || gaveUpRef.current) return;
      if (retryCountRef.current >= MAX_WS_RETRIES) {
        gaveUpRef.current = true;
        setStatus("error");
        return;
      }
      retryCountRef.current += 1;
      reconnectTimeout = setTimeout(connect, WS_RETRY_MS);
    };

    const connect = () => {
      if (cancelled || gaveUpRef.current) return;
      setStatus("connecting");
      const ws = new WebSocket(resolveNutritionWsUrl());
      wsRef.current = ws;

      ws.onopen = () => {
        retryCountRef.current = 0;
        gaveUpRef.current = false;
        setStatus("connected");
      };

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.event === "init") {
            applyTodayPayload(msg.data);
          } else if (msg.event === "new_meal") {
            setTodayMeals((prev) => [coerceMeal(msg.data), ...prev]);
            setTodayTotals((prev) => {
              if (!prev) return prev;
              return {
                total_kcal: prev.total_kcal + Number(msg.data.total_kcal || 0),
                protein_g: prev.protein_g + Number(msg.data.protein_g || 0),
                carbs_g: prev.carbs_g + Number(msg.data.carbs_g || 0),
                fat_g: prev.fat_g + Number(msg.data.fat_g || 0),
                fiber_g: prev.fiber_g + Number(msg.data.fiber_g || 0),
                meal_count: prev.meal_count + 1,
              };
            });
          } else if (msg.event === "meal_deleted") {
            void refreshToday();
          }
        } catch (e) {
          console.warn("WS msg parse error", e);
        }
      };

      ws.onclose = () => {
        wsRef.current = null;
        if (cancelled || !isNutritionLiveWsEnabled()) {
          setStatus("idle");
          return;
        }
        setStatus("disconnected");
        scheduleReconnect();
      };

      ws.onerror = () => {
        setStatus("error");
      };
    };

    connect();

    return () => {
      cancelled = true;
      clearTimeout(reconnectTimeout);
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, [liveWsEnabled, applyTodayPayload, refreshToday]);

  const logManualMeal = async (foodItem: string, weightGrams: number, locationTag = "manual") => {
    await fetch(`${resolveApiUrl()}/api/nutrition/manual`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        food_item: foodItem,
        weight_grams: weightGrams,
        location_tag: locationTag,
      }),
    });
    await refreshToday();
  };

  const searchFoods = async (q: string): Promise<FoodSearchHit[]> => {
    const res = await fetch(`${resolveApiUrl()}/api/nutrition/foods/search?q=${encodeURIComponent(q)}`);
    if (!res.ok) return [];
    const data = await res.json();
    return data.results || [];
  };

  const estimateFood = async (foodName: string, weightG: number): Promise<NutritionEstimate> => {
    const res = await fetch(`${resolveApiUrl()}/api/nutrition/foods/estimate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ food_name: foodName, weight_g: weightG }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Estimate failed");
    }
    return res.json();
  };

  const saveCustomFood = async (payload: {
    name: string;
    display_name?: string;
    per_g: NonNullable<NutritionEstimate["per_g"]>;
    default_serving_g?: number;
  }) => {
    await fetch(`${resolveApiUrl()}/api/nutrition/foods/custom`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  };

  const analyzePhoto = async (file: File) => {
    const form = new FormData();
    form.append("image", file);
    const res = await fetch(`${resolveApiUrl()}/api/nutrition/analyze-photo`, {
      method: "POST",
      body: form,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Photo analysis failed");
    }
    return res.json();
  };

  const confirmMeal = async (items: MealDraftItem[], mealType: string) => {
    const res = await fetch(`${resolveApiUrl()}/api/nutrition/meals`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        meal_type: mealType,
        items: items.map((it) => ({
          food_name: it.food_name,
          weight_g: it.weight_g,
          servings: it.servings,
          macros_source: it.macros_source,
          ai_per_g: it.ai_per_g,
        })),
      }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Failed to log meal");
    }
    await refreshToday();
  };

  const deleteMeal = async (mealId: string) => {
    const res = await fetch(`${resolveApiUrl()}/api/nutrition/meals/${encodeURIComponent(mealId)}`, {
      method: "DELETE",
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Delete failed");
    }
    await refreshToday();
  };

  const runPipeline = async () => {
    const res = await fetch(`${resolveApiUrl()}/api/nutrition/pipeline/run`, { method: "POST" });
    return res.json();
  };

  return (
    <NutritionContext.Provider
      value={{
        status,
        liveWsEnabled,
        setLiveWsEnabled,
        todayTotals,
        todayMeals,
        refreshToday,
        logManualMeal,
        searchFoods,
        estimateFood,
        saveCustomFood,
        analyzePhoto,
        confirmMeal,
        deleteMeal,
        runPipeline,
      }}
    >
      {children}
    </NutritionContext.Provider>
  );
}

export function useNutrition() {
  const context = useContext(NutritionContext);
  if (context === undefined) {
    throw new Error("useNutrition must be used within a NutritionProvider");
  }
  return context;
}
