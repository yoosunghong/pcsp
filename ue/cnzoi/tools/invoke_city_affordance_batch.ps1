param([int]$Start=0,[int]$Count=8)
$ErrorActionPreference='Stop'
$projectRoot=Split-Path $PSScriptRoot -Parent
Push-Location $projectRoot
try {
    . Saved/PCSP/CityAuthoring/mcp.ps1
    $plan=Get-Content Saved/PCSP/CityAffordances/layout-plan.json -Raw|ConvertFrom-Json
    $rows=@($plan.placements|Select-Object -Skip $Start -First $Count)
    # Encode JSON as a Python-compatible quoted string, never as shell code.
    $encoded=ConvertTo-Json -InputObject (ConvertTo-Json -InputObject $rows -Depth 60 -Compress) -Compress
    $script="import json`nPLACEMENTS=json.loads($encoded)`n"+(Get-Content tools/apply_city_affordances.py -Raw)
    $result=Invoke-CityTool 'editor_toolset.toolsets.programmatic.ProgrammaticToolset' 'execute_tool_script' @{script=$script} 240
    $result|ConvertTo-Json -Depth 100|Set-Content "Saved/PCSP/CityAffordances/applied-$Start.json"
    if($result.isError){throw $result.content.text}
    $data=($result.content.text|ConvertFrom-Json).returnValue|ConvertFrom-Json
    "Applied $($data.zones) zones / $($data.slots) slots, starting at $Start."
} finally {
    Pop-Location
}
