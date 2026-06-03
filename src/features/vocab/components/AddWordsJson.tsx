import { useMemo, useState } from "react";
import { useAuth } from "../../../context/AuthContext";
import { authFetch } from "../api/authClient";
import { Button } from "../../../app/components/ui/button";
import { Textarea } from "../../../app/components/ui/textarea";
import { Badge } from "../../../app/components/ui/badge";

const isNonEmpty = (v: unknown) => typeof v === "string" && v.trim().length > 0;

function validateEntry(entry: Record<string, unknown>) {
  const errors: string[] = [];
  if (!isNonEmpty(entry.word)) errors.push("word required");
  if (!isNonEmpty(entry.meaning)) errors.push("meaning required");
  return errors;
}

function normalizeEntry(raw: Record<string, unknown>) {
  return {
    word: String(raw.word ?? "").trim(),
    meaning: String(raw.meaning ?? "").trim(),
    pronunciation: String(raw.pronunciation ?? "").trim() || undefined,
    story_mnemonic: String(raw.story_mnemonic ?? "").trim() || undefined,
    etymology: String(raw.etymology ?? "").trim() || undefined,
    examples: Array.isArray(raw.examples) ? raw.examples : [],
    synonyms: Array.isArray(raw.synonyms) ? raw.synonyms : [],
    antonyms: Array.isArray(raw.antonyms) ? raw.antonyms : [],
    tags: Array.isArray(raw.tags) ? raw.tags : [],
  };
}

export function AddWordsJson() {
  const { token, isAdmin } = useAuth();
  const [jsonInput, setJsonInput] = useState("");
  const [parsed, setParsed] = useState<Record<string, unknown>[]>([]);
  const [preview, setPreview] = useState(false);
  const [onlyValid, setOnlyValid] = useState(true);
  const [status, setStatus] = useState<{ type: "ok" | "err"; message: string } | null>(null);
  const [busy, setBusy] = useState(false);

  const validations = useMemo(
    () => parsed.map((w) => validateEntry(w)),
    [parsed]
  );

  const validRows = useMemo(
    () =>
      parsed
        .map((w, i) => ({ raw: w, ok: validations[i].length === 0 }))
        .filter((x) => x.ok)
        .map((x) => normalizeEntry(x.raw)),
    [parsed, validations]
  );

  const handlePreview = () => {
    try {
      const data = JSON.parse(jsonInput);
      const arr = Array.isArray(data) ? data : [data];
      setParsed(arr);
      setPreview(true);
      setStatus(null);
    } catch (e) {
      setPreview(false);
      setParsed([]);
      setStatus({
        type: "err",
        message: e instanceof Error ? e.message : "Invalid JSON",
      });
    }
  };

  const handleSubmit = async () => {
    if (!isAdmin) {
      setStatus({ type: "err", message: "Admin login required to import words." });
      return;
    }
    const payload = onlyValid ? validRows : parsed.map((w) => normalizeEntry(w));
    if (!payload.length) {
      setStatus({ type: "err", message: "Nothing to submit." });
      return;
    }
    setBusy(true);
    try {
      const { data } = await authFetch(
        "/words/import/json",
        token,
        { method: "POST", body: JSON.stringify({ words: payload }) }
      );
      setStatus({
        type: "ok",
        message: `Added ${data.added ?? 0}, skipped ${data.skipped ?? 0} (total ${data.total_words ?? "?"})`,
      });
      setJsonInput("");
      setParsed([]);
      setPreview(false);
    } catch (e) {
      setStatus({
        type: "err",
        message: e instanceof Error ? e.message : "Import failed",
      });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="gloss-panel rounded-2xl p-6 max-w-4xl">
      <h2 className="text-xl font-semibold mb-2">Add words via JSON</h2>
      <p className="text-sm text-muted-foreground mb-4">
        Paste one object or an array. Required: <code>word</code>, <code>meaning</code>.
        Imports via <code>POST /words/import/json</code> (admin).
      </p>
      {!isAdmin && (
        <p className="text-sm text-amber-700 dark:text-amber-300 mb-3">
          Sign in as admin to submit. Preview still works.
        </p>
      )}
      <Textarea
        className="font-mono min-h-[200px]"
        placeholder='{"word":"...","meaning":"..."}'
        value={jsonInput}
        onChange={(e) => setJsonInput(e.target.value)}
      />
      <div className="mt-3 flex flex-wrap gap-2 items-center">
        <Button type="button" variant="secondary" onClick={handlePreview}>
          Preview
        </Button>
        {preview && (
          <>
            <Button type="button" onClick={handleSubmit} disabled={busy || !isAdmin}>
              {busy ? "Submitting…" : "Confirm & submit"}
            </Button>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={onlyValid}
                onChange={(e) => setOnlyValid(e.target.checked)}
              />
              Only valid rows
            </label>
            <Badge variant="outline">{validRows.length} valid</Badge>
            <Badge variant="outline">{parsed.length - validRows.length} invalid</Badge>
          </>
        )}
      </div>
      {preview && parsed.length > 0 && (
        <div className="mt-4 overflow-auto max-h-64 border rounded-lg text-sm">
          <table className="w-full">
            <thead>
              <tr className="border-b bg-muted/50">
                <th className="p-2 text-left">Word</th>
                <th className="p-2 text-left">Meaning</th>
                <th className="p-2 text-left">OK</th>
              </tr>
            </thead>
            <tbody>
              {parsed.map((w, i) => (
                <tr key={i} className="border-b">
                  <td className="p-2">{String(w.word ?? "—")}</td>
                  <td className="p-2">{String(w.meaning ?? "—").slice(0, 80)}</td>
                  <td className="p-2">
                    {validations[i].length === 0 ? "✓" : validations[i].join("; ")}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {status && (
        <p
          className={`mt-3 text-sm ${status.type === "ok" ? "text-emerald-600" : "text-destructive"}`}
        >
          {status.message}
        </p>
      )}
    </div>
  );
}
