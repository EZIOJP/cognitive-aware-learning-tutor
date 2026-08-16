import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";

export type DashboardChromeActions = {
  focusMode: boolean;
  toggleFocus: () => void;
  openAddWidget: () => void;
  openCustomize: () => void;
};

type DashboardChromeContextValue = {
  actions: DashboardChromeActions | null;
  setActions: (actions: DashboardChromeActions | null) => void;
};

const DashboardChromeContext = createContext<DashboardChromeContextValue | null>(
  null
);

export function DashboardChromeProvider({ children }: { children: ReactNode }) {
  const [actions, setActionsState] = useState<DashboardChromeActions | null>(null);
  const setActions = useCallback((next: DashboardChromeActions | null) => {
    setActionsState(next);
  }, []);

  const value = useMemo(() => ({ actions, setActions }), [actions, setActions]);

  return (
    <DashboardChromeContext.Provider value={value}>
      {children}
    </DashboardChromeContext.Provider>
  );
}

export function useDashboardChrome() {
  const ctx = useContext(DashboardChromeContext);
  if (!ctx) {
    throw new Error("useDashboardChrome must be used within DashboardChromeProvider");
  }
  return ctx;
}

/** Safe for top bar — null when provider missing or dashboard unmounted. */
export function useDashboardChromeOptional() {
  return useContext(DashboardChromeContext);
}
