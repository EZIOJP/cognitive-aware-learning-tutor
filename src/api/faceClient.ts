const API_BASE =
  (import.meta as { env?: { VITE_API_BASE?: string } }).env?.VITE_API_BASE || "http://localhost:8000";

export type FaceStatus = {
  attention: number;
  attitude: string;
  blink_rate: number;
  face_detected: boolean;
  details?: Record<string, number>;
  updated_at?: string;
};

/** Poll status posted by `backend/face_tracker.py` (Python OpenCV mirror). */
export async function fetchFaceStatus(): Promise<FaceStatus | null> {
  try {
    const res = await fetch(`${API_BASE}/api/vocab/face/status`);
    if (!res.ok) return null;
    const data = await res.json();
    const face = (data as { face?: FaceStatus })?.face;
    return face ?? null;
  } catch {
    return null;
  }
}
