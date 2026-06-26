@echo off
setlocal
cd /d "%~dp0"

if exist ".venv\Scripts\pip.exe" (
  set "PIP=.venv\Scripts\pip.exe"
) else (
  set "PIP=pip"
)

echo Installing Whisper dependencies (torch, transformers)...
echo This may take several minutes and downloads ~1.5 GB for large-v3-turbo on first use.
"%PIP%" install -r requirements-whisper.txt
echo Done.
endlocal
