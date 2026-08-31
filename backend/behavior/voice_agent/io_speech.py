"""Speech IO: Windows STT + Edge neural / Piper / SAPI TTS.

Voice modes (`jarvis` default | `normal`):
  - jarvis: en-GB-RyanNeural (+ rate/pitch) and light DSP post-filter on WAV
  - normal: plainer en-US-JennyNeural, natural rate, no Jarvis filter

Preference: VOICE_AGENT_TTS_MODE env → runtime/file `data/voice_agent/tts_mode.json`.
Env VOICE_AGENT_VOICE / VOICE_AGENT_TTS_RATE / VOICE_AGENT_TTS_PITCH still override.

Optional faster-whisper (CUDA) loads only during a voice session; call
`release_stt_models()` from session end. edge-tts remains the default TTS fallback.
Kokoro GPU TTS is deferred — see voice GPU session design spec.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import json
import logging
import os
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path

from backend.paths import ROOT

log = logging.getLogger("desktop_tracker.voice_agent")

_PIPER_DIR = ROOT / "data" / "voice_agent" / "piper"
_TTS_DIR = ROOT / "data" / "voice_agent" / "tts"
_TTS_MODE_PATH = ROOT / "data" / "voice_agent" / "tts_mode.json"

# Calm British male — Jarvis-adjacent butler vibe (Microsoft neural, free via edge-tts).
DEFAULT_EDGE_VOICE = "en-GB-RyanNeural"
DEFAULT_EDGE_RATE = "-8%"
DEFAULT_EDGE_PITCH = "-2Hz"
# Plainer US neural for normal mode.
NORMAL_EDGE_VOICE = "en-US-JennyNeural"
NORMAL_EDGE_RATE = "+0%"
NORMAL_EDGE_PITCH = "+0Hz"

TTS_MODES = ("jarvis", "normal")
DEFAULT_TTS_MODE = "jarvis"

_logged_edge_missing = False
_logged_whisper_skip = False

# In-process mutex — never run two TTS engines at once (Edge + SAPI overlap).
_speak_mutex = threading.Lock()

_whisper_lock = threading.Lock()
_whisper_model = None  # session-scoped; unloaded via release_stt_models()

_mode_lock = threading.Lock()
_runtime_mode: str | None = None  # set by set_tts_mode; mirrored to file


def tts_preference() -> str:
    """Return VOICE_AGENT_TTS: edge | piper | sapi (default edge)."""
    raw = (os.environ.get("VOICE_AGENT_TTS") or "edge").strip().lower()
    if raw in ("edge", "piper", "sapi"):
        return raw
    return "edge"


def get_tts_mode() -> str:
    """Current voice mode: jarvis | normal.

    Order: VOICE_AGENT_TTS_MODE env (if valid) → runtime/file → default jarvis.
    """
    env = (os.environ.get("VOICE_AGENT_TTS_MODE") or "").strip().lower()
    if env in TTS_MODES:
        return env
    with _mode_lock:
        if _runtime_mode in TTS_MODES:
            return _runtime_mode  # type: ignore[return-value]
    stored = _read_tts_mode_file()
    if stored in TTS_MODES:
        return stored
    return DEFAULT_TTS_MODE


def set_tts_mode(mode: str) -> str:
    """Persist and activate jarvis|normal. Returns normalized mode."""
    global _runtime_mode
    m = (mode or "").strip().lower()
    if m not in TTS_MODES:
        raise ValueError(f"tts mode must be one of {TTS_MODES}, got {mode!r}")
    with _mode_lock:
        _runtime_mode = m
        try:
            _TTS_MODE_PATH.parent.mkdir(parents=True, exist_ok=True)
            _TTS_MODE_PATH.write_text(
                json.dumps({"mode": m}, indent=2),
                encoding="utf-8",
            )
        except OSError as exc:
            log.warning("Could not persist tts_mode.json: %s", exc)
    return m


def _read_tts_mode_file() -> str | None:
    try:
        if not _TTS_MODE_PATH.is_file():
            return None
        data = json.loads(_TTS_MODE_PATH.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            m = str(data.get("mode") or "").strip().lower()
            return m if m in TTS_MODES else None
    except (OSError, json.JSONDecodeError):
        return None
    return None


def edge_voice() -> str:
    """Active Edge voice: VOICE_AGENT_VOICE env wins; else mode default."""
    env = (os.environ.get("VOICE_AGENT_VOICE") or "").strip()
    if env:
        return env
    if get_tts_mode() == "normal":
        return NORMAL_EDGE_VOICE
    return DEFAULT_EDGE_VOICE


def edge_rate() -> str:
    env = (os.environ.get("VOICE_AGENT_TTS_RATE") or "").strip()
    if env:
        return env
    if get_tts_mode() == "normal":
        return NORMAL_EDGE_RATE
    return DEFAULT_EDGE_RATE


def edge_pitch() -> str:
    env = (os.environ.get("VOICE_AGENT_TTS_PITCH") or "").strip()
    if env:
        return env
    if get_tts_mode() == "normal":
        return NORMAL_EDGE_PITCH
    return DEFAULT_EDGE_PITCH


def reset_speak_mutex_for_tests() -> None:
    """Replace in-process TTS mutex (tests / gate_alerts reset). Never release cross-thread."""
    global _speak_mutex
    _speak_mutex = threading.Lock()


def speak(text: str) -> None:
    """Speak text with one audio stream at a time (skip if already speaking)."""
    text = (text or "").strip()
    if not text:
        return
    # Non-blocking: if another utterance holds the lock, drop (gate_alerts queues).
    acquired = _speak_mutex.acquire(blocking=False)
    if not acquired:
        log.debug("speak skipped — already speaking")
        return
    held_cross = False
    try:
        from backend.behavior import gate_alerts as ga

        # Gate worker already holds the cross-process lock when it calls us.
        if getattr(ga, "_speaking", False):
            held_cross = False
        else:
            held_cross = ga._acquire_cross_process(wait_s=5.0)
            if not held_cross:
                log.debug("speak skipped — another process holds TTS")
                return
        pref = tts_preference()
        if pref == "sapi":
            _speak_sapi(text)
            return
        if pref == "piper":
            if _speak_piper(text):
                return
            _speak_sapi(text)
            return
        # default / edge: neural → piper → SAPI
        if _speak_edge(text):
            return
        if _speak_piper(text):
            return
        _speak_sapi(text)
    finally:
        if held_cross:
            try:
                from backend.behavior import gate_alerts as ga

                ga._release_cross_process()
            except Exception:  # noqa: BLE001
                pass
        if acquired:
            try:
                _speak_mutex.release()
            except RuntimeError:
                log.debug("speak mutex release skipped — not held by this thread")


def _speak_sapi(text: str) -> None:
    if os.name != "nt":
        log.info("TTS (no SAPI): %s", text[:120])
        return
    # Escape for PowerShell single-quoted string
    safe = text.replace("'", "''")[:800]
    ps = (
        "Add-Type -AssemblyName System.Speech; "
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        f"$s.Speak('{safe}')"
    )
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            check=False,
            capture_output=True,
            timeout=60,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("SAPI TTS failed: %s", exc)


def _maybe_jarvis_filter_wav(wav_path: Path) -> Path:
    """Apply Jarvis DSP when mode is jarvis; on error return original path."""
    if get_tts_mode() != "jarvis":
        return wav_path
    try:
        from backend.behavior.voice_agent.jarvis_filter import apply_jarvis_filter

        filtered = apply_jarvis_filter(wav_path, out_path=_TTS_DIR / "_last_jarvis.wav")
        if filtered.is_file() and filtered.stat().st_size > 44:
            return filtered
    except Exception as exc:  # noqa: BLE001
        log.debug("Jarvis filter skipped: %s", exc)
    return wav_path


def _mp3_to_wav(mp3_path: Path, wav_path: Path) -> bool:
    """Best-effort MP3→WAV. ffmpeg if on PATH, else Windows WinRT transcoder. Fail soft."""
    wav_path = Path(wav_path)
    wav_path.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        try:
            proc = subprocess.run(
                [
                    ffmpeg,
                    "-y",
                    "-i",
                    str(mp3_path),
                    "-acodec",
                    "pcm_s16le",
                    "-ar",
                    "24000",
                    str(wav_path),
                ],
                capture_output=True,
                timeout=60,
                check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if proc.returncode == 0 and wav_path.is_file() and wav_path.stat().st_size > 44:
                return True
        except Exception as exc:  # noqa: BLE001
            log.debug("ffmpeg mp3→wav failed: %s", exc)
    if os.name == "nt":
        return _mp3_to_wav_winrt(mp3_path, wav_path)
    return False


def _mp3_to_wav_winrt(mp3_path: Path, wav_path: Path) -> bool:
    """Convert MP3→WAV via Windows Media Transcoder (Win10+). Best-effort."""
    # Escape for PowerShell single-quoted strings
    src = str(Path(mp3_path).resolve()).replace("'", "''")
    dst = str(Path(wav_path).resolve()).replace("'", "''")
    ps = f"""
$ErrorActionPreference = 'Stop'
try {{
  Add-Type -AssemblyName System.Runtime.WindowsRuntime | Out-Null
  $null = [Windows.Storage.StorageFile,Windows.Storage,ContentType=WindowsRuntime]
  $null = [Windows.Media.MediaProperties.MediaEncodingProfile,Windows.Media,ContentType=WindowsRuntime]
  $null = [Windows.Media.Transcoding.MediaTranscoder,Windows.Media,ContentType=WindowsRuntime]
  $asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() |
    Where-Object {{ $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and
      $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' }})[0]
  function Await-Op($WinRtTask, $ResultType) {{
    $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
    $netTask = $asTask.Invoke($null, @($WinRtTask))
    $netTask.Wait(60000) | Out-Null
    if (-not $netTask.IsCompleted) {{ throw 'timeout' }}
    return $netTask.Result
  }}
  $asTaskAction = ([System.WindowsRuntimeSystemExtensions].GetMethods() |
    Where-Object {{ $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and
      $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncAction' }})[0]
  function Await-Action($WinRtTask) {{
    $netTask = $asTaskAction.Invoke($null, @($WinRtTask))
    $netTask.Wait(60000) | Out-Null
  }}
  $srcFile = Await-Op ([Windows.Storage.StorageFile]::GetFileFromPathAsync('{src}')) ([Windows.Storage.StorageFile])
  $outFolder = Await-Op ([Windows.Storage.StorageFolder]::GetFolderFromPathAsync([IO.Path]::GetDirectoryName('{dst}'))) ([Windows.Storage.StorageFolder])
  $outName = [IO.Path]::GetFileName('{dst}')
  $dstFile = Await-Op ($outFolder.CreateFileAsync($outName, [Windows.Storage.CreationCollisionOption]::ReplaceExisting)) ([Windows.Storage.StorageFile])
  $profile = [Windows.Media.MediaProperties.MediaEncodingProfile]::CreateWav(
    [Windows.Media.MediaProperties.AudioEncodingQuality]::Medium)
  $transcoder = New-Object Windows.Media.Transcoding.MediaTranscoder
  $prep = Await-Op ($transcoder.PrepareFileTranscodeAsync($srcFile, $dstFile, $profile)) ([Windows.Media.Transcoding.PrepareTranscodeResult])
  if (-not $prep.CanTranscode) {{ throw "cannot transcode: $($prep.FailureReason)" }}
  Await-Action ($prep.TranscodeAsync())
  if (-not (Test-Path -LiteralPath '{dst}')) {{ throw 'missing output' }}
  exit 0
}} catch {{
  [Console]::Error.WriteLine($_.Exception.Message)
  exit 1
}}
"""
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
            capture_output=True,
            timeout=90,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        ok = proc.returncode == 0 and wav_path.is_file() and wav_path.stat().st_size > 44
        if not ok and proc.stderr:
            log.debug("WinRT mp3→wav: %s", proc.stderr.decode("utf-8", errors="replace")[:300])
        return ok
    except Exception as exc:  # noqa: BLE001
        log.debug("WinRT mp3→wav failed: %s", exc)
        return False


def _speak_piper(text: str) -> bool:
    """Use piper CLI if piper.exe + .onnx model exist under data/voice_agent/piper/."""
    exe = shutil.which("piper") or str(_PIPER_DIR / "piper.exe")
    if not Path(exe).is_file() and not shutil.which("piper"):
        return False
    models = list(_PIPER_DIR.glob("*.onnx"))
    if not models:
        return False
    model = models[0]
    out_wav = _PIPER_DIR / "_last.wav"
    try:
        _PIPER_DIR.mkdir(parents=True, exist_ok=True)
        proc = subprocess.run(
            [exe, "--model", str(model), "--output_file", str(out_wav)],
            input=text.encode("utf-8"),
            capture_output=True,
            timeout=60,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if proc.returncode != 0 or not out_wav.is_file():
            return False
        play = _maybe_jarvis_filter_wav(out_wav)
        _play_wav(play)
        return True
    except Exception as exc:  # noqa: BLE001
        log.debug("Piper TTS skipped: %s", exc)
        return False


def _speak_edge(text: str) -> bool:
    """Microsoft Edge neural TTS via edge-tts (needs network + package)."""
    global _logged_edge_missing
    try:
        import edge_tts  # noqa: F401
    except ImportError:
        if not _logged_edge_missing:
            _logged_edge_missing = True
            log.info(
                "edge-tts not installed — using Piper/SAPI. "
                "For Jarvis-like neural voice: pip install edge-tts"
            )
        return False

    voice = edge_voice()
    rate = edge_rate()
    pitch = edge_pitch()
    out_mp3: Path | None = None
    out_wav: Path | None = None
    try:
        _TTS_DIR.mkdir(parents=True, exist_ok=True)
        # Unique files — concurrent processes must not fight over _last.mp3
        fd, tmp_name = tempfile.mkstemp(suffix=".mp3", prefix="edge_", dir=str(_TTS_DIR))
        os.close(fd)
        out_mp3 = Path(tmp_name)
        _run_async(_edge_save(text, voice=voice, rate=rate, pitch=pitch, path=out_mp3))
        if not out_mp3.is_file() or out_mp3.stat().st_size < 32:
            return False
        # Jarvis mode: convert → filter → play WAV when possible; else unfiltered mp3
        if get_tts_mode() == "jarvis":
            out_wav = out_mp3.with_suffix(".wav")
            if _mp3_to_wav(out_mp3, out_wav):
                play = _maybe_jarvis_filter_wav(out_wav)
                _play_wav(play)
                return True
        _play_mp3(out_mp3)
        return True
    except Exception as exc:  # noqa: BLE001
        log.warning("edge-tts failed (%s); falling back. voice=%s", exc, voice)
        return False
    finally:
        for p in (out_mp3, out_wav):
            if p is None:
                continue
            try:
                p.unlink(missing_ok=True)
            except OSError:
                pass


async def _edge_save(
    text: str,
    *,
    voice: str,
    rate: str,
    pitch: str,
    path: Path,
) -> None:
    import edge_tts

    communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
    await communicate.save(str(path))


def _run_async(coro):
    """Run coroutine; safe if an event loop is already running (tracker UI)."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result(timeout=90)


def _play_wav(path: Path) -> None:
    if os.name == "nt":
        try:
            import winsound

            winsound.PlaySound(str(path), winsound.SND_FILENAME)
            return
        except Exception:
            pass
    if os.name == "nt":
        subprocess.run(
            ["cmd", "/c", "start", "/min", "", str(path)],
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )


def _play_mp3(path: Path) -> None:
    """Play MP3 on Windows via WPF MediaPlayer (no ffmpeg)."""
    if os.name != "nt":
        log.info("TTS mp3 saved (no player): %s", path)
        return
    # Escape for PowerShell single-quoted path
    safe = str(path.resolve()).replace("'", "''")
    ps = (
        "Add-Type -AssemblyName PresentationCore; "
        "$p = New-Object System.Windows.Media.MediaPlayer; "
        f"$p.Open([Uri]::new('{safe}')); "
        "$p.Play(); "
        "$deadline = (Get-Date).AddSeconds(90); "
        "Start-Sleep -Milliseconds 200; "
        "while ($p.NaturalDuration.HasTimeSpan -eq $false -and (Get-Date) -lt $deadline) { "
        "  Start-Sleep -Milliseconds 50 "
        "}; "
        "if ($p.NaturalDuration.HasTimeSpan) { "
        "  while ($p.Position -lt $p.NaturalDuration.TimeSpan -and (Get-Date) -lt $deadline) { "
        "    Start-Sleep -Milliseconds 80 "
        "  } "
        "} else { Start-Sleep -Seconds 2 }; "
        "$p.Close()"
    )
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            check=False,
            capture_output=True,
            timeout=120,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if proc.returncode != 0:
            log.debug("MediaPlayer mp3 play rc=%s", proc.returncode)
    except Exception as exc:  # noqa: BLE001
        log.warning("MP3 playback failed: %s", exc)


def whisper_model_size() -> str:
    return (os.environ.get("VOICE_AGENT_WHISPER_MODEL") or "base").strip() or "base"


def _whisper_device() -> str:
    """Prefer CUDA when available; else CPU. Never hard-fail."""
    forced = (os.environ.get("VOICE_AGENT_WHISPER_DEVICE") or "").strip().lower()
    if forced in ("cuda", "cpu"):
        return forced
    try:
        import torch

        if torch.cuda.is_available():
            return "cuda"
    except Exception:  # noqa: BLE001
        pass
    return "cpu"


def _get_whisper_model():
    """Lazy-load faster-whisper for this session only. Optional dependency."""
    global _whisper_model, _logged_whisper_skip
    with _whisper_lock:
        if _whisper_model is not None:
            return _whisper_model
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            if not _logged_whisper_skip:
                _logged_whisper_skip = True
                log.info(
                    "faster-whisper not installed — using SpeechRecognition. "
                    "Optional GPU STT: pip install faster-whisper"
                )
            return None
        device = _whisper_device()
        compute = "float16" if device == "cuda" else "int8"
        size = whisper_model_size()
        try:
            log.info("Loading faster-whisper model=%s device=%s", size, device)
            _whisper_model = WhisperModel(size, device=device, compute_type=compute)
            return _whisper_model
        except Exception as exc:  # noqa: BLE001
            if device == "cuda":
                log.warning("faster-whisper CUDA failed (%s); retrying CPU", exc)
                try:
                    _whisper_model = WhisperModel(size, device="cpu", compute_type="int8")
                    return _whisper_model
                except Exception as exc2:  # noqa: BLE001
                    log.warning("faster-whisper unavailable: %s", exc2)
                    return None
            log.warning("faster-whisper unavailable: %s", exc)
            return None


def stt_model_resident() -> bool:
    """True if a faster-whisper instance is currently held (should be false when idle)."""
    with _whisper_lock:
        return _whisper_model is not None


def release_stt_models() -> None:
    """Unload session-scoped STT (faster-whisper). Safe when never loaded.

    edge-tts / Piper / SAPI are not kept warm — each speak() is ephemeral.
    """
    global _whisper_model
    model = None
    with _whisper_lock:
        model = _whisper_model
        _whisper_model = None
    if model is None:
        return
    try:
        del model
    except Exception:  # noqa: BLE001
        pass
    try:
        import gc

        gc.collect()
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:  # noqa: BLE001
        pass
    log.info("Released voice STT models (session end)")


def _transcribe_wav_faster_whisper(wav_path: Path) -> str:
    model = _get_whisper_model()
    if model is None:
        return ""
    try:
        segments, _info = model.transcribe(str(wav_path), beam_size=1, vad_filter=True)
        parts = [seg.text for seg in segments if getattr(seg, "text", None)]
        return " ".join(p.strip() for p in parts if p and p.strip()).strip()
    except Exception as exc:  # noqa: BLE001
        log.warning("faster-whisper transcribe failed: %s", exc)
        return ""


def listen_once(timeout_s: float = 6.0) -> str:
    """Mic STT: optional faster-whisper, else SpeechRecognition (sphinx/google)."""
    try:
        import speech_recognition as sr
    except ImportError:
        log.info("speech_recognition not installed — use text box")
        return ""
    recognizer = sr.Recognizer()
    try:
        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.3)
            audio = recognizer.listen(source, timeout=timeout_s, phrase_time_limit=12)
    except Exception as exc:  # noqa: BLE001
        log.warning("Microphone/STT unavailable: %s", exc)
        return ""

    # Prefer session-scoped faster-whisper when optional dep is present
    try:
        wav_bytes = audio.get_wav_data()
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(wav_bytes)
            tmp_path = Path(tmp.name)
        try:
            heard = _transcribe_wav_faster_whisper(tmp_path)
            if heard:
                return heard
        finally:
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:  # noqa: BLE001
                pass
    except Exception as exc:  # noqa: BLE001
        log.debug("whisper path skipped: %s", exc)

    try:
        return (recognizer.recognize_sphinx(audio) or "").strip()
    except Exception:
        pass
    try:
        return (recognizer.recognize_google(audio) or "").strip()
    except Exception as exc:
        log.warning("STT failed: %s", exc)
        return ""
