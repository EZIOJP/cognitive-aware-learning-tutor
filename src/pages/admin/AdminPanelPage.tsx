import { useEffect, useState } from "react";
import { useNavigate } from "react-router";
import { Button } from "../../app/components/ui/button";
import { Card } from "../../app/components/ui/card";
import { Input } from "../../app/components/ui/input";
import { useAuth } from "../../context/AuthContext";
import { authFetch } from "../../features/vocab/api/authClient";

interface AdminUser {
  id: number;
  username: string;
  password: string;
  created_at: string;
  is_admin: boolean;
  progress_rows: number;
  mastered_rows: number;
}

interface MathTemplate {
  id: number;
  title: string;
  topic: string;
  operation: string;
  min_value: number;
  max_value: number;
  number_type: string;
  decimal_places: number;
  points: number;
  is_active: boolean;
}

const EMPTY_MATH_TEMPLATE: Omit<MathTemplate, "id"> = {
  title: "",
  topic: "Arithmetic",
  operation: "add",
  min_value: 1,
  max_value: 20,
  number_type: "any",
  decimal_places: 0,
  points: 10,
  is_active: true,
};

export default function AdminPanelPage() {
  const nav = useNavigate();
  const { token, isAdmin } = useAuth();
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [words, setWords] = useState<any[]>([]);
  const [mathTemplates, setMathTemplates] = useState<MathTemplate[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [editing, setEditing] = useState<any | null>(null);
  const [editingMath, setEditingMath] = useState<MathTemplate | null>(null);
  const [newMath, setNewMath] = useState<Omit<MathTemplate, "id">>(EMPTY_MATH_TEMPLATE);
  const [creating, setCreating] = useState(false);
  const [newWord, setNewWord] = useState({ word: "", meaning: "", pronunciation: "" });
  const [passwordEdits, setPasswordEdits] = useState<Record<number, string>>({});
  const [file, setFile] = useState<File | null>(null);
  const [jsonInput, setJsonInput] = useState("");
  const [exportGroup, setExportGroup] = useState("1");
  const [exportIncludeProgress, setExportIncludeProgress] = useState(true);
  const [statusMsg, setStatusMsg] = useState("");

  const load = async () => {
    if (!token) return;
    setLoading(true);
    setError("");
    try {
      const u = await authFetch("/admin/users", token);
      const w = await authFetch("/words/by-criteria/?limit=200&offset=0", token);
      const m = await authFetch("/math/templates", token);
      setUsers((u.data as any).users || []);
      setWords((w.data as any).words || []);
      setMathTemplates((m.data as any).templates || []);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Load failed");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!isAdmin) {
      nav("/login");
      return;
    }
    load();
  }, [isAdmin]);

  const resetUser = async (id: number) => {
    if (!token) return;
    await authFetch(`/admin/users/${id}/reset-progress`, token, { method: "POST" });
    await load();
  };

  const resetPassword = async (id: number) => {
    if (!token) return;
    const password = passwordEdits[id]?.trim();
    if (!password) {
      setError("Enter a new password first");
      return;
    }
    setError("");
    try {
      await authFetch(`/admin/users/${id}/reset-password`, token, {
        method: "POST",
        body: JSON.stringify({ password }),
      });
      setPasswordEdits((prev) => ({ ...prev, [id]: "" }));
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Password reset failed");
    }
  };

  const resetAllUsers = async () => {
    if (!token) return;
    if (!window.confirm("Are you sure you want to reset progress for ALL users?")) return;
    setError("");
    try {
      await authFetch(`/admin/users/reset-all-progress`, token, { method: "POST" });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Reset failed");
    }
  };

  const saveWord = async () => {
    if (!token || !editing?.id) return;
    setError("");
    try {
      await authFetch(`/words/${editing.id}`, token, {
        method: "PUT",
        body: JSON.stringify({
          word: editing.word,
          meaning: editing.meaning,
          pronunciation: editing.pronunciation || "",
        }),
      });
      setEditing(null);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save failed");
    }
  };

  const createWord = async () => {
    if (!token) return;
    setError("");
    try {
      await authFetch(`/words`, token, {
        method: "POST",
        body: JSON.stringify(newWord),
      });
      setCreating(false);
      setNewWord({ word: "", meaning: "", pronunciation: "" });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Create failed");
    }
  };

  const deleteWord = async (id: number) => {
    if (!token) return;
    await authFetch(`/words/${id}`, token, { method: "DELETE" });
    await load();
  };

  const importCsv = async () => {
    if (!token || !file) return;
    setError("");
    try {
      const form = new FormData();
      form.append("file", file);
      await authFetch("/words/import/csv", token, { method: "POST", body: form });
      setFile(null);
      setStatusMsg("CSV import complete.");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "CSV import failed");
    }
  };

  const exportCsv = async () => {
    if (!token) return;
    setError("");
    try {
      const { res } = await authFetch("/words/export/csv", token, { method: "GET" });
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "vocab_words.csv";
      a.click();
      window.URL.revokeObjectURL(url);
      setStatusMsg("Exported full word bank (CSV).");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Export failed");
    }
  };

  const exportGroupJson = async () => {
    if (!token) return;
    const gn = Number.parseInt(exportGroup, 10);
    if (!Number.isFinite(gn) || gn < 1) {
      setError("Enter a valid group number (1+)");
      return;
    }
    setError("");
    try {
      const q = exportIncludeProgress ? "?include_progress=true" : "";
      const { res } = await authFetch(
        `/words/export/group/${gn}${q}`,
        token,
        { method: "GET" }
      );
      const data = await res.json();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `vocab_group_${gn}.json`;
      a.click();
      window.URL.revokeObjectURL(url);
      setStatusMsg(`Exported group ${gn} (JSON).`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Group JSON export failed");
    }
  };

  const exportGroupCsv = async () => {
    if (!token) return;
    const gn = Number.parseInt(exportGroup, 10);
    if (!Number.isFinite(gn) || gn < 1) {
      setError("Enter a valid group number (1+)");
      return;
    }
    setError("");
    try {
      const { res } = await authFetch(
        `/words/export/group/${gn}/csv`,
        token,
        { method: "GET" }
      );
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `vocab_group_${gn}.csv`;
      a.click();
      window.URL.revokeObjectURL(url);
      setStatusMsg(`Exported group ${gn} (CSV).`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Group CSV export failed");
    }
  };

  const importJson = async () => {
    if (!token || !jsonInput.trim()) return;
    setError("");
    try {
      const parsed = JSON.parse(jsonInput);
      const wordsArray = Array.isArray(parsed) ? parsed : (parsed.words || [parsed]);
      
      const res = await authFetch("/words/import/json", token, {
        method: "POST",
        body: JSON.stringify({ words: wordsArray }),
      });
      setJsonInput("");
      alert(`Imported! Added: ${res.data?.added || 0}, Skipped: ${res.data?.skipped || 0}`);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Invalid JSON or Import Failed");
    }
  };

  const createMathTemplate = async () => {
    if (!token) return;
    setError("");
    try {
      await authFetch("/math/templates", token, {
        method: "POST",
        body: JSON.stringify(newMath),
      });
      setNewMath(EMPTY_MATH_TEMPLATE);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Math template create failed");
    }
  };

  const saveMathTemplate = async () => {
    if (!token || !editingMath) return;
    setError("");
    try {
      const { id, ...payload } = editingMath;
      await authFetch(`/math/templates/${id}`, token, {
        method: "PUT",
        body: JSON.stringify(payload),
      });
      setEditingMath(null);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Math template save failed");
    }
  };

  const deleteMathTemplate = async (id: number) => {
    if (!token) return;
    await authFetch(`/math/templates/${id}`, token, { method: "DELETE" });
    await load();
  };

  return (
    <div className="h-full overflow-y-auto space-y-4">
      <Card className="gloss-panel p-4">
        <h2 className="text-xl font-semibold">Admin Panel</h2>
        <p className="text-sm text-muted-foreground">
          Users, reset progress, and word import/export/edit.
        </p>
      </Card>

      {error ? <p className="text-sm text-destructive">{error}</p> : null}
      {statusMsg ? <p className="text-sm text-emerald-500">{statusMsg}</p> : null}
      {loading ? <p className="text-sm text-muted-foreground">Loading…</p> : null}

      <Card className="gloss-panel p-4 space-y-3">
        <h3 className="font-semibold">Export by group</h3>
        <p className="text-xs text-muted-foreground">
          Download one group (30 words) as JSON (optional progress) or CSV for backup.
        </p>
        <div className="flex flex-wrap gap-2 items-center">
          <Input
            type="number"
            min={1}
            className="w-24"
            value={exportGroup}
            onChange={(e) => setExportGroup(e.target.value)}
            placeholder="Group #"
          />
          <label className="flex items-center gap-2 text-xs text-muted-foreground">
            <input
              type="checkbox"
              checked={exportIncludeProgress}
              onChange={(e) => setExportIncludeProgress(e.target.checked)}
            />
            Include progress (JSON)
          </label>
          <Button variant="outline" onClick={exportGroupJson}>
            Export group JSON
          </Button>
          <Button variant="outline" onClick={exportGroupCsv}>
            Export group CSV
          </Button>
        </div>
      </Card>

      <Card className="gloss-panel p-4 space-y-3">
        <h3 className="font-semibold">Import / Export CSV</h3>
        <div className="flex flex-wrap gap-2 items-center">
          <Input type="file" accept=".csv" onChange={(e) => setFile(e.target.files?.[0] || null)} className="max-w-xs" />
          <Button onClick={importCsv} disabled={!file}>Import CSV</Button>
          <Button variant="outline" onClick={exportCsv}>Export CSV</Button>
        </div>
      </Card>

      <Card className="gloss-panel p-4 space-y-3">
        <h3 className="font-semibold">Import JSON (Raw)</h3>
        <p className="text-xs text-muted-foreground">Paste an array of word objects. Requires "word" and "meaning" fields.</p>
        <textarea
          value={jsonInput}
          onChange={(e) => setJsonInput(e.target.value)}
          placeholder='[{"word": "test", "meaning": "an experiment"}]'
          className="w-full min-h-[100px] p-2 bg-background border rounded-md text-sm font-mono text-foreground"
        />
        <Button onClick={importJson} disabled={!jsonInput.trim()}>Import JSON</Button>
      </Card>

      <Card className="gloss-panel p-4">
        <div className="flex items-center justify-between mb-3">
          <div>
            <h3 className="font-semibold">Users</h3>
            <p className="text-xs text-muted-foreground">
              Prototype mode: stored passwords are visible here.
            </p>
          </div>
          <Button size="sm" variant="destructive" onClick={resetAllUsers}>
            Reset ALL Progress
          </Button>
        </div>
        <div className="space-y-2">
          {users.map((u) => (
            <div key={u.id} className="rounded-lg border p-3 space-y-3">
              <div className="flex items-start justify-between gap-3">
              <div>
                <p className="font-medium">{u.username} {u.is_admin ? "(admin)" : ""}</p>
                <p className="text-xs text-muted-foreground">
                  Progress rows: {u.progress_rows} · Mastered: {u.mastered_rows}
                </p>
                  <p className="text-xs font-mono mt-1">
                    Password: <span className="text-primary">{u.password}</span>
                  </p>
              </div>
              <Button size="sm" variant="destructive" onClick={() => resetUser(u.id)}>
                Reset Progress
              </Button>
              </div>
              <div className="flex flex-wrap gap-2">
                <Input
                  type="text"
                  placeholder="New password"
                  value={passwordEdits[u.id] || ""}
                  onChange={(e) =>
                    setPasswordEdits((prev) => ({ ...prev, [u.id]: e.target.value }))
                  }
                  className="max-w-xs"
                />
                <Button size="sm" variant="outline" onClick={() => resetPassword(u.id)}>
                  Reset Password
                </Button>
              </div>
            </div>
          ))}
        </div>
      </Card>

      <Card className="gloss-panel p-4 space-y-4">
        <div>
          <h3 className="font-semibold">Math Question Templates</h3>
          <p className="text-xs text-muted-foreground">
            Create random generators with ranges, number types, decimal places, and mastery points.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-2">
          <Input
            placeholder="Title"
            value={newMath.title}
            onChange={(e) => setNewMath({ ...newMath, title: e.target.value })}
          />
          <Input
            placeholder="Topic"
            value={newMath.topic}
            onChange={(e) => setNewMath({ ...newMath, topic: e.target.value })}
          />
          <select
            value={newMath.operation}
            onChange={(e) => setNewMath({ ...newMath, operation: e.target.value })}
            className="h-9 rounded-md border bg-background px-3 text-sm"
          >
            <option value="add">Add</option>
            <option value="subtract">Subtract</option>
            <option value="multiply">Multiply</option>
            <option value="divide">Divide</option>
            <option value="linear_equation">Linear Equation</option>
            <option value="simplify">Simplify Like Terms</option>
          </select>
          <select
            value={newMath.number_type}
            onChange={(e) => setNewMath({ ...newMath, number_type: e.target.value })}
            className="h-9 rounded-md border bg-background px-3 text-sm"
          >
            <option value="any">Any</option>
            <option value="odd">Odd</option>
            <option value="even">Even</option>
            <option value="positive">Positive</option>
            <option value="negative">Negative</option>
          </select>
          <Input
            type="number"
            placeholder="Min"
            value={newMath.min_value}
            onChange={(e) => setNewMath({ ...newMath, min_value: Number(e.target.value) })}
          />
          <Input
            type="number"
            placeholder="Max"
            value={newMath.max_value}
            onChange={(e) => setNewMath({ ...newMath, max_value: Number(e.target.value) })}
          />
          <Input
            type="number"
            placeholder="Decimals"
            value={newMath.decimal_places}
            onChange={(e) => setNewMath({ ...newMath, decimal_places: Number(e.target.value) })}
          />
          <Input
            type="number"
            placeholder="Points"
            value={newMath.points}
            onChange={(e) => setNewMath({ ...newMath, points: Number(e.target.value) })}
          />
        </div>
        <Button onClick={createMathTemplate} disabled={!newMath.title.trim()}>
          Add Math Template
        </Button>

        <div className="space-y-2">
          {mathTemplates.map((m) => (
            <div key={m.id} className="rounded-lg border p-3 flex flex-wrap items-center justify-between gap-3">
              <div className="min-w-0">
                <p className="font-medium">{m.title}</p>
                <p className="text-xs text-muted-foreground">
                  {m.topic} / {m.operation} / {m.number_type} / {m.min_value} to {m.max_value} / {m.points} pts
                </p>
              </div>
              <div className="flex gap-2">
                <Button size="sm" variant="outline" onClick={() => setEditingMath({ ...m })}>
                  Edit
                </Button>
                <Button size="sm" variant="destructive" onClick={() => deleteMathTemplate(m.id)}>
                  Delete
                </Button>
              </div>
            </div>
          ))}
        </div>
      </Card>

      <Card className="gloss-panel p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-semibold">Words (first 200)</h3>
          <Button size="sm" onClick={() => setCreating(true)}>Add Word</Button>
        </div>
        <div className="space-y-2">
          {words.map((w) => (
            <div key={w.id} className="rounded-lg border p-2 flex items-center justify-between gap-2">
              <div className="min-w-0">
                <p className="font-medium truncate">{w.word}</p>
                <p className="text-xs text-muted-foreground truncate">{w.meaning}</p>
              </div>
              <div className="flex gap-2">
                <Button size="sm" variant="outline" onClick={() => setEditing({ ...w })}>Edit</Button>
                <Button size="sm" variant="destructive" onClick={() => deleteWord(w.id)}>Delete</Button>
              </div>
            </div>
          ))}
        </div>
      </Card>

      {editing && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <Card className="gloss-panel p-6 space-y-4 w-full max-w-md shadow-lg">
            <h3 className="font-semibold text-lg">Edit Word #{editing.id}</h3>
            <div className="space-y-3">
              <Input placeholder="Word" value={editing.word} onChange={(e) => setEditing({ ...editing, word: e.target.value })} />
              <Input placeholder="Pronunciation" value={editing.pronunciation || ""} onChange={(e) => setEditing({ ...editing, pronunciation: e.target.value })} />
              <Input placeholder="Meaning" value={editing.meaning} onChange={(e) => setEditing({ ...editing, meaning: e.target.value })} />
            </div>
            <div className="flex gap-2 justify-end mt-4">
              <Button variant="outline" onClick={() => setEditing(null)}>Cancel</Button>
              <Button onClick={saveWord}>Save</Button>
            </div>
          </Card>
        </div>
      )}

      {editingMath && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <Card className="gloss-panel p-6 space-y-4 w-full max-w-2xl shadow-lg">
            <h3 className="font-semibold text-lg">Edit Math Template #{editingMath.id}</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <Input
                placeholder="Title"
                value={editingMath.title}
                onChange={(e) => setEditingMath({ ...editingMath, title: e.target.value })}
              />
              <Input
                placeholder="Topic"
                value={editingMath.topic}
                onChange={(e) => setEditingMath({ ...editingMath, topic: e.target.value })}
              />
              <select
                value={editingMath.operation}
                onChange={(e) => setEditingMath({ ...editingMath, operation: e.target.value })}
                className="h-9 rounded-md border bg-background px-3 text-sm"
              >
                <option value="add">Add</option>
                <option value="subtract">Subtract</option>
                <option value="multiply">Multiply</option>
                <option value="divide">Divide</option>
                <option value="linear_equation">Linear Equation</option>
                <option value="simplify">Simplify Like Terms</option>
              </select>
              <select
                value={editingMath.number_type}
                onChange={(e) => setEditingMath({ ...editingMath, number_type: e.target.value })}
                className="h-9 rounded-md border bg-background px-3 text-sm"
              >
                <option value="any">Any</option>
                <option value="odd">Odd</option>
                <option value="even">Even</option>
                <option value="positive">Positive</option>
                <option value="negative">Negative</option>
              </select>
              <Input
                type="number"
                placeholder="Min"
                value={editingMath.min_value}
                onChange={(e) => setEditingMath({ ...editingMath, min_value: Number(e.target.value) })}
              />
              <Input
                type="number"
                placeholder="Max"
                value={editingMath.max_value}
                onChange={(e) => setEditingMath({ ...editingMath, max_value: Number(e.target.value) })}
              />
              <Input
                type="number"
                placeholder="Decimals"
                value={editingMath.decimal_places}
                onChange={(e) => setEditingMath({ ...editingMath, decimal_places: Number(e.target.value) })}
              />
              <Input
                type="number"
                placeholder="Points"
                value={editingMath.points}
                onChange={(e) => setEditingMath({ ...editingMath, points: Number(e.target.value) })}
              />
            </div>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={editingMath.is_active}
                onChange={(e) => setEditingMath({ ...editingMath, is_active: e.target.checked })}
              />
              Active
            </label>
            <div className="flex gap-2 justify-end">
              <Button variant="outline" onClick={() => setEditingMath(null)}>Cancel</Button>
              <Button onClick={saveMathTemplate}>Save</Button>
            </div>
          </Card>
        </div>
      )}

      {creating && (
        <Card className="gloss-panel p-4 space-y-3">
          <h3 className="font-semibold">Create New Word</h3>
          <Input placeholder="Word" value={newWord.word} onChange={(e) => setNewWord({ ...newWord, word: e.target.value })} />
          <Input placeholder="Pronunciation" value={newWord.pronunciation} onChange={(e) => setNewWord({ ...newWord, pronunciation: e.target.value })} />
          <Input placeholder="Meaning" value={newWord.meaning} onChange={(e) => setNewWord({ ...newWord, meaning: e.target.value })} />
          <div className="flex gap-2">
            <Button onClick={createWord}>Create</Button>
            <Button variant="outline" onClick={() => setCreating(false)}>Cancel</Button>
          </div>
        </Card>
      )}
    </div>
  );
}
