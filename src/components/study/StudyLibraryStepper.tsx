import { cn } from "../../app/components/ui/utils";

const STEPS = ["1. Select Files", "2. Gap Analysis", "3. Review & Sync"] as const;

export type StudyWorkflowStep = 0 | 1 | 2;

type Props = {
  step: StudyWorkflowStep;
  onStepChange?: (step: StudyWorkflowStep) => void;
};

export function StudyLibraryStepper({ step, onStepChange }: Props) {
  return (
    <div className="study-library-glass flex h-12 overflow-hidden p-1 shrink-0">
      {STEPS.map((label, index) => (
        <button
          key={label}
          type="button"
          onClick={() => onStepChange?.(index as StudyWorkflowStep)}
          className={cn(
            "study-library-step flex-1 flex items-center justify-center text-xs font-medium rounded-lg transition-colors",
            onStepChange && "hover:bg-white/5 cursor-pointer",
          )}
          data-active={step === index}
        >
          {label}
        </button>
      ))}
    </div>
  );
}
