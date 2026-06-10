@echo off
setlocal
call "%~dp0_common.bat"
if errorlevel 1 exit /b 1

echo Pre-downloading TexTeller ONNX weights (may take several minutes)...
set TEXTELLER_CACHE_DIR=%ROOT%\models\texteller
if not exist "%TEXTELLER_CACHE_DIR%" mkdir "%TEXTELLER_CACHE_DIR%"

"%PY%" -c "from optimum.onnxruntime import ORTModelForVision2Seq; from transformers import AutoImageProcessor, AutoTokenizer; mid='Ji-Ha/TexTeller3-ONNX-dynamic'; c='%TEXTELLER_CACHE_DIR%'; ORTModelForVision2Seq.from_pretrained(mid, provider='CPUExecutionProvider', export=False, cache_dir=c); AutoImageProcessor.from_pretrained(mid, cache_dir=c); AutoTokenizer.from_pretrained(mid, cache_dir=c); print('OK: cached to', c)"

if errorlevel 1 exit /b 1
echo Done.
endlocal
