/**
 * Shell-level webcam host for Focus Body care.
 * Keeps attention/presence/posture alive outside Settings when attention is enabled.
 * Game Sleeper forces unload so Human.js / FaceTracker stay cold while gaming.
 */
import { useEffect, useState, type ReactNode } from "react";
import { loadBodyCarePrefs, subscribeBodyCarePrefs } from "../../lib/bodyCarePrefs";
import { clearBodyCareVision } from "../../lib/bodyCareVisionBus";
import { isFocusSleeperActive, subscribeFocusSleeper } from "../../lib/focusSleeper";

export function BodyCareVisionHost({ children }: { children?: ReactNode }) {
  const [wantAttention, setWantAttention] = useState(
    () => loadBodyCarePrefs().attentionEnabled,
  );
  const [sleeper, setSleeper] = useState(() => isFocusSleeperActive());
  const enabled = wantAttention && !sleeper;
  const [Provider, setProvider] = useState<null | ((p: {
    children: ReactNode;
    autoStart?: boolean;
  }) => ReactNode)>(null);

  useEffect(() => {
    return subscribeBodyCarePrefs((p) => setWantAttention(p.attentionEnabled));
  }, []);

  useEffect(() => {
    return subscribeFocusSleeper((s) => setSleeper(s.active));
  }, []);

  useEffect(() => {
    if (!enabled) {
      setProvider(null);
      clearBodyCareVision();
      return;
    }
    let cancelled = false;
    void import("../../face-tracker/FaceTrackerContext").then((m) => {
      if (!cancelled) {
        setProvider(() => m.FaceTrackerProvider as (p: {
          children: ReactNode;
          autoStart?: boolean;
        }) => ReactNode);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [enabled]);

  if (!enabled || !Provider) return <>{children}</>;
  return (
    <Provider autoStart>
      {children}
    </Provider>
  );
}

export default BodyCareVisionHost;
