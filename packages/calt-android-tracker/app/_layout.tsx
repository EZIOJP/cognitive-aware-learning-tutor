import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";

export default function RootLayout() {
  return (
    <>
      <StatusBar style="light" />
      <Stack
        screenOptions={{
          headerStyle: { backgroundColor: "#0f1419" },
          headerTintColor: "#e8f0ee",
          contentStyle: { backgroundColor: "#0f1419" },
        }}
      >
        <Stack.Screen name="index" options={{ title: "CALT Tracker" }} />
        <Stack.Screen name="settings" options={{ title: "Server" }} />
      </Stack>
    </>
  );
}
