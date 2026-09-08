import { Link } from "react-router";
import { Button } from "../../../app/components/ui/button";
import { Switch } from "../../../app/components/ui/switch";
import { ACTIVE_TAG_CAP, type StudyLoopPrefs } from "./activeTagsStorage";

export type LegacyTool =
  | "due"
  | "loop"
  | "start"
  | "decks"
  | "create"
  | "results";

type Props = {
  prefs: StudyLoopPrefs;
  onPrefsChange: (next: StudyLoopPrefs) => void;
  dueCount: number;
  onOpenTool: (tool: LegacyTool) => void;
};

export function SettingsTab({ prefs, onPrefsChange, dueCount, onOpenTool }: Props) {
  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-sm font-semibold">Settings</h2>
        <p className="text-xs text-muted-foreground mt-0.5">
          Board prefs (local) · links to Due, flash decks, and legacy starters.
        </p>
      </div>

      <div className="gloss-panel rounded-xl p-4 space-y-4">
        <h3 className="text-sm font-medium">Focus &amp; fluency</h3>

        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-sm font-medium">Active topic cap</p>
            <p className="text-xs text-muted-foreground">Soft cognitive-load limit</p>
          </div>
          <span className="text-sm rounded-full border border-primary/40 bg-primary/10 px-2.5 py-0.5 text-primary">
            {ACTIVE_TAG_CAP}
          </span>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-sm font-medium">FSRS under Active Topics</p>
            <p className="text-xs text-muted-foreground">Ready-to-review block on Learn</p>
          </div>
          <Switch
            checked={prefs.showFsrsUnderActive}
            onCheckedChange={(v) =>
              onPrefsChange({ ...prefs, showFsrsUnderActive: Boolean(v) })
            }
          />
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-sm font-medium">Speed fluency UI</p>
            <p className="text-xs text-muted-foreground">
              Reserved for R/C/S speed % when the API exposes it
            </p>
          </div>
          <Switch
            checked={prefs.speedFluencyUi}
            onCheckedChange={(v) => onPrefsChange({ ...prefs, speedFluencyUi: Boolean(v) })}
          />
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-sm font-medium">Progress rails</p>
            <p className="text-xs text-muted-foreground">
              Full topic list (deferred until R/C/S metrics ship)
            </p>
          </div>
          <Switch
            checked={prefs.showProgressRails}
            onCheckedChange={(v) =>
              onPrefsChange({ ...prefs, showProgressRails: Boolean(v) })
            }
          />
        </div>
      </div>

      <div className="gloss-panel rounded-xl p-4 space-y-3">
        <h3 className="text-sm font-medium">More tools</h3>
        <p className="text-xs text-muted-foreground">
          Legacy Study Loop surfaces — Due queue, flash decks, create, results, today&apos;s path.
        </p>
        <div className="flex flex-wrap gap-2">
          <Button size="sm" variant="outline" onClick={() => onOpenTool("due")}>
            Due queue (full list)
          </Button>
          <Button size="sm" variant="outline" onClick={() => onOpenTool("start")}>
            Quick start drills
          </Button>
          <Button size="sm" variant="outline" onClick={() => onOpenTool("decks")}>
            Flash decks
          </Button>
          <Button size="sm" variant="outline" onClick={() => onOpenTool("create")}>
            Create deck
          </Button>
          <Button size="sm" variant="outline" onClick={() => onOpenTool("results")}>
            Results
          </Button>
        </div>
        <p className="text-xs text-muted-foreground pt-1">
          <Link to="/lecture-notes" className="text-primary hover:underline">
            Lecture Notes
          </Link>
          {" · "}
          <Link to="/gre-vocab" className="text-primary hover:underline">
            GRE Vocab
          </Link>
        </p>
      </div>
    </div>
  );
}
