import { useEffect, useState } from "react";
import { Pressable, StyleSheet, Switch, Text, TextInput, View } from "react-native";
import { loadSettings, saveSettings, type AppSettings } from "../lib/settings";

export default function SettingsScreen() {
  const [s, setS] = useState<AppSettings | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    void loadSettings().then(setS);
  }, []);

  if (!s) return null;

  const persist = async () => {
    await saveSettings(s);
    setSaved(true);
    setTimeout(() => setSaved(false), 1500);
  };

  return (
    <View style={styles.root}>
      <Text style={styles.label}>API base URL</Text>
      <Text style={styles.hint}>FastAPI :8000 or tracker hub :8765 (LAN IP, not localhost)</Text>
      <TextInput
        style={styles.input}
        value={s.baseUrl}
        onChangeText={(baseUrl) => setS({ ...s, baseUrl })}
        autoCapitalize="none"
        autoCorrect={false}
        placeholder="http://192.168.x.x:8000"
        placeholderTextColor="#5a6864"
      />

      <Text style={styles.label}>JWT (optional for arm / confirm)</Text>
      <TextInput
        style={styles.input}
        value={s.jwt}
        onChangeText={(jwt) => setS({ ...s, jwt })}
        autoCapitalize="none"
        autoCorrect={false}
        secureTextEntry
        placeholder="Paste from web login"
        placeholderTextColor="#5a6864"
      />

      <Text style={styles.label}>Wearable key (hub :8765)</Text>
      <TextInput
        style={styles.input}
        value={s.wearableKey}
        onChangeText={(wearableKey) => setS({ ...s, wearableKey })}
        autoCapitalize="none"
        autoCorrect={false}
        placeholder="calt-local-wearables"
        placeholderTextColor="#5a6864"
      />

      <View style={styles.row}>
        <Text style={styles.labelInline}>Prefer tracker hub paths</Text>
        <Switch
          value={s.preferHub}
          onValueChange={(preferHub) => setS({ ...s, preferHub })}
          trackColor={{ true: "#1a9b8e" }}
        />
      </View>

      <Pressable style={styles.btn} onPress={persist}>
        <Text style={styles.btnText}>{saved ? "Saved" : "Save"}</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: "#0f1419", padding: 20, gap: 8 },
  label: { color: "#e8f0ee", fontWeight: "600", marginTop: 12 },
  labelInline: { color: "#e8f0ee", fontWeight: "600", flex: 1 },
  hint: { color: "#7a8a86", fontSize: 12 },
  input: {
    backgroundColor: "#171e24",
    borderWidth: 1,
    borderColor: "#243038",
    borderRadius: 10,
    color: "#e8f0ee",
    paddingHorizontal: 12,
    paddingVertical: 10,
  },
  row: { flexDirection: "row", alignItems: "center", marginTop: 16 },
  btn: {
    marginTop: 24,
    backgroundColor: "#1a9b8e",
    padding: 14,
    borderRadius: 10,
    alignItems: "center",
  },
  btnText: { color: "#fff", fontWeight: "600" },
});
