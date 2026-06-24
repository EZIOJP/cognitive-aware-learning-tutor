import { useCallback, useEffect, useRef, useState } from "react";
import { captureFaceEmbedding } from "./humanAuth";

export function useFaceAuthCapture() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const startCamera = useCallback(async () => {
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 640, height: 480, facingMode: "user" },
        audio: false,
      });
      streamRef.current = stream;
      const video = videoRef.current;
      if (!video) throw new Error("Video element missing");
      video.srcObject = stream;
      await video.play();
      setReady(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Camera unavailable");
      setReady(false);
    }
  }, []);

  const stopCamera = useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    const video = videoRef.current;
    if (video) video.srcObject = null;
    setReady(false);
  }, []);

  useEffect(() => () => stopCamera(), [stopCamera]);

  const captureEmbedding = useCallback(async (): Promise<number[] | null> => {
    const video = videoRef.current;
    if (!video || !ready) return null;
    return captureFaceEmbedding(video);
  }, [ready]);

  return { videoRef, ready, error, startCamera, stopCamera, captureEmbedding };
}
