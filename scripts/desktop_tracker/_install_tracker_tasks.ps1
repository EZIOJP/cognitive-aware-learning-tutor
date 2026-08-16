# Install / update CALT tracker logon + keepalive scheduled tasks (current user, no admin).
# Only wscript + pythonw — never cmd.exe / visible powershell (those flash consoles).
param(
  [Parameter(Mandatory = $true)][string]$Launcher,
  [Parameter(Mandatory = $true)][string]$Keepalive,
  [string]$TaskName = "CALT Desktop Tracker",
  [string]$KeepaliveName = "CALT Tracker Keepalive"
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $Keepalive
$TrayVbs = Join-Path $ScriptDir "tracker_tray_launch.vbs"
$KeepVbs = Join-Path $ScriptDir "keepalive_tracker.vbs"
$Root = Split-Path (Split-Path $ScriptDir -Parent) -Parent
$Pyw = Join-Path $Root ".venv\Scripts\pythonw.exe"
if (-not (Test-Path $Pyw)) {
  $Pyw = Join-Path $Root ".venv\Scripts\python.exe"
}

function Register-UserTask {
  param(
    [string]$Name,
    [string]$Execute,
    [string]$Argument,
    $Triggers
  )
  $action = New-ScheduledTaskAction -Execute $Execute -Argument $Argument
  $settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -Hidden
  $principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
  Register-ScheduledTask -TaskName $Name -Action $action -Trigger $Triggers -Settings $settings -Principal $principal -Force | Out-Null
}

$logon = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
Register-UserTask -Name $TaskName -Execute "wscript.exe" -Argument ("//B `"$TrayVbs`" `"$Pyw`"") -Triggers $logon
Write-Host "OK logon task: $TaskName"

$once = New-ScheduledTaskTrigger -Once -At ((Get-Date).AddMinutes(1)) `
  -RepetitionInterval (New-TimeSpan -Minutes 5) `
  -RepetitionDuration (New-TimeSpan -Days 3650)
Register-UserTask -Name $KeepaliveName -Execute "wscript.exe" -Argument ("//B `"$KeepVbs`"") -Triggers $once
Write-Host "OK keepalive task: $KeepaliveName (every 5 min)"
