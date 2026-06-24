import { resolveApiUrl } from "../utils/resolveBackendUrl";
import type { FocusEventType } from "../face-tracker/focusState";
import type { PomodoroMode } from "../context/PomodoroContext";

function authHeaders(): Record<string, string> {
  const h: Record<string, string> = { "Content-Type": "application/json" };
  const token = localStorage.getItem("vocab:auth-token");
  if (token) h.Authorization = `Bearer ${token}`;
  return h;
}

export async function postFocusEventStart(
  eventType: FocusEventType,
  pomodoroMode: PomodoroMode,
): Promise<number | null> {
  try {
    const res = await fetch(`${resolveApiUrl()}/api/vocab/focus/events/start`, {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({ event_type: eventType, pomodoro_mode: pomodoroMode }),
    });
    if (!res.ok) return null;
    const data = (await res.json()) as { id?: number };
    return data.id ?? null;
  } catch {
    return null;
  }
}

export async function postFocusEventEnd(eventId: number): Promise<void> {
  try {
    await fetch(`${resolveApiUrl()}/api/vocab/focus/events/${eventId}/end`, {
      method: "PATCH",
      headers: authHeaders(),
    });
  } catch {
    /* best-effort */
  }
}
