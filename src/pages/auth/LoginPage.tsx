import { useState } from "react";
import { useNavigate } from "react-router";
import { Button } from "../../app/components/ui/button";
import { Input } from "../../app/components/ui/input";
import { Card } from "../../app/components/ui/card";
import { useAuth } from "../../context/AuthContext";

export default function LoginPage() {
  const nav = useNavigate();
  const { login, register } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const onSubmit = async (mode: "login" | "register") => {
    setLoading(true);
    setError("");
    try {
      if (mode === "login") await login(username, password);
      else await register(username, password);
      nav("/gre-vocab");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Auth failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="h-full flex items-center justify-center p-4">
      <Card className="gloss-panel p-6 w-full max-w-sm">
        <h2 className="text-xl font-semibold mb-1">Vocab Login</h2>
        <p className="text-sm text-muted-foreground mb-4">
          Use admin/admin123 to access admin panel.
        </p>
        <div className="space-y-3">
          <Input
            placeholder="Username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
          />
          <Input
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          {error ? <p className="text-sm text-destructive">{error}</p> : null}
          <div className="flex gap-2">
            <Button
              className="flex-1"
              onClick={() => onSubmit("login")}
              disabled={loading}
            >
              Login
            </Button>
            <Button
              variant="outline"
              className="flex-1"
              onClick={() => onSubmit("register")}
              disabled={loading}
            >
              Register
            </Button>
          </div>
        </div>
      </Card>
    </div>
  );
}

