import { AlertCircle, X, Lightbulb } from "lucide-react";
import { Button } from "./ui/button";
import { Card } from "./ui/card";
import { motion, AnimatePresence } from "motion/react";

interface AITutorInterventionProps {
  isVisible: boolean;
  intervention: {
    message: string;
    question: string;
    detectedConcept: string;
    latex?: string;
    incompleteStep?: boolean;
    confidence?: number;
  } | null;
  onDismiss: () => void;
  onRespond: (response: string) => void;
}

export function AITutorIntervention({
  isVisible,
  intervention,
  onDismiss,
  onRespond,
}: AITutorInterventionProps) {
  if (!intervention) return null;

  return (
    <AnimatePresence>
      {isVisible && (
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -20 }}
          transition={{ duration: 0.3 }}
          className="fixed top-4 left-1/2 transform -translate-x-1/2 z-50 w-full max-w-2xl px-4"
        >
          <Card className="p-6 shadow-2xl border-2 border-amber-500 dark:border-amber-600">
            <div className="flex items-start gap-4">
              <div className="p-3 bg-amber-100 dark:bg-amber-900 rounded-full">
                <Lightbulb className="w-6 h-6 text-amber-600 dark:text-amber-400" />
              </div>

              <div className="flex-1">
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <h3 className="font-semibold flex items-center gap-2">
                      AI Tutor Intervention
                      <AlertCircle className="w-4 h-4 text-amber-600" />
                    </h3>
                    <p className="text-sm text-muted-foreground mt-1">
                      Detected concept: <span className="font-medium text-foreground">{intervention.detectedConcept}</span>
                    </p>
                  </div>
                  <Button onClick={onDismiss} variant="ghost" size="sm">
                    <X className="w-4 h-4" />
                  </Button>
                </div>

                <div className="space-y-3">
                  {intervention.latex ? (
                    <div className="p-2 rounded-md border bg-background/80">
                      <p className="text-xs text-muted-foreground mb-1">
                        Recognized from your board
                        {intervention.incompleteStep ? " (incomplete step)" : ""}
                        {typeof intervention.confidence === "number"
                          ? ` · ${Math.round(intervention.confidence * 100)}%`
                          : ""}
                      </p>
                      <code className="text-sm font-mono break-all">{intervention.latex}</code>
                    </div>
                  ) : null}
                  <p className="text-sm">{intervention.message}</p>
                  <div className="p-3 bg-muted rounded-lg">
                    <p className="text-sm font-medium">{intervention.question}</p>
                  </div>

                  <div className="flex gap-2 flex-wrap">
                    <Button
                      onClick={() => onRespond("cross-multiplication")}
                      variant="outline"
                      size="sm"
                    >
                      Cross-multiplication
                    </Button>
                    <Button
                      onClick={() => onRespond("negative-signs")}
                      variant="outline"
                      size="sm"
                    >
                      Negative signs
                    </Button>
                    <Button
                      onClick={() => onRespond("setup")}
                      variant="outline"
                      size="sm"
                    >
                      Matrix setup
                    </Button>
                    <Button
                      onClick={() => onRespond("other")}
                      variant="secondary"
                      size="sm"
                    >
                      Something else
                    </Button>
                  </div>
                </div>
              </div>
            </div>
          </Card>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
