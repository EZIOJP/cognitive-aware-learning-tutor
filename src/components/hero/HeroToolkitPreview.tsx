import { useTheme } from "../../context/ThemeContext";
import { HeroButton } from "./HeroButton";
import { HeroPanel } from "./HeroPanel";
import { HeroProgress } from "./HeroProgress";
import { LemillionAssistant } from "./LemillionAssistant";

/** Live preview of Stitch hero toolkit layers in Settings */
export function HeroToolkitPreview() {
  const {
    typographyPack,
    surfaceStyle,
    buttonVariant,
    motionLevel,
    widgets,
    accentColor,
    buttonStyle,
    backgroundStyle,
    radius,
  } = useTheme();

  return (
    <div className="space-y-4">
      <p className="text-xs text-muted-foreground">Hero toolkit preview</p>

      <div className="hero-display text-2xl text-primary hero-text-shadow">
        Hero headline
      </div>
      <p className="hero-body text-sm text-muted-foreground">
        Typography: {typographyPack} · Surface: {surfaceStyle} · Motion:{" "}
        {motionLevel}
      </p>

      <div className="flex flex-wrap gap-2">
        <HeroButton type="button">Power action</HeroButton>
        <HeroButton type="button" variant="outline">
          Outline
        </HeroButton>
        <HeroButton type="button" variant="secondary">
          Secondary
        </HeroButton>
      </div>

      <HeroPanel>
        <p className="hero-headline text-base mb-1">Study card</p>
        <p className="hero-body text-xs text-muted-foreground">
          Preset: {accentColor} · Buttons: {buttonStyle} / {buttonVariant} ·
          Background: {backgroundStyle} · Radius: {radius}
        </p>
        <div className="mt-3">
          <HeroProgress value={72} label="Session progress" />
        </div>
      </HeroPanel>

      {widgets.lemillionAssistant ? (
        <LemillionAssistant message="Toolkit preview — assistant widget enabled." />
      ) : null}

      {widgets.heroProgress ? (
        <HeroProgress value={45} label="Hero progress widget" />
      ) : null}

      <div
        className="hero-swatch rounded-sm text-primary-foreground"
        style={{ background: "var(--primary)" }}
      >
        <span className="text-xs">Primary</span>
        <span className="text-[10px] opacity-80">Swatch</span>
      </div>
    </div>
  );
}
