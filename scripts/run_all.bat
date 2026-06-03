@echo off
setlocal
call "%~dp0_common.bat"
if errorlevel 1 exit /b 1

echo.
echo Starting Cognitive-Aware Learning Tutor...
echo   API:       http://localhost:8000/health
echo   Frontend:  http://localhost:5173
echo   Login:     admin / admin123
echo.

echo Applying database migrations...
"%PY%" -m alembic upgrade head
if errorlevel 1 (
  echo Migration failed. Fix errors above before continuing.
  pause
  exit /b 1
)

start "API" cmd /k "cd /d "%ROOT%" & "%PY%" -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload"
start "Frontend" cmd /k "cd /d "%ROOT%" & npm.cmd run dev"

echo Both servers opened in separate windows. Keep them open while using the app.
endlocal
