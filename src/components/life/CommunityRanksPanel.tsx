import { useCallback, useEffect, useState } from "react";
import { Trophy, Wifi } from "lucide-react";
import { Button } from "../../app/components/ui/button";
import { Card } from "../../app/components/ui/card";
import { Input } from "../../app/components/ui/input";
import { Switch } from "../../app/components/ui/switch";
import {
  fetchCommunityNetwork,
  fetchCommunityRanks,
  saveCommunitySettings,
  type CommunityNetwork,
  type CommunityRanks,
} from "../../api/communityClient";
import { scoreColor } from "../productivity/GlanceBar";

export function CommunityRanksPanel({ compact = false }: { compact?: boolean }) {
  const [net, setNet] = useState<CommunityNetwork | null>(null);
  const [ranks, setRanks] = useState<CommunityRanks | null>(null);
  const [peerDraft, setPeerDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setError(null);
    try {
      const [n, r] = await Promise.all([fetchCommunityNetwork(), fetchCommunityRanks()]);
      setNet(n);
      setRanks(r);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load ranks");
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const persist = async (next: { publish_ranks: boolean; peers: string[] }) => {
    setBusy(true);
    try {
      await saveCommunitySettings(next);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setBusy(false);
    }
  };

  const siteUrl = net?.urls.tailscale_site?.[0];
  const tsUrl = net?.urls.tailscale_api[0];
  const rows = ranks?.rows ?? [];

  return (
    <Card className="p-6 gloss-panel space-y-3">
      <div className="flex items-center gap-2">
        <Trophy className="w-5 h-5 text-primary" />
        <h2 className="font-semibold">Ranks (opt-in)</h2>
        <span className="ml-auto text-xs text-muted-foreground">
          {net?.publish_ranks ? "Sharing pulse" : "Private — not sharing"}
        </span>
      </div>
      <p className="text-sm text-muted-foreground">
        Off for everyone until you turn it on. Friends on Tailscale only see display name + today&apos;s
        Pulse — never notes, bible, or tracker titles.
      </p>
      {error ? <p className="text-xs text-destructive">{error}</p> : null}

      <label className="flex items-center justify-between gap-3 text-sm">
        <span>Publish my Pulse to people I add</span>
        <Switch
          checked={Boolean(net?.publish_ranks)}
          disabled={busy || !net}
          onCheckedChange={(on) =>
            void persist({ publish_ranks: on, peers: net?.peers ?? [] })
          }
        />
      </label>

      {!compact && net ? (
        <div className="text-sm space-y-1 rounded-lg border border-border/40 bg-muted/20 p-3">
          <p className="flex items-center gap-1 text-muted-foreground">
            <Wifi className="w-3.5 h-3.5" />
            {net.tailscale.hint}
          </p>
          {siteUrl ? (
            <p>
              <span className="text-muted-foreground">Whole site (phone browser): </span>
              <a className="text-primary break-all underline" href={siteUrl} target="_blank" rel="noreferrer">
                {siteUrl}
              </a>
            </p>
          ) : null}
          {tsUrl ? (
            <p>
              <span className="text-muted-foreground">API (Android / watch): </span>
              <code className="text-foreground break-all">{tsUrl}</code>
            </p>
          ) : null}
          {net.urls.lan_site ? (
            <p>
              <span className="text-muted-foreground">LAN site: </span>
              <code className="text-foreground break-all">{net.urls.lan_site}</code>
            </p>
          ) : null}
        </div>
      ) : null}

      {!compact ? (
        <div className="flex gap-2">
          <Input
            value={peerDraft}
            onChange={(e) => setPeerDraft(e.target.value)}
            placeholder="Friend Tailscale URL — http://100.x.x.x:8000"
          />
          <Button
            size="sm"
            disabled={busy || !peerDraft.trim()}
            onClick={() => {
              const next = [...(net?.peers ?? []), peerDraft.trim()];
              setPeerDraft("");
              void persist({ publish_ranks: Boolean(net?.publish_ranks), peers: next });
            }}
          >
            Add
          </Button>
        </div>
      ) : null}

      {!compact && (net?.peers ?? []).length > 0 ? (
        <ul className="text-xs text-muted-foreground space-y-1">
          {net!.peers.map((p) => (
            <li key={p} className="flex items-center justify-between gap-2">
              <code className="break-all">{p}</code>
              <button
                type="button"
                className="text-destructive hover:underline"
                onClick={() =>
                  void persist({
                    publish_ranks: Boolean(net?.publish_ranks),
                    peers: net!.peers.filter((x) => x !== p),
                  })
                }
              >
                Remove
              </button>
            </li>
          ))}
        </ul>
      ) : null}

      <div className="space-y-2">
        {rows.length === 0 ? (
          <p className="text-sm text-muted-foreground">Your Pulse shows here. Add a friend URL to compare.</p>
        ) : (
          rows.map((row) => (
            <div
              key={`${row.rank}-${row.display_name}`}
              className="flex items-center justify-between rounded-lg border border-border/40 px-3 py-2"
            >
              <div className="min-w-0">
                <p className="text-sm font-medium truncate">
                  #{row.rank} {row.display_name}
                  {row.you ? " (you)" : ""}
                </p>
                <p className="text-xs text-muted-foreground">{row.pulse_label}</p>
              </div>
              <p className={`text-lg font-semibold tabular-nums ${scoreColor(row.pulse)}`}>{row.pulse}</p>
            </div>
          ))
        )}
      </div>
      {ranks?.unreachable?.length ? (
        <p className="text-xs text-muted-foreground">
          Unreachable: {ranks.unreachable.join(", ")}. They must opt in and be on Tailscale.
        </p>
      ) : null}
      <Button type="button" variant="outline" size="sm" onClick={() => void refresh()} disabled={busy}>
        Refresh ranks
      </Button>
    </Card>
  );
}
