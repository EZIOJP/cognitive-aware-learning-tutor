import { useEffect, useState } from "react";
import { useNavigate } from "react-router";
import { Loader2, ScanFace } from "lucide-react";
import { Button } from "../../app/components/ui/button";
import { Input } from "../../app/components/ui/input";
import { Card } from "../../app/components/ui/card";
import { useAuth } from "../../context/AuthContext";
import { postFaceLogin } from "../../api/faceClient";
import { useFaceAuthCapture } from "../../face-tracker/useFaceAuthCapture";

export default function LoginPage() {
  const nav = useNavigate();
  const { login, register, setTokenFromFace } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [faceLoading, setFaceLoading] = useState(false);
  const [error, setError] = useState("");
  const { videoRef, ready, error: camError, startCamera, stopCamera, captureEmbedding } =
    useFaceAuthCapture();

  useEffect(() => {
    void startCamera();
    return () => stopCamera();
  }, [startCamera, stopCamera]);

  const onSubmit = async (mode: "login" | "register") => {
    setLoading(true);
    setError("");
    try {
      if (mode === "login") await login(username, password);
      else await register(username, password);
      nav("/");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Auth failed");
    } finally {
      setLoading(false);
    }
  };

  const onFaceLogin = async () => {
    if (!username.trim()) {
      setError("Enter your username before face login.");
      return;
    }
    setFaceLoading(true);
    setError("");
    try {
      const embedding = await captureEmbedding();
      if (!embedding) throw new Error("Could not capture face — check lighting and camera.");
      const result = await postFaceLogin(username, embedding);
      if (!result) throw new Error("Face login failed — enroll your face on Profile first.");
      setTokenFromFace(result.token, result.user);
      nav("/");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Face login failed");
    } finally {
      setFaceLoading(false);
    }
  };

  return (
    <div className="h-full flex items-center justify-center p-4">
      <Card className="gloss-panel p-6 w-full max-w-sm space-y-4">
        <h2 className="text-xl font-semibold">Sign in</h2>
        <p className="text-sm text-muted-foreground">Demo: admin / admin123</p>
        <Input placeholder="Username" value={username} onChange={(e) => setUsername(e.target.value)} />
        <Input
          type="password"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        {error ? <p className="text-sm text-destructive">{error}</p> : null}
        <div className="flex gap-2">
          <Button className="flex-1" onClick={() => void onSubmit("login")} disabled={loading}>
            Login
          </Button>
          <Button
            variant="outline"
            className="flex-1"
            onClick={() => void onSubmit("register")}
            disabled={loading}
          >
            Register
          </Button>
        </div>

        <div className="border-t border-border/50 pt-4 space-y-3">
          <p className="text-xs font-medium text-muted-foreground">Face ID (username required)</p>
          <video
            ref={videoRef}
            muted
            playsInline
            className="w-full rounded-md bg-black/80 aspect-video object-cover"
          />
          {camError && <p className="text-xs text-destructive">{camError}</p>}
          <Button
            variant="secondary"
            className="w-full"
            disabled={!ready || faceLoading}
            onClick={() => void onFaceLogin()}
          >
            {faceLoading ? (
              <Loader2 className="w-4 h-4 animate-spin mr-1" />
            ) : (
              <ScanFace className="w-4 h-4 mr-1" />
            )}
            Login with face
          </Button>
          <p className="text-[10px] text-muted-foreground">
            Enroll on Profile after password login. Uses facemesh if faceres model is not installed.
          </p>
        </div>
      </Card>
    </div>
  );
}
