$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
Push-Location $projectRoot
try {
    . Saved/PCSP/CityAuthoring/mcp.ps1
    $script = Get-Content tools/tag_dieselpunk_navigation.py -Raw
    $result = Invoke-CityTool 'editor_toolset.toolsets.programmatic.ProgrammaticToolset' `
        'execute_tool_script' @{script=$script} 240
    $result | ConvertTo-Json -Depth 100 | Set-Content `
        Saved/PCSP/CityNavigation/tag-result.json
    if ($result.isError) { throw $result.content.text }
    $data = ($result.content.text | ConvertFrom-Json).returnValue | ConvertFrom-Json
    "Tagged $($data.walkable_count) walkable actors and $($data.obstacle_count) obstacles."
} finally {
    Pop-Location
}
