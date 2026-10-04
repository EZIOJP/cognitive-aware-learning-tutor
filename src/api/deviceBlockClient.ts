/**
 * Device lock (hosts): settings from device_block.json; apply/remove via pipe.
 */
import { enforcerNativeCmd, isFocusEnforcerBridgeAvailable } from "../lib/enforcerNativeCmd";
import { focusDataUrl } from "../utils/focusDataUrl";
import { isFocusDesktopShell } from "../utils/focusDesktopShell";

export type DeviceBlockSettings = {
  enabled?: boolean;
  block_porn?: boolean;
  block_watch?: boolean;
  block_social?: boolean;
  source?: string;
};

export type DeviceBlockStatus = {
  ok?: boolean;
  error?: string;
  settings: DeviceBlockSettings;
  active: boolean;
  configured_domain_count: number;
  managed_host_entries: number;
  needs_sync?: boolean;
  refresh?: string;
  refresh_error?: string;
  cache_as_of?: string;
  hosts_path?: string;
  verify_sample?: { hostname?: string; blocked?: boolean; in_hosts?: boolean; ips?: string[] };
  apply?: {
    ok?: boolean;
    needs_admin?: boolean;
    applied?: boolean;
    domain_count?: number;
    error?: string;
  };
};

function unwrap(r: Record<string, unknown> | null): DeviceBlockStatus {
  if (!r || r.ok === false) {
    throw new Error(String((r as { error?: string } | null)?.error || "device_block_failed"));
  }
  const db = (r.device_block || {}) as Record<string, unknown>;
  const settings = (db.settings || {}) as DeviceBlockSettings;
  return {
    ok: true,
    settings,
    active: Boolean(db.active),
    configured_domain_count: Number(db.configured_domain_count || 0),
    managed_host_entries: Number(db.managed_host_entries || 0),
    needs_sync: Boolean(db.needs_sync),
    refresh: String(db.refresh || "idle"),
    refresh_error: String(db.refresh_error || ""),
    cache_as_of: String(db.cache_as_of || ""),
    hosts_path: String(db.hosts_path || ""),
    verify_sample: db.verify_sample as DeviceBlockStatus["verify_sample"],
    apply: r.apply as DeviceBlockStatus["apply"],
  };
}

export function isDeviceBlockNativeAvailable(): boolean {
  return isFocusEnforcerBridgeAvailable();
}

export async function fetchDeviceBlockNative(): Promise<DeviceBlockStatus> {
  if (isFocusDesktopShell()) {
    try {
      const res = await fetch(focusDataUrl("device_block.json"), { cache: "no-store" });
      if (res.ok) {
        const settings = (await res.json()) as DeviceBlockSettings;
        return {
          ok: true,
          settings,
          active: Boolean(settings.enabled),
          configured_domain_count: 0,
          managed_host_entries: 0,
        };
      }
    } catch {
      /* fall through */
    }
  }
  const r = await enforcerNativeCmd("device_block.status", {}, 8000);
  return unwrap(r as Record<string, unknown> | null);
}

export async function saveDeviceBlockNative(
  patch: DeviceBlockSettings & { apply_now?: boolean; confirm?: string },
): Promise<DeviceBlockStatus> {
  const r = await enforcerNativeCmd("device_block.save", patch as Record<string, unknown>, 15000);
  return unwrap(r as Record<string, unknown> | null);
}

export async function removeDeviceBlockNative(confirm: string): Promise<DeviceBlockStatus> {
  const r = await enforcerNativeCmd("device_block.remove", { confirm }, 15000);
  return unwrap(r as Record<string, unknown> | null);
}

export async function refreshDeviceBlockListNative(force = true): Promise<DeviceBlockStatus> {
  await enforcerNativeCmd("device_block.refresh_list", { force }, 5000);
  // poll status after kick
  await new Promise((res) => setTimeout(res, 800));
  return fetchDeviceBlockNative();
}
