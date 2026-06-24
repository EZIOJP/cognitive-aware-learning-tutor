import { useCallback, useEffect, useRef, useState } from "react";
import { Loader2, Send } from "lucide-react";
import { postInsightsChat, type ChatMessage } from "../../api/hubClient";
import { Button } from "../../app/components/ui/button";
import { Input } from "../../app/components/ui/input";

type AiCoachChatProps = {
  /** Seed the thread with the daily review comment. */
  initialAssistantMessage?: string;
  compact?: boolean;
  className?: string;
};

export function AiCoachChat({
  initialAssistantMessage,
  compact = false,
  className = "",
}: AiCoachChatProps) {
  const [messages, setMessages] = useState<ChatMessage[]>(() =>
    initialAssistantMessage
      ? [{ role: "assistant", content: initialAssistantMessage }]
      : [
          {
            role: "assistant",
            content: "Ask me about your study plan, sleep, vocab, or math progress.",
          },
        ],
  );
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, sending]);

  const send = useCallback(async () => {
    const text = input.trim();
    if (!text || sending) return;
    setInput("");
    setError(null);
    const next: ChatMessage[] = [...messages, { role: "user", content: text }];
    setMessages(next);
    setSending(true);
    try {
      const res = await postInsightsChat(next);
      if (!res?.reply) throw new Error("No response from coach");
      setMessages([...next, { role: "assistant", content: res.reply }]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Chat failed");
    } finally {
      setSending(false);
    }
  }, [input, messages, sending]);

  return (
    <div className={`flex flex-col min-h-0 ${className}`}>
      <div
        className={`flex-1 overflow-y-auto space-y-3 pr-1 ${
          compact ? "max-h-52" : "min-h-[320px] max-h-[60vh]"
        }`}
      >
        {messages.map((m, i) => (
          <div
            key={`${m.role}-${i}`}
            className={`text-sm rounded-lg px-3 py-2 ${
              m.role === "user"
                ? "bg-primary/15 ml-6"
                : "bg-muted/60 mr-6 text-foreground/90"
            }`}
          >
            <p className="text-[10px] uppercase tracking-wide text-muted-foreground mb-1">
              {m.role === "user" ? "You" : "Coach"}
            </p>
            <p className="leading-relaxed whitespace-pre-wrap">{m.content}</p>
          </div>
        ))}
        {sending && (
          <p className="text-xs text-muted-foreground flex items-center gap-1">
            <Loader2 className="w-3 h-3 animate-spin" /> Thinking…
          </p>
        )}
        <div ref={bottomRef} />
      </div>
      {error && <p className="text-xs text-destructive mt-2">{error}</p>}
      <form
        className="flex gap-2 mt-3 shrink-0"
        onSubmit={(e) => {
          e.preventDefault();
          void send();
        }}
      >
        <Input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask your coach…"
          className="h-9 text-sm"
          disabled={sending}
        />
        <Button type="submit" size="sm" disabled={sending || !input.trim()} aria-label="Send">
          {sending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
        </Button>
      </form>
    </div>
  );
}
