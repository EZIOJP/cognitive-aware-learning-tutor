import { useState } from "react";
import { Link } from "react-router";
import { Settings2, Palette, Puzzle, Sun, Moon } from "lucide-react";
import { ThemeToggle } from "../../components/theme/ThemeToggle";
import { Card } from "../../app/components/ui/card";
import { Button } from "../../app/components/ui/button";
import { SettingsPageScroll } from "./SettingsPageScroll";

const VARIANT_KEY = "themeToggleVariant";

type ToggleVariant = "animated" | "compact";

function readVariant(): ToggleVariant {
  const v = localStorage.getItem(VARIANT_KEY);
  return v === "compact" ? "compact" : "animated";
}

export default function SettingsHubPage() {
  const [variant, setVariantState] = useState<ToggleVariant>(readVariant);

  const setVariant = (v: ToggleVariant) => {
    localStorage.setItem(VARIANT_KEY, v);
    setVariantState(v);
    window.dispatchEvent(new Event("theme-toggle-variant"));
  };

  return (
    <SettingsPageScroll className="p-6 max-w-lg mx-auto space-y-6">
      <div className="flex items-center gap-2">
        <Settings2 className="w-6 h-6" />
        <h1 className="text-2xl font-semibold">Settings</h1>
      </div>

      <Card className="gloss-panel p-5 space-y-4">
        <div className="flex items-center gap-2">
          <Palette className="w-5 h-5" />
          <h2 className="font-medium">Appearance</h2>
        </div>
        <p className="text-sm text-muted-foreground">
          Tap the control to switch light / dark. Icons animate between sun and moon.
        </p>
        <div className="flex items-center gap-4">
          <ThemeToggle size="md" variant={variant} />
          <span className="text-sm text-muted-foreground">Live preview</span>
        </div>
        <div>
          <p className="text-sm font-medium mb-2">Toggle style</p>
          <div className="flex gap-2">
            <Button
              type="button"
              variant={variant === "animated" ? "default" : "outline"}
              size="sm"
              onClick={() => setVariant("animated")}
            >
              <Sun className="w-4 h-4 mr-1" />
              Animated sky
            </Button>
            <Button
              type="button"
              variant={variant === "compact" ? "default" : "outline"}
              size="sm"
              onClick={() => setVariant("compact")}
            >
              <Moon className="w-4 h-4 mr-1" />
              Compact slider
            </Button>
          </div>
          <p className="text-xs text-muted-foreground mt-2">
            Top bar uses your chosen style after refresh.
          </p>
        </div>
        <Link
          to="/settings/theme"
          className="text-sm text-primary hover:underline inline-block"
        >
          Advanced theme (accent, radius, intensity) →
        </Link>
      </Card>

      <Card className="gloss-panel p-5">
        <div className="flex items-center gap-2 mb-2">
          <Puzzle className="w-5 h-5" />
          <h2 className="font-medium">Plugins</h2>
        </div>
        <p className="text-sm text-muted-foreground mb-3">
          Enable or disable study modules.
        </p>
        <div className="flex flex-col gap-1">
          <Link to="/settings/plugins" className="text-sm text-primary hover:underline">
            Manage plugins →
          </Link>
          <Link to="/settings/features" className="text-sm text-primary hover:underline">
            Feature Studio (custom metrics) →
          </Link>
        </div>
      </Card>
    </SettingsPageScroll>
  );
}
