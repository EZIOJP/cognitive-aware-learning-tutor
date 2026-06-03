@echo off
setlocal
call "%~dp0_common.bat"
if errorlevel 1 exit /b 1
cd /d "%ROOT%"
echo.
echo [migrate] alembic upgrade head
"%PY%" -m alembic upgrade head
if errorlevel 1 exit /b 1
"%PY%" -m alembic current
echo.
endlocal
