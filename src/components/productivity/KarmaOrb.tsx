import { useEffect, useState } from "react";

type Props = {
  state?: "idle" | "thinking" | "talking" | "listening";
  onClick?: () => void;
};

/**
 * Offline, low-cost homage to the supplied Karma Orb. It deliberately avoids
 * the original CDN Three.js dependency so Focus stays self-contained.
 */
export function KarmaOrb({ state = "idle", onClick }: Props) {
  const [pulse, setPulse] = useState(false);

  useEffect(() => {
    if (state !== "talking") return;
    const id = window.setInterval(() => setPulse((value) => !value), 420);
    return () => window.clearInterval(id);
  }, [state]);

  return (
    <button
      type="button"
      aria-label="Karma orb — get a Jarvis brief"
      onClick={onClick}
      className={`karma-orb karma-orb--${state}${pulse ? " karma-orb--pulse" : ""}`}
      title="Karma orb · brief"
    >
      <span className="karma-orb__ring karma-orb__ring--outer" />
      <span className="karma-orb__ring karma-orb__ring--inner" />
      <span className="karma-orb__core" />
    </button>
  );
}

export default KarmaOrb;
