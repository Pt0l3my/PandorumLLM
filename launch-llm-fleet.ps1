# ================================================================
#  launch-llm-fleet.ps1 - config-driven fleet spawner.
#  Reads fleet-config.json (seeded from fleet-config.default.json)
#  and launches each slot's assigned launcher in its own elevated
#  pwsh window. Runs elevated itself (via start-llm-stack.bat or
#  fleet-panel.py), so children inherit admin with no extra UAC.
#
#  Modes:
#    (no args)            boot the whole fleet, idempotent (SKIP if healthy)
#    -Slot slot1          only that slot
#    -Slot slot1 -Force   swap: kill whatever holds the port (even healthy),
#                         then launch the currently assigned launcher
#    -Slot slot1 -Stop    just take that slot down (supervisor-aware)
#  Slots with no launcher assigned ("Disabled" in the panel) are skipped (OFF).
#
#  Launcher archive (ps1-launchers\ next to this script):
#    - primary present, no archived copy  -> archive one (ARCH)
#    - primary present, archive differs   -> note it, primary wins
#    - primary MISSING, archive present   -> launch the archive (FALLB)
#      (archived copies keep their original self-invoke path, so the
#       crash-restart loop is inactive while running from the archive)
#
#  Pre-flight per slot:
#    - the REAL port is parsed from the launcher .ps1 itself; the
#      slot's port in the config is just the expectation (WARN on
#      mismatch)
#    - port free                          -> SPAWN
#    - /health answers                    -> SKIP (or SWAP with -Force)
#    - port held, no HTTP reply           -> clear the wedge, respawn
#    - every kill takes the supervisor pwsh window down FIRST, so the
#      launcher's trailing self-invoke can't resurrect the old model
#
#  Every SPAWN is appended to fleet-history.json (last 50, newest
#  first) - the PandorumLLM panel reads the same file.
#
#  Server windows spawn MINIMIZED and their full console stream is
#  tee'd into <logDir>\<ts>_srv_<name>.log for the panel's Log /
#  speed displays. The panel itself is never auto-started here -
#  since v0.1 the panel is the entry point.
# ================================================================

param(
    [string]$Slot,
    [switch]$Force,
    [switch]$Stop
)

$staggerSeconds = 3   # gap between spawns; raise if D: thrashes during model load

$stackDir    = $PSScriptRoot
$backupDir   = Join-Path $stackDir "ps1-launchers"
$configPath  = Join-Path $stackDir "fleet-config.json"
$defaultPath = Join-Path $stackDir "fleet-config.default.json"
$historyPath = Join-Path $stackDir "fleet-history.json"

New-Item -ItemType Directory -Force -Path $backupDir | Out-Null

# --- config ------------------------------------------------------
if (-not (Test-Path $configPath)) {
    if (Test-Path $defaultPath) {
        Copy-Item $defaultPath $configPath
        Write-Host "SEED  fleet-config.json created from fleet-config.default.json"
    } else {
        Write-Host "FATAL fleet-config.json missing and no default present"
        Start-Sleep -Seconds 5; exit 1
    }
}
$config = Get-Content -Raw $configPath | ConvertFrom-Json
$slots  = @($config.slots)
$logDir = $null
try { $logDir = $config.settings.logDir } catch {}
if ([string]::IsNullOrWhiteSpace($logDir)) { $logDir = Join-Path $stackDir "logs" }
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
if ($Slot) {
    $slots = @($slots | Where-Object { $_.id -eq $Slot })
    if ($slots.Count -eq 0) {
        Write-Host ("FATAL unknown slot id '{0}'" -f $Slot); exit 1
    }
}

# --- helpers -----------------------------------------------------
function Resolve-Launcher([string]$primary) {
    $name   = Split-Path $primary -Leaf
    $backup = Join-Path $backupDir $name
    if (Test-Path $primary) {
        if (-not (Test-Path $backup)) {
            Copy-Item $primary $backup
            Write-Host ("ARCH  {0} -> ps1-launchers\" -f $name)
        }
        elseif ((Get-FileHash $primary).Hash -ne (Get-FileHash $backup).Hash) {
            Write-Host ("NOTE  {0}: archived copy differs from primary (primary wins; delete the archived file to re-archive)" -f $name)
        }
        return $primary
    }
    if (Test-Path $backup) {
        Write-Host ("FALLB {0}: primary missing - launching archived copy" -f $name)
        return $backup
    }
    Write-Host ("MISS  {0}: not found in primary folder or archive - skipping" -f $name)
    return $null
}

function Get-LauncherPort([string]$path) {
    if ([string]::IsNullOrWhiteSpace($path) -or -not (Test-Path $path)) { return $null }
    $text = Get-Content -Raw $path
    if ($text -match '"--port"\s*,\s*"(\d+)"') { return [int]$Matches[1] }  # quoted args-array style
    if ($text -match '--port\s+(\d+)')         { return [int]$Matches[1] }  # single-string style
    return $null
}

function Get-PortState([int]$port) {
    $conn = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
            Select-Object -First 1
    if (-not $conn) { return @{ State = "free" } }
    try {
        $r = Invoke-WebRequest "http://127.0.0.1:$port/health" -TimeoutSec 3 -SkipHttpErrorCheck
        return @{ State = "alive"; Http = $r.StatusCode; OwnerPid = $conn.OwningProcess }
    } catch {
        return @{ State = "wedged"; OwnerPid = $conn.OwningProcess }
    }
}

function Stop-SlotPort([int]$port) {
    # kills the supervisor pwsh window FIRST (else the launcher's trailing
    # self-invoke respawns the old model), then the port owner itself
    $conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
             Select-Object -Unique OwningProcess
    $any = $false
    foreach ($c in $conns) {
        $srv = Get-CimInstance Win32_Process -Filter "ProcessId=$($c.OwningProcess)" -ErrorAction SilentlyContinue
        if ($srv) {
            $parent = Get-CimInstance Win32_Process -Filter "ProcessId=$($srv.ParentProcessId)" -ErrorAction SilentlyContinue
            if ($parent -and $parent.Name -eq 'pwsh.exe') {
                Write-Host ("KILL  supervisor window PID {0}" -f $parent.ProcessId)
                Stop-Process -Id $parent.ProcessId -Force -ErrorAction SilentlyContinue
            }
        }
        Write-Host ("KILL  port {0} owner PID {1} ({2})" -f $port, $c.OwningProcess, $srv.Name)
        Stop-Process -Id $c.OwningProcess -Force -ErrorAction SilentlyContinue
        Wait-Process -Id $c.OwningProcess -Timeout 5 -ErrorAction SilentlyContinue
        $any = $true
    }
    if ($any) { Start-Sleep -Seconds 2 }   # let the port and VRAM release
    return $any
}

function Add-HistoryEntry($slotObj, [int]$port, [string]$scriptPath) {
    $hist = @()
    if (Test-Path $historyPath) {
        try { $hist = @((Get-Content -Raw $historyPath | ConvertFrom-Json)) } catch { $hist = @() }
    }
    $entry = [pscustomobject]@{
        time   = (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
        slotId = $slotObj.id
        slot   = $slotObj.label
        port   = $port
        script = $scriptPath
        model  = $(try { $raw = Get-Content -Raw $scriptPath; $mm = [regex]::Match($raw, '"(?:-m|--model)",\s*"([^"]+\.gguf)"'); if (-not $mm.Success) { $mm = [regex]::Match($raw, '\$modelPath\s*=\s*"([^"]+)"') }; if ($mm.Success) { Split-Path $mm.Groups[1].Value -Leaf } else { "" } } catch { "" })
    }
    $hist = @($entry) + $hist
    if ($hist.Count -gt 50) { $hist = $hist[0..49] }
    ConvertTo-Json -InputObject @($hist) -Depth 4 | Set-Content -Path $historyPath -Encoding UTF8
}

# --- main --------------------------------------------------------
for ($i = 0; $i -lt $slots.Count; $i++) {
    $s = $slots[$i]

    if ($Stop) {
        $port = Get-LauncherPort $s.script
        if ($null -eq $port) { $port = [int]$s.port }
        Write-Host ("STOP  {0} (port {1})" -f $s.label, $port)
        if (-not (Stop-SlotPort $port)) { Write-Host ("      nothing listening on {0}" -f $port) }
        continue
    }

    if ([string]::IsNullOrWhiteSpace($s.script)) {
        Write-Host ("OFF   {0} - disabled" -f $s.label)
        continue
    }

    $launchPath = Resolve-Launcher $s.script
    if ($null -eq $launchPath) { continue }

    $actualPort = Get-LauncherPort $launchPath
    if ($null -eq $actualPort) {
        Write-Host ("NOTE  {0}: couldn't read --port from launcher; using slot port {1}" -f $s.label, $s.port)
        $actualPort = [int]$s.port
    }
    elseif ($actualPort -ne [int]$s.port) {
        Write-Host ("WARN  {0}: launcher binds port {1} but slot expects {2}" -f $s.label, $actualPort, $s.port)
    }

    $spawn = $true
    $ps = Get-PortState $actualPort
    if ($ps.State -eq "alive") {
        if ($Force) {
            Write-Host ("SWAP  {0} - replacing PID {1} on port {2}" -f $s.label, $ps.OwnerPid, $actualPort)
            Stop-SlotPort $actualPort | Out-Null
        } else {
            Write-Host ("SKIP  {0} - already serving on {1} (HTTP {2}, PID {3})" -f $s.label, $actualPort, $ps.Http, $ps.OwnerPid)
            $spawn = $false
        }
    }
    elseif ($ps.State -eq "wedged") {
        Write-Host ("CLEAR {0} - port {1} held by unresponsive PID {2}" -f $s.label, $actualPort, $ps.OwnerPid)
        Stop-SlotPort $actualPort | Out-Null
    }

    if ($spawn) {
        $stem = (Split-Path $launchPath -Leaf) -replace '\.ps1$',''
        $title = "{0} | {1}" -f $s.label, $stem
        Write-Host ("SPAWN {0} -> {1}" -f $s.label, $launchPath)
        $safeTitle = $title -replace "'", "''"
        # rotating per-slot logs: srv_<slotid>_1..5.log; reuse the oldest once 5 exist
        $pat  = "srv_{0}_*.log" -f $s.id
        $logs = @(Get-ChildItem -Path $logDir -Filter $pat -ErrorAction SilentlyContinue)
        if ($logs.Count -lt 5) {
            $used = @($logs | ForEach-Object { if ($_.Name -match '_(\d+)\.log$') { [int]$Matches[1] } })
            $n = 1; while ($used -contains $n) { $n++ }
            $srvLog = Join-Path $logDir ("srv_{0}_{1}.log" -f $s.id, $n)
        } else {
            $srvLog = ($logs | Sort-Object LastWriteTime | Select-Object -First 1).FullName
        }
        Set-Content -Path $srvLog -Encoding UTF8 -Value ("=== {0} | {1} | {2} ===" -f (Get-Date -Format s), $s.label, $stem)
        $cmd = "`$Host.UI.RawUI.WindowTitle = '$safeTitle'; " +
       "`$sw = [IO.StreamWriter]::new('$srvLog', `$true, [Text.UTF8Encoding]::new(`$false)); `$sw.AutoFlush = `$true; " +
       "& '$launchPath' *>&1 | ForEach-Object { `$r = `$_; " +
       "if (`$r -is [System.Management.Automation.InformationRecord] -and `$r.MessageData -is [System.Management.Automation.HostInformationMessage]) { " +
       "`$m = `$r.MessageData; `$sw.Write(`$m.Message); if (-not `$m.NoNewLine) { `$sw.Write([Environment]::NewLine) }; " +
       "`$h = @{Object = `$m.Message; NoNewline = [bool]`$m.NoNewLine}; " +
       "if (`$null -ne `$m.ForegroundColor) { `$h.ForegroundColor = `$m.ForegroundColor }; " +
       "if (`$null -ne `$m.BackgroundColor) { `$h.BackgroundColor = `$m.BackgroundColor }; " +
       "Write-Host @h } else { `$sw.WriteLine(`$r.ToString()); `$r } }"
        Start-Process pwsh -WindowStyle Minimized -ArgumentList "-NoExit","-ExecutionPolicy","Bypass","-Command","`"$cmd`""
        Add-HistoryEntry $s $actualPort $launchPath
        if ($i -lt $slots.Count - 1) { Start-Sleep -Seconds $staggerSeconds }
    }
}

if (-not $Slot -and -not $Stop) {
    Write-Host "Fleet pre-flight complete."
    Start-Sleep -Seconds 4   # leave the verdict lines readable before this window closes
}

# Manual full-fleet run:
# & "C:\start-llm-stack\launch-llm-fleet.ps1"
