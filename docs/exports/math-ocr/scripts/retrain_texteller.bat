@echo off
setlocal
call "%~dp0_common.bat"
if errorlevel 1 exit /b 1

echo Exporting DSC_handwriting_dataset.csv for TexTeller fine-tune...
"%PY%" "%ROOT%\scripts\retrain_texteller.py" --mode export %*
if errorlevel 1 exit /b 1
echo.
echo Dataset under data\math\texteller_finetune\train\
echo To fine-tune: clone TexTeller, set TEXTELLER_TRAIN_REPO, pip install texteller[train], then:
echo   "%PY%" "%ROOT%\scripts\retrain_texteller.py" --mode train
endlocal
