@echo off
setlocal
call "%~dp0_common.bat" env-only

echo Focus mirror (Python OpenCV) — backend on http://localhost:8000
echo Optional: set FACE_TRACKER_TOKEN in .env to your login JWT for hub sync.
"%PY%" "%ROOT%\backend\face_tracker.py"
endlocal
