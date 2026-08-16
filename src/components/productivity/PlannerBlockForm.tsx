import { useEffect, useState } from "react";
import { Button } from "../../app/components/ui/button";

const CATEGORIES = ["reading", "study", "lecture", "review", "break"] as const;

type Props = {
  defaultStart?: Date;
  onSubmit: (data: {
    title: string;
    category: string;
    start_at: string;
    duration_minutes: number;
  }) => Promise<void>;
  onCancel: () => void;
  /** Flatten into parent card (no nested border) */
  embedded?: boolean;
};

function toLocalInput(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function PlannerBlockForm({ defaultStart, onSubmit, onCancel, embedded = false }: Props) {
  const [title, setTitle] = useState("1 hr reading");
  const [category, setCategory] = useState<string>("reading");
  const [duration, setDuration] = useState(60);
  const [startLocal, setStartLocal] = useState(() => toLocalInput(defaultStart ?? new Date()));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (defaultStart) setStartLocal(toLocalInput(defaultStart));
  }, [defaultStart?.getTime()]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const start = new Date(startLocal);
      await onSubmit({
        title: title.trim() || "Study block",
        category,
        start_at: start.toISOString(),
        duration_minutes: duration,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create block");
    } finally {
      setSaving(false);
    }
  };

  return (
    <form
      onSubmit={(e) => void handleSubmit(e)}
      className={
        embedded
          ? "space-y-3 rounded-xl border border-white/10 bg-black/20 p-3"
          : "space-y-3 p-4 rounded-lg border border-border bg-card"
      }
    >
      <h3 className="text-sm font-semibold text-foreground">Quick add block</h3>
      {error && <p className="text-xs text-red-400">{error}</p>}
      <label className="block text-xs text-muted-foreground">
        Title
        <input
          className="mt-1 w-full rounded border border-border bg-background px-2 py-1.5 text-sm"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
        />
      </label>
      <label className="block text-xs text-muted-foreground">
        Category
        <select
          className="mt-1 w-full rounded border border-border bg-background px-2 py-1.5 text-sm"
          value={category}
          onChange={(e) => setCategory(e.target.value)}
        >
          {CATEGORIES.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
      </label>
      <div className="grid grid-cols-2 gap-2">
        <label className="block text-xs text-muted-foreground">
          Start
          <input
            type="datetime-local"
            className="mt-1 w-full rounded border border-border bg-background px-2 py-1.5 text-sm"
            value={startLocal}
            onChange={(e) => setStartLocal(e.target.value)}
          />
        </label>
        <label className="block text-xs text-muted-foreground">
          Duration (min)
          <input
            type="number"
            min={5}
            max={480}
            step={5}
            className="mt-1 w-full rounded border border-border bg-background px-2 py-1.5 text-sm"
            value={duration}
            onChange={(e) => setDuration(Number(e.target.value))}
          />
        </label>
      </div>
      <div className="flex gap-2 justify-end">
        <Button type="button" variant="ghost" size="sm" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" size="sm" disabled={saving}>
          {saving ? "Adding…" : "Add block"}
        </Button>
      </div>
    </form>
  );
}
