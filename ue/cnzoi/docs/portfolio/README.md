# PCSP UE5 Engineering Portfolio

Engineering-area PLAN documents pulled out of the main `ue/cnzoi/PLAN.md` so
they can stand alone as portfolio artifacts. This directory is now the home for
UE5 portfolio work: engineering extension plans, diagrams, and the final
capture/HUD scenario.

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
| P1 | [eqs-congestion.md](eqs-congestion.md) | Makes crowd behavior more demonstrable and reduces capacity hot spots. |
| P2 | [async-inference.md](async-inference.md) | Prepares the system for larger-scale portfolio runs beyond the current synchronous path. |
| P3 | [observability.md](observability.md) extensions | Feeds HUD/event timelines and portfolio data proof. |
| P4 | [demo-video-hud-plan.md](demo-video-hud-plan.md) | Adds camera focus, HUD, and capture flow after the runtime story is stronger. |
| P5 | [diagrams.md](diagrams.md) | Polishes explanatory artifacts after implementation details settle. |

| Document | Subsystem | Status |
| --- | --- | --- |
| [eqs-congestion.md](eqs-congestion.md) | EQS-driven affordance congestion handling | Deferred from Phase 2 |
| [async-inference.md](async-inference.md) | Asynchronous batched ONNX inference | Deferred from Phase 3 |
| [observability.md](observability.md) | Per-agent JSONL trace pipeline + analyzer | Phase 3/4 live |
| [hybrid-stack.md](hybrid-stack.md) | Policy / Behavior Tree integration contract | Phase 2 live |
| [demo-video-hud-plan.md](demo-video-hud-plan.md) | Portfolio video scenario, nearest-agent camera focus, and HUD structure | Phase 5 planned |
| [editor-setup-guide.md](editor-setup-guide.md) | GameMode/World Settings, agent camera mount (D2), spawner + Project Settings, capture CVars | Phase 5 editor setup |
| [hud-widget-guide.md](hud-widget-guide.md) | UMG HUD widgets (D4) and zone-overlay materials (D5) editor build | Phase 5 editor build |
| [diagrams.md](diagrams.md) | Architecture and runtime data-flow diagrams | Phase 5 live |
