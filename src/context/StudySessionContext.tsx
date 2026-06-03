import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  type ReactNode,
} from "react";
import type { BiometricData, CognitiveLoad } from "../types";
import { config } from "../config";

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

interface StudySessionContextValue {
  biometricData: BiometricData[];
  cognitiveLoad: CognitiveLoad;
  isConnected: boolean;
  canvasImageData: string;
  showIntervention: boolean;
  showDiagnostics: boolean;
  sessionData: SessionData;
  intervention: {
    message: string;
    question: string;
    detectedConcept: string;
  };
  handleCanvasChange: (imageData: string) => void;
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
  const [biometricData, setBiometricData] = useState<BiometricData[]>([]);
  const [cognitiveLoad, setCognitiveLoad] = useState<CognitiveLoad>("low");
  const [isConnected, setIsConnected] = useState(false);
  const [canvasImageData, setCanvasImageData] = useState("");
  const [lastCanvasUpdate, setLastCanvasUpdate] = useState(Date.now());
  const [showIntervention, setShowIntervention] = useState(false);
  const [showDiagnostics, setShowDiagnostics] = useState(false);
  const [sessionData, setSessionData] = useState<SessionData>({
    startTime: Date.now(),
    interventionCount: 0,
    stressPoints: [],
  });

  const triggerIntervention = useCallback((stressLevel: number) => {
    if (!config.intervention.enabled) return;
    setShowIntervention(true);
    setSessionData((prev) => ({
      ...prev,
      interventionCount: prev.interventionCount + 1,
      stressPoints: [
        ...prev.stressPoints,
        {
          concept: "Matrix Operations",
          stressLevel: Math.round(stressLevel),
          timestamp: new Date().toISOString(),
        },
      ],
    }));
  }, []);

  useEffect(() => {
    if (!config.dev.useSimulatedData) return;

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

      const timeSinceLastUpdate = (now - lastCanvasUpdate) / 1000;
      const { gammaThreshold, inactivityThreshold, autoTrigger } =
        config.intervention;

      if (
        config.intervention.enabled &&
        autoTrigger &&
        avgGamma > gammaThreshold &&
        timeSinceLastUpdate > inactivityThreshold &&
        !showIntervention
      ) {
        triggerIntervention(avgGamma);
      }
    }, intervalMs);

    return () => {
      clearTimeout(connectTimer);
      clearInterval(dataInterval);
    };
  }, [lastCanvasUpdate, showIntervention, triggerIntervention]);

  const handleCanvasChange = useCallback((imageData: string) => {
    setCanvasImageData(imageData);
    setLastCanvasUpdate(Date.now());
  }, []);

  const handleInterventionDismiss = () => setShowIntervention(false);

  const handleInterventionResponse = (response: string) => {
    console.log("User selected:", response);
    setShowIntervention(false);
  };

  const handleSessionComplete = () => setShowDiagnostics(true);

  const handleNewSession = () => {
    setShowDiagnostics(false);
    setSessionData({
      startTime: Date.now(),
      interventionCount: 0,
      stressPoints: [],
    });
    setBiometricData([]);
  };

  const intervention = {
    message:
      "Your cognitive load spiked right after setting up this matrix.",
    question:
      "Are you facing trouble with the cross-multiplication, or is it the negative signs?",
    detectedConcept: "Matrix Cross-Multiplication",
  };

  const diagnosticsSummary = {
    duration: (Date.now() - sessionData.startTime) / 1000,
    totalProblems: 3,
    interventions: sessionData.interventionCount,
    stressPoints: [
      ...sessionData.stressPoints,
      {
        concept: "Derivatives",
        stressLevel: 45,
        timestamp: new Date().toISOString(),
      },
      {
        concept: "Integration",
        stressLevel: 78,
        timestamp: new Date().toISOString(),
      },
      {
        concept: "Limits",
        stressLevel: 32,
        timestamp: new Date().toISOString(),
      },
    ],
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
