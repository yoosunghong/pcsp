# Portfolio Demo Video Runbook

## Goal and boundary

Demonstrate that PCSP selects high-level semantic intent while Unreal executes movement and interactions through Behavior Tree, Blackboard, affordance reservation, and NavMesh. Use `Map_PCSPDistrict_Portfolio` only; never present its capture results as the research experiment map's result.

## Capture sequence

| Time | Beat | Evidence |
| --- | --- | --- |
| 0–8s | Establishing city | 64 active agents and zone overlays |
| 8–20s | Hybrid stack | `PCSP Decision → Blackboard → MoveToAffordance → PerformInteraction` |
| 20–38s | Agent focus | observer camera and compact live HUD |
| 38–55s | Persona contrast | three agents, same architecture, distinct semantic actions |
| 55–70s | Congestion/recovery | reservation, capacity, and retry behavior |
| 70–85s | Scale | 16/64 population comparison |
| 85–105s | Data trail | JSONL events plus one aggregate plot |

For the contrast beat, use repeatable Work-, Social-, and Fitness/Leisure-oriented personas, pinning IDs through `-PCSP_PersonaIds` when available. Show policy action, mapped category, BT task, and selected interaction point; never imply the policy emits a world location directly.

## Deterministic launch presets

| Preset | Command switches | Use |
| --- | --- | --- |
| Demo readable | `-PCSP_AgentCount=16 -PCSP_SpawnSeed=0` | close persona and affordance shots |
| Demo scale | `-PCSP_AgentCount=64 -PCSP_SpawnSeed=0` | establishing and scale proof |

Use `-PCSP_RunDurationSeconds=300` for unattended captures. Keep `pcsp.PolicyMode=0` for the real hybrid demo. If a specific model must be shown, first run `research/scripts/swap_ue5_onnx.py <tag>`; the log and HUD badge must identify that model.

## Before recording

- Open `Map_PCSPDistrict_Portfolio`; confirm the ONNX model and persona cache load.
- Verify the player begins as a free camera and `F` focus does not stop AI/BT execution.
- Verify `Tab` / `Shift+Tab`, HUD toggle, and zone-overlay toggle.
- Verify zone registration and NavMesh; avoid a capture with streaming-related `FindBestZone` failures.
- Capture the session stamp. After the run, analyze it with `research/scripts/analyze_ue_session.py` and retain an action/category chart for the data-trail beat.

## Risks

| Risk | Mitigation |
| --- | --- |
| Observer control disrupts AI | use view-target blending, not controller possession |
| HUD obscures footage | default to compact, state-only panels |
| Demo-map changes contaminate evidence | label demo outputs separately from experiment outputs |
| Persona text is too long | prepare short display summaries for selected IDs |
| Overlays look like editor debug | reserve dense debug UI for brief technical cutaways |
