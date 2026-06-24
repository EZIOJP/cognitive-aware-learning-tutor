import type { FrameReading } from "./useHumanTracker";

const DEBOUNCE_MS = 2000;
const ROLL_WINDOW_MS = 1200;
const ROLL_DELTA = 12;

/** Detect wave via Human gesture flag or rapid head-roll oscillation (no hand model required). */
export class WaveDetector {
  private lastWaveAt = 0;
  private rollSamples: { t: number; roll: number }[] = [];

  reset(): void {
    this.lastWaveAt = 0;
    this.rollSamples = [];
  }

  update(reading: FrameReading, gestureWave: boolean): boolean {
    const now = Date.now();
    if (now - this.lastWaveAt < DEBOUNCE_MS) return false;

    if (gestureWave) {
      this.lastWaveAt = now;
      return true;
    }

    if (!reading.faceDetected) {
      this.rollSamples = [];
      return false;
    }

    this.rollSamples.push({ t: now, roll: reading.roll });
    this.rollSamples = this.rollSamples.filter((s) => now - s.t < ROLL_WINDOW_MS);

    if (this.rollSamples.length < 4) return false;

    let flips = 0;
    for (let i = 1; i < this.rollSamples.length; i++) {
      const d = this.rollSamples[i].roll - this.rollSamples[i - 1].roll;
      if (Math.abs(d) >= ROLL_DELTA) flips++;
    }

    if (flips >= 3) {
      this.lastWaveAt = now;
      this.rollSamples = [];
      return true;
    }
    return false;
  }
}
