import { useState } from "react";
import { Activity, Apple, Zap, Scale, Loader2, Info } from "lucide-react";
import { Card } from "../../app/components/ui/card";
import { useNutrition } from "./NutritionContext";

export function NutritionPage() {
  const { status, liveWsEnabled, setLiveWsEnabled, todayTotals, todayMeals, logManualMeal, runPipeline } =
    useNutrition();
  const [pipelineInsights, setPipelineInsights] = useState<any>(null);
  const [isRunningPipeline, setIsRunningPipeline] = useState(false);
  const [manualFood, setManualFood] = useState("");
  const [manualWeight, setManualWeight] = useState("");

  const handleManualLog = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!manualFood || !manualWeight) return;
    await logManualMeal(manualFood, parseFloat(manualWeight));
    setManualFood("");
    setManualWeight("");
  };

  const handleRunPipeline = async () => {
    setIsRunningPipeline(true);
    const res = await runPipeline();
    setPipelineInsights(res.insights);
    setIsRunningPipeline(false);
  };

  return (
    <div className="h-full overflow-y-auto max-w-5xl mx-auto space-y-6 p-4">
      <header className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold flex items-center gap-3">
            <Apple className="w-8 h-8 text-emerald-500" />
            NutriNode Dashboard
          </h1>
          <p className="text-muted-foreground mt-2">
            Manual logging uses REST. Live feed status:
            <span
              className={`ml-2 px-2 py-1 text-xs rounded-full ${
                status === "connected"
                  ? "bg-emerald-500/20 text-emerald-500"
                  : status === "error"
                    ? "bg-red-500/20 text-red-500"
                    : status === "idle"
                      ? "bg-muted text-muted-foreground"
                      : "bg-amber-500/20 text-amber-500"
              }`}
            >
              {liveWsEnabled ? status : "live feed off"}
            </span>
          </p>
        </div>
        <label className="flex items-center gap-3 cursor-pointer rounded-xl border border-border/60 px-4 py-3 gloss-panel shrink-0">
          <input
            type="checkbox"
            className="h-4 w-4 accent-emerald-500"
            checked={liveWsEnabled}
            onChange={(e) => setLiveWsEnabled(e.target.checked)}
          />
          <span className="text-sm">
            <span className="font-medium block">Live hardware WebSocket</span>
            <span className="text-muted-foreground text-xs">
              Off by default — turn on when ESP32 / scale is connected
            </span>
          </span>
        </label>
      </header>

      {/* Totals Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: "Calories", val: todayTotals?.total_kcal || 0, unit: "kcal", icon: Zap, color: "text-amber-500" },
          { label: "Protein", val: todayTotals?.protein_g || 0, unit: "g", icon: Activity, color: "text-blue-500" },
          { label: "Carbs", val: todayTotals?.carbs_g || 0, unit: "g", icon: Activity, color: "text-emerald-500" },
          { label: "Fats", val: todayTotals?.fat_g || 0, unit: "g", icon: Activity, color: "text-rose-500" },
        ].map(stat => (
          <Card key={stat.label} className="p-4 gloss-panel flex flex-col justify-center">
            <div className="flex items-center gap-2 mb-2 text-muted-foreground">
              <stat.icon className={`w-4 h-4 ${stat.color}`} />
              <span className="text-sm font-medium">{stat.label}</span>
            </div>
            <div className="text-2xl font-bold">
              {Math.round(stat.val)} <span className="text-sm font-normal text-muted-foreground">{stat.unit}</span>
            </div>
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Live Feed */}
        <div className="lg:col-span-2 space-y-4">
          <h2 className="text-xl font-semibold flex items-center gap-2">
            <Scale className="w-5 h-5" /> Today's Log
          </h2>
          <div className="space-y-3">
            {todayMeals.length === 0 ? (
              <Card className="p-8 text-center text-muted-foreground border-dashed">
                No meals logged today yet. Plate some food!
              </Card>
            ) : (
              todayMeals.map(meal => (
                <Card key={meal.meal_id} className="p-4 gloss-panel flex justify-between items-center">
                  <div>
                    <h3 className="font-semibold capitalize text-lg">{meal.food_item}</h3>
                    <div className="text-xs text-muted-foreground flex items-center gap-2 mt-1">
                      <span className="bg-primary/10 text-primary px-2 py-0.5 rounded-full">{meal.location_tag}</span>
                      <span>{meal.weight_g}g</span>
                      <span>•</span>
                      <span>{new Date(meal.timestamp).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</span>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="font-bold text-lg text-amber-500">{Math.round(meal.total_kcal)} kcal</div>
                    <div className="text-xs text-muted-foreground">
                      P: {Math.round(meal.protein_g)}g | C: {Math.round(meal.carbs_g)}g
                    </div>
                  </div>
                </Card>
              ))
            )}
          </div>
        </div>

        {/* Right Column: Actions & Pipeline */}
        <div className="space-y-6">
          <Card className="p-5 gloss-panel">
            <h3 className="font-semibold mb-4">Manual Entry</h3>
            <form onSubmit={handleManualLog} className="space-y-3">
              <div>
                <label className="text-xs text-muted-foreground mb-1 block">Food Item</label>
                <input 
                  type="text" 
                  value={manualFood} 
                  onChange={e => setManualFood(e.target.value)} 
                  className="w-full bg-background border border-border rounded-md px-3 py-2 text-sm"
                  placeholder="e.g. Chicken Biryani"
                />
              </div>
              <div>
                <label className="text-xs text-muted-foreground mb-1 block">Weight (grams)</label>
                <input 
                  type="number" 
                  value={manualWeight} 
                  onChange={e => setManualWeight(e.target.value)} 
                  className="w-full bg-background border border-border rounded-md px-3 py-2 text-sm"
                  placeholder="250"
                />
              </div>
              <button type="submit" className="w-full bg-primary text-primary-foreground py-2 rounded-md text-sm font-medium hover:bg-primary/90 transition-colors">
                Log Meal
              </button>
            </form>
          </Card>

          <Card className="p-5 gloss-panel">
            <h3 className="font-semibold mb-2">Data Pipeline Insights</h3>
            <p className="text-xs text-muted-foreground mb-4">Run the weekly aggregation pipeline to spot dietary anomalies.</p>
            <button 
              onClick={handleRunPipeline} 
              disabled={isRunningPipeline}
              className="w-full bg-secondary text-secondary-foreground py-2 rounded-md text-sm font-medium hover:bg-secondary/80 transition-colors flex justify-center items-center gap-2"
            >
              {isRunningPipeline ? <Loader2 className="w-4 h-4 animate-spin" /> : <Activity className="w-4 h-4" />}
              Generate Insights
            </button>

            {pipelineInsights && (
              <div className="mt-4 pt-4 border-t border-border/50 text-sm">
                <div className="flex items-center gap-2 text-emerald-400 font-medium mb-2">
                  <Info className="w-4 h-4" /> Weekly Summary
                </div>
                <div className="space-y-2 text-xs">
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Total Calories:</span>
                    <span>{Math.round(pipelineInsights.weekly_totals?.total_kcal || 0)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Top Food:</span>
                    <span className="capitalize">{pipelineInsights.top_foods[0]?.[0] || 'N/A'}</span>
                  </div>
                  {pipelineInsights.anomalies?.length > 0 && (
                    <div className="mt-3 p-3 bg-rose-500/10 border border-rose-500/20 rounded-md text-rose-400">
                      <strong>Anomaly Detected:</strong> {pipelineInsights.anomalies[0].food_item} logged at {pipelineInsights.anomalies[0].weight_g}g.
                    </div>
                  )}
                </div>
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
