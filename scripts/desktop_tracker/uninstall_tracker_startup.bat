@echo off

setlocal

set "TASK_NAME=CALT Desktop Tracker"

set "LINK=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\CALT Desktop Tracker.lnk"



echo Removing scheduled task: %TASK_NAME%

schtasks /Delete /TN "%TASK_NAME%" /F >nul 2>&1

if errorlevel 1 (

  echo   Task not found or could not be deleted.

) else (

  echo   Task removed.

)



if exist "%LINK%" (

  del /f /q "%LINK%"

  echo   Startup shortcut removed.

) else (

  echo   No startup shortcut found.

)



echo Done.

endlocal
