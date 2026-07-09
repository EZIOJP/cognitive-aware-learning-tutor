# CALT Android APK — server hosting

The Cognitive backend serves the CALT Timetable APK for download from **Settings** in the web app and from the Android app’s **Check for updates**.

---

## Files on disk

| Path | Purpose |
|------|---------|
| `data/downloads/calt-android.apk` | The installable APK (built elsewhere, copied here) |
| `data/downloads/calt-android.manifest.json` | Version metadata shown in UI |

**These files are not auto-generated.** Run the publish script after each Android build.

---

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/app/calt-android/latest` | JSON: version, size, release notes, `download_url` |
| GET | `/api/app/calt-android/download` | Serves `calt-android.apk` |

Implementation: `backend/app/router.py`

---

## Publish workflow (after Android build)

```bat
REM 1. Build Android app (in calt-timetable folder)
cd "..\New folder (6)\calt-timetable"
set JAVA_HOME=C:\Program Files\Android\Android Studio\jbr
gradlew.bat assembleDebug

REM 2. Copy APK into Cognitive downloads
cd "..\Cognitive-Aware Learning Tutor"
scripts\publish_calt_apk.bat

REM 3. (Optional) Edit version in data\downloads\calt-android.manifest.json

REM 4. Start stack
run.bat
```

---

## Web UI

**Settings** → **CALT Timetable (Android)**

- Shows version from manifest + file size from APK
- **Download APK** → `/api/app/calt-android/download`
- **Refresh** → re-fetches `/latest`

Frontend: `src/pages/settings/CaltAndroidDownloadCard.tsx`

---

## Phone download URLs

Replace `<PC-IP>` with your PC’s LAN address (`ipconfig` → IPv4):

```
http://<PC-IP>:8000/api/app/calt-android/download
http://<PC-IP>:8000/api/app/calt-android/latest
```

Or open the Cognitive web app on the phone → **Settings**.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| 404 “CALT Android build not available” | Run `scripts\publish_calt_apk.bat` after building APK |
| Download works on PC but not phone | Same Wi‑Fi; firewall allow port 8000; use LAN IP not `localhost` |
| Version wrong in UI | Update `calt-android.manifest.json` |
| Publish script fails | Build APK first; check path to `calt-timetable` in `scripts\publish_calt_apk.bat` |

---

## Android app update check

The CALT app calls `GET /api/app/calt-android/latest` using the **same server URL** configured in Settings. If `version_code` on the server is higher than installed, it offers **Download**.

See also: `New folder (6)/calt-timetable/docs/RELEASE.md`
