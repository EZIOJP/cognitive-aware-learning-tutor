' Tray restart — confirm dialog + same "go" path as restart_desktop_tracker.bat
Option Explicit

Dim sh, fso, root, scriptDir, py, pyw, rc

Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
root = fso.GetParentFolderName(fso.GetParentFolderName(scriptDir))

If fso.FileExists(root & "\.venv\Scripts\python.exe") Then
  py = root & "\.venv\Scripts\python.exe"
Else
  py = "python"
End If
If fso.FileExists(root & "\.venv\Scripts\pythonw.exe") Then
  pyw = root & "\.venv\Scripts\pythonw.exe"
Else
  pyw = py
End If

sh.CurrentDirectory = root

rc = sh.Run("""" & py & """ -m backend.behavior.tracker_restart confirm", 0, True)
If rc <> 0 Then WScript.Quit 0

On Error Resume Next
sh.Environment("PROCESS")("CALT_TRACKER_SKIP_STOP_PIN") = "1"
On Error GoTo 0

sh.Run """" & pyw & """ -m backend.behavior.tracker_restart go", 0, False
