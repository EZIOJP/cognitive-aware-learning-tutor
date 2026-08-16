import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { Link } from "expo-router";
import {
  confirmMorningPlan,
  fetchDayStatus,
  fetchMobileAlerts,
  setHardBlockArmed,
  type DayStatus,
} from "../lib/api";
import { notifyOnce, relayAlerts } from "../lib/notify";
import { loadSettings } from "../lib/settings";

export default function TrackerScreen() {
  const [status, setStatus] = useState<DayStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [hint, setHint] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const s = await loadSettings();
      const data = await fetchDayStatus(s.baseUrl, {
        jwt: s.jwt || undefined,
        wearableKey: s.wearableKey || undefined,
        preferHub: s.preferHub,
      });
      setStatus(data);
      if (s.jwt) {
        const alerts = await fetchMobileAlerts(s.baseUrl, s.jwt, true);
        const n = await relayAlerts(alerts);
        if (n) setHint(`Relayed ${n} alert(s) → phone (watch if mirror on)`);
      } else if (data.notify?.title) {
        // Hub path: surface notify locally when fingerprint-worthy payload exists
        await notifyOnce(data.notify.title, data.notify.body || "");
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
    const id = setInterval(() => void refresh(), 60_000);
    return () => clearInterval(id);
  }, [refresh]);

  const onArm = async (armed: boolean) => {
    setHint(null);
    try {
      const s = await loadSettings();
      // Solo-local FastAPI accepts policy writes without JWT; hub cannot arm.
      await setHardBlockArmed(s.baseUrl.replace(":8765", ":8000"), s.jwt || "solo", armed);
      setHint(armed ? "Hard-block armed" : "Hard-block disarmed");
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const onConfirmPlan = async () => {
    setHint(null);
    try {
      const s = await loadSettings();
      await confirmMorningPlan(s.baseUrl.replace(":8765", ":8000"), s.jwt || "solo");
      setHint("Plan confirmed");
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const m = status?.morning;
  const hb = status?.hard_block;
  const tr = status?.tracker;
  const w = status?.wearables;
  const wake = m?.suggested_wake;

  return (
    <ScrollView
      style={styles.root}
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={busy} onRefresh={refresh} tintColor="#7dd3c0" />}
    >
      <View style={styles.rowBetween}>
        <Text style={styles.brand}>CALT</Text>
        <Link href="/settings" style={styles.link}>
          Server
        </Link>
      </View>

      {error ? <Text style={styles.error}>{error}</Text> : null}
      {hint ? <Text style={styles.hint}>{hint}</Text> : null}
      {!status && busy ? <ActivityIndicator color="#7dd3c0" /> : null}

      {status ? (
        <>
          <Text style={styles.mode}>{status.browser_mode_label || status.browser_mode || "—"}</Text>
          <Text style={styles.sub}>
            Next: {m?.next || "—"} · Tracker {status.tracker_alive || tr?.alive ? "alive" : tr?.status || "off"}
          </Text>

          <View style={styles.card}>
            <Text style={styles.cardTitle}>Morning checklist</Text>
            {(status.checklist || []).map((c) => (
              <Text key={c.id} style={[styles.check, c.active && styles.checkActive]}>
                {c.done ? "✓" : "○"} {c.label}
              </Text>
            ))}
            {m?.hint ? <Text style={styles.muted}>{m.hint}</Text> : null}
            {wake?.suggested_local ? (
              <Text style={styles.muted}>
                Soft wake ~{String(wake.suggested_local).slice(11, 16)} (not a watch alarm)
              </Text>
            ) : null}
            {m?.next === "plan" ? (
              <Pressable style={styles.btn} onPress={onConfirmPlan}>
                <Text style={styles.btnText}>Confirm plan</Text>
              </Pressable>
            ) : null}
          </View>

          <View style={styles.card}>
            <Text style={styles.cardTitle}>Hard-block</Text>
            <Text style={styles.body}>
              {hb?.armed ? "Armed" : "Disarmed"}
              {hb?.locked ? " · Locked" : hb?.unlocked ? " · Unlocked" : ""}
            </Text>
            <Text style={styles.muted}>
              Focus {hb?.productive_minutes ?? "—"} / {hb?.daily_goal_minutes ?? "—"} min
              {hb?.remaining_minutes != null ? ` · ${hb.remaining_minutes}m left` : ""}
            </Text>
            <View style={styles.row}>
              <Pressable style={[styles.btn, styles.btnHalf]} onPress={() => onArm(true)}>
                <Text style={styles.btnText}>Arm</Text>
              </Pressable>
              <Pressable
                style={[styles.btn, styles.btnHalf, styles.btnDanger]}
                onPress={() => onArm(false)}
              >
                <Text style={styles.btnText}>Disarm</Text>
              </Pressable>
            </View>
          </View>

          <View style={styles.card}>
            <Text style={styles.cardTitle}>Wearables</Text>
            <Text style={styles.body}>
              Sleep {w?.sleep_hours ?? "—"}h · Steps {w?.steps ?? "—"}
            </Text>
            <Text style={styles.muted}>
              Stand {w?.stand_hours ?? "—"}h
              {w?.sitting_min != null ? ` · Sitting ${w.sitting_min}m` : ""}
            </Text>
            <Text style={styles.muted}>Last ingest {w?.last_ingest_at || "—"}</Text>
          </View>

          <Text style={styles.limits}>
            Amazfit alerts = phone local notification (mirror to watch). Full CALT is not a watch face
            APK — use packages/calt-zepp mini-program for wrist sync.
          </Text>
        </>
      ) : null}

      <Pressable style={styles.btnGhost} onPress={refresh}>
        <Text style={styles.btnGhostText}>{busy ? "Refreshing…" : "Refresh"}</Text>
      </Pressable>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: "#0f1419" },
  content: { padding: 20, paddingBottom: 48, gap: 12 },
  rowBetween: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  brand: { fontSize: 28, fontWeight: "700", color: "#e8f0ee", letterSpacing: 1 },
  link: { color: "#7dd3c0", fontSize: 16 },
  mode: { fontSize: 22, fontWeight: "600", color: "#c4b5fd", marginTop: 8 },
  sub: { color: "#9aa8a4", marginBottom: 4 },
  card: {
    backgroundColor: "#171e24",
    borderRadius: 12,
    padding: 14,
    gap: 6,
    borderWidth: 1,
    borderColor: "#243038",
  },
  cardTitle: { color: "#e8f0ee", fontWeight: "600", fontSize: 16, marginBottom: 4 },
  check: { color: "#9aa8a4", fontSize: 15 },
  checkActive: { color: "#7dd3c0", fontWeight: "600" },
  body: { color: "#e8f0ee", fontSize: 15 },
  muted: { color: "#7a8a86", fontSize: 13 },
  error: { color: "#f07070", marginVertical: 4 },
  hint: { color: "#7dd3c0", marginVertical: 4 },
  row: { flexDirection: "row", gap: 8, marginTop: 8 },
  btn: {
    backgroundColor: "#1a9b8e",
    paddingVertical: 12,
    paddingHorizontal: 16,
    borderRadius: 10,
    alignItems: "center",
    marginTop: 8,
  },
  btnHalf: { flex: 1 },
  btnDanger: { backgroundColor: "#8b3a3a" },
  btnText: { color: "#fff", fontWeight: "600" },
  btnGhost: { padding: 14, alignItems: "center" },
  btnGhostText: { color: "#7dd3c0" },
  limits: { color: "#5a6864", fontSize: 12, lineHeight: 18, marginTop: 8 },
});
