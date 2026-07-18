@echo off
REM Same as control.bat — keep under scripts\ for discoverability.
setlocal
call "%~dp0_common.bat" env-only
"%PY%" "%~dp0server_lifecycle.py" menu
endlocal
