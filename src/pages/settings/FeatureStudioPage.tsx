import { useEffect, useState } from "react";
import { Link } from "react-router";
import { Plus, Sparkles, Trash2, ArrowLeft, Pencil } from "lucide-react";
import { Card } from "../../app/components/ui/card";
import { useAuth } from "../../context/AuthContext";
import {
  createCustomFeature,
  patchCustomFeature,
  deleteCustomFeature,
  downloadHubExport,
  fetchCustomFeatures,
  fetchFeaturesCatalog,
  fetchHubMetrics,
  type HubCatalogFeature,
  type HubCustomFeature,
  type HubMetricRow,
} from "../../api/hubClient";
import { usePluginRegistry } from "../../plugins/PluginRegistryProvider";

type MetricDraft = { label: string; slug: string; unit: string };

const emptyMetric = (): MetricDraft => ({ label: "", slug: "", unit: "count" });

export function FeatureStudioPage() {
  const { isAuthenticated } = useAuth();
  const { refreshFromServer } = usePluginRegistry();
  const [catalog, setCatalog] = useState<HubCatalogFeature[]>([]);
  const [custom, setCustom] = useState<HubCustomFeature[]>([]);
  const [metrics, setMetrics] = useState<HubMetricRow[]>([]);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [featureSlug, setFeatureSlug] = useState("");
  const [draftMetrics, setDraftMetrics] = useState<MetricDraft[]>([emptyMetric()]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [editDescription, setEditDescription] = useState("");

  const reload = async () => {
    const [cat, cust, met] = await Promise.all([
      fetchFeaturesCatalog(),
      fetchCustomFeatures(),
      fetchHubMetrics(),
    ]);
    setCatalog(cat);
    setCustom(cust);
    setMetrics(met);
  };

  useEffect(() => {
    void reload();
  }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await createCustomFeature({
        name,
        description: description || undefined,
        feature_slug: featureSlug,
        metrics: draftMetrics
          .filter((m) => m.label.trim() && m.slug.trim())
          .map((m) => ({
            label: m.label.trim(),
            slug: m.slug.trim().toLowerCase().replace(/-/g, "_"),
            unit: m.unit || "count",
            source_type: "manual",
          })),
      });
      setName("");
      setDescription("");
      setFeatureSlug("");
      setDraftMetrics([emptyMetric()]);
      await reload();
      await refreshFromServer();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create feature");
    } finally {
      setBusy(false);
    }
  };

  const handleDelete = async (featureId: string) => {
    if (!confirm("Remove this custom feature and its metrics?")) return;
    await deleteCustomFeature(featureId);
    await reload();
    await refreshFromServer();
  };

  const startEdit = (f: HubCustomFeature) => {
    setEditingId(f.feature_id);
    setEditName(f.name);
    setEditDescription(f.description ?? "");
    setError(null);
  };

  const handleSaveEdit = async (featureId: string) => {
    setBusy(true);
    setError(null);
    try {
      await patchCustomFeature(featureId, {
        name: editName.trim(),
        description: editDescription.trim() || null,
      });
      setEditingId(null);
      await reload();
      await refreshFromServer();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not update feature");
    } finally {
      setBusy(false);
    }
  };

  if (!isAuthenticated) {
    return (
      <div className="p-8 max-w-lg mx-auto text-center space-y-4">
        <p className="text-muted-foreground">Sign in to create custom features and sync them across devices.</p>
        <Link to="/login" className="text-primary underline">
          Go to login
        </Link>
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto max-w-4xl mx-auto space-y-8 p-4">
      <div className="flex items-center gap-3">
        <Link to="/settings/plugins" className="p-2 rounded-lg hover:bg-muted">
          <ArrowLeft className="w-5 h-5" />
        </Link>
        <div>
          <h1 className="text-3xl font-bold flex items-center gap-3">
            <Sparkles className="w-8 h-8 text-violet-400" />
            Feature Studio
          </h1>
          <p className="text-muted-foreground mt-1">
            Add your own modules with customized metrics — no app redeploy. Coded plugins still ship with the app;
            enable them under Plugin Manager.
          </p>
        </div>
      </div>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">Built-in catalog</h2>
        <div className="grid gap-3 md:grid-cols-2">
          {catalog.map((f) => (
            <Card key={f.plugin_id} className="p-4 gloss-panel text-sm">
              <p className="font-medium">{f.name}</p>
              <p className="text-muted-foreground mt-1">{f.description}</p>
              <ul className="mt-2 text-xs text-muted-foreground space-y-0.5">
                {f.metrics.map((m) => (
                  <li key={m.slug}>
                    {m.label} ({m.unit})
                  </li>
                ))}
              </ul>
            </Card>
          ))}
        </div>
      </section>

      <section>
        <h2 className="text-lg font-semibold mb-3">Create custom feature</h2>
        <Card className="p-5 gloss-panel">
          <form onSubmit={(e) => void handleCreate(e)} className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="block text-sm">
                <span className="text-muted-foreground">Feature name</span>
                <input
                  className="mt-1 w-full px-3 py-2 rounded-lg bg-muted/40 border border-border"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                  placeholder="Water tracking"
                />
              </label>
              <label className="block text-sm">
                <span className="text-muted-foreground">URL slug</span>
                <input
                  className="mt-1 w-full px-3 py-2 rounded-lg bg-muted/40 border border-border"
                  value={featureSlug}
                  onChange={(e) => setFeatureSlug(e.target.value)}
                  required
                  placeholder="water"
                  pattern="[a-z][a-z0-9-]{1,32}"
                />
              </label>
            </div>
            <label className="block text-sm">
              <span className="text-muted-foreground">Description (optional)</span>
              <textarea
                className="mt-1 w-full px-3 py-2 rounded-lg bg-muted/40 border border-border min-h-[60px]"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
            </label>

            <div className="space-y-2">
              <p className="text-sm font-medium">Metrics to track</p>
              {draftMetrics.map((m, i) => (
                <div key={i} className="grid gap-2 sm:grid-cols-3">
                  <input
                    placeholder="Label (Glasses of water)"
                    className="px-3 py-2 rounded-lg bg-muted/40 border border-border text-sm"
                    value={m.label}
                    onChange={(e) => {
                      const next = [...draftMetrics];
                      next[i] = { ...next[i], label: e.target.value };
                      setDraftMetrics(next);
                    }}
                  />
                  <input
                    placeholder="slug (glasses)"
                    className="px-3 py-2 rounded-lg bg-muted/40 border border-border text-sm"
                    value={m.slug}
                    onChange={(e) => {
                      const next = [...draftMetrics];
                      next[i] = { ...next[i], slug: e.target.value };
                      setDraftMetrics(next);
                    }}
                  />
                  <input
                    placeholder="unit"
                    className="px-3 py-2 rounded-lg bg-muted/40 border border-border text-sm"
                    value={m.unit}
                    onChange={(e) => {
                      const next = [...draftMetrics];
                      next[i] = { ...next[i], unit: e.target.value };
                      setDraftMetrics(next);
                    }}
                  />
                </div>
              ))}
              <button
                type="button"
                className="text-xs text-primary flex items-center gap-1"
                onClick={() => setDraftMetrics((d) => [...d, emptyMetric()])}
              >
                <Plus className="w-3 h-3" /> Add metric
              </button>
            </div>

            {error ? <p className="text-sm text-rose-400">{error}</p> : null}

            <button
              type="submit"
              disabled={busy}
              className="px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium"
            >
              {busy ? "Creating…" : "Create feature"}
            </button>
          </form>
        </Card>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">Your custom features</h2>
        {custom.length === 0 ? (
          <p className="text-sm text-muted-foreground">None yet — create one above.</p>
        ) : (
          custom.map((f) => (
            <Card key={f.feature_id} className="p-4 gloss-panel flex flex-col gap-3">
              {editingId === f.feature_id ? (
                <div className="space-y-2">
                  <input
                    className="w-full px-3 py-2 rounded-lg bg-muted/40 border border-border text-sm"
                    value={editName}
                    onChange={(e) => setEditName(e.target.value)}
                    placeholder="Feature name"
                  />
                  <input
                    className="w-full px-3 py-2 rounded-lg bg-muted/40 border border-border text-sm"
                    value={editDescription}
                    onChange={(e) => setEditDescription(e.target.value)}
                    placeholder="Description"
                  />
                  <div className="flex gap-2">
                    <button
                      type="button"
                      disabled={busy || !editName.trim()}
                      className="px-3 py-1.5 rounded-lg bg-primary text-primary-foreground text-sm"
                      onClick={() => void handleSaveEdit(f.feature_id)}
                    >
                      Save
                    </button>
                    <button
                      type="button"
                      className="px-3 py-1.5 rounded-lg bg-muted text-sm"
                      onClick={() => setEditingId(null)}
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <div className="flex justify-between gap-4">
                  <div>
                    <p className="font-medium">{f.name}</p>
                    {f.description ? (
                      <p className="text-sm text-muted-foreground mt-0.5">{f.description}</p>
                    ) : null}
                    <p className="text-xs text-muted-foreground">{f.feature_id}</p>
                    <Link to={`/features/${f.feature_id}`} className="text-xs text-primary mt-2 inline-block">
                      Open →
                    </Link>
                  </div>
                  <div className="flex gap-1 shrink-0">
                    <button
                      type="button"
                      onClick={() => startEdit(f)}
                      className="p-2 text-muted-foreground hover:bg-muted rounded-lg"
                      title="Edit name & description"
                    >
                      <Pencil className="w-4 h-4" />
                    </button>
                    <button
                      type="button"
                      onClick={() => void handleDelete(f.feature_id)}
                      className="p-2 text-rose-400 hover:bg-rose-500/10 rounded-lg"
                      title="Delete feature"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              )}
            </Card>
          ))
        )}
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">Export central data</h2>
        <p className="text-sm text-muted-foreground">
          Download life logs, rollups, and reading counts from the hub. Full account dump: Profile → export.
        </p>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            className="px-3 py-2 rounded-lg bg-muted text-sm hover:bg-muted/80"
            onClick={() => void downloadHubExport("json").catch((e) => setError(String(e)))}
          >
            Download JSON
          </button>
          <button
            type="button"
            className="px-3 py-2 rounded-lg bg-muted text-sm hover:bg-muted/80"
            onClick={() => void downloadHubExport("csv").catch((e) => setError(String(e)))}
          >
            Download CSV
          </button>
        </div>
      </section>

      <section className="space-y-2">
        <h2 className="text-lg font-semibold">Active metrics (yours + enabled plugins)</h2>
        <ul className="text-sm space-y-1 text-muted-foreground">
          {metrics.map((m) => (
            <li key={m.slug}>
              {m.label} · <code className="text-xs">{m.slug}</code>
              {m.user_owned ? " · custom" : " · system"}
            </li>
          ))}
        </ul>
      </section>

      <Card className="p-4 gloss-panel text-sm text-muted-foreground">
        <p className="font-medium text-foreground">Shipping a coded plugin (developers)</p>
        <ol className="list-decimal list-inside mt-2 space-y-1">
          <li>Add <code>PluginDef</code> under <code>src/plugins/</code> and <code>registerPlugin()</code></li>
          <li>Import in <code>src/plugins/index.ts</code></li>
          <li>Add entry to <code>backend/hub/services/catalog.py</code> and seed defaults</li>
          <li>Users enable it in Plugin Manager — state saves to the server</li>
        </ol>
      </Card>
    </div>
  );
}
