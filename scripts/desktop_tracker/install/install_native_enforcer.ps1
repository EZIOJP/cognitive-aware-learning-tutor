# Install CALT native C++ enforcer as Windows Service (Admin).
# Build first: scripts\desktop_tracker\build\build_native_enforcer.bat
param(
  [switch]$Uninstall,
  [string]$DbPath = ""
)

$ErrorActionPreference = "Stop"
$Repo = Split-Path (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent) -Parent
$ExeCandidates = @(
  (Join-Path $Repo "calt-focus\backend\calt_enforcer\build\Release\calt_enforcer.exe"),
  (Join-Path $Repo "calt-focus\backend\calt_enforcer\build\calt_enforcer.exe")
)
$Exe = $ExeCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $Exe) { throw "Missing calt_enforcer.exe - run build\build_native_enforcer.bat first" }

if (-not $DbPath) {
  $DbPath = Join-Path $Repo "data\vocab_app.db"
}

$svc = "CALTEnforcer"
if ($Uninstall) {
  Stop-Service $svc -ErrorAction SilentlyContinue
  sc.exe delete $svc | Out-Null
  [Environment]::SetEnvironmentVariable("CALT_DB", $null, "Machine")
  [Environment]::SetEnvironmentVariable("CALT_ENFORCER_LOCK", $null, "Machine")
  $lock = Join-Path $Repo "data\behavior\enforcer_owner.lock"
  if (Test-Path $lock) { Remove-Item -Force $lock -ErrorAction SilentlyContinue }
  Write-Host "Removed service $svc and cleared CALT_DB / lock env"
  exit 0
}

# Machine-level env for service process
[Environment]::SetEnvironmentVariable("CALT_DB", $DbPath, "Machine")
[Environment]::SetEnvironmentVariable(
  "CALT_ENFORCER_LOCK",
  (Join-Path $Repo "data\behavior\enforcer_owner.lock"),
  "Machine"
)

sc.exe stop $svc 2>$null | Out-Null
sc.exe delete $svc 2>$null | Out-Null
sc.exe create $svc binPath= "`"$Exe`" --service" start= auto DisplayName= "CALT Desktop Enforcer (native)"
sc.exe description $svc "Native hard-block process kills for CALT. Shared SQLite with Python API. Not Cold Turkey."
sc.exe failure $svc reset= 0 actions= restart/5000/restart/5000/restart/5000
# Recovery: if CALTEnforcer crashes, Windows restarts it after 5s (×3). While the
# service is down, Arm kills briefly fail-open (no process kills until back). SoftLand
# Gate still works via calt_msg_host reading softland_policy.json.
Start-Service $svc
Write-Host "OK: $svc running. DB=$DbPath"
Write-Host "Service Recovery: restart on failure (5s). Brief Arm fail-open while restarting."
Write-Host "Python UI kills stay off while ownership lock is refreshed by this service."
