import {
  forwardRef,
  useCallback,
  useImperativeHandle,
  useRef,
  type ReactNode,
} from "react";
import { Box, Tldraw, type Editor, type TLShapeId } from "tldraw";
import "tldraw/tldraw.css";
import type { MathCanvasHandle } from "./types";

interface TldrawMathCanvasProps {
  /** Enable tldraw's built-in snap grid (default on). */
  showGrid?: boolean;
  persistenceKey?: string;
  hideUi?: boolean;
  onCanvasChange?: (stamp: string) => void;
  onEraserStroke?: () => void;
  children?: ReactNode;
}

function blobToDataUrl(blob: Blob): Promise<string | null> {
  return new Promise((resolve) => {
    const reader = new FileReader();
    reader.onloadend = () => resolve(typeof reader.result === "string" ? reader.result : null);
    reader.readAsDataURL(blob);
  });
}

export const TldrawMathCanvas = forwardRef<MathCanvasHandle, TldrawMathCanvasProps>(
  function TldrawMathCanvas(
    { showGrid = true, persistenceKey, hideUi = false, onCanvasChange, onEraserStroke, children },
    ref
  ) {
    const editorRef = useRef<Editor | null>(null);
    const eraserCountRef = useRef(0);
    const onCanvasChangeRef = useRef(onCanvasChange);
    const onEraserStrokeRef = useRef(onEraserStroke);
    onCanvasChangeRef.current = onCanvasChange;
    onEraserStrokeRef.current = onEraserStroke;

    const handleMount = useCallback((editor: Editor) => {
      editorRef.current = editor;
      if (showGrid) {
        editor.updateInstanceState({ isGridMode: true });
      }

      editor.on("event", (info) => {
        if (info.name === "pointer_up" && editor.getCurrentToolId() === "eraser") {
          eraserCountRef.current += 1;
          onEraserStrokeRef.current?.();
        }
      });
      editor.store.listen(
        () => {
          onCanvasChangeRef.current?.(`tldraw-${Date.now()}`);
        },
        { scope: "document", source: "user" }
      );
    }, [showGrid]);

    useImperativeHandle(
      ref,
      () => ({
        exportPng: async () => {
          const editor = editorRef.current;
          if (!editor) return null;
          const ids = [...editor.getCurrentPageShapeIds()] as TLShapeId[];
          if (!ids.length) return null;
          const shapeBounds = ids
            .map((id) => editor.getShapePageBounds(id))
            .filter((b): b is NonNullable<typeof b> => !!b);
          const bounds = shapeBounds.length ? Box.Common(shapeBounds) : undefined;
          const { blob } = await editor.toImage(ids, {
            format: "png",
            background: true,
            darkMode: false,
            padding: 16,
            scale: 2,
            ...(bounds ? { bounds } : {}),
          });
          return blobToDataUrl(blob);
        },
        exportPaths: async () => null,
        hasContent: () => {
          const editor = editorRef.current;
          return !!editor && editor.getCurrentPageShapeIds().size > 0;
        },
        getEraserEventCount: () => eraserCountRef.current,
        resetEraserCount: () => {
          eraserCountRef.current = 0;
        },
        clearAll: () => {
          const editor = editorRef.current;
          if (!editor) return;
          const ids = [...editor.getCurrentPageShapeIds()];
          if (ids.length) editor.deleteShapes(ids);
        },
        getEditor: () => editorRef.current,
      }),
      []
    );

    return (
      <div className="math-canvas-container">
        <Tldraw
          options={{ maxPages: 1 }}
          persistenceKey={persistenceKey}
          hideUi={hideUi}
          onMount={handleMount}
        >
          {children}
        </Tldraw>
      </div>
    );
  }
);
