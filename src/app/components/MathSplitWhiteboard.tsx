import { forwardRef, useImperativeHandle, useRef, useState, useCallback } from "react";
import { ReactSketchCanvas, type ReactSketchCanvasRef } from "react-sketch-canvas";
import { Eraser, Trash2, Download, Pencil } from "lucide-react";
import { Button } from "./ui/button";
import { Slider } from "./ui/slider";

const COLORS = ["#000000", "#ef4444", "#3b82f6", "#22c55e", "#f59e0b"];

export interface MathSplitWhiteboardHandle {
  clearAll: () => void;
}

interface MathSplitWhiteboardProps {
  onCanvasChange: (imageData: string) => void;
}

export const MathSplitWhiteboard = forwardRef<MathSplitWhiteboardHandle, MathSplitWhiteboardProps>(
  function MathSplitWhiteboard({ onCanvasChange }, ref) {
    const mainRef = useRef<ReactSketchCanvasRef>(null);
    const roughRef = useRef<ReactSketchCanvasRef>(null);
    const [strokeWidth, setStrokeWidth] = useState(3);
    const [eraserWidth, setEraserWidth] = useState(12);
    const [tool, setTool] = useState<"pen" | "eraser">("pen");
    const [strokeColor, setStrokeColor] = useState("#000000");

    const clearAll = useCallback(async () => {
      await mainRef.current?.clearCanvas();
      await roughRef.current?.clearCanvas();
      onCanvasChange("");
    }, [onCanvasChange]);

    useImperativeHandle(ref, () => ({ clearAll }), [clearAll]);

    const stroke = tool === "pen" ? strokeColor : "transparent";

    const handleExport = async () => {
      const imageData = await mainRef.current?.exportImage("png");
      if (imageData) onCanvasChange(imageData);
    };

    return (
      <div className="flex flex-col h-full min-h-[320px]">
        <div className="flex flex-wrap items-center gap-2 p-2 border-b bg-muted/30 shrink-0">
          <Button size="sm" variant={tool === "pen" ? "default" : "outline"} onClick={() => setTool("pen")}>
            <Pencil className="w-4 h-4" />
          </Button>
          <Button size="sm" variant={tool === "eraser" ? "default" : "outline"} onClick={() => setTool("eraser")}>
            <Eraser className="w-4 h-4" />
          </Button>
          <div className="flex gap-1">
            {COLORS.map((c) => (
              <button
                key={c}
                type="button"
                onClick={() => { setStrokeColor(c); setTool("pen"); }}
                className={`w-7 h-7 rounded border-2 ${strokeColor === c && tool === "pen" ? "border-primary" : "border-transparent"}`}
                style={{ backgroundColor: c }}
              />
            ))}
          </div>
          <Slider
            className="w-24"
            min={1}
            max={20}
            step={1}
            value={[tool === "pen" ? strokeWidth : eraserWidth]}
            onValueChange={(v) => (tool === "pen" ? setStrokeWidth(v[0]) : setEraserWidth(v[0]))}
          />
          <Button size="sm" variant="outline" onClick={() => mainRef.current?.undo()}>Undo</Button>
          <Button size="sm" variant="outline" onClick={() => mainRef.current?.redo()}>Redo</Button>
          <Button size="sm" variant="outline" onClick={clearAll}><Trash2 className="w-4 h-4" /></Button>
          <Button size="sm" variant="outline" onClick={handleExport}><Download className="w-4 h-4" /></Button>
        </div>
        <div className="flex-1 flex gap-2 p-2 min-h-0">
          <div className="flex-[0_0_65%] flex flex-col min-h-0 rounded-lg border overflow-hidden bg-white dark:bg-gray-950">
            <div className="text-xs px-2 py-1 bg-muted/50 border-b">Main workspace</div>
            <div className="flex-1 min-h-[200px] p-1">
              <ReactSketchCanvas
                ref={mainRef}
                strokeWidth={strokeWidth}
                eraserWidth={eraserWidth}
                strokeColor={stroke}
                canvasColor="transparent"
                onStroke={() => onCanvasChange(`stroke-${Date.now()}`)}
                className="w-full h-full"
              />
            </div>
          </div>
          <div className="flex-[0_0_35%] flex flex-col min-h-0 rounded-lg border overflow-hidden bg-amber-50 dark:bg-amber-950/30">
            <div className="text-xs px-2 py-1 bg-amber-600/80 text-white border-b">Rough work</div>
            <div className="flex-1 min-h-[200px] p-1">
              <ReactSketchCanvas
                ref={roughRef}
                strokeWidth={strokeWidth}
                eraserWidth={eraserWidth}
                strokeColor={stroke}
                canvasColor="#fef3c7"
                onStroke={() => onCanvasChange(`rough-${Date.now()}`)}
                className="w-full h-full"
              />
            </div>
          </div>
        </div>
      </div>
    );
  }
);
