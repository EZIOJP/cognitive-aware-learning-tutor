/**
 * Viewport-locked ruled grid behind the sketch layer. Pure CSS — never part of
 * PNG exports (the sketch canvas exports with a transparent background).
 * Optionally renders N highlighted character cells with a faded ghost prompt.
 */

interface FixedGridOverlayProps {
  cellPx: number;
  /** Highlighted character cells for training prompts (0 = plain grid only). */
  cells?: number;
  /** Prompt text rendered faintly inside the highlighted cells as a guide. */
  ghostText?: string;
}

export function FixedGridOverlay({ cellPx, cells = 0, ghostText = "" }: FixedGridOverlayProps) {
  const chars = ghostText ? [...ghostText.replace(/\s+/g, "")] : [];
  return (
    <div className="math-grid-overlay" aria-hidden="true">
      <div
        className="math-grid-overlay-lines"
        style={{ backgroundSize: `${cellPx}px ${cellPx}px` }}
      />
      {cells > 0 && (
        <div className="math-grid-cell-row">
          {Array.from({ length: cells }, (_, i) => (
            <div
              key={i}
              className="math-grid-cell"
              style={{ width: cellPx * 1.5, height: cellPx * 2 }}
            >
              {cells > 1 ? (chars[i] ?? "") : ghostText}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
