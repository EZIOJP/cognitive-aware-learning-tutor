@echo off
setlocal
call "%~dp0_common.bat"
if errorlevel 1 exit /b 1

echo.
echo === Installing UniMERNet-T (second OCR engine) ===
echo This downloads ~500MB from Hugging Face. Please wait...
echo.

"%PIP%" install tokenizers ftfy huggingface_hub
if errorlevel 1 exit /b 1

"%PY%" "%ROOT%\scripts\install_unimernet.py"
if errorlevel 1 (
  echo.
  echo Install failed. Check network connection and try again.
  exit /b 1
)

echo.
echo Done. Restart run.bat / API server, then open Math Practice or Recognize Test.
endlocal
