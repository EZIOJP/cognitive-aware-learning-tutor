' Launch desktop tracker with system tray (no console).
' Usage: wscript //B tracker_tray_launch.vbs [path\to\python.exe]
Option Explicit

Dim sh, fso, root, scriptDir, py, cmdLine

Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
root = fso.GetParentFolderName(fso.GetParentFolderName(scriptDir))

If WScript.Arguments.Count > 0 Then
  py = Trim(WScript.Arguments(0))
End If
If Len(py) = 0 Then
  If fso.FileExists(root & "\.venv\Scripts\python.exe") Then
    py = root & "\.venv\Scripts\python.exe"
  Else
    py = "python"
  End If
End If

' Unset TRACKER_NO_TRAY for this child (tray mode); hidden window.
cmdLine = "cmd /c ""cd /d """ & root & """ && set TRACKER_NO_TRAY=&& """ & py & """ -m backend.behavior.desktop_tracker"""
sh.Run cmdLine, 0, False
