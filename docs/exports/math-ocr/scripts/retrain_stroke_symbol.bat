@echo off
setlocal
call "%~dp0_common.bat"
if errorlevel 1 exit /b 1

echo Retraining stroke_symbol from DSC_handwriting_dataset paths_json...
"%PY%" "%ROOT%\scripts\retrain_stroke_symbol.py" %*
endlocal
