import { Link } from "react-router";
import { ArrowLeft, CheckCircle2, XCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { useAuth } from "../../context/AuthContext";
import { authFetch } from "../../features/vocab/api/authClient";
import { Card } from "../../app/components/ui/card";

interface MathAttempt {
  id: number;
  topic: string;
  prompt: string;
  expected_answer: string;
  user_answer: string;
  is_correct: boolean;
  created_at: string;
}

interface MasteryTopic {
  topic: string;
  mastery_points: number;
  accuracy: number;
  attempts: number;
  status: string;
}

export function MathReportsPage() {
  const { token } = useAuth();
  const [attempts, setAttempts] = useState<MathAttempt[]>([]);
  const [mastery, setMastery] = useState<MasteryTopic[]>([]);

  useEffect(() => {
    if (!token) return;
    Promise.all([
      authFetch("/math/sessions", token),
      authFetch("/math/mastery", token),
    ]).then(([s, m]) => {
      setAttempts((s.data as { attempts?: MathAttempt[] }).attempts || []);
      setMastery((m.data as { topics?: MasteryTopic[] }).topics || []);
    });
  }, [token]);

  return (
    <div className="h-full overflow-y-auto space-y-6 pb-8 p-1">
      <Link to="/math-tutor" className="inline-flex items-center gap-1 text-sm text-primary hover:underline">
        <ArrowLeft className="w-4 h-4" /> Math dashboard
      </Link>
      <h1 className="text-2xl font-semibold">Math reports</h1>
      {!token && (
        <p className="text-sm text-muted-foreground">Log in to see saved attempts and mastery.</p>
      )}
      <div className="grid md:grid-cols-2 gap-4 max-w-4xl">
        <Card className="gloss-panel p-4 space-y-2">
          <h2 className="font-semibold">Mastery by topic</h2>
          {mastery.length ? mastery.map((m) => (
            <div key={m.topic} className="rounded-lg border p-2 text-sm">
              <div className="flex justify-between">
                <span>{m.topic}</span>
                <span className="font-mono">{m.mastery_points}/100</span>
              </div>
              <p className="text-xs text-muted-foreground">{m.status} · {m.accuracy}% · {m.attempts} tries</p>
            </div>
          )) : (
            <p className="text-sm text-muted-foreground">No mastery data yet.</p>
          )}
        </Card>
        <Card className="gloss-panel p-4 space-y-2">
          <h2 className="font-semibold">Recent attempts</h2>
          {attempts.slice(0, 12).map((a) => (
            <div key={a.id} className="rounded-lg border p-2 text-xs flex gap-2">
              {a.is_correct ? (
                <CheckCircle2 className="w-4 h-4 text-green-500 shrink-0" />
              ) : (
                <XCircle className="w-4 h-4 text-red-500 shrink-0" />
              )}
              <div>
                <p className="font-medium truncate">{a.prompt}</p>
                <p className="text-muted-foreground">{a.topic} · You: {a.user_answer}</p>
              </div>
            </div>
          ))}
        </Card>
      </div>
    </div>
  );
}
