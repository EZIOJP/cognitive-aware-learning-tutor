import { useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { LogOut, ScanFace, Loader2 } from "lucide-react";
import { useNavigate } from "react-router";
import { Button } from "../app/components/ui/button";
import { Card } from "../app/components/ui/card";
import { fetchFaceEnrolled, postFaceEnroll } from "../api/faceClient";
import { useFaceAuthCapture } from "../face-tracker/useFaceAuthCapture";

export function ProfilePage() {
  const { user, isAuthenticated, logout } = useAuth();
  const nav = useNavigate();
  const [enrolled, setEnrolled] = useState<boolean | null>(null);
  const [enrolling, setEnrolling] = useState(false);
  const [faceMsg, setFaceMsg] = useState<string | null>(null);
  const { videoRef, ready, error: camError, startCamera, stopCamera, captureEmbedding } =
    useFaceAuthCapture();

  useEffect(() => {
    if (!isAuthenticated) return;
    void fetchFaceEnrolled().then(setEnrolled);
    void startCamera();
    return () => stopCamera();
  }, [isAuthenticated, startCamera, stopCamera]);

  const onEnrollFace = async () => {
    setEnrolling(true);
    setFaceMsg(null);
    try {
      const embedding = await captureEmbedding();
      if (!embedding) throw new Error("Could not capture face.");
      const ok = await postFaceEnroll(embedding);
      if (!ok) throw new Error("Enroll request failed.");
      setEnrolled(true);
      setFaceMsg("Face enrolled — you can use face login next time.");
    } catch (e) {
      setFaceMsg(e instanceof Error ? e.message : "Enroll failed");
    } finally {
      setEnrolling(false);
    }
  };

  if (!isAuthenticated) {
    return (
      <div className="flex flex-col items-center justify-center h-full p-8 text-center space-y-4">
        <h2 className="text-2xl font-bold">Not Logged In</h2>
        <p className="text-muted-foreground">Please log in to view your profile.</p>
        <button
          onClick={() => nav("/login")}
          className="px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors"
        >
          Go to Login
        </button>
      </div>
    );
  }

  return (
    <div className="p-8 max-w-2xl mx-auto space-y-8 animate-in fade-in duration-500">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Profile</h1>
        <p className="text-muted-foreground mt-2">
          Manage your account settings and preferences.
        </p>
      </div>

      <div className="bg-card border border-border/50 rounded-xl p-6 shadow-sm space-y-4">
        <div className="space-y-1">
          <p className="text-sm font-medium text-muted-foreground">Username</p>
          <p className="text-lg font-semibold">{user?.username}</p>
        </div>
        
        <div className="space-y-1">
          <p className="text-sm font-medium text-muted-foreground">Role</p>
          <p className="text-lg font-semibold capitalize">{user?.role}</p>
        </div>
      </div>

      <Card className="p-6 gloss-panel space-y-3">
        <div className="flex items-center gap-2">
          <ScanFace className="w-5 h-5 text-primary" />
          <h2 className="font-semibold">Face ID</h2>
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
          {enrolled ? "Re-enroll face" : "Enroll face for login"}
        </Button>
        {faceMsg && <p className="text-xs text-muted-foreground">{faceMsg}</p>}
      </Card>

      <div className="pt-4">
        <button
          onClick={() => {
            logout();
            nav("/");
          }}
          className="flex items-center gap-2 px-4 py-2 text-destructive hover:bg-destructive/10 rounded-lg transition-colors font-medium"
        >
          <LogOut className="w-4 h-4" />
          Log out
        </button>
      </div>
    </div>
  );
}
