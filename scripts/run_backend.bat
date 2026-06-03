@echo off
setlocal
call "%~dp0_common.bat"
if errorlevel 1 exit /b 1

echo Vocab API: http://localhost:8000/api/vocab
"%PY%" -m uvicorn backend.vocab_backend:app --host 0.0.0.0 --port 8000 --reload
endlocal
