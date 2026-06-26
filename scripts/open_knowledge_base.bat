@echo off
cd /d "%~dp0.."
echo Opening Knowledge Base setup in your browser...
echo Make sure run.bat is running (frontend + backend).
start "" "http://localhost:5173/knowledge-base"
exit /b 0
