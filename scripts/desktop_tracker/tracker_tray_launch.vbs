' Launch CALT Desktop (PySide6) — tracker + hub + productivity UI, no cmd window.
' Usage: wscript //B tracker_tray_launch.vbs [path\to\python.exe|pythonw.exe]
' Legacy: set CALT_USE_LEGACY_TRAY=1 to launch backend.behavior.desktop_tracker instead.
Option Explicit

Dim sh, fso, root, scriptDir, py, pyw, cmdLine, legacy

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

If LCase(Right(py, 10)) = "python.exe" Then
  pyw = Left(py, Len(py) - 10) & "pythonw.exe"
  If fso.FileExists(pyw) Then py = pyw
End If

sh.CurrentDirectory = root
On Error Resume Next
legacy = LCase(Trim(sh.Environment("PROCESS")("CALT_USE_LEGACY_TRAY")))
On Error GoTo 0

If legacy = "1" Or legacy = "true" Or legacy = "yes" Then
  On Error Resume Next
  sh.Environment("PROCESS")("TRACKER_NO_TRAY") = ""
  On Error GoTo 0
  cmdLine = """" & py & """ -m backend.behavior.desktop_tracker"
Else
  cmdLine = """" & py & """ -m backend.behavior.calt_desktop"
End If

' 0 = hidden window — never flash a console
sh.Run cmdLine, 0, False
