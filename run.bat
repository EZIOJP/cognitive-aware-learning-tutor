@echo off
rem Main launcher — installs deps once, then starts backend + frontend
cd /d "%~dp0"
call "%~dp0scripts\run_all.bat"
