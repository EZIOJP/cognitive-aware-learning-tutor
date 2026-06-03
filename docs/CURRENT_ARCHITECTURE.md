# Current Architecture

This document describes what exists in the project today.

## App Summary

The app is a local React study dashboard with two major study areas:

- GRE Vocabulary
- Math Tutor / Smart Pomodoro prototype

The application is currently frontend-first. Most GRE vocabulary progress is kept
in browser `localStorage`. EEG/cognitive-load data is simulated in the frontend by
default.

## Frontend Stack

- Vite 6
- React 18
- TypeScript-flavored TSX
- React Router
- Tailwind CSS 4
- Radix UI primitives
- shadcn-style local UI components
- lucide-react icons
- Recharts for charts
- react-sketch-canvas for the math whiteboard
- motion for animation

## Frontend Entry Points

```text
src/main.tsx
src/app/App.tsx
src/layout/AppShell.tsx
```

`src/app/App.tsx` defines the app routes:

```text
/                       Study Hub
/math-tutor             Math Tutor prototype
/gre-vocab              GRE Vocabulary hub
/gre-vocab/read         Vocab read mode
/gre-vocab/read/:mode   Filtered read modes
/gre-vocab/cycle        Vocab cycle manager
/settings/theme         Theme settings
```

## Global Providers

```text
src/context/ThemeContext.tsx
src/context/StudySessionContext.tsx
```

`StudySessionContext` owns:

- simulated biometric data
- cognitive load state
- connection state
- canvas image state
- intervention visibility state
- session diagnostics summary

Important config:

```text
src/config.ts
```

Current default:

```ts
config.dev.useSimulatedData = true
config.intervention.enabled = false
config.intervention.autoTrigger = false
```

## GRE Vocabulary Architecture

Main pages:

```text
src/pages/GreVocabPage.tsx
src/pages/vocab/VocabReadPage.tsx
src/pages/vocab/VocabCyclePage.tsx
```

Core vocab logic:

```text
src/features/vocab/store/vocabStore.ts
src/features/vocab/cycle/cycleService.ts
src/features/vocab/components/read/ReadMode.tsx
src/features/vocab/cycle/components/CycleManager.tsx
```

Data source:

```text
public/data/words.json
```

Progress storage:

```text
localStorage key: vocab:user-progress
localStorage key: vocab:group-progress
```

The vocab module dynamically assigns `group_number` values at 30 words per group.

## Math Tutor Architecture

Main page:

```text
src/pages/MathTutorPage.tsx
```

Components:

```text
src/app/components/MathWhiteboard.tsx
src/app/components/PomodoroTimer.tsx
src/app/components/BiometricMonitor.tsx
src/app/components/AITutorIntervention.tsx
src/app/components/PostSessionDiagnostics.tsx
```

Top-bar docks:

```text
src/layout/topbar/PomodoroDock.tsx
src/layout/topbar/BrainActivityDock.tsx
src/layout/topbar/CognitiveLoadDock.tsx
```

Note: `AITutorIntervention` exists, but the intervention UI still needs to be
mounted into the visible app flow before automatic interventions can be seen.

## Backend Reference Architecture

Reference backend:

```text
backend_example.py
```

It demonstrates:

- UDP listener on port `5005`
- raw EEG buffer
- FFT band extraction with SciPy/NumPy
- WebSocket endpoint at `/ws/eeg`
- intervention endpoint at `/api/intervention`
- session logging endpoint at `/api/log-session`
- health endpoint at `/health`

Reference vocab backend:

```text
vocab_backend.py
```

It provides a lightweight non-Django FastAPI vocab API that mirrors some older
vocab app endpoints.

## Current Data Flow

Default frontend-only mode:

```text
StudySessionContext simulated data
  -> biometricData[]
  -> top-bar EEG display
  -> cognitive load chip
  -> diagnostics prototype
```

Reference real-data mode:

```text
ESP32-S3 or UDP spoofer
  -> UDP port 5005
  -> backend_example.py
  -> FFT alpha/beta/gamma
  -> WebSocket /ws/eeg
  -> React dashboard
```

## Current Build Status

The frontend builds with:

```bat
npm.cmd run build
```

Vite may warn that the main JavaScript chunk is larger than 500 kB. That is a
performance warning, not a build failure.

