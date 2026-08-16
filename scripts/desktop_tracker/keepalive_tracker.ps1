# Relaunch CALT desktop tracker if it is not running.
# No new package deps. At most one root tracker (mutex + root-process check + launch lock).
$ErrorActionPreference = "SilentlyContinue"
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
if (-not (Test-Path (Join-Path $Root "backend\behavior\desktop_tracker.py"))) {
  $Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
}
$Vbs = Join-Path $PSScriptRoot "tracker_tray_launch.vbs"
$Py = Join-Path $Root ".venv\Scripts\pythonw.exe"
if (-not (Test-Path $Py)) {
  $PyAlt = Join-Path $Root ".venv\Scripts\python.exe"
  if (Test-Path $PyAlt) { $Py = $PyAlt } else { $Py = "pythonw" }
}
$LockDir = Join-Path $Root "data\logs"
$LockFile = Join-Path $LockDir "tracker_keepalive.launch.lock"
$MutexNames = @(
  "Local\CognitiveAwareTutor.DesktopTracker",
  "Global\CognitiveAwareTutor.DesktopTracker"
)

function Get-TrackerPythonProcs {
  return @(Get-CimInstance Win32_Process |
    Where-Object {
      ($_.Name -eq "python.exe" -or $_.Name -eq "pythonw.exe") -and
      $_.CommandLine -and
      ($_.CommandLine -match "backend\.behavior\.desktop_tracker|-m\s+backend\.behavior\.desktop_tracker")
    })
}

function Get-RootTrackerCount {
  $all = Get-TrackerPythonProcs
  if ($all.Count -eq 0) { return 0 }
  $ids = @($all | ForEach-Object { $_.ProcessId })
  # Ignore multiprocessing children whose parent is also a tracker python.
  return @($all | Where-Object { $ids -notcontains $_.ParentProcessId }).Count
}

# 1) Named mutex held by a live tracker?
try {
  Add-Type -Namespace CalKeepalive -Name Native -MemberDefinition @"
    [System.Runtime.InteropServices.DllImport("kernel32.dll", SetLastError=true, CharSet=System.Runtime.InteropServices.CharSet.Unicode)]
    public static extern System.IntPtr OpenMutex(uint dwDesiredAccess, bool bInheritHandle, string lpName);
    [System.Runtime.InteropServices.DllImport("kernel32.dll")]
    public static extern bool CloseHandle(System.IntPtr hObject);
"@ -ErrorAction Stop
  foreach ($MutexName in $MutexNames) {
    $h = [CalKeepalive.Native]::OpenMutex(0x00100000, $false, $MutexName) # SYNCHRONIZE
    if ($h -ne [IntPtr]::Zero) {
      [void][CalKeepalive.Native]::CloseHandle($h)
      exit 0
    }
  }
} catch {
  # Type already loaded or OpenMutex unavailable — fall through
}

# 2) Root tracker already running?
if ((Get-RootTrackerCount) -ge 1) { exit 0 }

# 3) Launch lock — avoid two keepalives starting two processes in the same window
if (-not (Test-Path $LockDir)) { New-Item -ItemType Directory -Path $LockDir -Force | Out-Null }
$now = Get-Date
if (Test-Path $LockFile) {
  $age = ($now - (Get-Item $LockFile).LastWriteTime).TotalSeconds
  if ($age -lt 45) { exit 0 }
}
try {
  Set-Content -Path $LockFile -Value $PID -Force -ErrorAction Stop
} catch {
  exit 0
}

if ((Get-RootTrackerCount) -ge 1) { exit 0 }

if (-not (Test-Path $Vbs)) { exit 1 }

Start-Process -FilePath "wscript.exe" -ArgumentList @("//B", "`"$Vbs`"", "`"$Py`"") -WorkingDirectory $Root -WindowStyle Hidden | Out-Null
exit 0
