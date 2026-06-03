@echo off
setlocal
call "%~dp0_common.bat"
if errorlevel 1 exit /b 1

echo.
echo Starting Cognitive-Aware Learning Tutor...
echo   Vocab API: http://localhost:8000/api/vocab
echo   Frontend:  http://localhost:5173
echo.

start "Vocab API" cmd /k "cd /d "%ROOT%" & "%PY%" -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload"
start "Frontend" cmd /k "cd /d "%ROOT%" & npm.cmd run dev"

echo Both servers opened in separate windows. Keep them open while using the app.
endlocal
