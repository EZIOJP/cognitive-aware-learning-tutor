import type { WordWithProgress } from "../../types";
import { Badge } from "../../../../app/components/ui/badge";
import { Card } from "../../../../app/components/ui/card";

interface WordCardProps {
  word: WordWithProgress;
}

function masteryVariant(mastery: number) {
  if (mastery < 0) return "destructive" as const;
  if (mastery <= 2) return "secondary" as const;
  if (mastery <= 5) return "default" as const;
  return "outline" as const;
}

export function WordCard({ word }: WordCardProps) {
  const breakdown = word.word_breakdown;

  return (
    <Card className="gloss-panel h-full flex flex-col overflow-hidden border-0 shadow-lg">
      <header className="shrink-0 px-5 py-4 border-b border-border/60 bg-gradient-to-r from-blue-50/80 to-violet-50/50 dark:from-zinc-900/80 dark:to-zinc-800/50">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 className="text-2xl sm:text-3xl font-bold tracking-tight break-words">
              {word.word}
            </h2>
            {word.pronunciation && (
              <p className="text-muted-foreground italic mt-1">
                /{word.pronunciation}/
              </p>
            )}
          </div>
          <div className="flex flex-wrap gap-2 shrink-0">
            <Badge variant={masteryVariant(word.mastery)} className="font-mono tabular-nums min-w-[3rem] justify-center">
              M{word.mastery}
            </Badge>
            <Badge variant="outline">G{word.group_number}</Badge>
            {word.is_due && (
              <Badge variant="destructive" className="text-[10px]">
                Due
              </Badge>
            )}
          </div>
        </div>
      </header>

      <div className="flex-1 overflow-y-auto p-5 space-y-5">
        <section>
          <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-1">
            Meaning
          </h3>
          <p className="text-base leading-relaxed">{word.meaning}</p>
        </section>

        {word.story_mnemonic && (
          <section className="rounded-xl bg-amber-50/80 dark:bg-amber-950/30 p-4 border border-amber-200/50 dark:border-amber-800/40">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-amber-800 dark:text-amber-200 mb-1">
              Mnemonic
            </h3>
            <p className="text-sm leading-relaxed">{word.story_mnemonic}</p>
          </section>
        )}

        {word.etymology && (
          <section>
            <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-1">
              Etymology
            </h3>
            <p className="text-sm text-muted-foreground leading-relaxed">
              {word.etymology}
            </p>
          </section>
        )}

        {breakdown && (breakdown.prefix || breakdown.root || breakdown.suffix) && (
          <section className="flex flex-wrap gap-2">
            {breakdown.prefix && (
              <Badge variant="secondary">Prefix: {breakdown.prefix}</Badge>
            )}
            {breakdown.root && (
              <Badge variant="secondary">Root: {breakdown.root}</Badge>
            )}
            {breakdown.suffix && (
              <Badge variant="secondary">Suffix: {breakdown.suffix}</Badge>
            )}
          </section>
        )}

        {word.synonyms && word.synonyms.length > 0 && (
          <section>
            <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">
              Synonyms
            </h3>
            <div className="flex flex-wrap gap-1.5">
              {word.synonyms.map((s) => (
                <Badge key={s} variant="outline" className="font-normal">
                  {s}
                </Badge>
              ))}
            </div>
          </section>
        )}

        {word.antonyms && word.antonyms.length > 0 && (
          <section>
            <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">
              Antonyms
            </h3>
            <div className="flex flex-wrap gap-1.5">
              {word.antonyms.map((a) => (
                <Badge key={a} variant="outline" className="font-normal">
                  {a}
                </Badge>
              ))}
            </div>
          </section>
        )}

        {word.examples && word.examples.length > 0 && (
          <section>
            <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">
              Examples
            </h3>
            <ul className="space-y-2">
              {word.examples.slice(0, 3).map((ex, i) => (
                <li
                  key={i}
                  className="text-sm pl-3 border-l-2 border-primary/30 leading-relaxed"
                >
                  {ex.text}
                </li>
              ))}
            </ul>
          </section>
        )}
      </div>
    </Card>
  );
}
