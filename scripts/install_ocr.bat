@echo off
setlocal
call "%~dp0_common.bat"
if errorlevel 1 exit /b 1

echo Installing math OCR (pix2tex) — Windows-safe pins, no MSVC stringzilla build...
"%PIP%" install pix2tex==0.1.4 --no-deps
if errorlevel 1 exit /b 1
"%PIP%" install -r "%ROOT%\backend\requirements-ocr.txt"
if errorlevel 1 exit /b 1

echo.
echo Verifying LatexOCR import...
"%PY%" -c "from pix2tex.cli import LatexOCR; print('OK: pix2tex ready')"
if errorlevel 1 (
  echo ERROR: OCR verification failed.
  exit /b 1
)
echo Done. Restart the API server, then use /math-tutor/recognize-test
endlocal
