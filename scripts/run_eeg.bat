@echo off
setlocal
rem Optional EEG / WebSocket prototype (backend_example.py) — not the main vocab API
call "%~dp0_common.bat" env-only

echo EEG reference backend (local): http://localhost:8000/health
call "%~dp0print_lan_urls.bat"
"%PY%" -m uvicorn backend.backend_example:app --host 0.0.0.0 --port 8000 --reload
endlocal
