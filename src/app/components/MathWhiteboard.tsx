import { useRef, useState, useCallback } from "react";
import { ReactSketchCanvas, ReactSketchCanvasRef } from "react-sketch-canvas";
import { Eraser, Trash2, Download, Pencil } from "lucide-react";
import { Button } from "./ui/button";
import { Card } from "./ui/card";
import { Slider } from "./ui/slider";

interface MathWhiteboardProps {
  onCanvasChange: (imageData: string) => void;
}

export function MathWhiteboard({ onCanvasChange }: MathWhiteboardProps) {
  const canvasRef = useRef<ReactSketchCanvasRef>(null);
  const [strokeWidth, setStrokeWidth] = useState(3);
  const [eraserWidth, setEraserWidth] = useState(10);
  const [tool, setTool] = useState<"pen" | "eraser">("pen");

  const handleClear = async () => {
    if (canvasRef.current) {
      await canvasRef.current.clearCanvas();
      onCanvasChange("");
    }
  };

  const handleExport = async () => {
    if (canvasRef.current) {
      const imageData = await canvasRef.current.exportImage("png");
      onCanvasChange(imageData);

      // Also allow user to download
      const link = document.createElement("a");
      link.download = `math-problem-${Date.now()}.png`;
      link.href = imageData;
      link.click();
    }
  };

  const handleUndo = () => {
    if (canvasRef.current) {
      canvasRef.current.undo();
    }
  };

  const handleRedo = () => {
    if (canvasRef.current) {
      canvasRef.current.redo();
    }
  };

  const handleStroke = useCallback(() => {
    onCanvasChange(`stroke-${Date.now()}`);
  }, [onCanvasChange]);

  return (
    <Card className="flex flex-col h-full">
      <div className="flex items-center justify-between p-3 border-b">
        <h3>Math Workspace</h3>
        <div className="flex gap-2">
          <Button
            onClick={() => setTool("pen")}
            variant={tool === "pen" ? "default" : "outline"}
            size="sm"
          >
            <Pencil className="w-4 h-4" />
          </Button>
          <Button
            onClick={() => setTool("eraser")}
            variant={tool === "eraser" ? "default" : "outline"}
            size="sm"
          >
            <Eraser className="w-4 h-4" />
          </Button>
          <Button onClick={handleUndo} variant="outline" size="sm">
            Undo
          </Button>
          <Button onClick={handleRedo} variant="outline" size="sm">
            Redo
          </Button>
          <Button onClick={handleClear} variant="outline" size="sm">
            <Trash2 className="w-4 h-4" />
          </Button>
          <Button onClick={handleExport} variant="outline" size="sm">
            <Download className="w-4 h-4" />
          </Button>
        </div>
      </div>

      <div className="flex gap-3 items-center p-3 border-b bg-muted/30">
        <span className="text-sm font-medium min-w-[80px]">
          {tool === "pen" ? "Pen Size:" : "Eraser Size:"}
        </span>
        <Slider
          value={tool === "pen" ? [strokeWidth] : [eraserWidth]}
          onValueChange={(value) => {
            if (tool === "pen") {
              setStrokeWidth(value[0]);
            } else {
              setEraserWidth(value[0]);
            }
          }}
          min={1}
          max={20}
          step={1}
          className="w-32"
        />
        <span className="text-sm text-muted-foreground">
          {tool === "pen" ? strokeWidth : eraserWidth}px
        </span>
      </div>

      <div className="flex-1 p-4 bg-white dark:bg-gray-900">
        <ReactSketchCanvas
          ref={canvasRef}
          strokeWidth={strokeWidth}
          eraserWidth={eraserWidth}
          strokeColor={tool === "pen" ? "#000000" : "transparent"}
          canvasColor="transparent"
          onStroke={handleStroke}
          className="border-2 border-dashed border-gray-300 dark:border-gray-700 rounded-lg w-full h-full"
          exportWithBackgroundImage={true}
          style={{
            border: "2px dashed #cbd5e1",
            borderRadius: "8px",
          }}
        />
      </div>
    </Card>
  );
}
