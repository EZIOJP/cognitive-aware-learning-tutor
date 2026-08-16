/**
 * Tiny AsyncStorage shim — uses SecureStore when available, else in-memory.
 * Avoids adding @react-native-async-storage until first npm install.
 */
import * as SecureStore from "expo-secure-store";
import { Platform } from "react-native";

const mem = new Map<string, string>();

async function setItem(key: string, value: string): Promise<void> {
  mem.set(key, value);
  if (Platform.OS === "web") return;
  try {
    await SecureStore.setItemAsync(key, value);
  } catch {
    /* ignore */
  }
}

async function getItem(key: string): Promise<string | null> {
  if (mem.has(key)) return mem.get(key) ?? null;
  if (Platform.OS === "web") return null;
  try {
    return (await SecureStore.getItemAsync(key)) ?? null;
  } catch {
    return null;
  }
}

const AsyncStorage = { getItem, setItem };
export default AsyncStorage;
