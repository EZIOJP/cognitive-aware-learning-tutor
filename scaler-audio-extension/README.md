# Scaler Lecture Audio — Chrome extension

Download lecture audio from **Scaler** (scaler.com) for local **Whisper** transcription in Transcript Notes Studio.

> **Personal study only.** Use only for courses you're enrolled in. Do not redistribute downloaded content.

## Install (Chrome / Edge)

1. Open `chrome://extensions`
2. Enable **Developer mode**
3. **Load unpacked** → select this folder:  
   `scaler-audio-extension/`
4. Pin **Scaler Lecture Audio** on the toolbar

## Use

1. Open a **Scaler lecture** in Chrome and **start the video** (so the player loads media URLs).
2. Click the extension icon → **Scan this tab**.
3. Pick a URL and click **Save** (goes to `Downloads/Scaler/`).
   - **`.m3u8` (HLS)** — extension merges segments into a `.ts` file (Whisper can transcribe it).
   - **`.mp4` / `.webm`** — direct download.
4. If no URLs appear, use **Record audio**:
   - Click Record → **play the full lecture** → click **Stop recording**.
   - Saves `.webm` to `Downloads/Scaler/`.

## Whisper pipeline (10/10 transcript path)

1. **Transcript Notes Studio** → **Transcribe audio** tab  
2. Select the downloaded file from `Downloads/Scaler/`  
3. Run Whisper → get full `.txt` transcript  
4. **Summarize** with PDF/Colab references (semantic grouping on)

Full lecture audio → **15k–40k words** instead of ~1k from live captions.

## Troubleshooting

| Issue | Try |
|-------|-----|
| No URLs on scan | Start video playback, wait 10s, scan again |
| Player in iframe | Extension scans all frames; refresh page |
| HLS download fails | Use **Record audio** while video plays |
| CORS on download | Record fallback always works in-browser |

## Files

- `content.js` — detects video + captures media URLs (fetch/XHR hook)
- `background.js` — HLS merge + `chrome.downloads`
- `popup.html/js` — UI

## Optional: copy into project transcripts folder

After download, copy the file to:

`data/transcripts/` or `transcript-notes-studio/data/transcripts/`

Then summarize from Studio or Study Library.
