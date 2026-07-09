import { Link } from "react-router";
import { ScrollText } from "lucide-react";
import { StudyLibraryLogPanel } from "../../components/study/StudyLibraryLogPanel";
import "../../styles/study-library.css";

export function SystemLogsPage() {
  return (
    <div className="min-h-full study-library-page text-emerald-50">
      <div className="max-w-5xl mx-auto px-4 py-6 space-y-6">
        <header className="space-y-2">
          <div className="flex items-center gap-2 text-emerald-300/80 text-sm">
            <ScrollText className="size-4" />
            <span>Diagnostics</span>
          </div>
          <h1 className="text-2xl font-semibold tracking-tight">App logs</h1>
          <p className="text-sm text-emerald-100/70 max-w-2xl leading-relaxed">
            One place to read backend, note generation, corpus build, and Transcript Studio logs.
            When something fails, check here before guessing.
          </p>
          <div className="flex flex-wrap gap-3 text-xs">
            <Link to="/lecture-notes" className="text-emerald-300 hover:underline">
              Lecture Notes
            </Link>
            <Link to="/knowledge-base" className="text-emerald-300 hover:underline">
              Knowledge Base
            </Link>
          </div>
        </header>

        <StudyLibraryLogPanel defaultFile="backend.log" live pollMs={5000} maxLines={400} />

        <StudyLibraryLogPanel
          title="Note generation log"
          defaultFile="notes_generation.log"
          live
          pollMs={5000}
          maxLines={300}
        />
      </div>
    </div>
  );
}
