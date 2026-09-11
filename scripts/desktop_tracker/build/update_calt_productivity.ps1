#Requires -Version 5.1
<#
.SYNOPSIS
  Automate CALT Productivity updates for Focus (UI + natives + classify rules).

.DESCRIPTION
  Safe while Focus/enforcer are running:
  - Always rebuilds dist-focus + classify_rules.json
  - Builds natives; if exe is locked, writes *.exe.new beside the running binary
  - Writes data/behavior/pending_update.json describing what still needs a restart

.EXAMPLE
  powershell -File scripts\desktop_tracker\build\update_calt_productivity.ps1
#>
param(
  [switch]$SkipNatives,
  [switch]$SkipUi,
  [switch]$Quiet
)

$ErrorActionPreference = "Stop"
$Repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
Set-Location $Repo

function Write-Info([string]$msg) {
  if (-not $Quiet) { Write-Host $msg }
}

function Test-FileLocked([string]$path) {
  if (-not (Test-Path $path)) { return $false }
  try {
    $fs = [System.IO.File]::Open($path, 'Open', 'ReadWrite', 'None')
    $fs.Close()
    return $false
  } catch {
    return $true
  }
}

function Copy-ReplaceOrNew([string]$src, [string]$dest) {
  if (-not (Test-Path $src)) { return @{ ok = $false; mode = "missing_src" } }
  $dir = Split-Path $dest -Parent
  if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir | Out-Null }
  if (Test-FileLocked $dest) {
    $newPath = "$dest.new"
    Copy-Item -Force $src $newPath
    return @{ ok = $true; mode = "pending_new"; path = $newPath }
  }
  Copy-Item -Force $src $dest
  return @{ ok = $true; mode = "replaced"; path = $dest }
}

$pending = [ordered]@{
  schema_version = 1
  updated_at     = (Get-Date).ToString("s")
  ui             = $null
  classify_rules = $null
  enforcer       = $null
  focus          = $null
  msg_host       = $null
  needs_restart  = $false
  notes          = @()
}

# ── 1) Classify rules (P5b) ───────────────────────────────────────────────
Write-Info "==> export_classify_rules.py"
try {
  python (Join-Path $Repo "scripts\desktop_tracker\build\export_classify_rules.py")
  $pending.classify_rules = "ok"
} catch {
  $pending.classify_rules = "failed: $_"
  $pending.notes += "classify_rules export failed"
}

# ── 2) Focus UI ───────────────────────────────────────────────────────────
if (-not $SkipUi) {
  Write-Info "==> npm run build:focus"
  $npm = Start-Process -FilePath "cmd.exe" -ArgumentList "/c", "npm run build:focus" `
    -WorkingDirectory $Repo -Wait -PassThru -NoNewWindow
  if ($npm.ExitCode -eq 0 -and (Test-Path (Join-Path $Repo "dist-focus\index.html"))) {
    $pending.ui = "ok"
  } else {
    $pending.ui = "failed exit=$($npm.ExitCode)"
    $pending.notes += "build:focus failed — check Node/npm on PATH"
  }
} else {
  $pending.ui = "skipped"
}

# ── 3) Natives ────────────────────────────────────────────────────────────
if (-not $SkipNatives) {
  Write-Info "==> build_native_enforcer.bat"
  $enfBat = Join-Path $Repo "scripts\desktop_tracker\build\build_native_enforcer.bat"
  $enf = Start-Process -FilePath "cmd.exe" -ArgumentList "/c", "`"$enfBat`"" `
    -WorkingDirectory $Repo -Wait -PassThru -NoNewWindow
  $enfBuilt = Join-Path $Repo "native\calt_enforcer\build\calt_enforcer.exe"
  if (-not (Test-Path $enfBuilt)) {
    $enfBuilt = Join-Path $Repo "native\calt_enforcer\build\Release\calt_enforcer.exe"
  }
  if ($enf.ExitCode -eq 0 -and (Test-Path $enfBuilt)) {
    $payload = Join-Path $Repo "scripts\desktop_tracker\installer\installer_payload\bin\calt_enforcer.exe"
    $r1 = Copy-ReplaceOrNew $enfBuilt $payload
    $enfModes = @($r1.mode)
    if ($r1.mode -eq "pending_new") { $pending.needs_restart = $true }
    # Stage .new beside the build output when that exe is locked (running)
    if (Test-FileLocked $enfBuilt) {
      Copy-Item -Force $enfBuilt "$enfBuilt.new"
      $enfModes += "pending_new"
      $pending.needs_restart = $true
      $pending.notes += "calt_enforcer.exe was locked — wrote .new; SoftLand off + Apply pending update to swap"
    }
    $pending.enforcer = ($enfModes -join ",")
  } else {
    $pending.enforcer = "failed exit=$($enf.ExitCode)"
    $pending.notes += "enforcer build failed"
  }

  Write-Info "==> build_native_focus.bat"
  $focBat = Join-Path $Repo "scripts\desktop_tracker\build\build_native_focus.bat"
  $foc = Start-Process -FilePath "cmd.exe" -ArgumentList "/c", "`"$focBat`"" `
    -WorkingDirectory $Repo -Wait -PassThru -NoNewWindow
  $focBuilt = Join-Path $Repo "native\calt_focus\build\calt_focus.exe"
  if (-not (Test-Path $focBuilt)) {
    $focBuilt = Join-Path $Repo "native\calt_focus\build\Release\calt_focus.exe"
  }
  if ($foc.ExitCode -eq 0 -and (Test-Path $focBuilt)) {
    $payloadF = Join-Path $Repo "scripts\desktop_tracker\installer\installer_payload\bin\calt_focus.exe"
    $rF = Copy-ReplaceOrNew $focBuilt $payloadF
    $focModes = @($rF.mode)
    # If Focus is running from build\, stage .new beside it
    if (Test-FileLocked $focBuilt) {
      Copy-Item -Force $focBuilt "$focBuilt.new"
      $focModes += "pending_new"
      $pending.needs_restart = $true
      $pending.notes += "calt_focus.exe locked — wrote calt_focus.exe.new; Quit Focus (SoftLand off) then Apply pending update"
    }
    $pending.focus = ($focModes -join ",")
  } else {
    $pending.focus = "failed exit=$($foc.ExitCode)"
    $pending.notes += "focus build failed"
  }

  # Optional msg-host
  $msgBat = Join-Path $Repo "scripts\desktop_tracker\build\build_calt_msg_host.bat"
  if (Test-Path $msgBat) {
    Write-Info "==> build_calt_msg_host.bat"
    $mh = Start-Process -FilePath "cmd.exe" -ArgumentList "/c", "`"$msgBat`"" `
      -WorkingDirectory $Repo -Wait -PassThru -NoNewWindow
    $pending.msg_host = if ($mh.ExitCode -eq 0) { "ok" } else { "failed exit=$($mh.ExitCode)" }
  } else {
    $pending.msg_host = "skipped"
  }
} else {
  $pending.enforcer = "skipped"
  $pending.focus = "skipped"
  $pending.msg_host = "skipped"
}

$outPending = Join-Path $Repo "data\behavior\pending_update.json"
$pending | ConvertTo-Json -Depth 5 | Set-Content -Path $outPending -Encoding utf8
Write-Info "==> wrote $outPending"
Write-Info ($pending | ConvertTo-Json -Compress)

# Exit 0 if UI ok (natives may be pending)
if ($pending.ui -eq "failed" -or ($pending.ui -like "failed*")) { exit 1 }
if ($pending.classify_rules -like "failed*") { exit 1 }
exit 0
