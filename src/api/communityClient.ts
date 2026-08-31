import { resolveApiUrl } from "../utils/resolveBackendUrl";

const TOKEN_KEY = "vocab:auth-token";

function headers(): HeadersInit {
  const h: Record<string, string> = { "Content-Type": "application/json" };
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) h.Authorization = `Bearer ${token}`;
  return h;
}

export type CommunityNetwork = {
  tailscale: {
    installed: boolean;
    running: boolean;
    ipv4: string[];
    magicdns: string | null;
    hint: string;
  };
  urls: {
    lan_site: string | null;
    lan_api: string | null;
    lan_wearables: string | null;
    tailscale_site: string[];
    tailscale_api: string[];
    tailscale_wearables: string[];
  };
  publish_ranks: boolean;
  peers: string[];
};

export type RankRow = {
  rank: number;
  display_name: string;
  pulse: number;
  pulse_label?: string | null;
  day?: string | null;
  you?: boolean;
  reachable?: boolean;
  peer?: string;
};

export type CommunityRanks = {
  publish_ranks: boolean;
  rows: RankRow[];
  unreachable: string[];
  peer_count: number;
};

export async function fetchCommunityNetwork(): Promise<CommunityNetwork> {
  const res = await fetch(resolveApiUrl("/api/community/network"), { headers: headers() });
  if (!res.ok) throw new Error(`community network ${res.status}`);
  return res.json();
}

export async function saveCommunitySettings(body: {
  publish_ranks: boolean;
  peers: string[];
}): Promise<{ publish_ranks: boolean; peers: string[] }> {
  const res = await fetch(resolveApiUrl("/api/community/settings"), {
    method: "PUT",
    headers: headers(),
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`community settings ${res.status}`);
  return res.json();
}

export async function fetchCommunityRanks(): Promise<CommunityRanks> {
  const res = await fetch(resolveApiUrl("/api/community/ranks"), { headers: headers() });
  if (!res.ok) throw new Error(`community ranks ${res.status}`);
  return res.json();
}
