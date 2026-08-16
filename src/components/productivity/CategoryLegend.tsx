import { CATEGORY_COLORS } from "../../api/plannerClient";
import type { HourSlice } from "./hourSliceTypes";

const LEGEND_ORDER = ["Sleep", "study", "reading", "lecture", "review", "break", "personal", "spiritual"];

type Props = {
  slices: HourSlice[];
};

export function CategoryLegend({ slices }: Props) {
  const present = new Set<string>();
  for (const sl of slices) {
    for (const seg of sl.segments) {
      if (seg.source === "sleep") present.add("Sleep");
      else present.add((seg.category || "Other").toLowerCase());
    }
  }
  if (present.size === 0) return null;

  const items: { label: string; color: string }[] = [];
  for (const key of LEGEND_ORDER) {
    const lookup = key === "Sleep" ? "Sleep" : key.toLowerCase();
    if (!present.has(lookup) && !present.has(key)) continue;
    present.delete(lookup);
    present.delete(key);
    const color =
      key === "Sleep"
        ? "#6366f1"
        : CATEGORY_COLORS[key.toLowerCase()] ?? CATEGORY_COLORS.default;
    items.push({ label: key === "Sleep" ? "Sleep" : key, color });
  }
  for (const extra of [...present].sort()) {
    items.push({
      label: extra,
      color: CATEGORY_COLORS[extra.toLowerCase()] ?? CATEGORY_COLORS.default,
    });
  }

  return (
    <div className="hour-category-legend" title="Category colors for 2D track">
      {items.map((it) => (
        <span key={it.label} className="hour-category-legend-item">
          <span className="hour-category-swatch" style={{ background: it.color }} />
          {it.label}
        </span>
      ))}
    </div>
  );
}
