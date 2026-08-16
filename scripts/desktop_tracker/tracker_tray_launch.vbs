' Launch desktop tracker with system tray — no visible cmd window.
' Usage: wscript //B tracker_tray_launch.vbs [path\to\python.exe|pythonw.exe]
Option Explicit

Dim sh, fso, root, scriptDir, py, pyw, cmdLine

Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
root = fso.GetParentFolderName(fso.GetParentFolderName(scriptDir))

If WScript.Arguments.Count > 0 Then
  py = Trim(WScript.Arguments(0))
End If
If Len(py) = 0 Then
  If fso.FileExists(root & "\.venv\Scripts\pythonw.exe") Then
    py = root & "\.venv\Scripts\pythonw.exe"
  ElseIf fso.FileExists(root & "\.venv\Scripts\python.exe") Then
    py = root & "\.venv\Scripts\python.exe"
  Else
    py = "pythonw"
  End If
End If

' Prefer pythonw so no console host appears
If LCase(Right(py, 10)) = "python.exe" Then
  pyw = Left(py, Len(py) - 10) & "pythonw.exe"
  If fso.FileExists(pyw) Then py = pyw
End If

sh.CurrentDirectory = root
On Error Resume Next
sh.Environment("PROCESS")("TRACKER_NO_TRAY") = ""
On Error GoTo 0

cmdLine = """" & py & """ -m backend.behavior.desktop_tracker"
' 0 = hidden window — never flash a console
sh.Run cmdLine, 0, False
