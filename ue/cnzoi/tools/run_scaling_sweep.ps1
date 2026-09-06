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

.PARAMETER MassHybrid
	Run the all-Mass architecture at each TotalNpcCounts value.

.PARAMETER TotalNpcCounts
  Total NPC counts for -MassHybrid. Default: 128,256,512,1024.

.PARAMETER HeroAgentCount
	Compatibility parameter. Must be 0 in Mass mode.

.PARAMETER Seeds
  Array of RNG seeds per agent-count. Default: 0,1,2.

.PARAMETER DurationSeconds
  Wall-time per run (excludes engine startup). Default: 600 (= 10 min).

.PARAMETER WindowedRes
  Window size as "WxH". Default: "800x450". Keep rendering on so frame_ms
  reflects the realtime budget the paper claims.

.PARAMETER MapPath
  Optional long package path to benchmark instead of the configured default map.

.PARAMETER RenderOffscreen
  Render without a desktop window. Use this for unattended, reproducible runs.

.PARAMETER DryRun
  Print the planned command lines without launching anything.

.PARAMETER Trace
  Capture an Unreal Insights .utrace file for every run under TraceDirectory.

.PARAMETER TraceDirectory
  Output directory for -Trace captures. Defaults to Saved/Profiling/PCSP.

.PARAMETER TraceMemory
  Include the memory channel. This can grow a 30-second trace above 500 MB.

.PARAMETER ExtraConsoleCommands
  Optional comma-separated CVars appended to -ExecCmds for A/B experiments.

.EXAMPLE
  # Default 18-run sweep, 10 min each (~3.5 h with engine startups).
  .\run_scaling_sweep.ps1

  # Faster pilot: 5 min per run, only 2 seeds.
  .\run_scaling_sweep.ps1 -DurationSeconds 300 -Seeds 0,1

  # Just print what would run.
  .\run_scaling_sweep.ps1 -DryRun

  # All-Mass runs at 128/256/512/1024 total NPCs.
  .\run_scaling_sweep.ps1 -MassHybrid -DurationSeconds 300 -Seeds 0,1,2
#>
[CmdletBinding()]
param(
    [string]   $EnginePath      = $null,
    [string]   $ProjectPath     = $null,
    [int[]]    $AgentCounts     = @(8, 16, 32, 64, 96, 128),
    [switch]   $MassHybrid,
    [int[]]    $TotalNpcCounts  = @(128, 256, 512, 1024),
    [int]      $HeroAgentCount  = 0,
    [int[]]    $Seeds           = @(0, 1, 2),
    [int]      $DurationSeconds = 600,
    [string]   $WindowedRes     = "800x450",
	[string]   $MapPath         = "",
	[switch]   $RenderOffscreen,
    [int]      $StartIndex      = 1,
	[switch]   $Trace,
	[switch]   $TraceMemory,
	[string]   $TraceDirectory  = $null,
	[string]   $ExtraConsoleCommands = "",
	[ValidateSet(-1, 0, 1)]
	[int]      $MassCharacterRepresentation = -1,
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

# --- Build run matrix ---
$runConfigs = @()
if ($MassHybrid) {
    if ($HeroAgentCount -ne 0) {
		throw "Mass mode is all-Mass; HeroAgentCount must be 0, got $HeroAgentCount"
    }
    foreach ($total in $TotalNpcCounts) {
        if ($total -lt $HeroAgentCount) {
            throw "TotalNpcCounts entry $total is smaller than HeroAgentCount $HeroAgentCount"
        }
        $runConfigs += [pscustomobject]@{
            Total = $total
            Hero  = $HeroAgentCount
            Mass  = $total - $HeroAgentCount
        }
    }
} else {
    foreach ($n in $AgentCounts) {
        $runConfigs += [pscustomobject]@{ Total = $n; Hero = $n; Mass = 0 }
    }
}

if ($Trace -and -not $TraceDirectory) {
	$TraceDirectory = Join-Path (Split-Path -Parent $ProjectPath) "Saved\Profiling\PCSP"
}
if ($Trace -and -not (Test-Path $TraceDirectory)) {
	New-Item -ItemType Directory -Path $TraceDirectory -Force | Out-Null
}
if ($Trace) {
	# Unreal resolves relative -tracefile paths beneath Saved/Profiling, which can
	# silently duplicate a caller-supplied relative directory. Always pass an
	# absolute path so captures land exactly where the sweep reports them.
	$TraceDirectory = (Resolve-Path -LiteralPath $TraceDirectory).Path
}

# --- Banner ---
$totalRuns = $runConfigs.Count * $Seeds.Count
$estMins = [math]::Round(($DurationSeconds + 45) * $totalRuns / 60.0, 1)
Write-Host "===================================================================="
Write-Host " PCSP T1.3 scaling sweep"
Write-Host "   Engine:   $Exe"
Write-Host "   Project:  $ProjectPath"
	Write-Host "   Mode:     $(if ($MassHybrid) { 'All Mass' } else { 'Actor debug baseline' })"
Write-Host "   Totals:   $($runConfigs.Total -join ', ')"
if ($MassHybrid) { Write-Host "   Mass:     all NPCs are Mass entities" }
Write-Host "   Seeds:    $($Seeds -join ', ')"
Write-Host "   Duration: $DurationSeconds s per run"
Write-Host "   Total:    $totalRuns runs  (est. ~$estMins min wall-clock incl. ~45s startup each)"
Write-Host "   Window:   ${ResX}x${ResY}"
Write-Host "   Map:      $(if ($MapPath) { $MapPath } else { '<project default>' })"
Write-Host "   Display:  $(if ($RenderOffscreen) { 'render offscreen' } else { 'visible window' })"
Write-Host "===================================================================="

$runIdx = 0
foreach ($cfg in $runConfigs) {
    foreach ($seed in $Seeds) {
        $runIdx++
        if ($runIdx -lt $StartIndex) {
            Write-Host "[$runIdx/$totalRuns] SKIP (StartIndex=$StartIndex) total=$($cfg.Total) hero=$($cfg.Hero) mass=$($cfg.Mass) seed=$seed"
            continue
        }
        $stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
        # Pass values as cmdline switches (NOT -ExecCmds). UE's -ExecCmds queue
        # often runs after the first map's BeginPlay, so CVar-based overrides
        # arrive too late for the spawner/perf-sampler to see. FCommandLine is
        # populated before any BeginPlay, so FParse::Value reads always win.
        # We keep -ExecCmds too as a belt-and-suspenders for late readers.
        $execCmds = "pcsp.AgentCount $($cfg.Hero), pcsp.MassEntityCount $($cfg.Mass), pcsp.SpawnSeed $seed, pcsp.RunDurationSeconds $DurationSeconds"
		if ($ExtraConsoleCommands) {
			$execCmds = "$execCmds, $ExtraConsoleCommands"
		}
		$mapArgument = if ($MapPath) { " `"$MapPath`"" } else { "" }
        $argString = "`"$ProjectPath`"$mapArgument -game -WINDOWED -ResX=$ResX -ResY=$ResY -Unattended -NoSplash -NoSound -PCSP_AgentCount=$($cfg.Hero) -PCSP_MassEntityCount=$($cfg.Mass) -PCSP_SpawnSeed=$seed -PCSP_RunDurationSeconds=$DurationSeconds -ExecCmds=`"$execCmds`""
		if ($RenderOffscreen) {
			$argString = "$argString -RenderOffscreen"
		}
		if ($MassCharacterRepresentation -ge 0) {
			$argString = "$argString -PCSP_MassCharacterRepresentation=$MassCharacterRepresentation"
		}
		if ($Trace) {
			$traceStamp = Get-Date -Format "yyyyMMdd_HHmmss"
			$tracePath = Join-Path $TraceDirectory ("pcsp_total{0}_hero{1}_mass{2}_seed{3}_{4}.utrace" -f $cfg.Total, $cfg.Hero, $cfg.Mass, $seed, $traceStamp)
			$traceChannels = if ($TraceMemory) { "cpu,gpu,frame,bookmark,memory" } else { "cpu,gpu,frame,bookmark" }
			$argString = "$argString -trace=$traceChannels -tracefile=`"$tracePath`" -StatNamedEvents"
		}

        Write-Host ""
        Write-Host "[$runIdx/$totalRuns] $stamp  total=$($cfg.Total) hero=$($cfg.Hero) mass=$($cfg.Mass) seed=$seed"
        Write-Host "  $Exe $argString"

        if ($DryRun) { continue }

        $start = Get-Date
		$processArgs = @{
			FilePath = $Exe
			ArgumentList = $argString
			PassThru = $true
		}
		if ($RenderOffscreen) {
			$processArgs.WindowStyle = "Hidden"
		}
        $proc = Start-Process @processArgs
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
