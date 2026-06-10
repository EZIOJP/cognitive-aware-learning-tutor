@echo off
setlocal
call "%~dp0_common.bat"
if errorlevel 1 exit /b 1

echo Installing math OCR (TexTeller ONNX, CPU only)...
"%PIP%" install -r "%ROOT%\backend\requirements-ocr.txt"
if errorlevel 1 exit /b 1

echo.
echo Verifying TexTeller ONNX stack...
"%PY%" -c "from backend.math.texteller_onnx import texteller_available; assert texteller_available(); print('OK: TexTeller ONNX ready (model downloads on first Recognize)')"
if errorlevel 1 (
  echo ERROR: OCR verification failed.
  exit /b 1
)
echo Done. Restart the API server, then use /math-tutor/recognize-test
endlocal
