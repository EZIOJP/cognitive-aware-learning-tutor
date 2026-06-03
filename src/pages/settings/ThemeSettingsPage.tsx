import React from "react";
import { Link, useNavigate } from "react-router";
import { useTheme } from "../../context/ThemeContext";
import { ThemeToggle } from "../../components/theme/ThemeToggle";

const ACCENT_OPTIONS = [
  { label: "Default", value: "default" },
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
    <div className="p-6 max-w-md mx-auto">
      <Link to="/settings" className="text-sm text-primary hover:underline mb-2 inline-block">
        ← Settings
      </Link>
      <h2 className="text-2xl font-bold mb-4">Theme Settings</h2>
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
              className={`p-2 rounded border ${accentColor === opt.value ? "border-2 border-primary" : "border"}`}
              onClick={() => setAccentColor(opt.value)}
            >
              {opt.label}
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
      <button
        className="mt-4 px-4 py-2 bg-primary text-primary-foreground rounded"
        onClick={handleBack}
      >
        Back
      </button>
    </div>
  );
}
