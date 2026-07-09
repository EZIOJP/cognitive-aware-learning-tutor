import { useEffect, useState } from "react";
import { Download, RefreshCw, Smartphone } from "lucide-react";
import { Button } from "../../app/components/ui/button";
import {
  caltAndroidDownloadUrl,
  fetchCaltAndroidLatest,
  formatApkSize,
  type CaltAndroidLatest,
} from "../../api/appClient";

export function CaltAndroidDownloadCard() {
  const [info, setInfo] = useState<CaltAndroidLatest | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      setInfo(await fetchCaltAndroidLatest());
    } catch (e) {
      setInfo(null);
      setError(e instanceof Error ? e.message : "Could not reach server");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const downloadUrl = caltAndroidDownloadUrl();

  return (
    <div className="space-y-3">
      <p className="text-sm text-muted-foreground">
        Install or update the CALT Timetable companion on your phone. Open this page on
        Android, tap download, then allow install from your browser.
      </p>

      {loading && (
        <p className="text-sm text-muted-foreground">Checking for build on server…</p>
      )}

      {!loading && error && (
        <div className="space-y-2">
          <p className="text-sm text-destructive">{error}</p>
          <p className="text-xs text-muted-foreground">
            On the PC: build the APK, then run{" "}
            <code className="text-xs bg-muted px-1 rounded">scripts\publish_calt_apk.bat</code>
          </p>
          <Button type="button" variant="outline" size="sm" onClick={() => void load()}>
            <RefreshCw className="w-4 h-4 mr-1" />
            Retry
          </Button>
        </div>
      )}

      {!loading && info && (
        <div className="space-y-3">
          <div className="text-sm space-y-1">
            <p>
              <span className="font-medium">Version {info.version_name}</span>
              <span className="text-muted-foreground"> · build {info.version_code}</span>
            </p>
            <p className="text-muted-foreground">
              {formatApkSize(info.size_bytes)} · updated{" "}
              {new Date(info.updated_at).toLocaleString()}
            </p>
            {info.release_notes ? (
              <p className="text-muted-foreground">{info.release_notes}</p>
            ) : null}
          </div>
          <div className="flex flex-wrap gap-2">
            <Button asChild>
              <a href={downloadUrl} download={info.filename}>
                <Download className="w-4 h-4 mr-1" />
                Download APK
              </a>
            </Button>
            <Button type="button" variant="outline" size="sm" onClick={() => void load()}>
              <RefreshCw className="w-4 h-4 mr-1" />
              Refresh
            </Button>
          </div>
          <p className="text-xs text-muted-foreground">
            Phone on Wi‑Fi: use the same LAN URL as Settings in the app (
            <code className="bg-muted px-1 rounded">/api/app/calt-android/download</code>
            ). USB:{" "}
            <code className="bg-muted px-1 rounded">adb reverse tcp:8000 tcp:8000</code>
          </p>
        </div>
      )}
    </div>
  );
}

export function CaltAndroidDownloadCardHeader() {
  return (
    <div className="flex items-center gap-2 mb-2">
      <Smartphone className="w-5 h-5" />
      <h2 className="font-medium">CALT Timetable (Android)</h2>
    </div>
  );
}
