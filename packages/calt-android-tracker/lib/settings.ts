import AsyncStorage from "./storage";

const KEYS = {
  baseUrl: "calt_base_url",
  jwt: "calt_jwt",
  wearableKey: "calt_wearable_key",
  preferHub: "calt_prefer_hub",
} as const;

export type AppSettings = {
  baseUrl: string;
  jwt: string;
  wearableKey: string;
  preferHub: boolean;
};

const DEFAULTS: AppSettings = {
  baseUrl: "http://192.168.0.110:8000",
  jwt: "",
  wearableKey: "calt-local-wearables",
  preferHub: false,
};

export async function loadSettings(): Promise<AppSettings> {
  const [baseUrl, jwt, wearableKey, preferHub] = await Promise.all([
    AsyncStorage.getItem(KEYS.baseUrl),
    AsyncStorage.getItem(KEYS.jwt),
    AsyncStorage.getItem(KEYS.wearableKey),
    AsyncStorage.getItem(KEYS.preferHub),
  ]);
  return {
    baseUrl: baseUrl || DEFAULTS.baseUrl,
    jwt: jwt || DEFAULTS.jwt,
    wearableKey: wearableKey || DEFAULTS.wearableKey,
    preferHub: preferHub === "1" || DEFAULTS.preferHub,
  };
}

export async function saveSettings(patch: Partial<AppSettings>): Promise<void> {
  const cur = await loadSettings();
  const next = { ...cur, ...patch };
  await Promise.all([
    AsyncStorage.setItem(KEYS.baseUrl, next.baseUrl),
    AsyncStorage.setItem(KEYS.jwt, next.jwt),
    AsyncStorage.setItem(KEYS.wearableKey, next.wearableKey),
    AsyncStorage.setItem(KEYS.preferHub, next.preferHub ? "1" : "0"),
  ]);
}
