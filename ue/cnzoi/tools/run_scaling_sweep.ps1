<#
.SYNOPSIS
  T1.3 UE5 scaling-sweep driver. Runs the cnzoi standalone game N times,
  varying pcsp.AgentCount and pcsp.SpawnSeed via -ExecCmds. Each run
  auto-quits after pcsp.RunDurationSeconds via PCSPPerfSamplerSubsystem.

.DESCRIPTION
  Launches UnrealEditor.exe with `-game` so the project runs as a
  standalone executable (no editor UI) using the map set as
  "Game Default Map" / "Editor Startup Map" in Project Settings.
  Telemetry lands in <project>/Saved/PCSP/Logs/<stamp>/ as usual.

.PARAMETER EnginePath
  Path to the UnrealEditor.exe install root (e.g. "C:\Program Files\Epic Games\UE_5.7").
  Default: auto-detect from .uproject EngineAssociation via the Epic registry.

.PARAMETER ProjectPath
  Absolute path to cnzoi.uproject. Default: resolved relative to this script.

.PARAMETER AgentCounts
  Array of agent counts to sweep. Default: 8,16,32,64,96,128.

.PARAMETER Seeds
  Array of RNG seeds per agent-count. Default: 0,1,2.

.PARAMETER DurationSeconds
  Wall-time per run (excludes engine startup). Default: 600 (= 10 min).

.PARAMETER WindowedRes
  Window size as "WxH". Default: "800x450". Keep rendering on so frame_ms
  reflects the realtime budget the paper claims.

.PARAMETER DryRun
  Print the planned command lines without launching anything.

.EXAMPLE
  # Default 18-run sweep, 10 min each (~3.5 h with engine startups).
  .\run_scaling_sweep.ps1

  # Faster pilot: 5 min per run, only 2 seeds.
  .\run_scaling_sweep.ps1 -DurationSeconds 300 -Seeds 0,1

  # Just print what would run.
  .\run_scaling_sweep.ps1 -DryRun
#>
[CmdletBinding()]
param(
    [string]   $EnginePath      = $null,
    [string]   $ProjectPath     = $null,
    [int[]]    $AgentCounts     = @(8, 16, 32, 64, 96, 128),
    [int[]]    $Seeds           = @(0, 1, 2),
    [int]      $DurationSeconds = 600,
    [string]   $WindowedRes     = "800x450",
    [switch]   $DryRun
)

$ErrorActionPreference = "Stop"

# --- Resolve project path ---
if (-not $ProjectPath) {
    $here = Split-Path -Parent $MyInvocation.MyCommand.Path
    $ProjectPath = Join-Path $here "..\cnzoi.uproject" | Resolve-Path | Select-Object -ExpandProperty Path
}
if (-not (Test-Path $ProjectPath)) {
    throw "Project not found: $ProjectPath"
}

# --- Resolve engine path from .uproject EngineAssociation if not provided ---
if (-not $EnginePath) {
    $uproj = Get-Content $ProjectPath -Raw | ConvertFrom-Json
    $assoc = $uproj.EngineAssociation
    $key = "HKLM:\SOFTWARE\EpicGames\Unreal Engine\$assoc"
    if (Test-Path $key) {
        $EnginePath = (Get-ItemProperty $key).InstalledDirectory
    } else {
        $guess = "C:\Program Files\Epic Games\UE_$assoc"
        if (Test-Path $guess) {
            $EnginePath = $guess
        } else {
            throw "Could not locate UE $assoc install. Pass -EnginePath explicitly."
        }
    }
}

$Exe = Join-Path $EnginePath "Engine\Binaries\Win64\UnrealEditor.exe"
if (-not (Test-Path $Exe)) {
    throw "UnrealEditor.exe not found at: $Exe"
}

# --- Resolution parse ---
if ($WindowedRes -notmatch '^(\d+)x(\d+)$') {
    throw "WindowedRes must look like '800x450', got '$WindowedRes'"
}
$ResX = [int]$Matches[1]
$ResY = [int]$Matches[2]

# --- Banner ---
$totalRuns = $AgentCounts.Count * $Seeds.Count
$estMins = [math]::Round(($DurationSeconds + 45) * $totalRuns / 60.0, 1)
Write-Host "===================================================================="
Write-Host " PCSP T1.3 scaling sweep"
Write-Host "   Engine:   $Exe"
Write-Host "   Project:  $ProjectPath"
Write-Host "   Counts:   $($AgentCounts -join ', ')"
Write-Host "   Seeds:    $($Seeds -join ', ')"
Write-Host "   Duration: $DurationSeconds s per run"
Write-Host "   Total:    $totalRuns runs  (est. ~$estMins min wall-clock incl. ~45s startup each)"
Write-Host "   Window:   ${ResX}x${ResY}"
Write-Host "===================================================================="

$runIdx = 0
foreach ($n in $AgentCounts) {
    foreach ($seed in $Seeds) {
        $runIdx++
        $stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
        # Pass values as cmdline switches (NOT -ExecCmds). UE's -ExecCmds queue
        # often runs after the first map's BeginPlay, so CVar-based overrides
        # arrive too late for the spawner/perf-sampler to see. FCommandLine is
        # populated before any BeginPlay, so FParse::Value reads always win.
        # We keep -ExecCmds too as a belt-and-suspenders for late readers.
        $execCmds = "pcsp.AgentCount $n, pcsp.SpawnSeed $seed, pcsp.RunDurationSeconds $DurationSeconds"
        $argString = "`"$ProjectPath`" -game -WINDOWED -ResX=$ResX -ResY=$ResY -Unattended -NoSplash -NoSound -PCSP_AgentCount=$n -PCSP_SpawnSeed=$seed -PCSP_RunDurationSeconds=$DurationSeconds -ExecCmds=`"$execCmds`""

        Write-Host ""
        Write-Host "[$runIdx/$totalRuns] $stamp  agents=$n seed=$seed"
        Write-Host "  $Exe $argString"

        if ($DryRun) { continue }

        $start = Get-Date
        $proc = Start-Process -FilePath $Exe -ArgumentList $argString -PassThru
        # Watchdog: in-engine auto-quit should fire at DurationSeconds. Give it
        # +90s of grace for engine shutdown, then force-kill so one stuck run
        # can't hang the whole sweep overnight.
        $watchdogSeconds = $DurationSeconds + 90
        if (-not $proc.WaitForExit($watchdogSeconds * 1000)) {
            Write-Warning "  Watchdog: run exceeded ${watchdogSeconds}s, force-killing PID $($proc.Id)"
            try { Stop-Process -Id $proc.Id -Force -ErrorAction Stop } catch { }
            $proc.WaitForExit(10000) | Out-Null
        }
        $elapsed = (New-TimeSpan -Start $start -End (Get-Date)).TotalSeconds
        Write-Host ("  exit code = {0}, elapsed = {1:N1}s" -f $proc.ExitCode, $elapsed)
    }
}

Write-Host ""
Write-Host "===================================================================="
Write-Host " Sweep complete. To aggregate results, run:"
Write-Host ""
Write-Host "   python research/scripts/analyze_scaling_sweep.py ``"
Write-Host "     --sessions ue/cnzoi/Saved/PCSP/Logs/<today_stamp>* ``"
Write-Host "     --out      research/results/ue_sessions/scaling_<date> ``"
Write-Host "     --plot"
Write-Host "===================================================================="
