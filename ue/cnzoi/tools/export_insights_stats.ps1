<#
.SYNOPSIS
  Headless Unreal Insights timer/statistics exporter for PCSP .utrace files.

.DESCRIPTION
  Uses the documented ExecOnAnalysisComplete response-file path so every trace
  produces a timer catalogue, aggregated timer statistics, and analysis log.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string[]] $TracePath,
    [string] $InsightsExe = "C:\Program Files\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealInsights.exe"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $InsightsExe)) {
    throw "UnrealInsights.exe not found: $InsightsExe"
}

foreach ($traceEntry in $TracePath) {
    $resolvedTrace = (Resolve-Path -LiteralPath $traceEntry).Path
    $outputDir = Split-Path -Parent $resolvedTrace
    $stem = [IO.Path]::GetFileNameWithoutExtension($resolvedTrace)
    $timersPath = Join-Path $outputDir "${stem}_timers.csv"
    $statsPath = Join-Path $outputDir "${stem}_timer_stats.csv"
    $logPath = Join-Path $outputDir "${stem}_insights.log"
    $responsePath = Join-Path $outputDir "${stem}_export.rsp"

    [IO.File]::WriteAllLines($responsePath, @(
        "TimingInsights.ExportTimers $timersPath",
        "TimingInsights.ExportTimerStatistics $statsPath -sortBy=TotalInclusiveTime -sortOrder=Descending"
    ))

    $insightsArgs = @(
        "-OpenTraceFile=$resolvedTrace",
        "-ABSLOG=$logPath",
        "-AutoQuit",
        "-NoUI",
        "-ExecOnAnalysisCompleteCmd=@=$responsePath",
        "-log"
    )

    Write-Host "Analyzing $resolvedTrace"
    $process = Start-Process -FilePath $InsightsExe -ArgumentList $insightsArgs -PassThru -WindowStyle Hidden
    $process.WaitForExit()
    if ($process.ExitCode -ne 0) {
        throw "Unreal Insights failed with exit code $($process.ExitCode): $resolvedTrace"
    }
    if (-not (Test-Path -LiteralPath $statsPath)) {
        throw "Timer statistics export missing: $statsPath"
    }
    Write-Host "  -> $statsPath"
}
