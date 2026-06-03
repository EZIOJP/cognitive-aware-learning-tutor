import { useCallback, useState } from "react";
import type { CycleGroupStart, CyclePhase, QuizResults } from "../types";
import type { WordWithProgress } from "../../types";
import {
  getLowMasteryFromAttempts,
  markGroupStudied,
} from "../cycleService";
import { CycleDashboard } from "./CycleDashboard";
import { CycleReadStep } from "./CycleReadStep";
import { CycleQuizStep } from "./CycleQuizStep";
import { CycleReportStep } from "./CycleReportStep";
import { LowMasteryPrompt } from "./LowMasteryPrompt";

const MAX_LOW_CYCLES = 5;

export function CycleManager() {
  const [phase, setPhase] = useState<CyclePhase>("dashboard");
  const [group, setGroup] = useState<CycleGroupStart | null>(null);
  const [activeWords, setActiveWords] = useState<WordWithProgress[]>([]);
  const [quizResults, setQuizResults] = useState<QuizResults | null>(null);
  const [lowMasteryWords, setLowMasteryWords] = useState<WordWithProgress[]>([]);
  const [completedCycles, setCompletedCycles] = useState(0);
  const [isLowMasteryFlow, setIsLowMasteryFlow] = useState(false);

  const resetToDashboard = useCallback(() => {
    setPhase("dashboard");
    setGroup(null);
    setActiveWords([]);
    setQuizResults(null);
    setLowMasteryWords([]);
    setCompletedCycles(0);
    setIsLowMasteryFlow(false);
  }, []);

  const handleStartCycle = useCallback((data: CycleGroupStart) => {
    setGroup(data);
    setActiveWords(data.words);
    setQuizResults(null);
    setLowMasteryWords([]);
    setCompletedCycles(0);
    setIsLowMasteryFlow(false);
    setPhase("reading");
  }, []);

  const handleReadingComplete = useCallback((words: WordWithProgress[]) => {
    setActiveWords(words);
    setPhase("quiz");
  }, []);

  const handleQuizComplete = useCallback(
    (results: QuizResults) => {
      setQuizResults(results);
      const low = getLowMasteryFromAttempts(results.attempts, activeWords);
      setLowMasteryWords(low);
      setCompletedCycles((c) => c + 1);
      setPhase(isLowMasteryFlow ? "low_mastery_report" : "report");
    },
    [activeWords, isLowMasteryFlow]
  );

  const handleReportContinue = useCallback(() => {
    if (!isLowMasteryFlow && lowMasteryWords.length > 0) {
      setPhase("low_mastery_prompt");
      return;
    }
    if (group) markGroupStudied(group.groupNumber);
    resetToDashboard();
  }, [isLowMasteryFlow, lowMasteryWords.length, group, resetToDashboard]);

  const handleStartLowMasteryReview = useCallback(() => {
    setActiveWords(lowMasteryWords);
    setIsLowMasteryFlow(true);
    setPhase("low_mastery_reading");
  }, [lowMasteryWords]);

  const handleLowMasteryPrompt = useCallback(
    (repeat: boolean) => {
      if (repeat && completedCycles < MAX_LOW_CYCLES) {
        handleStartLowMasteryReview();
      } else {
        if (group) markGroupStudied(group.groupNumber);
        resetToDashboard();
      }
    },
    [completedCycles, handleStartLowMasteryReview, group, resetToDashboard]
  );

  if (!group && phase !== "dashboard") {
    resetToDashboard();
    return <CycleDashboard onStartCycle={handleStartCycle} />;
  }

  switch (phase) {
    case "dashboard":
      return <CycleDashboard onStartCycle={handleStartCycle} />;

    case "reading":
      return (
        <CycleReadStep
          words={activeWords}
          groupNumber={group!.groupNumber}
          isLowMastery={false}
          onComplete={handleReadingComplete}
          onBack={resetToDashboard}
        />
      );

    case "quiz":
      return (
        <CycleQuizStep
          words={activeWords}
          groupNumber={group!.groupNumber}
          isLowMastery={isLowMasteryFlow}
          onComplete={handleQuizComplete}
          onBack={resetToDashboard}
        />
      );

    case "report":
      return quizResults ? (
        <CycleReportStep
          results={quizResults}
          isLowMasteryMode={false}
          lowMasteryWords={lowMasteryWords}
          onStartLowMastery={handleStartLowMasteryReview}
          onContinue={handleReportContinue}
          onBack={resetToDashboard}
        />
      ) : null;

    case "low_mastery_prompt":
      return (
        <LowMasteryPrompt
          words={lowMasteryWords}
          cycleCount={completedCycles}
          maxCycles={MAX_LOW_CYCLES}
          onRepeat={() => handleLowMasteryPrompt(true)}
          onSkip={() => handleLowMasteryPrompt(false)}
          onBack={resetToDashboard}
        />
      );

    case "low_mastery_reading":
      return (
        <CycleReadStep
          words={activeWords}
          groupNumber={group!.groupNumber}
          isLowMastery={true}
          onComplete={handleReadingComplete}
          onBack={resetToDashboard}
        />
      );

    case "low_mastery_quiz":
      return (
        <CycleQuizStep
          words={activeWords}
          groupNumber={group!.groupNumber}
          isLowMastery={true}
          onComplete={handleQuizComplete}
          onBack={resetToDashboard}
        />
      );

    case "low_mastery_report":
      return quizResults ? (
        <CycleReportStep
          results={quizResults}
          isLowMasteryMode={true}
          lowMasteryWords={getLowMasteryFromAttempts(
            quizResults.attempts,
            activeWords
          )}
          onStartLowMastery={() => {
            const stillLow = getLowMasteryFromAttempts(
              quizResults.attempts,
              activeWords
            );
            setLowMasteryWords(stillLow);
            if (stillLow.length > 0 && completedCycles < MAX_LOW_CYCLES) {
              setPhase("low_mastery_prompt");
            } else {
              if (group) markGroupStudied(group.groupNumber);
              resetToDashboard();
            }
          }}
          onContinue={() => {
            const stillLow = getLowMasteryFromAttempts(
              quizResults.attempts,
              activeWords
            );
            setLowMasteryWords(stillLow);
            if (stillLow.length > 0 && completedCycles < MAX_LOW_CYCLES) {
              setPhase("low_mastery_prompt");
            } else {
              if (group) markGroupStudied(group.groupNumber);
              resetToDashboard();
            }
          }}
          onBack={resetToDashboard}
        />
      ) : null;

    default:
      return <CycleDashboard onStartCycle={handleStartCycle} />;
  }
}
