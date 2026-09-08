import { ChevronRight } from "lucide-react";
import { cn } from "../../app/components/ui/utils";
import { breadcrumbParts } from "./studyLibraryUtils";

type Props = {
  browsePath: string;
  fileCount: number;
  folderCount: number;
  onBrowsePath: (path: string) => void;
};

export function StudyLibraryBreadcrumb({ browsePath, fileCount, folderCount, onBrowsePath }: Props) {
  const crumbs = breadcrumbParts(browsePath);

  return (
    <nav className="study-library-breadcrumb min-w-0 hidden md:flex" aria-label="Folder location">
      {crumbs.map((c, i) => (
        <span key={c.path} className="flex items-center min-w-0">
          {i > 0 ? <ChevronRight className="w-3 h-3 mx-0.5 shrink-0 opacity-50" /> : null}
          <button
            type="button"
            onClick={() => onBrowsePath(c.path)}
            className={cn(
              "truncate hover:underline text-[11px]",
              i === crumbs.length - 1 ? "text-foreground font-medium" : "text-muted-foreground",
            )}
          >
            {c.label}
          </button>
        </span>
      ))}
      <span className="study-library-breadcrumb-count ml-2 shrink-0">
        {fileCount} note{fileCount === 1 ? "" : "s"}
        {folderCount ? ` · ${folderCount} folder${folderCount === 1 ? "" : "s"}` : ""}
      </span>
    </nav>
  );
}
