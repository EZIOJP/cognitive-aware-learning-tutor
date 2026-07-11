import { Paperclip, X } from "lucide-react";

type SessionUploadDropzoneProps = {
  file: File | null;
  onFileChange: (file: File | null) => void;
};

export function SessionUploadDropzone({ file, onFileChange }: SessionUploadDropzoneProps) {
  return (
    <div className="flex items-center gap-2">
      <label className="cursor-pointer inline-flex items-center gap-1.5 rounded-md border border-input bg-background px-3 py-1.5 text-xs font-medium hover:bg-accent">
        <input
          type="file"
          className="hidden"
          accept=".pdf,application/pdf,text/plain"
          onChange={(e) => onFileChange(e.target.files?.[0] ?? null)}
        />
        <Paperclip className="w-3.5 h-3.5" />
        Attach PDF
      </label>
      {file ? (
        <span className="text-xs text-muted-foreground flex items-center gap-1">
          {file.name}
          <button
            type="button"
            className="text-destructive hover:opacity-80"
            onClick={() => onFileChange(null)}
            aria-label="Remove file"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </span>
      ) : (
        <span className="text-xs text-muted-foreground">Ephemeral — not saved to corpus</span>
      )}
    </div>
  );
}
