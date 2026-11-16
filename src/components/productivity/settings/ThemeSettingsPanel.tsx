/**
 * Theme / UI controls — used by Study ThemeSettingsPage and Focus Settings → Appearance.
 */
import { useTheme } from "../../../context/ThemeContext";
import { ThemeToggle } from "../../theme/ThemeToggle";
import { Button } from "../../../app/components/ui/button";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "../../../app/components/ui/accordion";
import { HeroToolkitPreview } from "../../hero";
import {
  ALL_THEME_PRESETS,
  BACKGROUND_STYLES,
  BUTTON_STYLES,
  type ThemeEnergy,
  type ThemePreset,
  type ThemePresetGroup,
} from "../../../theme/presets";
import {
  TYPOGRAPHY_PACKS,
  SURFACE_STYLES,
  BUTTON_VARIANTS,
  MOTION_LEVELS,
  TOPBAR_TITLE_STYLES,
  TOPBAR_TITLE_FONTS,
  TOPBAR_TITLE_SIZES,
} from "../../../theme/layers";
import { isFocusDesktopShell } from "../../../utils/focusDesktopShell";

const RADIUS_OPTIONS = [
  { label: "Small", value: "sm" },
  { label: "Medium", value: "md" },
  { label: "Large", value: "lg" },
  { label: "XL", value: "xl" },
];

const GROUP_LABELS: Record<ThemePresetGroup, string> = {
  basic: "Basic accents",
  "life-clock": "Life Clock (Stitch)",
  lemillion: "Lemillion hero themes",
  "study-hub": "Study Hub",
};

const ENERGY_LABEL: Record<ThemeEnergy, string> = {
  calm: "Calm",
  moderate: "Moderate",
  intense: "Intense",
};

const ENERGY_CLASS: Record<ThemeEnergy, string> = {
  calm: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300",
  moderate: "bg-amber-500/15 text-amber-800 dark:text-amber-200",
  intense: "bg-rose-500/15 text-rose-700 dark:text-rose-300",
};

function PresetCard({
  preset,
  selected,
  onSelect,
}: {
  preset: ThemePreset;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className={`text-left rounded-xl border overflow-hidden transition-all hover:border-primary/50 ${
        selected ? "border-2 border-primary ring-2 ring-primary/20" : "border-border"
      }`}
    >
      {preset.preview ? (
        <div className="aspect-video w-full bg-muted overflow-hidden">
          <img
            src={preset.preview}
            alt=""
            className="w-full h-full object-cover object-top"
            loading="lazy"
          />
        </div>
      ) : (
        <div
          className="aspect-video w-full flex items-center justify-center text-2xl font-bold bg-muted text-primary"
          aria-hidden
        >
          Aa
        </div>
      )}
      <div className="p-2.5 space-y-1">
        <div className="flex items-center justify-between gap-1">
          <span className="text-sm font-medium leading-tight">{preset.label}</span>
          {preset.energy ? (
            <span
              className={`text-[10px] px-1.5 py-0.5 rounded-full shrink-0 ${ENERGY_CLASS[preset.energy]}`}
            >
              {ENERGY_LABEL[preset.energy]}
            </span>
          ) : null}
        </div>
        {preset.hint ? (
          <p className="text-[10px] text-muted-foreground leading-snug">{preset.hint}</p>
        ) : null}
      </div>
    </button>
  );
}

function LayerOptionGrid<T extends string>({
  options,
  value,
  onChange,
}: {
  options: { id: T; label: string; hint?: string }[];
  value: T;
  onChange: (id: T) => void;
}) {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
      {options.map((opt) => (
        <button
          key={opt.id}
          type="button"
          className={`p-2.5 rounded-lg border text-left text-sm ${
            value === opt.id ? "border-2 border-primary" : "border-border"
          }`}
          onClick={() => onChange(opt.id)}
        >
          <span className="font-medium block">{opt.label}</span>
          {opt.hint ? (
            <span className="text-[10px] text-muted-foreground">{opt.hint}</span>
          ) : null}
        </button>
      ))}
    </div>
  );
}

export type ThemeSettingsPanelProps = {
  /** Focus Settings embed — skip Study-only chrome / widgets. */
  embedded?: boolean;
};

export function ThemeSettingsPanel({ embedded = false }: ThemeSettingsPanelProps) {
  const focusShell = isFocusDesktopShell() || embedded;
  const {
    isDarkMode,
    accentColor,
    radius,
    intensity,
    buttonStyle,
    backgroundStyle,
    typographyPack,
    surfaceStyle,
    buttonVariant,
    motionLevel,
    widgets,
    topbarTitleStyle,
    topbarTitleFont,
    topbarTitleSize,
    isHeroLayersActive,
    setAccentColor,
    setRadius,
    setIntensity,
    setButtonStyle,
    setBackgroundStyle,
    setTypographyPack,
    setSurfaceStyle,
    setButtonVariant,
    setMotionLevel,
    toggleWidget,
    setTopbarTitleStyle,
    setTopbarTitleFont,
    setTopbarTitleSize,
    applyPreset,
    resetStudyDefaults,
  } = useTheme();

  const selectedPreset = ALL_THEME_PRESETS.find((p) => p.id === accentColor);

  const groupIds: ThemePresetGroup[] = focusShell
    ? ["basic", "life-clock", "lemillion"]
    : ["basic", "life-clock", "lemillion"];

  const groups = groupIds.map((g) => ({
    id: g,
    label: GROUP_LABELS[g],
    presets: ALL_THEME_PRESETS.filter((p) => p.group === g),
  }));

  return (
    <div className="space-y-5">
      <section className="gloss-panel rounded-2xl border border-border/50 p-4 md:p-5 space-y-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="text-[15px] font-semibold text-foreground">Theme & UI</h3>
            <p className="mt-1 text-[13px] leading-relaxed text-muted-foreground max-w-2xl">
              {focusShell
                ? "Light / dark, color presets, surfaces, type, and motion. Sidebar title look is below."
                : "Color presets apply first. Hero toolkit layers are optional."}
            </p>
          </div>
          <Button type="button" variant="outline" size="sm" onClick={resetStudyDefaults}>
            {focusShell ? "Reset defaults" : "Reset study defaults"}
          </Button>
        </div>

        <div className="grid gap-3 md:grid-cols-2">
          {isHeroLayersActive && !focusShell ? (
            <p className="text-xs rounded-xl border border-primary/30 bg-primary/5 px-3 py-2 text-muted-foreground">
              Hero layers active. Use Reset if anything feels too flashy.
            </p>
          ) : null}
          {selectedPreset?.preferDark && !isDarkMode ? (
            <p className="text-xs rounded-xl border border-border px-3 py-2 text-muted-foreground">
              {selectedPreset.label} is designed for dark mode. Light mode uses a derived palette.
            </p>
          ) : null}
        </div>
      </section>

      <div className="grid gap-5 xl:grid-cols-[minmax(16rem,0.7fr)_minmax(0,1.6fr)]">
        <aside className="space-y-4">
          <section className="gloss-panel rounded-2xl border border-border/50 p-4 space-y-3">
            <div>
              <h4 className="text-sm font-semibold">Live mode</h4>
              <p className="text-xs text-muted-foreground">Switch light / dark. Long-press the toggle opens this page.</p>
            </div>
            <div className="flex items-center gap-4 rounded-xl border border-border/50 bg-background/35 p-3">
              <ThemeToggle size="md" />
              <div>
                <p className="text-sm font-medium">{isDarkMode ? "Dark" : "Light"}</p>
                <p className="text-xs text-muted-foreground">Click to toggle</p>
              </div>
            </div>
            {!focusShell ? (
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => window.dispatchEvent(new Event("theme-toggle:meteor-pass"))}
              >
                Preview meteor pass
              </Button>
            ) : null}
          </section>

          <section className="gloss-panel rounded-2xl border border-border/50 p-4 space-y-3">
            <div>
              <h4 className="text-sm font-semibold">Custom accent</h4>
              <p className="text-xs text-muted-foreground">Use after picking a preset.</p>
            </div>
            <div className="flex items-center gap-4">
              <input
                type="color"
                aria-label="Custom accent color"
                value={accentColor.startsWith("#") ? accentColor : "#705d00"}
                onChange={(e) => setAccentColor(e.target.value)}
                className="w-12 h-12 rounded-xl cursor-pointer border border-border bg-background"
              />
              <div>
                <p className="text-sm font-medium">Hex color</p>
                <p className="text-xs text-muted-foreground font-mono">
                  {accentColor.startsWith("#") ? accentColor : "Preset accent"}
                </p>
              </div>
            </div>
          </section>
        </aside>

        <div className="gloss-panel rounded-2xl border border-border/50 p-4 md:p-5">
          <Accordion
            type="multiple"
            defaultValue={["colors", "surfaces", "typography"]}
          >
            <AccordionItem value="colors">
              <AccordionTrigger>Color presets</AccordionTrigger>
              <AccordionContent className="space-y-6 pt-2">
                {groups.map((group) => (
                  <section key={group.id}>
                    <h3 className="text-base font-medium mb-1">{group.label}</h3>
                    {group.id === "lemillion" ? (
                      <p className="text-xs text-muted-foreground mb-3">
                        Heroic Spotlight keeps study typography. High-Velocity & Pro add motion.
                      </p>
                    ) : null}
                    <div className="grid grid-cols-1 sm:grid-cols-2 2xl:grid-cols-3 gap-3">
                      {group.presets.map((preset) => (
                        <PresetCard
                          key={preset.id}
                          preset={preset}
                          selected={accentColor === preset.id}
                          onSelect={() => applyPreset(preset.id)}
                        />
                      ))}
                    </div>
                  </section>
                ))}
              </AccordionContent>
            </AccordionItem>

            <AccordionItem value="surfaces">
              <AccordionTrigger>Surfaces & buttons</AccordionTrigger>
              <AccordionContent className="space-y-5 pt-2">
                <section>
                  <h3 className="text-sm font-medium mb-1">App button style</h3>
                  <LayerOptionGrid
                    options={BUTTON_STYLES}
                    value={buttonStyle}
                    onChange={setButtonStyle}
                  />
                </section>
                <section>
                  <h3 className="text-sm font-medium mb-1">Hero button variant</h3>
                  <p className="text-xs text-muted-foreground mb-2">
                    Opt-in comic/chamfer/skew. Default leaves buttons alone.
                  </p>
                  <LayerOptionGrid
                    options={BUTTON_VARIANTS}
                    value={buttonVariant}
                    onChange={setButtonVariant}
                  />
                </section>
                <section>
                  <h3 className="text-sm font-medium mb-1">Surface style</h3>
                  <LayerOptionGrid
                    options={SURFACE_STYLES}
                    value={surfaceStyle}
                    onChange={setSurfaceStyle}
                  />
                </section>
                <section>
                  <h3 className="text-sm font-medium mb-1">Background texture</h3>
                  <LayerOptionGrid
                    options={BACKGROUND_STYLES}
                    value={backgroundStyle}
                    onChange={setBackgroundStyle}
                  />
                </section>
              </AccordionContent>
            </AccordionItem>

            <AccordionItem value="typography">
              <AccordionTrigger>Typography & motion</AccordionTrigger>
              <AccordionContent className="space-y-5 pt-2">
                <section>
                  <h3 className="text-sm font-medium mb-1">Typography pack</h3>
                  <LayerOptionGrid
                    options={TYPOGRAPHY_PACKS}
                    value={typographyPack}
                    onChange={setTypographyPack}
                  />
                </section>
                <section>
                  <h3 className="text-sm font-medium mb-1">Top bar title</h3>
                  <div className="space-y-3">
                    <div>
                      <p className="text-[11px] text-muted-foreground mb-1">Look</p>
                      <LayerOptionGrid
                        options={TOPBAR_TITLE_STYLES}
                        value={topbarTitleStyle}
                        onChange={setTopbarTitleStyle}
                      />
                    </div>
                    <div>
                      <p className="text-[11px] text-muted-foreground mb-1">Font</p>
                      <LayerOptionGrid
                        options={TOPBAR_TITLE_FONTS}
                        value={topbarTitleFont}
                        onChange={setTopbarTitleFont}
                      />
                    </div>
                    <div>
                      <p className="text-[11px] text-muted-foreground mb-1">Size</p>
                      <LayerOptionGrid
                        options={TOPBAR_TITLE_SIZES}
                        value={topbarTitleSize}
                        onChange={setTopbarTitleSize}
                      />
                    </div>
                  </div>
                </section>
                <section>
                  <h3 className="text-sm font-medium mb-1">Motion level</h3>
                  <LayerOptionGrid
                    options={MOTION_LEVELS}
                    value={motionLevel}
                    onChange={setMotionLevel}
                  />
                </section>
                <section>
                  <h3 className="text-sm font-medium mb-2">Corner radius</h3>
                  <div className="grid grid-cols-4 gap-2">
                    {RADIUS_OPTIONS.map((opt) => (
                      <button
                        key={opt.value}
                        type="button"
                        className={`p-2 rounded-lg border text-sm ${
                          radius === opt.value ? "border-2 border-primary" : "border-border"
                        }`}
                        onClick={() => setRadius(opt.value)}
                      >
                        {opt.label}
                      </button>
                    ))}
                  </div>
                </section>
                <section>
                  <h3 className="text-sm font-medium mb-2">Mode intensity</h3>
                  <input
                    type="range"
                    aria-label="Mode intensity"
                    min={0}
                    max={100}
                    value={intensity}
                    onChange={(e) => setIntensity(Number(e.target.value))}
                    className="w-full accent-primary"
                  />
                  <div className="flex justify-between text-xs text-muted-foreground mt-1">
                    <span>Lighter</span>
                    <span>Darker</span>
                  </div>
                </section>
              </AccordionContent>
            </AccordionItem>

            {!focusShell ? (
              <>
                <AccordionItem value="widgets">
                  <AccordionTrigger>Dashboard widgets</AccordionTrigger>
                  <AccordionContent className="space-y-3 pt-2">
                    <p className="text-xs text-muted-foreground">
                      Optional hero widgets on the home dashboard only.
                    </p>
                    <label className="flex items-center gap-3 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={widgets.lemillionAssistant}
                        onChange={() => toggleWidget("lemillionAssistant")}
                        className="accent-primary"
                      />
                      <span className="text-sm">Lemillion assistant bubble</span>
                    </label>
                    <label className="flex items-center gap-3 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={widgets.heroProgress}
                        onChange={() => toggleWidget("heroProgress")}
                        className="accent-primary"
                      />
                      <span className="text-sm">Hero progress bar</span>
                    </label>
                  </AccordionContent>
                </AccordionItem>

                <AccordionItem value="toolkit-preview">
                  <AccordionTrigger>Toolkit live preview</AccordionTrigger>
                  <AccordionContent>
                    <div className="gloss-panel rounded-xl p-4 border border-border/40 mt-2">
                      <HeroToolkitPreview />
                    </div>
                  </AccordionContent>
                </AccordionItem>
              </>
            ) : null}
          </Accordion>
        </div>
      </div>
    </div>
  );
}

export default ThemeSettingsPanel;
