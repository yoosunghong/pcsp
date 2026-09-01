# Demo Observer and HUD Contract

## Observer camera

`APCSPDemoPlayerController` is an observer, not a gameplay controller. `F` focuses the nearest valid `APCSPAgentCharacter`; `Tab` and `Shift+Tab` cycle deterministically; `F` again or `Esc` returns to spectator view. Use `SetViewTargetWithBlend(0.35s)`, not `Possess()`, so each agent retains its AI controller and Behavior Tree.

The selected agent must have a persona component. Resolve nearest distance from the spectator camera (or player pawn) and break ties by lowest persona ID. Supported views are follow third person, shoulder debug, top-down lock, and free spectator.

## HUD boundary

`UPCSPAgentDebugViewModel` builds read-only `FPCSPHudAgentSnapshot` values for UMG. It must never mutate policy, Blackboard, reservations, needs, or social state. `UPCSPTrajectoryLogComponent` supplies a bounded recent-event buffer shared with JSONL output.

| Panel | Required state |
| --- | --- |
| Run badge | policy mode, agent count, session stamp, optional inference/failure summary |
| Agent card | persona ID/summary, embedding state, current zone |
| Needs | eight need values and most urgent marker |
| Decision stack | action, category, target, urgency, reservation, BT phase |
| Affordance | zone, capacity/occupancy, free points, distance, latest failure |
| Social | nearby count, affinity, target |
| Trajectory strip | recent decision/complete/failure rows |
| Zone legend/minimap | category colors, selected agent and target zone |

Keep the center clear, panel sizes stable, and category colors consistent. The detailed UMG and zone-overlay authoring steps live in [../../guides/demo-hud-widgets.md](../../guides/demo-hud-widgets.md).
