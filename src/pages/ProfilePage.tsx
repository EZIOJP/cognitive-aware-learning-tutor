import { useEffect, useMemo, useState } from "react";
import { ScanFace, Loader2, HardDrive, Smartphone } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { Button } from "../app/components/ui/button";
import { Card } from "../app/components/ui/card";
import { Input } from "../app/components/ui/input";
import { fetchFaceEnrolled, postFaceEnroll } from "../api/faceClient";
import { useFaceAuthCapture } from "../face-tracker/useFaceAuthCapture";
import { useEaster, useTapCombo } from "../easter";
import { CommunityRanksPanel } from "../components/life/CommunityRanksPanel";
import { resolveApiUrl } from "../utils/resolveBackendUrl";

const SILLY_NAMES = [
  "Captain Focus",
  "Professor Potato",
  "Sir Cramalot",
  "Quiz Wizard",
  "Byte Knight",
  "Study Goblin",
];

function wearablesHubUrl(): string {
  try {
    const u = new URL(resolveApiUrl());
    u.port = "8765";
    u.pathname = "/";
    return u.origin;
  } catch {
    return "http://localhost:8765";
  }
}

export function ProfilePage() {
  const { user, isAuthenticated, sessionReady, updateProfile } = useAuth();
  const { burst } = useEaster();
  const [enrolled, setEnrolled] = useState<boolean | null>(null);
  const [enrolling, setEnrolling] = useState(false);
  const [faceMsg, setFaceMsg] = useState<string | null>(null);
  const [sillyName, setSillyName] = useState<string | null>(null);
  const [displayName, setDisplayName] = useState("");
  const [savingName, setSavingName] = useState(false);
  const [nameMsg, setNameMsg] = useState<string | null>(null);
  const onNameTap = useTapCombo(3, () => {
    const next = SILLY_NAMES[Math.floor(Math.random() * SILLY_NAMES.length)];
    setSillyName(next);
    burst("confetti", next);
    window.setTimeout(() => setSillyName(null), 4000);
  });
  const { videoRef, ready, error: camError, startCamera, stopCamera, captureEmbedding } =
    useFaceAuthCapture();

  const apiUrl = useMemo(() => resolveApiUrl(), []);
  const hubUrl = useMemo(() => wearablesHubUrl(), []);

  useEffect(() => {
    if (!user) return;
    setDisplayName(user.display_name || "");
  }, [user?.id, user?.display_name]);

  useEffect(() => {
    if (!isAuthenticated) return;
    void fetchFaceEnrolled().then(setEnrolled);
    void startCamera();
    return () => stopCamera();
  }, [isAuthenticated, startCamera, stopCamera]);

  const onSaveName = async () => {
    setSavingName(true);
    setNameMsg(null);
    try {
      await updateProfile({ display_name: displayName.trim() || null });
      setNameMsg("Saved.");
    } catch (e) {
      setNameMsg(e instanceof Error ? e.message : "Could not save");
    } finally {
      setSavingName(false);
    }
  };

  const onEnrollFace = async () => {
    setEnrolling(true);
    setFaceMsg(null);
    try {
      const embedding = await captureEmbedding();
      if (!embedding) throw new Error("Could not capture face.");
      const ok = await postFaceEnroll(embedding);
      if (!ok) throw new Error("Enroll request failed.");
      setEnrolled(true);
      setFaceMsg("Face enrolled — optional unlock for this machine.");
    } catch (e) {
      setFaceMsg(e instanceof Error ? e.message : "Enroll failed");
    } finally {
      setEnrolling(false);
    }
  };

  if (!sessionReady) {
    return (
      <div className="flex items-center justify-center h-full p-8 text-muted-foreground">
        Loading profile…
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <div className="flex flex-col items-center justify-center h-full p-8 text-center space-y-4">
        <h2 className="text-2xl font-bold">Backend offline</h2>
        <p className="text-muted-foreground max-w-md">
          Start the local API with <code className="text-foreground">run.bat</code>, then refresh.
          This PC is the owner — there is no sign-in page.
        </p>
      </div>
    );
  }

  const shownName = sillyName ?? user?.display_name ?? user?.username;

  return (
    <div className="p-8 max-w-2xl mx-auto space-y-8 animate-in fade-in duration-500">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Profile</h1>
        <p className="text-muted-foreground mt-2">
          One owner on this machine. Notes, quiz, tracker, and health stay in local files.
        </p>
      </div>

      <div className="bg-card border border-border/50 rounded-xl p-6 shadow-sm space-y-4">
        <div className="space-y-1">
          <p className="text-sm font-medium text-muted-foreground">Display name</p>
          <p
            className="text-lg font-semibold cursor-pointer select-none"
            onClick={onNameTap}
            title="Triple-tap…"
          >
            {shownName}
          </p>
          <div className="flex gap-2 pt-1">
            <Input
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder="How you want to appear"
              maxLength={80}
            />
            <Button size="sm" disabled={savingName} onClick={() => void onSaveName()}>
              {savingName ? <Loader2 className="w-4 h-4 animate-spin" /> : "Save"}
            </Button>
          </div>
          {nameMsg && <p className="text-xs text-muted-foreground">{nameMsg}</p>}
        </div>

        <div className="space-y-1">
          <p className="text-sm font-medium text-muted-foreground">Local account</p>
          <p className="text-sm">{user?.username}</p>
        </div>
      </div>

      <Card className="p-6 gloss-panel space-y-3">
        <div className="flex items-center gap-2">
          <HardDrive className="w-5 h-5 text-primary" />
          <h2 className="font-semibold">This machine&apos;s data</h2>
        </div>
        <p className="text-sm text-muted-foreground">
          SQLite and notes live under <code className="text-foreground">data/</code> on this PC.
          Phone and watch: same Tailscale or LAN URLs. Open the <strong>site</strong> link
          (<code className="text-foreground">:5173</code>) in a browser for the full app.
        </p>
        <div className="text-sm space-y-1">
          <p>
            <span className="text-muted-foreground">Web API: </span>
            <code className="text-foreground break-all">{apiUrl}</code>
          </p>
          <p className="flex items-start gap-1">
            <Smartphone className="w-4 h-4 mt-0.5 shrink-0 text-muted-foreground" />
            <span>
              <span className="text-muted-foreground">Wearables hub: </span>
              <code className="text-foreground break-all">{hubUrl}</code>
            </span>
          </p>
        </div>
      </Card>

      <CommunityRanksPanel />

      <Card className="p-6 gloss-panel space-y-3">
        <div className="flex items-center gap-2">
          <ScanFace className="w-5 h-5 text-primary" />
          <h2 className="font-semibold">Face unlock</h2>
          <span className="ml-auto text-xs text-muted-foreground">
            {enrolled === null ? "…" : enrolled ? "Enrolled" : "Not enrolled"}
          </span>
        </div>
        <video
          ref={videoRef}
          muted
          playsInline
          className="w-full max-w-sm rounded-md bg-black/80 aspect-video object-cover"
        />
        {camError && <p className="text-xs text-destructive">{camError}</p>}
        <Button size="sm" disabled={!ready || enrolling} onClick={() => void onEnrollFace()}>
          {enrolling ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : null}
          {enrolled ? "Re-enroll face" : "Enroll face"}
        </Button>
        {faceMsg && <p className="text-xs text-muted-foreground">{faceMsg}</p>}
      </Card>
    </div>
  );
}
