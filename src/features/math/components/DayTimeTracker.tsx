import { LifeClockWidget } from "../../../components/hub/LifeClockWidget";

/** Back-compat wrapper — prefer LifeClockWidget */
export function DayTimeTracker({ compact = false }: { compact?: boolean }) {
  return <LifeClockWidget compact={compact} embedded={compact} />;
}
