import { resolveApiUrl } from "../utils/resolveBackendUrl";
import type { FocusPayload } from "../face-tracker/focusState";

export type FaceFocusStatus = Pick<
  FocusPayload,
  "not_focused" | "head_turned_away" | "long_eye_closure" | "no_face"
>;

export type FaceStatus = {
  attention: number;
  attitude: string;
  blink_rate: number;
  face_detected: boolean;
  details?: Record<string, number>;
  updated_at?: string;
  focus?: FaceFocusStatus;
};

/** Post a status payload (browser tracker). JWT enables hub face_attention readings. */
export async function postFaceStatus(
  payload: Omit<FaceStatus, "updated_at">,
): Promise<boolean> {
  try {
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    const token = localStorage.getItem("vocab:auth-token");
    if (token) headers.Authorization = `Bearer ${token}`;
    const res = await fetch(`${resolveApiUrl()}/api/vocab/face/status`, {
      method: "POST",
      headers,
      body: JSON.stringify(payload),
    });
    return res.ok;
  } catch {
    return false;
  }
}

/** Capture face embedding for enroll/login (Human face.description). */
export async function postFaceEnroll(embedding: number[]): Promise<boolean> {
  try {
    const token = localStorage.getItem("vocab:auth-token");
    if (!token) return false;
    const res = await fetch(`${resolveApiUrl()}/api/vocab/auth/face/enroll`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ embedding }),
    });
    return res.ok;
  } catch {
    return false;
  }
}

export async function postFaceLogin(
  username: string,
  embedding: number[],
): Promise<{ token: string; user: { id: number; username: string } } | null> {
  try {
    const res = await fetch(`${resolveApiUrl()}/api/vocab/auth/face/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: username.trim().toLowerCase(), embedding }),
    });
    if (!res.ok) return null;
    return (await res.json()) as { token: string; user: { id: number; username: string } };
  } catch {
    return null;
  }
}

export async function fetchFaceEnrolled(): Promise<boolean> {
  try {
    const token = localStorage.getItem("vocab:auth-token");
    if (!token) return false;
    const res = await fetch(`${resolveApiUrl()}/api/vocab/auth/face/status`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) return false;
    const data = (await res.json()) as { enrolled?: boolean };
    return Boolean(data.enrolled);
  } catch {
    return false;
  }
}
