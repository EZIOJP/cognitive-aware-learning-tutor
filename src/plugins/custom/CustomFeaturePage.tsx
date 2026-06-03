import { useEffect, useState } from "react";
import { Sparkles, Plus } from "lucide-react";
import { Card } from "../../app/components/ui/card";
import {
  fetchCustomFeatures,
  postHubReading,
  type HubCustomFeature,
  type HubMetricRow,
} from "../../api/hubClient";

type Props = { featureId: string };

export function CustomFeaturePage({ featureId }: Props) {
  const [feature, setFeature] = useState<HubCustomFeature | null>(null);
  const [values, setValues] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    const list = await fetchCustomFeatures();
    setFeature(list.find((f) => f.feature_id === featureId) ?? null);
  };

  useEffect(() => {
    void load();
  }, [featureId]);

  const logMetric = async (metric: HubMetricRow) => {
    const raw = values[metric.slug];
    const num = parseFloat(raw);
    if (Number.isNaN(num)) {
      setError(`Enter a number for ${metric.label}`);
      return;
    }
    setError(null);
    setSaving(metric.slug);
    const ok = await postHubReading(metric.slug, num);
    setSaving(null);
    if (!ok) setError("Failed to save reading");
    else setValues((v) => ({ ...v, [metric.slug]: "" }));
  };

  if (!feature) {
    return (
      <div className="p-8 text-muted-foreground">
        Custom feature not found. It may have been removed.
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto max-w-3xl mx-auto space-y-6 p-4">
      <header>
        <h1 className="text-3xl font-bold flex items-center gap-3">
          <Sparkles className="w-8 h-8 text-violet-400" />
          {feature.name}
        </h1>
        {feature.description ? (
          <p className="text-muted-foreground mt-2">{feature.description}</p>
        ) : null}
      </header>

      {error ? <p className="text-sm text-rose-400">{error}</p> : null}

      <div className="space-y-4">
        {feature.metrics.map((m) => (
          <Card key={m.slug} className="p-4 gloss-panel flex flex-col sm:flex-row sm:items-end gap-3">
            <div className="flex-1">
              <p className="font-medium">{m.label}</p>
              <p className="text-xs text-muted-foreground">
                {m.slug} · {m.unit ?? "count"} · {m.source_type}
              </p>
            </div>
            <div className="flex gap-2 items-center">
              <input
                type="number"
                step="any"
                className="w-32 px-3 py-2 rounded-lg bg-muted/40 border border-border text-sm"
                placeholder="Value"
                value={values[m.slug] ?? ""}
                onChange={(e) => setValues((v) => ({ ...v, [m.slug]: e.target.value }))}
              />
              <button
                type="button"
                onClick={() => void logMetric(m)}
                disabled={saving === m.slug}
                className="px-3 py-2 rounded-lg bg-primary text-primary-foreground text-sm flex items-center gap-1"
              >
                <Plus className="w-4 h-4" />
                Log
              </button>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
