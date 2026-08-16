param(
    [Parameter(Mandatory = $true)][string]$Launcher,
    [Parameter(Mandatory = $true)][string]$Root,
    [Parameter(Mandatory = $true)][string]$Link
)

# Prefer wscript (no console). If Launcher is a .bat, retarget to tray VBS.
$ScriptDir = Split-Path -Parent $Launcher
$Vbs = Join-Path $ScriptDir "tracker_tray_launch.vbs"
$Pyw = Join-Path $Root ".venv\Scripts\pythonw.exe"
if (-not (Test-Path $Pyw)) {
  $Pyw = Join-Path $Root ".venv\Scripts\python.exe"
}

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($Link)
if (Test-Path $Vbs) {
  $shortcut.TargetPath = "$env:WINDIR\System32\wscript.exe"
  $shortcut.Arguments = "//B `"$Vbs`" `"$Pyw`""
} else {
  $shortcut.TargetPath = $Launcher
  $shortcut.Arguments = ""
}
$shortcut.WorkingDirectory = $Root
$shortcut.WindowStyle = 7
$shortcut.Description = "CALT desktop activity tracker (system tray, no console)"
$shortcut.Save()
