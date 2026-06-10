import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  useRef,
  type ReactNode,
} from "react";
import type { BiometricData, CognitiveLoad } from "../types";
import { config } from "../config";
import { usePlugins } from "../plugins/registry";
import { useAuth } from "./AuthContext";
import { postHubReading } from "../api/hubClient";
import { patchInterventionRecover, postMathIntervention } from "../api/mathClient";
import { EEGWebSocketClient } from "../utils/websocket";

interface StressPoint {
  concept: string;
  stressLevel: number;
  timestamp: string;
}

interface SessionData {
  startTime: number;
  interventionCount: number;
  stressPoints: StressPoint[];
}

interface InterventionState {
  message: string;
  question: string;
  detectedConcept: string;
  sessionSnapshotId?: string;
  latex?: string;
  incompleteStep?: boolean;
  confidence?: number;
}

export interface CanvasBridge {
  exportPng: () => Promise<string | null>;
  exportPaths: () => Promise<unknown[] | null>;
  getEraserEventCount: () => number;
  resetEraserCount: () => void;
}

interface StudySessionContextValue {
  biometricData: BiometricData[];
  cognitiveLoad: CognitiveLoad;
  isConnected: boolean;
  canvasImageData: string;
  showIntervention: boolean;
  showDiagnostics: boolean;
  sessionData: SessionData;
  intervention: InterventionState;
  handleCanvasChange: (imageData: string) => void;
  notifyEraserStroke: () => void;
  registerCanvasExporter: (fn: (() => Promise<string | null>) | null) => void;
  registerCanvasBridge: (bridge: CanvasBridge | null) => void;
  handleInterventionDismiss: () => void;
  handleInterventionResponse: (response: string) => void;
  handleSessionComplete: () => void;
  handleNewSession: () => void;
  setShowDiagnostics: (v: boolean) => void;
  diagnosticsSummary: {
    duration: number;
    totalProblems: number;
    interventions: number;
    stressPoints: StressPoint[];
    overallPerformance: "excellent" | "good" | "needs-improvement";
  };
}

const StudySessionContext = createContext<StudySessionContextValue | null>(null);

export function useStudySession() {
  const ctx = useContext(StudySessionContext);
  if (!ctx) {
    throw new Error("useStudySession must be used within StudySessionProvider");
  }
  return ctx;
}

export function StudySessionProvider({ children }: { children: ReactNode }) {
  const { enabledIds, isLoaded } = usePlugins();
  const { isAuthenticated } = useAuth();
  const eegActive = isLoaded && enabledIds.includes("eeg");

  const [biometricData, setBiometricData] = useState<BiometricData[]>([]);
  const [cognitiveLoad, setCognitiveLoad] = useState<CognitiveLoad>("low");
  const [isConnected, setIsConnected] = useState(false);
  const [canvasImageData, setCanvasImageData] = useState("");
  const [lastCanvasUpdate, setLastCanvasUpdate] = useState(Date.now());
  const [showIntervention, setShowIntervention] = useState(false);
  const [showDiagnostics, setShowDiagnostics] = useState(false);
  const [intervention, setIntervention] = useState<InterventionState>({
    message: "",
    question: "",
    detectedConcept: "",
  });
  const [sessionData, setSessionData] = useState<SessionData>({
    startTime: Date.now(),
    interventionCount: 0,
    stressPoints: [],
  });

  const lastInterventionRef = useRef(0);
  const eraserStrokesRef = useRef(0);
  const canvasExporterRef = useRef<(() => Promise<string | null>) | null>(null);
  const canvasBridgeRef = useRef<CanvasBridge | null>(null);
  const interventionInFlightRef = useRef(false);

  const registerCanvasExporter = useCallback((fn: (() => Promise<string | null>) | null) => {
    canvasExporterRef.current = fn;
  }, []);

  const registerCanvasBridge = useCallback((bridge: CanvasBridge | null) => {
    canvasBridgeRef.current = bridge;
  }, []);

  const notifyEraserStroke = useCallback(() => {
    eraserStrokesRef.current += 1;
  }, []);

  const applyInterventionResult = useCallback(
    (result: {
      hint: string;
      question: string;
      detected_concept: string;
      session_snapshot_id: string;
      triggered: boolean;
      latex?: string;
      incomplete_step?: boolean;
      confidence?: number;
    }) => {
      if (!result.triggered) return;
      setIntervention({
        message: result.hint,
        question: result.question,
        detectedConcept: result.detected_concept,
        sessionSnapshotId: result.session_snapshot_id,
        latex: result.latex,
        incompleteStep: result.incomplete_step,
        confidence: result.confidence,
      });
      setShowIntervention(true);
      lastInterventionRef.current = Date.now();
      eraserStrokesRef.current = 0;
      canvasBridgeRef.current?.resetEraserCount();
      setSessionData((prev) => ({
        ...prev,
        interventionCount: prev.interventionCount + 1,
        stressPoints: [
          ...prev.stressPoints,
          {
            concept: result.detected_concept,
            stressLevel: 70,
            timestamp: new Date().toISOString(),
          },
        ],
      }));
    },
    []
  );

  const requestIntervention = useCallback(async () => {
    if (!config.intervention.enabled || !isAuthenticated) return;
    if (interventionInFlightRef.current || showIntervention) return;

    const now = Date.now();
    const cooldownMs = config.intervention.minTimeBetweenInterventions * 1000;
    if (now - lastInterventionRef.current < cooldownMs) return;

    const idleSec = (now - lastCanvasUpdate) / 1000;
    if (idleSec < config.intervention.inactivityThreshold) return;

    const latest = biometricData[biometricData.length - 1];
    const gamma = latest?.gamma ?? 55;
    const attention = latest ? Math.max(0, 100 - latest.gamma * 0.8) : 60;
    const eraserEvents =
      canvasBridgeRef.current?.getEraserEventCount() ?? eraserStrokesRef.current;
    const stuckness =
      0.4 * Math.min(idleSec / 90, 1) +
      0.3 * Math.min(eraserEvents / 5, 1) +
      0.3 * Math.min(Math.max((gamma - 55) / 30, 0), 1);
    if (stuckness < 0.5) return;

    const bridge = canvasBridgeRef.current;
    const png = bridge
      ? await bridge.exportPng()
      : await canvasExporterRef.current?.();
    if (!png) return;

    const paths = bridge ? await bridge.exportPaths() : null;
    const pathsJson = paths ? JSON.stringify(paths) : undefined;

    interventionInFlightRef.current = true;
    try {
      const result = await postMathIntervention({
        canvas_image: png,
        paths_json: pathsJson,
        topic: "math practice",
        gamma,
        attention,
        canvas_idle_seconds: idleSec,
        eraser_events: eraserEvents,
      });
      applyInterventionResult(result);
    } catch (e) {
      if (config.dev.debug) console.warn("Intervention API failed:", e);
    } finally {
      interventionInFlightRef.current = false;
    }
  }, [
    isAuthenticated,
    showIntervention,
    lastCanvasUpdate,
    biometricData,
    applyInterventionResult,
  ]);

  useEffect(() => {
    if (!eegActive) {
      setIsConnected(false);
      setBiometricData([]);
      setCognitiveLoad("low");
      return;
    }

    if (!config.dev.useSimulatedData) {
      const client = new EEGWebSocketClient(config.backend.websocketUrl);
      client.onConnectionChange(setIsConnected);
      client.onData((data) => {
        const newData: BiometricData = {
          alpha: data.alpha,
          beta: data.beta,
          gamma: data.gamma,
          timestamp: data.timestamp,
        };
        setBiometricData((prev) => [
          ...prev.slice(-(config.visualization.maxDataPoints - 1)),
          newData,
        ]);
        const { highThreshold, mediumThreshold } = config.cognitiveLoad;
        if (data.gamma > highThreshold) setCognitiveLoad("high");
        else if (data.gamma > mediumThreshold) setCognitiveLoad("medium");
        else setCognitiveLoad("low");
      });
      client.connect();
      return () => client.disconnect();
    }

    const connectTimer = setTimeout(() => setIsConnected(true), 1000);
    const intervalMs = 1000 / config.dev.simulatedUpdateRate;

    const dataInterval = setInterval(() => {
      const now = Date.now();
      const baseAlpha = 30 + Math.random() * 20;
      const baseBeta = 40 + Math.random() * 30;
      const baseGamma = 20 + Math.random() * 40;
      const gammaSpike = Math.random() > 0.9 ? 40 : 0;
      const avgGamma = baseGamma + gammaSpike;

      const newData: BiometricData = {
        alpha: baseAlpha,
        beta: baseBeta,
        gamma: avgGamma,
        timestamp: now,
      };

      setBiometricData((prev) => [
        ...prev.slice(-(config.visualization.maxDataPoints - 1)),
        newData,
      ]);

      const { highThreshold, mediumThreshold } = config.cognitiveLoad;
      if (avgGamma > highThreshold) setCognitiveLoad("high");
      else if (avgGamma > mediumThreshold) setCognitiveLoad("medium");
      else setCognitiveLoad("low");
    }, intervalMs);

    return () => {
      clearTimeout(connectTimer);
      clearInterval(dataInterval);
    };
  }, [eegActive]);

  useEffect(() => {
    if (!config.intervention.enabled || !config.intervention.autoTrigger) return;
    const id = setInterval(() => void requestIntervention(), 5000);
    return () => clearInterval(id);
  }, [requestIntervention]);

  useEffect(() => {
    if (!eegActive || !isAuthenticated) return;
    const id = setInterval(() => {
      const latest = biometricData[biometricData.length - 1];
      if (!latest) return;
      const attention = Math.max(0, Math.min(100, 100 - latest.gamma * 0.8));
      void postHubReading("eeg_attention", Math.round(attention * 10) / 10);
    }, 30_000);
    return () => clearInterval(id);
  }, [eegActive, isAuthenticated, biometricData]);

  const handleCanvasChange = useCallback((imageData: string) => {
    setCanvasImageData(imageData);
    setLastCanvasUpdate(Date.now());
  }, []);

  const handleInterventionDismiss = useCallback(() => {
    if (intervention.sessionSnapshotId) {
      void patchInterventionRecover(intervention.sessionSnapshotId, "dismissed");
    }
    setShowIntervention(false);
  }, [intervention.sessionSnapshotId]);

  const handleInterventionResponse = useCallback(
    (response: string) => {
      if (intervention.sessionSnapshotId) {
        void patchInterventionRecover(intervention.sessionSnapshotId, `response:${response}`);
      }
      setShowIntervention(false);
    },
    [intervention.sessionSnapshotId]
  );

  const handleSessionComplete = () => setShowDiagnostics(true);

  const handleNewSession = () => {
    setShowDiagnostics(false);
    setSessionData({
      startTime: Date.now(),
      interventionCount: 0,
      stressPoints: [],
    });
    setBiometricData([]);
    lastInterventionRef.current = 0;
    eraserStrokesRef.current = 0;
  };

  const diagnosticsSummary = {
    duration: (Date.now() - sessionData.startTime) / 1000,
    totalProblems: 3,
    interventions: sessionData.interventionCount,
    stressPoints: sessionData.stressPoints,
    overallPerformance:
      sessionData.interventionCount < 3
        ? ("excellent" as const)
        : ("good" as const),
  };

  return (
    <StudySessionContext.Provider
      value={{
        biometricData,
        cognitiveLoad,
        isConnected,
        canvasImageData,
        showIntervention,
        showDiagnostics,
        sessionData,
        intervention,
        handleCanvasChange,
        notifyEraserStroke,
        registerCanvasExporter,
        registerCanvasBridge,
        handleInterventionDismiss,
        handleInterventionResponse,
        handleSessionComplete,
        handleNewSession,
        setShowDiagnostics,
        diagnosticsSummary,
      }}
    >
      {children}
    </StudySessionContext.Provider>
  );
}
