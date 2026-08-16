@echo off
rem Keepalive entry — delegates to hidden VBS (no console flash).
wscript.exe //B "%~dp0keepalive_tracker.vbs"
