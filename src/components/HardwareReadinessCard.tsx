import { Cpu, Radio, Sparkles } from "lucide-react";
import { Card } from "../app/components/ui/card";

/** Shown in settings — clarifies software is ready before hardware / GPU purchase. */
export function HardwareReadinessCard() {
  return (
    <Card className="p-5 gloss-panel border-primary/20 bg-primary/5 space-y-3">
      <div className="flex items-start gap-3">
        <div className="w-10 h-10 rounded-xl bg-primary/15 flex items-center justify-center shrink-0">
          <Sparkles className="w-5 h-5 text-primary" />
        </div>
        <div className="space-y-1 text-sm">
          <p className="font-semibold text-foreground">Software ready — hardware optional</p>
          <p className="text-muted-foreground">
            EEG and NutriNode run in <strong className="font-medium text-foreground">demo mode</strong> until you
            add ESP32 boards. Math tutor uses built-in coaching (no GPU). When your laptop is back, you can
            optionally enable Ollama — see the guide below.
          </p>
        </div>
      </div>
      <ul className="text-xs text-muted-foreground space-y-1.5 ml-1">
        <li className="flex items-center gap-2">
          <Radio className="w-3.5 h-3.5 text-violet-400 shrink-0" />
          EEG plugin → simulation now; ESP32 → UDP port 5005 later
        </li>
        <li className="flex items-center gap-2">
          <Cpu className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
          NutriNode → manual meals now; scale/board later
        </li>
      </ul>
      <p className="text-xs text-primary font-medium">
        Guide: <code className="text-[10px] font-normal">docs/HARDWARE_AND_AI_LATER.md</code>
      </p>
    </Card>
  );
}
