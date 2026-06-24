import { useCallback, useEffect, useRef, useState } from "react";
import { FolderOpen, Loader2, Send, Sparkles } from "lucide-react";
import {
  fetchAgentFiles,
  postProjectAgentChat,
  type AgentSnapshot,
  type ChatMessage,
} from "../../api/hubClient";
import { Button } from "../../app/components/ui/button";
import { Input } from "../../app/components/ui/input";

const QUICK_PROMPTS = [
  "What is incomplete in the lecture pipeline? Give Cursor tasks.",
  "Audit top CSS classes — what should we consolidate?",
  "List the 5 highest-impact fixes to finish this website.",
  "Which files handle quiz + FSRS review? What is missing?",
  "How do live captions, notes, and snapshots connect? Gaps?",
];

type ProjectAgentChatProps = {
  snapshot: AgentSnapshot | null;
  className?: string;
};

export function ProjectAgentChat({ snapshot, className = "" }: ProjectAgentChatProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: "assistant",
      content:
        "I'm your Project Agent (Gemma + codebase access). I read real files, routes, and CSS from this repo. " +
        "Ask me what to build next — I'll give you small tasks you can paste into Cursor.",
    },
  ]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [browseOpen, setBrowseOpen] = useState(false);
  const [browseFiles, setBrowseFiles] = useState<string[]>([]);
  const [browseLoading, setBrowseLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, sending]);

  const send = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || sending) return;
      setInput("");
      setError(null);
      const next: ChatMessage[] = [...messages, { role: "user", content: trimmed }];
      setMessages(next);
      setSending(true);
      try {
        const res = await postProjectAgentChat(next);
        if (!res?.reply) throw new Error("No response from Project Agent");
        setMessages([...next, { role: "assistant", content: res.reply }]);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Chat failed");
      } finally {
        setSending(false);
      }
    },
    [messages, sending],
  );

  const openBrowse = useCallback(async () => {
    setBrowseOpen((v) => !v);
    if (browseFiles.length > 0) return;
    setBrowseLoading(true);
    try {
      const files = await fetchAgentFiles();
      setBrowseFiles(files);
    } finally {
      setBrowseLoading(false);
    }
  }, [browseFiles.length]);

  const attachFile = useCallback((path: string) => {
    setInput((prev) => (prev ? `${prev}\n\nInclude context from: ${path}` : `Include context from: ${path}`));
    setBrowseOpen(false);
  }, []);

  return (
    <div className={`flex flex-col min-h-0 gap-3 ${className}`}>
      {snapshot && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-center text-[10px] shrink-0">
          <div className="rounded-lg bg-muted/40 px-2 py-2">
            <p className="text-base font-bold text-primary">{snapshot.scanned_files}</p>
            <p className="text-muted-foreground">Files indexed</p>
          </div>
          <div className="rounded-lg bg-muted/40 px-2 py-2">
            <p className="text-base font-bold">{snapshot.frontend_routes?.length ?? 0}</p>
            <p className="text-muted-foreground">UI routes</p>
          </div>
          <div className="rounded-lg bg-muted/40 px-2 py-2">
            <p className="text-base font-bold">{snapshot.api_route_count ?? 0}</p>
            <p className="text-muted-foreground">API routes</p>
          </div>
          <div className="rounded-lg bg-muted/40 px-2 py-2">
            <p className="text-base font-bold">{snapshot.open_todos?.length ?? 0}</p>
            <p className="text-muted-foreground">Open TODOs</p>
          </div>
        </div>
      )}

      <div className="flex flex-wrap gap-1.5 shrink-0">
        {QUICK_PROMPTS.map((p) => (
          <button
            key={p}
            type="button"
            disabled={sending}
            onClick={() => void send(p)}
            className="text-[10px] rounded-full border border-border/60 bg-muted/30 px-2.5 py-1 hover:bg-muted/60 disabled:opacity-50 text-left"
          >
            {p.length > 48 ? `${p.slice(0, 48)}…` : p}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto space-y-3 pr-1 min-h-[280px] max-h-[55vh]">
        {messages.map((m, i) => (
          <div
            key={`${m.role}-${i}`}
            className={`text-sm rounded-lg px-3 py-2 ${
              m.role === "user" ? "bg-primary/15 ml-4" : "bg-muted/60 mr-4 text-foreground/90"
            }`}
          >
            <p className="text-[10px] uppercase tracking-wide text-muted-foreground mb-1 flex items-center gap-1">
              {m.role === "user" ? (
                "You"
              ) : (
                <>
                  <Sparkles className="h-3 w-3" /> Project Agent (Gemma)
                </>
              )}
            </p>
            <p className="leading-relaxed whitespace-pre-wrap">{m.content}</p>
          </div>
        ))}
        {sending && (
          <p className="text-xs text-muted-foreground flex items-center gap-1">
            <Loader2 className="h-3 w-3 animate-spin" /> Reading codebase + thinking…
          </p>
        )}
        <div ref={bottomRef} />
      </div>

      {error && <p className="text-xs text-destructive shrink-0">{error}</p>}

      <form
        className="flex flex-col gap-2 shrink-0"
        onSubmit={(e) => {
          e.preventDefault();
          void send(input);
        }}
      >
        <div className="flex gap-2">
          <Button type="button" variant="outline" size="sm" disabled={sending} onClick={() => void openBrowse()}>
            <FolderOpen className="h-3.5 w-3.5 mr-1" />
            Browse files
          </Button>
        </div>
        {browseOpen && (
          <div className="max-h-32 overflow-y-auto rounded-lg border bg-muted/30 p-2 text-xs space-y-1">
            {browseLoading && (
              <p className="text-muted-foreground flex items-center gap-1">
                <Loader2 className="h-3 w-3 animate-spin" /> Loading…
              </p>
            )}
            {!browseLoading &&
              browseFiles.map((path) => (
                <button
                  key={path}
                  type="button"
                  className="block w-full text-left truncate hover:text-primary"
                  onClick={() => attachFile(path)}
                >
                  {path}
                </button>
              ))}
          </div>
        )}
        <div className="flex gap-2">
        <Input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about files, CSS, routes, or what to fix next…"
          disabled={sending}
          className="text-sm"
        />
        <Button type="submit" size="icon" disabled={sending || !input.trim()}>
          <Send className="h-4 w-4" />
        </Button>
        </div>
      </form>
    </div>
  );
}
