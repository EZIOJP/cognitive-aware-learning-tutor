import * as Notifications from "expo-notifications";
import { Platform } from "react-native";
import type { MobileAlert } from "./api";

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: false,
    shouldSetBadge: false,
  }),
});

export async function ensureNotifyPermission(): Promise<boolean> {
  if (Platform.OS === "web") return false;
  const cur = await Notifications.getPermissionsAsync();
  if (cur.granted) return true;
  const req = await Notifications.requestPermissionsAsync();
  return !!req.granted;
}

/** Fire local notifications — Zepp mirrors phone notifications onto the watch when enabled. */
export async function relayAlerts(alerts: MobileAlert[]): Promise<number> {
  if (!alerts.length) return 0;
  const ok = await ensureNotifyPermission();
  if (!ok) return 0;
  let n = 0;
  for (const a of alerts) {
    const title = (a.title || "CALT").slice(0, 48);
    const body = (a.body || "Day rules updated").slice(0, 120);
    await Notifications.scheduleNotificationAsync({
      content: { title, body, sound: false },
      trigger: null,
    });
    n += 1;
  }
  return n;
}

export async function notifyOnce(title: string, body: string): Promise<void> {
  const ok = await ensureNotifyPermission();
  if (!ok) return;
  await Notifications.scheduleNotificationAsync({
    content: { title: title.slice(0, 48), body: body.slice(0, 120), sound: false },
    trigger: null,
  });
}
