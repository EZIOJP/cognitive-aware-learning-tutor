import { AlertCircle, X, Lightbulb } from "lucide-react";
import { useState } from "react";
import { Button } from "./ui/button";
import { Card } from "./ui/card";
import { Input } from "./ui/input";
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
    structuralConfidence?: number;
    tutorSilent?: boolean;
    sessionSnapshotId?: string;
  } | null;
  onDismiss: () => void;
  onRespond: (response: string) => void;
  onConfirmLatex?: () => void;
  onCorrectLatex?: (latex: string) => void;
}

export function AITutorIntervention({
  isVisible,
  intervention,
  onDismiss,
  onRespond,
  onConfirmLatex,
  onCorrectLatex,
}: AITutorInterventionProps) {
  const [editing, setEditing] = useState(false);
  const [fixLatex, setFixLatex] = useState("");

  if (!intervention) return null;

  // Tutor silence: no interrupt mid-flow when backend suppressed the hint.
  if (intervention.tutorSilent && !(intervention.message || "").trim()) {
    return null;
  }

  const lowStruct =
    typeof intervention.structuralConfidence === "number" &&
    intervention.structuralConfidence < 0.45;
  const lowConf =
    typeof intervention.confidence === "number" && intervention.confidence < 0.45;
  const showConfirm = Boolean(intervention.latex) && (lowConf || lowStruct || !intervention.tutorSilent);

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
                      Detected concept:{" "}
                      <span className="font-medium text-foreground">
                        {intervention.detectedConcept}
                      </span>
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
                        I read this as
                        {intervention.incompleteStep ? " (incomplete step)" : ""}
                        {typeof intervention.confidence === "number"
                          ? ` · ${Math.round(intervention.confidence * 100)}%`
                          : ""}
                        {typeof intervention.structuralConfidence === "number"
                          ? ` · structure ${Math.round(intervention.structuralConfidence * 100)}%`
                          : ""}
                      </p>
                      <code className="text-sm font-mono break-all">{intervention.latex}</code>
                      {showConfirm && (
                        <div className="flex flex-wrap gap-2 mt-2">
                          <Button
                            size="sm"
                            variant="default"
                            onClick={() => onConfirmLatex?.()}
                          >
                            Yes, that&apos;s right
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => {
                              setFixLatex(intervention.latex || "");
                              setEditing(true);
                            }}
                          >
                            Fix reading…
                          </Button>
                        </div>
                      )}
                      {editing && (
                        <div className="flex gap-2 mt-2">
                          <Input
                            value={fixLatex}
                            onChange={(e) => setFixLatex(e.target.value)}
                            placeholder="Correct LaTeX"
                            className="font-mono text-sm"
                          />
                          <Button
                            size="sm"
                            onClick={() => {
                              if (fixLatex.trim()) onCorrectLatex?.(fixLatex.trim());
                              setEditing(false);
                            }}
                          >
                            Save
                          </Button>
                        </div>
                      )}
                    </div>
                  ) : null}
                  {intervention.message ? (
                    <p className="text-sm">{intervention.message}</p>
                  ) : null}
                  {intervention.question ? (
                    <div className="p-3 bg-muted rounded-lg">
                      <p className="text-sm font-medium">{intervention.question}</p>
                    </div>
                  ) : null}

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
                    <Button onClick={() => onRespond("setup")} variant="outline" size="sm">
                      Matrix setup
                    </Button>
                    <Button onClick={() => onRespond("other")} variant="secondary" size="sm">
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
