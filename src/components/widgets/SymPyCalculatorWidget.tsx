import { useCallback, useState } from "react";
import { Calculator, Loader2 } from "lucide-react";
import { evalMathExpression } from "../../api/mathClient";
import { Button } from "../../app/components/ui/button";

const EXAMPLES = ["2*x + 3*x", "integrate(x**2, x)", "diff(sin(x), x)", "solve(x**2 - 4, x)"];

export function SymPyCalculatorWidget() {
  const [expression, setExpression] = useState("2*x + 3*x");
  const [result, setResult] = useState<{
    latex: string;
    text: string;
    steps: string[];
    error?: string;
  } | null>(null);
  const [loading, setLoading] = useState(false);

  const runEval = useCallback(async (expr?: string) => {
    const q = (expr ?? expression).trim();
    if (!q) return;
    setLoading(true);
    const out = await evalMathExpression(q);
    setLoading(false);
    if (!out) {
      setResult({ latex: "", text: "", steps: [], error: "Could not reach math API — sign in and start backend." });
      return;
    }
    if (!out.ok) {
      setResult({ latex: "", text: "", steps: out.steps ?? [], error: out.error ?? "Invalid expression" });
      return;
    }
    setResult({ latex: out.latex, text: out.result, steps: out.steps, error: undefined });
  }, [expression]);

  return (
    <div className="flex flex-col gap-3 h-full min-h-[140px]">
      <div className="flex gap-2">
        <input
          type="text"
          value={expression}
          onChange={(e) => setExpression(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && void runEval()}
          placeholder="e.g. integrate(x**2, x)"
          className="flex-1 min-w-0 rounded-lg border border-border/60 bg-background/50 px-3 py-2 text-sm font-mono"
          aria-label="Math expression"
        />
        <Button
          type="button"
          size="sm"
          onClick={() => void runEval()}
          disabled={loading}
          className="shrink-0"
        >
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Calculator className="w-4 h-4" />}
        </Button>
      </div>

      <div className="flex flex-wrap gap-1">
        {EXAMPLES.map((ex) => (
          <button
            key={ex}
            type="button"
            onClick={() => {
              setExpression(ex);
              void runEval(ex);
            }}
            className="text-[10px] px-2 py-0.5 rounded-full border border-border/50 text-muted-foreground hover:text-foreground hover:border-primary/40 transition-colors"
          >
            {ex}
          </button>
        ))}
      </div>

      {result?.error ? (
        <p className="text-xs text-destructive">{result.error}</p>
      ) : result ? (
        <div className="space-y-1">
          <p className="text-lg font-semibold font-mono text-primary">{result.text}</p>
          {result.latex ? (
            <p className="text-xs text-muted-foreground font-mono truncate" title={result.latex}>
              LaTeX: {result.latex}
            </p>
          ) : null}
          {result.steps.length > 1 ? (
            <ul className="text-[10px] text-muted-foreground space-y-0.5">
              {result.steps.map((s) => (
                <li key={s}>{s}</li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : (
        <p className="text-xs text-muted-foreground">SymPy-backed — try an example above.</p>
      )}
    </div>
  );
}
