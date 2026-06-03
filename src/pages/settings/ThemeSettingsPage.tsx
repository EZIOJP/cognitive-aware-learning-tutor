import React from "react";
import { Link, useNavigate } from "react-router";
import { useTheme } from "../../context/ThemeContext";
import { ThemeToggle } from "../../components/theme/ThemeToggle";

const ACCENT_OPTIONS = [
  { label: "Default", value: "default" },
  { label: "Midnight Amber", value: "midnight-amber", hint: "Stitch Life Clock theme" },
  { label: "Oceanic Aurora", value: "oceanic-aurora", hint: "Stitch teal life clock" },
  { label: "Emerald", value: "emerald" },
  { label: "Violet", value: "violet" },
  { label: "Rose", value: "rose" },
  { label: "Amber", value: "amber" },
];

const RADIUS_OPTIONS = [
  { label: "Small", value: "sm" },
  { label: "Medium", value: "md" },
  { label: "Large", value: "lg" },
  { label: "Extra Large", value: "xl" },
];

export default function ThemeSettingsPage() {
  const navigate = useNavigate();
  const { accentColor, radius, intensity, setAccentColor, setRadius, setIntensity } = useTheme();

  const handleBack = () => navigate(-1);

  return (
    <div className="p-6 max-w-lg mx-auto space-y-4">
      <Link to="/settings" className="text-sm text-primary hover:underline inline-block">
        ← Settings
      </Link>
      <div className="gloss-panel rounded-2xl p-6 space-y-6">
      <div>
        <h2 className="text-2xl font-bold">Theme Settings</h2>
        <p className="text-sm text-muted-foreground mt-1">
          Customize appearance — maps to your saved theme tokens
        </p>
      </div>
      <div className="flex items-center gap-3 mb-6">
        <ThemeToggle size="sm" />
        <span className="text-sm text-muted-foreground">Quick light / dark</span>
      </div>
      <section className="mb-6">
        <h3 className="text-lg font-medium mb-2">Accent Color</h3>
        <div className="grid grid-cols-3 gap-2 mb-4">
          {ACCENT_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              type="button"
              className={`p-2 rounded border text-left ${accentColor === opt.value ? "border-2 border-primary" : "border"}`}
              onClick={() => setAccentColor(opt.value)}
            >
              <span className="block font-medium">{opt.label}</span>
              {"hint" in opt && opt.hint ? (
                <span className="block text-[10px] text-muted-foreground mt-0.5">{opt.hint}</span>
              ) : null}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-4">
          <label className="text-sm font-medium">Custom Color:</label>
          <input 
            type="color" 
            value={accentColor.startsWith("#") ? accentColor : "#10b981"} 
            onChange={(e) => setAccentColor(e.target.value)} 
            className="w-10 h-10 rounded cursor-pointer"
          />
        </div>
      </section>
      
      <section className="mb-6">
        <h3 className="text-lg font-medium mb-2">Mode Intensity (Darkness/Lightness)</h3>
        <input 
          type="range" 
          min="0" 
          max="100" 
          value={intensity} 
          onChange={(e) => setIntensity(Number(e.target.value))}
          className="w-full accent-primary"
        />
        <div className="flex justify-between text-xs text-muted-foreground mt-1">
          <span>Lighter</span>
          <span>Darker</span>
        </div>
      </section>
      <section className="mb-6">
        <h3 className="text-lg font-medium mb-2">Corner Radius</h3>
        <div className="grid grid-cols-4 gap-2">
          {RADIUS_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              className={`p-2 rounded border ${radius === opt.value ? "border-2 border-primary" : "border"}`}
              onClick={() => setRadius(opt.value)}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </section>
      <div className="gloss-panel rounded-xl p-4 border border-border/40">
        <p className="text-xs text-muted-foreground mb-2">Preview</p>
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-primary/20 flex items-center justify-center text-sm font-semibold">
            Aa
          </div>
          <div>
            <p className="text-sm font-medium">Study Hub card</p>
            <p className="text-xs text-muted-foreground">Accent & radius apply globally</p>
          </div>
        </div>
      </div>
      <button
        type="button"
        className="px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium"
        onClick={handleBack}
      >
        Back
      </button>
      </div>
    </div>
  );
}
