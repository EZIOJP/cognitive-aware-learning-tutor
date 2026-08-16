' Keepalive — no cmd/powershell window. Run: wscript //B keepalive_tracker.vbs
Option Explicit

Dim sh, fso, scriptDir, root, pyw, keepalivePy

Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
root = fso.GetParentFolderName(fso.GetParentFolderName(scriptDir))

pyw = root & "\.venv\Scripts\pythonw.exe"
If Not fso.FileExists(pyw) Then
  pyw = root & "\.venv\Scripts\python.exe"
End If
keepalivePy = "-m backend.behavior.tracker_keepalive"

sh.CurrentDirectory = root
' Window style 0 = completely hidden
sh.Run """" & pyw & """ " & keepalivePy, 0, False
