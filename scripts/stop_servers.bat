@echo off
REM Stop API (:8000) and Frontend (:5173) cleanly.
setlocal
call "%~dp0_common.bat" env-only
"%PY%" "%~dp0server_lifecycle.py" stop
endlocal
