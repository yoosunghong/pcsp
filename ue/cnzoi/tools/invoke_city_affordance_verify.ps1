param([int]$Start=0,[int]$Count=12,[string]$Phase='before-save')
$ErrorActionPreference='Stop'
$projectRoot=Split-Path $PSScriptRoot -Parent
Push-Location $projectRoot
try {
    . Saved/PCSP/CityAuthoring/mcp.ps1
    $plan=Get-Content Saved/PCSP/CityAffordances/layout-plan.json -Raw|ConvertFrom-Json
    $rows=@($plan.placements|Select-Object -Skip $Start -First $Count)
    $encoded=ConvertTo-Json -InputObject (ConvertTo-Json -InputObject $rows -Depth 60 -Compress) -Compress
    $body=Get-Content tools/verify_city_affordances.py -Raw
    if($Phase -eq 'after-reload'){$body=$body.Replace('TRACE_GROUND = True','TRACE_GROUND = False')}
    $script="import json`nPLACEMENTS=json.loads($encoded)`n"+$body
    $result=Invoke-CityTool 'editor_toolset.toolsets.programmatic.ProgrammaticToolset' 'execute_tool_script' @{script=$script} 240
    $result|ConvertTo-Json -Depth 100|Set-Content "Saved/PCSP/CityAffordances/verify-$Phase-$Start.json"
    if($result.isError){throw $result.content.text}
    $data=($result.content.text|ConvertFrom-Json).returnValue|ConvertFrom-Json
    if($data.failures.Count){throw ($data.failures|ConvertTo-Json -Depth 10)}
    "Verified $($data.zone_count) zones / $($data.slot_count) slots ($Phase, offset $Start)."
} finally {
    Pop-Location
}
