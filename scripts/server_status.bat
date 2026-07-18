@echo off
REM Show whether API / Frontend are listening and healthy.
setlocal
call "%~dp0_common.bat" env-only
"%PY%" "%~dp0server_lifecycle.py" status
endlocal
