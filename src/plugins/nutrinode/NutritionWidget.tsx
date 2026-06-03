import { Apple, Plus } from "lucide-react";
import { useNutrition } from "./NutritionContext";

export function NutritionWidget() {
  const { todayTotals, status } = useNutrition();

  const cal = Math.round(todayTotals?.total_kcal || 0);
  const pro = Math.round(todayTotals?.protein_g || 0);
  
  // Example targets
  const calTarget = 2000;
  const proTarget = 150;

  const calPct = Math.min((cal / calTarget) * 100, 100);
  const proPct = Math.min((pro / proTarget) * 100, 100);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex flex-col">
          <span className="text-2xl font-bold">{cal} <span className="text-sm font-normal text-muted-foreground">/ {calTarget} kcal</span></span>
        </div>
        <div
          className={`w-2 h-2 rounded-full ${
            status === "connected"
              ? "bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.8)]"
              : status === "idle"
                ? "bg-muted"
                : "bg-amber-500/80"
          }`}
          title={status === "connected" ? "Live feed" : "REST / live feed off"}
        />
      </div>
      
      <div className="space-y-2">
        <div className="flex items-center justify-between text-xs">
          <span className="text-muted-foreground">Energy</span>
          <span className="font-medium text-amber-500">{Math.round(calPct)}%</span>
        </div>
        <div className="h-1.5 bg-muted/30 rounded-full overflow-hidden">
          <div className="h-full bg-amber-500 rounded-full transition-all duration-1000" style={{ width: `${calPct}%` }} />
        </div>
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between text-xs">
          <span className="text-muted-foreground">Protein</span>
          <span className="font-medium text-blue-500">{pro}g / {proTarget}g</span>
        </div>
        <div className="h-1.5 bg-muted/30 rounded-full overflow-hidden">
          <div className="h-full bg-blue-500 rounded-full transition-all duration-1000" style={{ width: `${proPct}%` }} />
        </div>
      </div>
    </div>
  );
}
