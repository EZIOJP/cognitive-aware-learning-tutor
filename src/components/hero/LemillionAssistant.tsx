import { cn } from "../../app/components/ui/utils";

interface LemillionAssistantProps {
  message?: string;
  className?: string;
}

const DEFAULT_MSG =
  "Phase complete. Your study rhythm is building — keep the momentum.";

export function LemillionAssistant({
  message = DEFAULT_MSG,
  className,
}: LemillionAssistantProps) {
  return (
    <div className={cn("lemillion-bubble relative", className)}>
      <p className="hero-label text-primary mb-1">Lemillion</p>
      <p className="hero-body text-sm leading-relaxed">{message}</p>
    </div>
  );
}
