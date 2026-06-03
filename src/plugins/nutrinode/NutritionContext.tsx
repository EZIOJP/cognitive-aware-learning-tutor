import React, { createContext, useContext, useEffect, useState, useRef } from "react";

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
  status: "connected" | "disconnected" | "error" | "connecting";
  todayTotals: NutritionTotals | null;
  todayMeals: MealEntry[];
  logManualMeal: (foodItem: string, weightGrams: number, locationTag?: string) => Promise<void>;
  runPipeline: () => Promise<any>;
}

const NutritionContext = createContext<NutritionState | undefined>(undefined);

export function NutritionProvider({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState<NutritionState["status"]>("connecting");
  const [todayTotals, setTodayTotals] = useState<NutritionTotals | null>(null);
  const [todayMeals, setTodayMeals] = useState<MealEntry[]>([]);
  const wsRef = useRef<WebSocket | null>(null);
  
  const WS_URL = "ws://localhost:8000/ws/nutrition/live";
  const API_URL = "http://localhost:8000";

  useEffect(() => {
    let reconnectTimeout: ReturnType<typeof setTimeout>;

    const connect = () => {
      setStatus("connecting");
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        setStatus("connected");
      };

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.event === "init") {
            setTodayTotals(msg.data.totals);
            setTodayMeals(msg.data.meals);
          } else if (msg.event === "new_meal") {
            setTodayMeals((prev) => [msg.data, ...prev]);
            // Optimistically update totals
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
        setStatus("disconnected");
        reconnectTimeout = setTimeout(connect, 3000);
      };

      ws.onerror = () => {
        setStatus("error");
      };
    };

    connect();

    return () => {
      clearTimeout(reconnectTimeout);
      wsRef.current?.close();
    };
  }, []);

  const logManualMeal = async (foodItem: string, weightGrams: number, locationTag = "manual") => {
    await fetch(`${API_URL}/api/nutrition/manual`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ food_item: foodItem, weight_grams: weightGrams, location_tag: locationTag })
    });
  };

  const runPipeline = async () => {
    const res = await fetch(`${API_URL}/api/nutrition/pipeline/run`, { method: "POST" });
    return res.json();
  };

  return (
    <NutritionContext.Provider value={{ status, todayTotals, todayMeals, logManualMeal, runPipeline }}>
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
