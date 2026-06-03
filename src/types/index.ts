/**
 * Type definitions for the EEG AI Math Tutor
 * These types define the unified payload structure that combines
 * biometric data with canvas state for AI analysis
 */

export interface BiometricData {
  alpha: number; // Alpha wave power (8-13 Hz) - Relaxed state
  beta: number; // Beta wave power (13-30 Hz) - Focused state
  gamma: number; // Gamma wave power (30-100 Hz) - High cognitive load
  timestamp: number; // Unix timestamp in milliseconds
}

export interface CanvasState {
  imageData: string; // Base64 encoded PNG of the canvas
  lastUpdateTime: number; // Unix timestamp of last drawing activity
  strokeCount?: number; // Optional: number of strokes drawn
}

export interface UnifiedPayload {
  biometric: BiometricData;
  canvas: CanvasState;
  session: {
    sessionId: string;
    startTime: number;
    interventionCount: number;
  };
  timestamp: number;
}

export interface AIIntervention {
  message: string; // AI's observation about where the student is stuck
  question: string; // Targeted question to guide the student
  detectedConcept: string; // Math concept being worked on
  confidence?: number; // Optional: AI's confidence in the detection (0-1)
  suggestedResources?: string[]; // Optional: links to helpful resources
}

export interface StressPoint {
  concept: string; // Math concept that caused stress
  stressLevel: number; // 0-100 scale
  timestamp: string; // ISO timestamp
  duration?: number; // How long the stress lasted (seconds)
}

export interface SessionSummary {
  duration: number; // Session duration in seconds
  totalProblems: number; // Number of problems attempted
  interventions: number; // Number of AI interventions
  stressPoints: StressPoint[]; // Moments of high cognitive load
  overallPerformance: "excellent" | "good" | "needs-improvement";
  avgCognitiveLoad?: number; // Average cognitive load throughout session
  peakStressTime?: number; // Timestamp of highest stress
}

export interface ConnectionState {
  isConnected: boolean;
  deviceName: string;
  sampleRate: number; // Hz
  lastPacketTime?: number; // Unix timestamp of last received packet
  packetLoss?: number; // Percentage of packet loss (0-100)
}

export type CognitiveLoad = "low" | "medium" | "high";

/**
 * WebSocket message types for communication with FastAPI backend
 */
export interface WSMessage {
  type: "eeg_data" | "intervention_request" | "session_summary";
  payload: any;
}

export interface EEGDataMessage extends WSMessage {
  type: "eeg_data";
  payload: BiometricData;
}

export interface InterventionRequestMessage extends WSMessage {
  type: "intervention_request";
  payload: {
    canvasImage: string;
    biometricData: BiometricData;
  };
}

export interface SessionSummaryMessage extends WSMessage {
  type: "session_summary";
  payload: SessionSummary;
}
