@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0.."

set "LIB=data\raw_library\linear_algebra"
set "LOGDIR=data\logs"
set "REPORT=%LOGDIR%\corpus_setup_latest.log"
if not exist "%LOGDIR%" mkdir "%LOGDIR%"

> "%REPORT%" echo ============================================================
>> "%REPORT%" echo Corpus MML setup report
>> "%REPORT%" echo Started: %DATE% %TIME%
>> "%REPORT%" echo Project: %CD%
>> "%REPORT%" echo ============================================================
>> "%REPORT%" echo.

call :writelog "Step 1: Ensure metadata.json"
if not exist "%LIB%\metadata.json" (
  copy /Y "%LIB%\metadata.json.example" "%LIB%\metadata.json" >> "%REPORT%" 2>&1
  call :writelog "  Created metadata.json"
) else (
  call :writelog "  metadata.json OK"
)

call :writelog "Step 2: Find Mathematics for Machine Learning PDF (Deisenroth)"
set "DEST=%LIB%\Mathematics_for_ML.pdf"
set "FOUND=0"
if exist "%DEST%" (
  for %%F in ("%DEST%") do call :writelog "  PDF present: %%~nxF (%%~zF bytes)"
  set "FOUND=1"
  goto :pdf_done
)
for %%F in ("%USERPROFILE%\Downloads\*.pdf") do (
  set "NAME=%%~nxF"
  echo !NAME! | findstr /I /C:"Deisenroth" /C:"Mathematics for Machine Learning" >nul
  if not errorlevel 1 (
    echo !NAME! | findstr /I "Designing Huyen Grus Bruce Mitchell" >nul
    if errorlevel 1 (
      copy /Y "%%~F" "%DEST%" >> "%REPORT%" 2>&1
      call :writelog "  Copied: !NAME!"
      set "FOUND=1"
      goto :pdf_done
    )
  )
)
:pdf_done
if "!FOUND!"=="0" (
  call :writelog "  WARN: MML PDF not found. Manually copy to:"
  call :writelog "    %DEST%"
  call :writelog "  Skipping textbook ingest; will try lecture transcript."
)

call :writelog "Step 3: Folder listing"
dir /b "%LIB%" >> "%REPORT%" 2>&1

call :writelog "Step 4: Status before"
python -m backend.corpus.cli status >> "%REPORT%" 2>&1

if "!FOUND!"=="1" (
  call :writelog "Step 5a: Ingest MML chapter 1"
  python -m backend.corpus.cli ingest --source textbook --path %LIB% --chapter 1 >> "%REPORT%" 2>&1
  call :writelog "Step 5b: Ingest MML chapter 2"
  python -m backend.corpus.cli ingest --source textbook --path %LIB% --chapter 2 >> "%REPORT%" 2>&1
  set "DOC=mml_2021_deisenroth"
  set "QSUBJ=linear_algebra"
) else (
  call :writelog "Step 5: Ingest lecture transcript"
  python -m backend.corpus.cli ingest --source transcript --path data\transcripts\live_captions_20260623_204143.txt >> "%REPORT%" 2>&1
  set "DOC=transcript_live_captions_20260623_204143"
  set "QSUBJ=lecture"
)

call :writelog "Step 6: Verify !DOC!"
python -m backend.corpus.cli verify-registry --document !DOC! >> "%REPORT%" 2>&1

call :writelog "Step 7: Test queries"
python -m backend.corpus.cli query "What is an eigenvalue?" --subject linear_algebra >> "%REPORT%" 2>&1
python -m backend.corpus.cli query "numpy array indexing" --subject lecture >> "%REPORT%" 2>&1

call :writelog "Step 8: Status after"
python -m backend.corpus.cli status >> "%REPORT%" 2>&1

>> "%REPORT%" echo.
>> "%REPORT%" echo Finished: %DATE% %TIME%
>> "%REPORT%" echo ============================================================

echo.
echo === Report: %REPORT% ===
echo.
type "%REPORT%"
endlocal
exit /b 0

:writelog
echo %~1
>> "%REPORT%" echo %~1
exit /b 0
