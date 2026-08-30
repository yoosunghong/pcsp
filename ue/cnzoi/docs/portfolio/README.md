# PCSP UE5 Engineering Portfolio

Engineering-area PLAN documents pulled out of the main `ue/cnzoi/PLAN.md` so
they can stand alone as portfolio artifacts. This directory is now the home for
UE5 portfolio work: implemented engineering case studies, extension plans,
diagrams, and the final capture/HUD scenario.

Differs from `PLAN.md` in scope:

- `PLAN.md` tracks every phase of the integration and is research-driven.
- Documents under this directory are scoped to a single engineering subsystem
  and written for an engine-focused reader (gameplay programmer, AI
  programmer, performance engineer).
- Portfolio implementation order starts with UE5 engineering extensions
  (`async-inference`, `eqs-congestion`, contract/observability cleanup), then
  moves to the demo-facing camera/HUD and capture work.

## Implementation Order

| Priority | Work | Why first |
| --- | --- | --- |
| P0 | [hybrid-stack.md](hybrid-stack.md) cleanup | Stabilizes the action/category contract before extending execution. |
| P1 | [mass-1024-scaling.md](mass-1024-scaling.md) | Converts the measured Actor/NavMesh ceiling into a two-tier 1,024-NPC architecture. |
| P2 | [eqs-congestion.md](eqs-congestion.md) | Makes hero-tier crowd behavior more demonstrable and reduces capacity hot spots. |
| P3 | [async-inference.md](async-inference.md) | Adds true dynamic-batch execution after Actor/navigation costs are removed. |
| P4 | [observability.md](observability.md) extensions | Feeds HUD/event timelines and portfolio data proof. |
| P5 | [demo-video-hud-plan.md](demo-video-hud-plan.md) | Defines camera focus, HUD, and the author-owned capture flow. |
| P6 | [diagrams.md](diagrams.md) | Explains the research-to-runtime system and hybrid execution. |

| Document | Subsystem | Status |
| --- | --- | --- |
| [mass-1024-scaling.md](mass-1024-scaling.md) | Actor path admission + Mass simulation LOD | First implementation and 1,024-entity smoke verified; visible benchmark pending |
| [eqs-congestion.md](eqs-congestion.md) | EQS-driven affordance congestion handling | Deferred from Phase 2 |
| [async-inference.md](async-inference.md) | Asynchronous batched ONNX inference | Deferred from Phase 3 |
| [observability.md](observability.md) | Per-agent, path-scheduler, and Mass JSONL telemetry + analyzer | Phase 3/4 live and scaling-aware |
| [hybrid-stack.md](hybrid-stack.md) | Policy / Behavior Tree integration contract | Phase 2 live |
| [demo-video-hud-plan.md](demo-video-hud-plan.md) | Portfolio video scenario, nearest-agent camera focus, and HUD structure | Runtime scaffold and HUD assets present; capture pending |
| [editor-setup-guide.md](editor-setup-guide.md) | GameMode/World Settings, agent camera mount, spawner, and capture CVars | Editor setup guide available |
| [hud-widget-guide.md](hud-widget-guide.md) | UMG HUD widgets and zone-overlay materials | HUD widget assets present; final capture validation pending |
| [diagrams.md](diagrams.md) | Architecture and runtime data-flow diagrams | Phase 5 live |

## Current handoff

The portfolio now has a complete technical narrative from research objective to
engine bottleneck, architectural intervention, instrumentation, and verified
runtime smoke. The only presentation artifact intentionally left to the author
is video capture. Before publishing quantitative 1,024-NPC performance claims,
run the normal visible three-seed sweep and attach Unreal Insights CPU, render,
navigation, Mass, and memory captures.
