import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router";
import { Loader2, Send } from "lucide-react";
import { postHubChat, type ChatMessage, type HubChatResponse } from "../../api/hubClient";
import { loadLlmPrefs } from "../../api/transcriptsClient";
import { Button } from "../../app/components/ui/button";
import { Input } from "../../app/components/ui/input";
import { AgentPicker, type HubAgentId } from "./AgentPicker";
import { SessionUploadDropzone } from "./SessionUploadDropzone";
import { useEaster } from "../../easter";

type HubChatPanelProps = {
  className?: string;
};

export function HubChatPanel({ className = "" }: HubChatPanelProps) {
  const [agent, setAgent] = useState<HubAgentId>("auto");
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: "assistant",
      content:
        "Cortex Hub — pick an agent mode or use Auto. Attach a PDF for ephemeral Q&A, or ask about your corpus, code, or study plan.",
    },
  ]);
  const [input, setInput] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastMeta, setLastMeta] = useState<Pick<HubChatResponse, "agent_used" | "trace" | "rag_sources"> | null>(
    null,
  );
  const conversationId = useRef(`hub-${Date.now()}`);
  const bottomRef = useRef<HTMLDivElement>(null);
  const { burst } = useEaster();

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, sending]);

  useEffect(() => {
    if (file) setAgent("pdf_rag");
  }, [file]);

  const send = useCallback(async () => {
    const text = input.trim();
    if ((!text && !file) || sending) return;
    if (text.toLowerCase() === "psst") {
      setInput("");
      burst("hat");
      return;
    }
    setInput("");
    setError(null);
    const userContent = text || (file ? `[Upload ${file.name}]` : "");
    const next: ChatMessage[] = [...messages, { role: "user", content: userContent }];
    setMessages(next);
    setSending(true);
    const uploadFile = file;
    setFile(null);
    try {
      const res = await postHubChat({
        messages: next,
        agent,
        conversationId: conversationId.current,
        file: uploadFile ?? undefined,
        llm: loadLlmPrefs(),
      });
      if (!res?.reply) throw new Error("No response from hub");
      setLastMeta({
        agent_used: res.agent_used,
        trace: res.trace,
        rag_sources: res.rag_sources,
      });
      setMessages([...next, { role: "assistant", content: res.reply }]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Chat failed");
    } finally {
      setSending(false);
    }
  }, [agent, burst, file, input, messages, sending]);

  return (
    <div className={`flex flex-col min-h-0 gap-3 ${className}`}>
      <AgentPicker value={agent} onChange={setAgent} />
      <SessionUploadDropzone file={file} onFileChange={setFile} />
      <div className="flex-1 overflow-y-auto space-y-3 pr-1 min-h-[360px] max-h-[58vh]">
        {messages.map((m, i) => (
          <div
            key={`${m.role}-${i}`}
            className={`text-sm rounded-lg px-3 py-2 ${
              m.role === "user" ? "bg-primary/15 ml-8" : "bg-muted/60 mr-8 text-foreground/90"
            }`}
          >
            <p className="text-[10px] uppercase tracking-wide text-muted-foreground mb-1">
              {m.role === "user" ? "You" : "Hub"}
            </p>
            <p className="leading-relaxed whitespace-pre-wrap">{m.content}</p>
            {m.role === "assistant" && m.content.includes("/lecture-notes") ? (
              <Link to="/lecture-notes" className="text-xs text-primary hover:underline mt-2 inline-block">
                Open Lecture Notes →
              </Link>
            ) : null}
          </div>
        ))}
        {sending && (
          <p className="text-xs text-muted-foreground flex items-center gap-1">
            <Loader2 className="w-3 h-3 animate-spin" /> Routing…
          </p>
        )}
        <div ref={bottomRef} />
      </div>
      {lastMeta?.agent_used ? (
        <p className="text-[10px] text-muted-foreground">
          Agent: {lastMeta.agent_used}
          {lastMeta.trace?.length ? ` · ${lastMeta.trace.join(" → ")}` : ""}
          {lastMeta.rag_sources?.length ? ` · sources: ${lastMeta.rag_sources.slice(0, 3).join(", ")}` : ""}
        </p>
      ) : null}
      {error && <p className="text-xs text-destructive">{error}</p>}
      <form
        className="flex gap-2 shrink-0"
        onSubmit={(e) => {
          e.preventDefault();
          void send();
        }}
      >
        <Input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={
            agent === "auto"
              ? "Ask Cortex Hub…"
              : `Message (${agent})…`
          }
          className="h-9 text-sm"
          disabled={sending}
        />
        <Button type="submit" size="sm" disabled={sending || (!input.trim() && !file)} aria-label="Send">
          {sending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
        </Button>
      </form>
    </div>
  );
}
