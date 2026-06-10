import { useEffect, useRef, useState } from "react";

const LS_KEY = "widget:desmos:expressions";
const DESMOS_SCRIPT = "https://www.desmos.com/api/v1.9/calculator.js?apiKey=dcb31709b452b1cf9d26976845cc9b1c";

type DesmosCalculator = {
  setExpression: (opts: { id: string; latex: string }) => void;
  getState: () => { expressions: { list: { id: string; latex?: string }[] } };
  setState: (state: unknown) => void;
  destroy: () => void;
};

declare global {
  interface Window {
    Desmos?: {
      GraphingCalculator: (
        el: HTMLElement,
        opts?: { expressions?: boolean; settingsMenu?: boolean; zoomButtons?: boolean }
      ) => DesmosCalculator;
    };
  }
}

function loadDesmosScript(): Promise<void> {
  if (window.Desmos) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const existing = document.querySelector(`script[src^="https://www.desmos.com/api"]`);
    if (existing) {
      existing.addEventListener("load", () => resolve());
      return;
    }
    const script = document.createElement("script");
    script.src = DESMOS_SCRIPT;
    script.async = true;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("Desmos script failed to load"));
    document.head.appendChild(script);
  });
}

export function DesmosGraphWidget() {
  const containerRef = useRef<HTMLDivElement>(null);
  const calcRef = useRef<DesmosCalculator | null>(null);
  const [expr, setExpr] = useState(() => {
    try {
      const saved = localStorage.getItem(LS_KEY);
      return saved ? (JSON.parse(saved) as string) : "y=x^2";
    } catch {
      return "y=x^2";
    }
  });
  const [ready, setReady] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        await loadDesmosScript();
        if (cancelled || !containerRef.current || !window.Desmos) return;
        const calc = window.Desmos.GraphingCalculator(containerRef.current, {
          expressions: true,
          settingsMenu: false,
          zoomButtons: true,
        });
        calcRef.current = calc;
        calc.setExpression({ id: "graph1", latex: expr });
        setReady(true);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Desmos unavailable");
      }
    })();
    return () => {
      cancelled = true;
      calcRef.current?.destroy();
      calcRef.current = null;
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const applyExpr = () => {
    const latex = expr.trim();
    if (!latex || !calcRef.current) return;
    calcRef.current.setExpression({ id: "graph1", latex });
    localStorage.setItem(LS_KEY, JSON.stringify(latex));
  };

  return (
    <div className="flex flex-col gap-2 h-full min-h-[180px]">
      <div className="flex gap-2">
        <input
          type="text"
          value={expr}
          onChange={(e) => setExpr(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && applyExpr()}
          placeholder="y = x^2"
          className="flex-1 rounded-lg border border-border/60 bg-background/50 px-3 py-1.5 text-sm font-mono"
          aria-label="Desmos expression"
        />
        <button
          type="button"
          onClick={applyExpr}
          disabled={!ready}
          className="px-3 py-1.5 rounded-lg text-xs font-medium bg-primary text-primary-foreground disabled:opacity-50"
        >
          Plot
        </button>
      </div>
      {error ? (
        <p className="text-xs text-destructive">{error}</p>
      ) : (
        <div
          ref={containerRef}
          className="flex-1 min-h-[120px] rounded-lg border border-border/40 overflow-hidden bg-background/30"
        />
      )}
    </div>
  );
}
