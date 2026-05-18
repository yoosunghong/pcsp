# PCSP UE5 Engineering Portfolio

Engineering-area PLAN documents pulled out of the main `ue/cnzoi/PLAN.md` so
they can stand alone as portfolio artifacts. Each document is self-contained:
problem statement, current state, proposed design, work breakdown, validation
criteria, and risk notes.

Differs from `PLAN.md` in scope:

- `PLAN.md` tracks every phase of the integration and is research-driven.
- Documents under this directory are scoped to a single engineering subsystem
  and written for an engine-focused reader (gameplay programmer, AI
  programmer, performance engineer).

| Document | Subsystem | Status |
| --- | --- | --- |
| [eqs-congestion.md](eqs-congestion.md) | EQS-driven affordance congestion handling | Deferred from Phase 2 |
| [async-inference.md](async-inference.md) | Asynchronous batched ONNX inference | Deferred from Phase 3 |
| [observability.md](observability.md) | Per-agent JSONL trace pipeline + analyzer | Phase 3/4 — live |
| [hybrid-stack.md](hybrid-stack.md) | Policy ↔ Behavior Tree integration contract | Phase 2 — live |
