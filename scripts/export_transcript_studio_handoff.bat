@echo off
setlocal
cd /d "%~dp0..\transcript-notes-studio"
echo === Export Transcript Notes Studio handoff bundle ===
python export_handoff.py %*
if errorlevel 1 exit /b 1
echo.
echo Bundle ready. Move handoff-export\ anywhere or zip it for another agent.
endlocal
