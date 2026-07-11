import { Code2, FileText, Globe, MessageSquare, Rocket, Sparkles, Zap } from "lucide-react";
import { Button } from "../../app/components/ui/button";

export type HubAgentId =
  | "auto"
  | "chat"
  | "coding"
  | "corpus"
  | "search"
  | "pdf_rag"
  | "study";

const AGENTS: { id: HubAgentId; label: string; icon: typeof Zap }[] = [
  { id: "auto", label: "Auto", icon: Zap },
  { id: "chat", label: "Chat", icon: MessageSquare },
  { id: "coding", label: "Coding", icon: Code2 },
  { id: "corpus", label: "Corpus", icon: Sparkles },
  { id: "search", label: "Search", icon: Globe },
  { id: "pdf_rag", label: "PDF", icon: FileText },
  { id: "study", label: "Study", icon: Rocket },
];

type AgentPickerProps = {
  value: HubAgentId;
  onChange: (id: HubAgentId) => void;
};

export function AgentPicker({ value, onChange }: AgentPickerProps) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {AGENTS.map(({ id, label, icon: Icon }) => (
        <Button
          key={id}
          type="button"
          size="sm"
          variant={value === id ? "default" : "outline"}
          className="h-8 gap-1.5 text-xs"
          onClick={() => onChange(id)}
        >
          <Icon className="w-3.5 h-3.5" />
          {label}
        </Button>
      ))}
    </div>
  );
}
