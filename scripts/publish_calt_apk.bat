@echo off
REM Copy latest CALT Timetable debug APK into Cognitive downloads folder.
setlocal

set "SRC=%~dp0..\..\New folder (6)\calt-timetable\app\build\outputs\apk\debug\app-debug.apk"
set "DEST=%~dp0..\data\downloads\calt-android.apk"
set "MANIFEST=%~dp0..\data\downloads\calt-android.manifest.json"

if not exist "%SRC%" (
  echo APK not found. Build first:
  echo   cd "New folder (6)\calt-timetable"
  echo   gradlew.bat assembleDebug
  exit /b 1
)

copy /Y "%SRC%" "%DEST%"
if errorlevel 1 exit /b 1

echo Published: %DEST%
echo.
echo Update data\downloads\calt-android.manifest.json version_name / version_code when you bump the app.
echo Web: Settings - CALT Timetable ^(Android^) - Download APK
echo Direct: http://localhost:8000/api/app/calt-android/download

endlocal
