# Demo Implementation Status

## Completed scaffold (2026-05-23)

- `APCSPDemoPlayerController`: F/Tab/Shift+Tab/H/Z bindings, blended view target, and HUD/overlay delegates.
- `UPCSPAgentDebugViewModel`: read-only snapshot adapter for UMG.
- `UPCSPTrajectoryLogComponent`: bounded recent-entry ring buffer with event/category/urgency metadata.

## Remaining authoring work

| Item | Owner surface | Definition of done |
| --- | --- | --- |
| Camera mount | agent BP or camera proxy | stable follow/shoulder shot without AI disruption |
| UMG widgets | `WBP_PCSPDemoHUD` family | binds snapshot and observer delegates |
| Zone overlay | material/actor assets | category colors and selected-target update |
| Curated personas | spawner launch settings | repeatable 3–5 ID set |
| Sequence/capture | Level Sequence + runbook | establishing and scale shots reproducible |

Use [../../guides/portfolio-editor-setup.md](../../guides/portfolio-editor-setup.md) for editor configuration and [video-runbook.md](video-runbook.md) for acceptance before filming.
