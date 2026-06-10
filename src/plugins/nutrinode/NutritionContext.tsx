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
  total_kcal: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
  fiber_g: number;
  confidence: number;
  is_healthy: boolean | null;
  location_tag: string;
  source: string;
}

export interface NutritionTotals {
  total_kcal: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
  fiber_g: number;
  meal_count: number;
}

interface NutritionState {
  status: "connected" | "disconnected" | "error" | "connecting" | "idle";
  liveWsEnabled: boolean;
  setLiveWsEnabled: (on: boolean) => void;
  todayTotals: NutritionTotals | null;
  todayMeals: MealEntry[];
  refreshToday: () => Promise<void>;
  logManualMeal: (foodItem: string, weightGrams: number, locationTag?: string) => Promise<void>;
  runPipeline: () => Promise<unknown>;
}

const NutritionContext = createContext<NutritionState | undefined>(undefined);

const MAX_WS_RETRIES = 3;
const WS_RETRY_MS = 5000;

export function NutritionProvider({ children }: { children: React.ReactNode }) {
  const [liveWsEnabled, setLiveWsEnabledState] = useState(isNutritionLiveWsEnabled);
  const [status, setStatus] = useState<NutritionState["status"]>("idle");
  const [todayTotals, setTodayTotals] = useState<NutritionTotals | null>(null);
  const [todayMeals, setTodayMeals] = useState<MealEntry[]>([]);
  const wsRef = useRef<WebSocket | null>(null);
  const retryCountRef = useRef(0);
  const gaveUpRef = useRef(false);

  const applyTodayPayload = useCallback((data: { totals?: NutritionTotals; meals?: MealEntry[] }) => {
    if (data.totals) setTodayTotals(data.totals);
    if (data.meals) setTodayMeals(data.meals);
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
            setTodayMeals((prev) => [msg.data, ...prev]);
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
  }, [liveWsEnabled, applyTodayPayload]);

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
