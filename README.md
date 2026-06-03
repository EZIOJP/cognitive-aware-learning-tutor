# Cognitive-Aware Learning Tutor

A local-first, premium study companion for GRE vocabulary, math practice, Pomodoro sessions, and future cognitive-load-aware AI tutoring. It integrates biometric feed analysis, deep browser behavior tracking, and health metrics to provide a comprehensive, closed-loop learning dashboard.

The long-term vision is a unified, intelligent study space that detects cognitive states (focus, stress, overload, fatigue) and dynamically adapts to optimize human learning efficiency:

```text
student work + behavior + biometric signals -> cognitive state classification -> real-time tutor adjustments / adaptive recommendations -> optimized learning outcome
```

---

## 🚀 What Works Now (Current Version Changes)

### 💻 Frontend & Dashboard UI
- **Draggable & Persisted Dashboard Layout:** The homepage features draggable widget cards (Study Time, Vocab Progress, AI Reviews, Community, Browser Activity, and Life Score) whose arrangement is saved in `localStorage`.
- **Advanced Theme Settings:** Upgraded settings page allowing users to customize hex accent colors, select background theme styles, and control dark/light mode intensity (contrast level).
- **Life Tracker Dashboard & Page:** A dedicated health & wellness tracking suite (accessible via the ❤️ sidebar icon) assessing four pillars:
  - **Health:** Sleep hours/quality, exercise, water, healthy meals.
  - **Productivity:** Study minutes, tasks completed, deep work blocks.
  - **Digital Wellbeing:** Screen time, social media usage, outdoor time.
  - **Mental:** Mood score, stress levels, meditation time.
  - Generates a composite **Life Score (0-100)** and logs historical trend lines over a 7-day period.

### 🔌 Chrome SelfTracker Extension
- **Real-Time Data Streaming:** Built-in auto-reconnecting WebSocket connection to the local backend.
- **Deep Scrapers:**
  - **YouTube Deep Scrape:** Extracts video metadata, channels, playlist completions, chapter selections, real-time duration milestones (25%, 50%, 75%), and applies learning vs. leisure heuristics.
  - **Scalar Deep Scrape:** Collects current section/chapter, sidebar navigation progression, remaining page items, code-block presence, and computes estimated reading minutes left on the current document.
  - **Heuristic Idle & Active Tracker:** Tracks cursor velocity, clicks, keystroke count, and scrolls to flag active, skimming, reading, writing, or passive watching sessions.

### ⚙️ Backend Data Pipelines
- **FastAPI Integration Backend (`vocab_backend.py`):**
  - **Behavioral WS Feed:** Processes payloads from the browser extension and saves logs in daily CSV formats (`data_logs/DSC_browser_behavior_*.csv`).
  - **Aggregated Analytics API:** Calculates active domains, top categories, average daily productivity percentages, and event summaries.
  - **Local Ollama AI Integration:** Classifies raw scrapings using a local LLM (`llama3`), featuring a graceful timeout fallback to heuristic classifiers if local server instances are unavailable or slow.

---

## 🔮 Future Vision

The future roadmap for the Cognitive-Aware Learning Tutor includes:

1. **EEG Hardware Integration:** 
   - Connecting real-time EEG (Alpha/Beta/Gamma bands) using ESP32-S3 and BioAmp EXG sensors.
   - Processing EEG data over UDP into FFT power bands to compute active engagement and cognitive workload scores.
2. **Close-Loop AI Tutoring:** 
   - Deploying locally-hosted vision models (LLaVA/Ollama) to inspect math canvas workspaces.
   - Offering non-intrusive, interactive tips whenever "stuckness" is detected from joint behavioral, facial, and EEG streams.
3. **Advanced Biometric Diagnostics:**
   - Post-session summary reports highlighting physical fatigue against task completion performance.

---

## 📁 Project Structure & Docs

- AI coding rules: `.cursor/rules/` (Cursor agent context)
- File kernel: `AGENTS.md`, `docs/PROJECT_LAYOUT.md`, `docs/FILE_MAP.md`, `docs/SESSION_LOG.md`
- [Documentation index](docs/README.md)
- [Current Architecture](docs/CURRENT_ARCHITECTURE.md)
- [Future Vision](docs/FUTURE_VISION.md)
- [Setup, Dependencies, and Commands](docs/SETUP_AND_COMMANDS.md)
- [Original Integration Guide](docs/INTEGRATION_GUIDE.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)

---

## ⚙️ Quick Start

### 1. Start the app

```bat
run.bat
```

First run installs Python + npm deps automatically. Opens vocab API (8000) and frontend (5173).

Frontend only:

```bat
scripts\run_frontend.bat
```

Visit: `http://localhost:5173`

### 2. Backend only

```bat
scripts\run_backend.bat
```

After dependency changes:

```bat
scripts\setup.bat
```

### 3. Chrome SelfTracker Extension Installation
1. Navigate to `chrome://extensions` in your Google Chrome browser.
2. Toggle on **Developer Mode** (top-right corner).
3. Click **Load unpacked** (top-left corner).
4. Select the `selftracker-extension` directory from this project root.
