import { Link, useNavigate } from "react-router";
import { useTheme } from "../../context/ThemeContext";
import { ThemeToggle } from "../../components/theme/ThemeToggle";
import { SettingsPageScroll } from "./SettingsPageScroll";
import { Button } from "../../app/components/ui/button";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "../../app/components/ui/accordion";
import { HeroToolkitPreview } from "../../components/hero";
import {
  ALL_THEME_PRESETS,
  BACKGROUND_STYLES,
  BUTTON_STYLES,
  type ThemeEnergy,
  type ThemePreset,
  type ThemePresetGroup,
} from "../../theme/presets";
import {
  TYPOGRAPHY_PACKS,
  SURFACE_STYLES,
  BUTTON_VARIANTS,
  MOTION_LEVELS,
} from "../../theme/layers";

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

export default function ThemeSettingsPage() {
  const navigate = useNavigate();
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
    applyPreset,
    resetStudyDefaults,
  } = useTheme();

  const selectedPreset = ALL_THEME_PRESETS.find((p) => p.id === accentColor);

  const groups = (["basic", "life-clock", "lemillion"] as ThemePresetGroup[]).map(
    (g) => ({
      id: g,
      label: GROUP_LABELS[g],
      presets: ALL_THEME_PRESETS.filter((p) => p.group === g),
    })
  );

  return (
    <SettingsPageScroll className="p-4 md:p-6 max-w-3xl mx-auto pb-16">
      <Link to="/settings" className="text-sm text-primary hover:underline inline-block mb-4">
        ← Settings
      </Link>

      <div className="gloss-panel rounded-2xl p-5 md:p-6 space-y-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-2xl font-bold">Theme Settings</h2>
            <p className="text-sm text-muted-foreground mt-1">
              Color presets apply first. Hero toolkit layers are optional — defaults keep
              the calm study app unchanged.
            </p>
          </div>
          <Button type="button" variant="outline" size="sm" onClick={resetStudyDefaults}>
            Reset study defaults
          </Button>
        </div>

        {isHeroLayersActive ? (
          <p className="text-xs rounded-lg border border-primary/30 bg-primary/5 px-3 py-2 text-muted-foreground">
            Hero layers active. Vocab and math pages stay functional; use Reset if anything
            feels too flashy.
          </p>
        ) : null}

        {selectedPreset?.preferDark && !isDarkMode ? (
          <p className="text-xs rounded-lg border border-border px-3 py-2 text-muted-foreground">
            {selectedPreset.label} is designed for dark mode. Light mode uses a derived palette
            that keeps accent colors readable.
          </p>
        ) : null}

        <div className="flex items-center gap-3">
          <ThemeToggle size="sm" />
          <span className="text-sm text-muted-foreground">Light / dark mode</span>
        </div>

        <Accordion type="multiple" defaultValue={["colors", "toolkit-preview"]}>
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
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
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

              <section>
                <h3 className="text-base font-medium mb-2">Custom accent</h3>
                <div className="flex items-center gap-4">
                  <label className="text-sm font-medium">Hex color</label>
                  <input
                    type="color"
                    aria-label="Custom accent color"
                    value={accentColor.startsWith("#") ? accentColor : "#705d00"}
                    onChange={(e) => setAccentColor(e.target.value)}
                    className="w-10 h-10 rounded cursor-pointer border border-border"
                  />
                  {accentColor.startsWith("#") ? (
                    <span className="text-xs text-muted-foreground font-mono">
                      {accentColor}
                    </span>
                  ) : null}
                </div>
              </section>
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
                  Opt-in comic/chamfer/skew from Stitch toolkit. Default leaves shadcn buttons alone.
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
        </Accordion>

        <Button type="button" onClick={() => navigate(-1)}>
          Back
        </Button>
      </div>
    </SettingsPageScroll>
  );
}
