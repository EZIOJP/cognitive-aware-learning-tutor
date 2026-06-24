import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
  type RefObject,
} from "react";
import { useLocation } from "react-router";
import { postFaceStatus } from "../api/faceClient";
import { postFocusEventEnd, postFocusEventStart } from "../api/focusClient";
import { getActiveProfile, getActiveProfileName } from "./calibration";
import { FocusState, type FocusPayload } from "./focusState";
import { BlinkRateTracker, scoreAttention, type FaceStatusPayload } from "./scoring";
import { useHumanTracker } from "./useHumanTracker";
import { usePomodoro } from "../context/PomodoroContext";
import { WaveDetector } from "./waveDetector";
import { triggerWaveSnapshot } from "./waveSnapshot";

const POST_INTERVAL_MS = 1000;

type FaceTrackerContextValue = {
  tracking: boolean;
  startTracking: () => void;
  stopTracking: () => void;
  toggleTracking: () => void;
  status: ReturnType<typeof useHumanTracker>["status"];
  error: string | null;
  payload: FaceStatusPayload | null;
  focus: FocusPayload;
  profileName: string | null;
  lastSnapshotMarker: string | null;
  videoRef: RefObject<HTMLVideoElement | null>;
  /** Hidden video element — must stay mounted while tracking. */
  VideoElement: () => ReactNode;
};

const FaceTrackerContext = createContext<FaceTrackerContextValue | null>(null);

export function useFaceTracker() {
  const ctx = useContext(FaceTrackerContext);
  if (!ctx) throw new Error("useFaceTracker must be used within FaceTrackerProvider");
  return ctx;
}

/** Optional hook — returns null when Focus Mirror plugin is disabled. */
export function useFaceTrackerOptional() {
  return useContext(FaceTrackerContext);
}

export function FaceTrackerProvider({ children }: { children: ReactNode }) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const blinkRef = useRef(new BlinkRateTracker());
  const focusRef = useRef(new FocusState());
  const waveRef = useRef(new WaveDetector());
  const lastPostRef = useRef(0);
  const prevNotFocusedRef = useRef(false);
  const activeEventIdRef = useRef<number | null>(null);

  const { pathname } = useLocation();
  const onCalibrate = pathname.includes("/focus/calibrate");
  const { mode: pomodoroMode, isRunning: pomodoroRunning } = usePomodoro();

  const [tracking, setTracking] = useState(false);
  const [payload, setPayload] = useState<FaceStatusPayload | null>(null);
  const [focus, setFocus] = useState<FocusPayload>({
    not_focused: false,
    head_turned_away: false,
    long_eye_closure: false,
    no_face: false,
    active_event_type: null,
  });
  const [profileName, setProfileName] = useState<string | null>(null);
  const [lastSnapshotMarker, setLastSnapshotMarker] = useState<string | null>(null);

  const active = tracking && !onCalibrate;
  const { reading, status, error } = useHumanTracker(active, videoRef);

  const stopTracking = useCallback(() => {
    void postFaceStatus({
      attention: 0,
      attitude: "stopped",
      blink_rate: 0,
      face_detected: false,
      details: {},
      focus: {
        not_focused: false,
        head_turned_away: false,
        long_eye_closure: false,
        no_face: false,
      },
    });
    focusRef.current.reset();
    waveRef.current.reset();
    blinkRef.current.reset();
    setPayload(null);
    setFocus({
      not_focused: false,
      head_turned_away: false,
      long_eye_closure: false,
      no_face: false,
      active_event_type: null,
    });
    setTracking(false);
  }, []);

  const startTracking = useCallback(() => {
    blinkRef.current.reset();
    focusRef.current.reset();
    waveRef.current.reset();
    setProfileName(getActiveProfileName());
    setTracking(true);
  }, []);

  const toggleTracking = useCallback(() => {
    if (tracking) stopTracking();
    else startTracking();
  }, [tracking, stopTracking, startTracking]);

  useEffect(() => {
    if (!active || !reading) return;
    const profile = getActiveProfile();
    const blinkRate = blinkRef.current.update(reading.eyeOpenness, profile.eyelidBaseline);
    const scored = scoreAttention(reading, profile, blinkRate);
    const focusPayload = focusRef.current.update(reading, profile, profile.eyelidBaseline);
    setPayload(scored);
    setFocus(focusPayload);

    if (waveRef.current.update(reading, reading.waveGesture)) {
      void triggerWaveSnapshot().then((marker) => {
        if (marker) setLastSnapshotMarker(marker);
      });
    }

    const shouldLog =
      pomodoroMode === "focus" && pomodoroRunning && focusPayload.not_focused !== prevNotFocusedRef.current;

    if (shouldLog && focusPayload.not_focused && focusPayload.active_event_type) {
      void postFocusEventStart(focusPayload.active_event_type, pomodoroMode).then((id) => {
        activeEventIdRef.current = id;
      });
    } else if (shouldLog && !focusPayload.not_focused && activeEventIdRef.current != null) {
      void postFocusEventEnd(activeEventIdRef.current);
      activeEventIdRef.current = null;
    }
    prevNotFocusedRef.current = focusPayload.not_focused;

    const now = Date.now();
    if (now - lastPostRef.current >= POST_INTERVAL_MS) {
      lastPostRef.current = now;
      void postFaceStatus({
        ...scored,
        focus: {
          not_focused: focusPayload.not_focused,
          head_turned_away: focusPayload.head_turned_away,
          long_eye_closure: focusPayload.long_eye_closure,
          no_face: focusPayload.no_face,
        },
      });
    }
  }, [active, reading, pomodoroMode, pomodoroRunning]);

  const VideoElement = useCallback(
    () => (
      <video
        ref={videoRef}
        muted
        playsInline
        className="fixed w-px h-px opacity-0 pointer-events-none -z-50"
        aria-hidden
      />
    ),
    [],
  );

  return (
    <FaceTrackerContext.Provider
      value={{
        tracking,
        startTracking,
        stopTracking,
        toggleTracking,
        status,
        error,
        payload,
        focus,
        profileName,
        lastSnapshotMarker,
        videoRef,
        VideoElement,
      }}
    >
      <VideoElement />
      {children}
    </FaceTrackerContext.Provider>
  );
}
