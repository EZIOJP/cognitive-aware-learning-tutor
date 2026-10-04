import { useMemo, useState, type ReactNode } from "react";
import { useTheme } from "../../../context/ThemeContext";
import {
  SIDEBAR_STICKER_FONTS,
  SIDEBAR_STICKER_DEFAULTS,
  SIDEBAR_STICKER_LAYER_PRESETS,
  SIDEBAR_STICKER_SCALE_MIN,
  SIDEBAR_STICKER_SCALE_MAX,
  SIDEBAR_STICKER_RINGS_MAX,
  SIDEBAR_STICKER_RINGS_MIN,
  SIDEBAR_STICKER_RADIUS_MIN,
  SIDEBAR_STICKER_RADIUS_MAX,
  addSidebarStickerRing,
  removeSidebarStickerRing,
  updateSidebarStickerRing,
  cloneSidebarStickerLayers,
  type SidebarStickerFontId,
} from "../../../theme/layers";
import { cn } from "../../../app/components/ui/utils";
import { ContourStickerLabel } from "../../theme/ContourStickerLabel";

function FieldLabel({ children }: { children: ReactNode }) {
  return (
    <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
      {children}
    </p>
  );
}

function ColorSwatch({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (c: string) => void;
}) {
  return (
    <label className="flex flex-col items-center gap-1 cursor-pointer group">
      <span className="relative inline-flex h-9 w-9 overflow-hidden rounded-full border border-border/60 shadow-sm ring-offset-2 ring-offset-background group-hover:ring-2 group-hover:ring-sky-500/40">
        <span className="sr-only">{label}</span>
        <input
          type="color"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="absolute inset-0 h-[200%] w-[200%] -translate-x-1/4 -translate-y-1/4 cursor-pointer border-0 p-0"
        />
      </span>
      <span className="text-[9px] text-muted-foreground">{label}</span>
    </label>
  );
}

function EasySlider({
  label,
  hint,
  value,
  min,
  max,
  suffix,
  onChange,
}: {
  label: string;
  hint?: string;
  value: number;
  min: number;
  max: number;
  suffix: string;
  onChange: (n: number) => void;
}) {
  return (
    <div className="space-y-1.5">
      <div className="flex items-baseline justify-between gap-2">
        <div>
          <p className="text-[12px] font-medium text-foreground">{label}</p>
          {hint ? <p className="text-[10px] text-muted-foreground">{hint}</p> : null}
        </div>
        <span className="shrink-0 font-mono text-[12px] tabular-nums text-sky-200/90">
          {value}
          {suffix}
        </span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={1}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full accent-sky-500"
      />
    </div>
  );
}

const FONT_GROUPS: { id: "calligraphy" | "cursive" | "brush"; label: string }[] = [
  { id: "calligraphy", label: "Calligraphy" },
  { id: "cursive", label: "Cursive italic" },
  { id: "brush", label: "Brush" },
];

/** Contour sticker — fonts, dynamic rings, builtin + saved presets. */
export function SidebarTitleStickerPanel() {
  const {
    sidebarStickerFont,
    sidebarStickerScale,
    sidebarStickerCoreFill,
    sidebarStickerLayers,
    sidebarStickerCustomPresets,
    setSidebarStickerFont,
    setSidebarStickerScale,
    setSidebarStickerCoreFill,
    setSidebarStickerLayers,
    applySidebarStickerThemePreset,
    saveSidebarStickerPreset,
    deleteSidebarStickerPreset,
  } = useTheme();

  const [previewText, setPreviewText] = useState("Elegant");
  const [presetId, setPresetId] = useState(SIDEBAR_STICKER_DEFAULTS.presetId);
  const [saveName, setSaveName] = useState("");

  const rings = sidebarStickerLayers.rings;
  const outerRadius = rings[rings.length - 1]?.radius ?? 0;

  const fontCss = useMemo(() => {
    const f = SIDEBAR_STICKER_FONTS.find((x) => x.id === sidebarStickerFont);
    return f?.css ?? '"Great Vibes", cursive';
  }, [sidebarStickerFont]);

  const applyPreset = (id: string) => {
    setPresetId(id);
    applySidebarStickerThemePreset(id);
  };

  const handleSavePreset = () => {
    const id = saveSidebarStickerPreset(saveName || "My sticker");
    if (!id) return;
    setPresetId(id);
    setSaveName("");
  };

  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-[13px] font-semibold text-foreground">Title sticker</h3>
        <p className="text-[11px] text-muted-foreground mt-0.5 leading-relaxed">
          Calligraphy fonts, add or remove contour rings, and save your own presets.
        </p>
      </div>

      <div
        className={cn(
          "sidebar-sticker-preview sticky top-0 z-20 -mx-1 space-y-2 rounded-xl border border-border/50 p-3 shadow-[0_12px_28px_rgba(0,0,0,0.35)]",
        )}
        style={{
          backgroundColor: "rgba(11, 18, 32, 0.96)",
          backgroundImage:
            "linear-gradient(rgba(56,120,200,0.07) 1px, transparent 1px), linear-gradient(90deg, rgba(56,120,200,0.07) 1px, transparent 1px)",
          backgroundSize: "20px 20px",
        }}
      >
        <div className="flex min-h-[5.5rem] items-center justify-center overflow-visible px-0 py-2">
          <ContourStickerLabel
            text={previewText.trim() || "Elegant"}
            fontSizePx={Math.round(36 * (sidebarStickerScale / 100))}
            fontFamily={fontCss}
            fill={sidebarStickerCoreFill}
            variant="live"
          />
        </div>
        <div className="flex flex-wrap items-center justify-between gap-2 border-t border-white/10 pt-2">
          <p className="text-[9px] font-semibold uppercase tracking-[0.16em] text-sky-300/75">
            Live preview
          </p>
          <p className="text-[10px] tabular-nums text-sky-100/75">
            {rings.length} ring{rings.length === 1 ? "" : "s"} · outer {outerRadius}px
          </p>
        </div>
      </div>

      <div className="space-y-1.5">
        <FieldLabel>Preview text</FieldLabel>
        <input
          type="text"
          value={previewText}
          onChange={(e) => setPreviewText(e.target.value)}
          className="w-full rounded-lg border border-border/50 bg-background/40 px-3 py-2 text-[13px] text-foreground outline-none focus:border-primary/50"
          placeholder="Elegant"
        />
      </div>

      <div className="space-y-1.5">
        <FieldLabel>Font</FieldLabel>
        <select
          value={sidebarStickerFont}
          onChange={(e) => setSidebarStickerFont(e.target.value as SidebarStickerFontId)}
          className="w-full rounded-lg border border-border/50 bg-background/40 px-3 py-2 text-[13px] text-foreground outline-none focus:border-primary/50"
        >
          {FONT_GROUPS.map((g) => (
            <optgroup key={g.id} label={g.label}>
              {SIDEBAR_STICKER_FONTS.filter((f) => f.group === g.id).map((f) => (
                <option key={f.id} value={f.id} style={{ fontFamily: f.css }}>
                  {f.label}
                </option>
              ))}
            </optgroup>
          ))}
        </select>
      </div>

      <EasySlider
        label="Title size"
        hint="How large the sticker reads in the sidebar"
        value={sidebarStickerScale}
        min={SIDEBAR_STICKER_SCALE_MIN}
        max={SIDEBAR_STICKER_SCALE_MAX}
        suffix="%"
        onChange={setSidebarStickerScale}
      />

      <div className="space-y-2 rounded-xl border border-border/40 bg-background/25 px-3 py-3">
        <div className="flex items-center justify-between gap-2">
          <FieldLabel>Contour layers</FieldLabel>
          <button
            type="button"
            disabled={rings.length >= SIDEBAR_STICKER_RINGS_MAX}
            className="rounded-md border border-border/50 px-2 py-1 text-[11px] text-foreground hover:bg-background/50 disabled:opacity-40"
            onClick={() => setSidebarStickerLayers(addSidebarStickerRing(sidebarStickerLayers))}
          >
            + Add layer
          </button>
        </div>
        <div className="space-y-3 pt-1">
          {rings.map((ring, index) => (
            <div
              key={`ring-${index}-${ring.radius}`}
              className="space-y-2 rounded-lg border border-white/5 bg-black/20 px-2.5 py-2"
            >
              <div className="flex items-center justify-between gap-2">
                <p className="text-[11px] font-medium text-foreground">
                  Layer {index + 1}
                  <span className="ml-1.5 text-[10px] font-normal text-muted-foreground">
                    {index === 0 ? "inner" : index === rings.length - 1 ? "outer" : "mid"}
                  </span>
                </p>
                <button
                  type="button"
                  disabled={rings.length <= SIDEBAR_STICKER_RINGS_MIN}
                  className="text-[11px] text-rose-300/90 hover:text-rose-200 disabled:opacity-30"
                  onClick={() =>
                    setSidebarStickerLayers(
                      removeSidebarStickerRing(sidebarStickerLayers, index),
                    )
                  }
                >
                  Remove
                </button>
              </div>
              <div className="flex items-end gap-3">
                <div className="min-w-0 flex-1">
                  <EasySlider
                    label="Dilation"
                    value={ring.radius}
                    min={SIDEBAR_STICKER_RADIUS_MIN}
                    max={SIDEBAR_STICKER_RADIUS_MAX}
                    suffix="px"
                    onChange={(n) =>
                      setSidebarStickerLayers(
                        updateSidebarStickerRing(sidebarStickerLayers, index, {
                          radius: n,
                        }),
                      )
                    }
                  />
                </div>
                <ColorSwatch
                  label="Color"
                  value={ring.color}
                  onChange={(c) =>
                    setSidebarStickerLayers(
                      updateSidebarStickerRing(sidebarStickerLayers, index, {
                        color: c,
                      }),
                    )
                  }
                />
              </div>
            </div>
          ))}
        </div>
        <div className="pt-1">
          <ColorSwatch
            label="Core text"
            value={sidebarStickerCoreFill}
            onChange={setSidebarStickerCoreFill}
          />
        </div>
      </div>

      <div className="space-y-2 rounded-xl border border-border/40 bg-background/25 px-3 py-3">
        <FieldLabel>Presets</FieldLabel>
        <select
          value={presetId}
          onChange={(e) => applyPreset(e.target.value)}
          className="w-full rounded-lg border border-border/50 bg-background/40 px-3 py-2 text-[13px] text-foreground outline-none focus:border-primary/50"
        >
          <optgroup label="Built-in">
            {SIDEBAR_STICKER_LAYER_PRESETS.map((p) => (
              <option key={p.id} value={p.id}>
                {p.label}
              </option>
            ))}
          </optgroup>
          {sidebarStickerCustomPresets.length > 0 ? (
            <optgroup label="Saved">
              {sidebarStickerCustomPresets.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.label}
                </option>
              ))}
            </optgroup>
          ) : null}
        </select>

        <div className="flex flex-wrap items-center gap-2 pt-1">
          <input
            type="text"
            value={saveName}
            onChange={(e) => setSaveName(e.target.value)}
            placeholder="Preset name"
            className="min-w-[8rem] flex-1 rounded-lg border border-border/50 bg-background/40 px-3 py-2 text-[13px] text-foreground outline-none focus:border-primary/50"
          />
          <button
            type="button"
            className="rounded-lg border border-sky-500/40 bg-sky-500/15 px-3 py-2 text-[12px] font-medium text-sky-100 hover:bg-sky-500/25"
            onClick={handleSavePreset}
          >
            Save preset
          </button>
        </div>

        {presetId.startsWith("custom-") ? (
          <button
            type="button"
            className="text-[11px] text-rose-300/90 underline hover:text-rose-200"
            onClick={() => {
              deleteSidebarStickerPreset(presetId);
              setPresetId(SIDEBAR_STICKER_DEFAULTS.presetId);
            }}
          >
            Delete saved preset
          </button>
        ) : null}
      </div>

      <button
        type="button"
        className="text-[11px] text-muted-foreground underline hover:text-foreground"
        onClick={() => {
          setSidebarStickerFont(SIDEBAR_STICKER_DEFAULTS.font);
          setSidebarStickerScale(SIDEBAR_STICKER_DEFAULTS.scale);
          setSidebarStickerCoreFill(SIDEBAR_STICKER_DEFAULTS.coreFill);
          setSidebarStickerLayers(
            cloneSidebarStickerLayers(SIDEBAR_STICKER_DEFAULTS.layers),
          );
          setPresetId(SIDEBAR_STICKER_DEFAULTS.presetId);
          setPreviewText("Elegant");
        }}
      >
        Reset to Classic White
      </button>
    </div>
  );
}
