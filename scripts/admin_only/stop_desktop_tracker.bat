@echo off
REM Admin-only tracker stop/restart entry points (PIN-gated).
REM Prefer these over hunting for stop_desktop_tracker under scripts\ root.

call "%~dp0..\desktop_tracker\stop_desktop_tracker.bat" %*
