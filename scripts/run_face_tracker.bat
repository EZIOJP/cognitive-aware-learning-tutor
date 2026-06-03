@echo off
setlocal
call "%~dp0_common.bat" env-only

echo Face tracker — vocab backend should be on http://localhost:8000
"%PY%" "%ROOT%\backend\face_tracker.py"
endlocal
