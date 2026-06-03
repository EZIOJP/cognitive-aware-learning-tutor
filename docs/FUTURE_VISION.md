# Future Vision

This document captures the long-term Smart Pomodoro Study Companion roadmap.

## Product Thesis

The best consumer-facing version is not "an EEG app." The strongest product idea
is:

```text
An AI study companion that notices when the learner is stuck and gives the right
hint at the right moment.
```

Biometrics are a powerful optional signal. The core product value is timely,
context-aware learning support.

## North Star

Build a closed-loop local learning system:

```text
student writes math
  -> app observes behavior and cognitive load
  -> local AI reads the whiteboard
  -> stuckness score triggers a Socratic hint
  -> session logs improve future hints
```

## Phase 1: Software MVP and Mock Data

Goal: prove the real-time software loop before buying hardware.

Tasks:

- Build or finalize the React canvas and dashboard
- Add a Python UDP spoofer that emits fake high-speed EEG-like samples
- Run FastAPI as the UDP-to-WebSocket router
- Stream alpha/beta/gamma data into the frontend
- Verify Pomodoro and cognitive-load UI react to thresholds

Mock data flow:

```text
Python UDP spoofer
  -> UDP localhost:5005
  -> FastAPI data router
  -> WebSocket ws://localhost:8000/ws/eeg
  -> React dashboard
```

## Phase 2: Vision and Behavioral Tracking

Goal: prove local AI can understand the learner's whiteboard.

Tasks:

- Install Ollama locally
- Pull `llava:7b`
- Send base64 canvas images from React to FastAPI
- Have LLaVA describe the visible math step
- Generate targeted Socratic hints
- Optionally add OpenCV/MediaPipe for blink and face-mesh signals

Desired behavior:

```text
canvas pause + high stuckness score
  -> screenshot canvas
  -> LLaVA reads math
  -> tutor asks a targeted question
```

## Phase 3: Hardware Acquisition and Assembly

Goal: replace mock data with real EXG samples.

Hardware:

- ESP32-S3 board
- BioAmp EXG Pill
- sports sweatband
- dry/snap electrodes
- jumper wires
- Lenovo LOQ laptop for processing

Data flow:

```text
BioAmp EXG Pill
  -> ESP32-S3 ADC at 250 Hz
  -> UDP Wi-Fi packets
  -> FastAPI
  -> FFT
  -> WebSocket
  -> dashboard
```

Firmware note:

If SD-card logging is added, file-scanning and file-writing logic should use the
`DSC` prefix instead of old `test_` prefixes.

## Phase 4: Closed-Loop Tutor and Data Flywheel

Goal: convert sessions into a personal learning dataset.

Tasks:

- Implement stuckness score
- Log session windows to CSV or JSONL
- Store canvas snapshots at key moments
- Store hints given and whether the learner recovered
- Add complaint submission for difficult topics
- Cross-reference complaints with biometric/behavioral logs
- Restructure future hints based on personal learning patterns

Example training/logging record:

```json
{
  "session_id": "local-001",
  "topic": "gradient_descent",
  "canvas_snapshot": "base64-or-file-reference",
  "eeg_window": {
    "alpha": 21.5,
    "beta": 42.1,
    "gamma": 78.4
  },
  "behavior": {
    "canvas_inactive_seconds": 47,
    "eraser_events": 3
  },
  "stuckness_score": 0.86,
  "hint_given": "Which term changes when you take the partial derivative?",
  "learner_recovered": true
}
```

## Stuckness Score Moonshot

Do not depend on gamma alone. A useful score should combine:

- gamma spike relative to personal baseline
- beta/gamma ratio
- canvas inactivity
- repeated erasing
- repeated wrong answers
- long pauses after a step
- Pomodoro fatigue stage
- self-reported confusion

## Consumer Validity Notes

The consumer-valid product is the learning loop, not the hardware novelty.

Recommended product ladder:

1. Software-only stuckness-aware tutor
2. Prosumer biometric learning lab
3. Polished consumer wearable plus tutor ecosystem

Finish the software-only learning value first. Add EEG only after the intervention
loop is useful without hardware.

