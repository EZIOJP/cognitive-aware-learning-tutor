import { createContext, useContext, type ReactNode } from "react";
import type { HourSlice } from "./hourSliceTypes";

type HourSliceContextValue = {
  slices: HourSlice[];
  dayKey: string;
  enabled: boolean;
};

const HourSliceContext = createContext<HourSliceContextValue>({
  slices: [],
  dayKey: "",
  enabled: false,
});

export function HourSliceProvider({
  slices,
  dayKey,
  enabled,
  children,
}: {
  slices: HourSlice[];
  dayKey: string;
  enabled: boolean;
  children: ReactNode;
}) {
  return (
    <HourSliceContext.Provider value={{ slices, dayKey, enabled }}>{children}</HourSliceContext.Provider>
  );
}

export function useHourSlices(): HourSliceContextValue {
  return useContext(HourSliceContext);
}

export function slicesForDay(slices: HourSlice[], dayKey: string): HourSlice[] {
  return slices.filter((s) => s.date === dayKey);
}
