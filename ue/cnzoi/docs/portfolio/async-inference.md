# Asynchronous Batched ONNX Inference

**Status:** Deferred from Phase 3. Current substitute: synchronous
per-agent inference with a 0.5 s decision throttle.
**Owner:** AI / Engine Programmer
**Target scale:** 64–256 agents at 60 Hz

## Problem

`UPCSPPolicySubsystem::RunInferenceWithLogits` is currently synchronous and
single-agent. Each call:

1. Allocates a `[1, 33]` obs tensor and a `[1, 64]` persona tensor.
2. Runs `Model->RunSync(InputBindings, OutputBindings)` on the game thread.
3. Returns a `[1, 20]` logit vector.

At 16 agents with the 0.5 s throttle this costs ~32 syncs/s — comfortably
under budget (ONNX itself is ~0.3 ms on CPU). At 64 agents post-throttle
backoff it climbs to ~130 syncs/s and starts to compete with the rest of the
game thread. At the 32-agent stress, the 2026-05-17 baseline measured
~7.5 inferences/agent/s before the throttle was added; even with the
throttle, scaling beyond 64 agents will push synchronous game-thread
inference past 1 ms per frame.

## Goal

Move ONNX inference off the game thread, **batch all due agents into a
single call**, and amortize the per-call overhead. Target:

- 64 agents: median game-thread inference time per frame **< 0.1 ms**.
- 256 agents: same workload runs in **≤ 2 ms** of total wall-clock across a
  pool of worker tasks.
- Throughput at 256 agents: same `interactions_per_agent` and category
  coverage as the 64-agent baseline.

## Design

### Three-stage pipeline

```
┌──────────────────────┐   collect    ┌───────────────────────┐  dispatch  ┌──────────────────────┐
│ BTTask_PCSPDecision  │ ───────────► │ FInferenceBatchQueue  │ ─────────► │ FAsyncInferenceWorker│
│  (game thread)       │              │  (lock-free MPSC)     │            │  (TaskGraph thread)  │
└──────────────────────┘              └───────────────────────┘            └──────────┬───────────┘
        ▲                                                                              │
        │                                                                              │
        └──────────────────────── publish result ──────────────────────────────────────┘
                                  (per-agent atomic slot,
                                   game thread polls next tick)
```

Each `BTTask_PCSPDecision` tick still runs on the game thread but **does not
block** on inference. Instead:

1. It writes the agent's `obs` + `persona_proj` into the agent's
   pre-allocated `FInferenceRequest` slot and atomically marks `bPending = true`.
2. It returns `EBTNodeResult::InProgress` and the task observes the result
   slot on subsequent ticks.
3. Until the slot is filled, the agent keeps the **last cached action** —
   the same fallback the throttle already uses for sub-throttle ticks.

A background `FInferenceCoordinator` runs once per frame (TickFunction on a
non-game thread group):

1. Drains the pending request queue into a contiguous obs batch `[N, 33]`
   and persona batch `[N, 64]`.
2. Calls `Model->RunSync` once with batch size `N` (NNE/ONNX Runtime supports
   dynamic axes — the export script already sets `batch` as the dynamic dim).
3. Splits the `[N, 20]` logits and writes each row back to the requesting
   agent's result slot, atomically flipping `bPending = false`.

### Memory layout

Per-agent slots live in a single `TArray<FInferenceSlot>` indexed by
`AgentIndex` (assigned at spawn). Slots are pre-allocated, fixed-size, and
never grow at runtime:

```cpp
struct FInferenceSlot {
    alignas(64) FStaticArray<float, 33> Obs;
    alignas(64) FStaticArray<float, 64> Persona;
    alignas(64) FStaticArray<float, 20> Logits;
    std::atomic<uint8> State; // 0 = idle, 1 = pending, 2 = ready
};
```

`alignas(64)` keeps each field on its own cache line — false sharing between
neighbouring agents was a pathology in early prototypes.

### Batching policy

- **Latency cap:** a request waits at most one frame before dispatch. If
  the coordinator misses the frame (worker still running last batch), the
  request rolls forward; the agent keeps its cached action for one more
  tick. With a 0.5 s decision throttle this is invisible.
- **Batch budget:** dispatch at most `MaxBatchSize` requests per call
  (default 32). Larger batches don't help — NNE's `RunSync` is dominated
  by fixed overhead below ~16 and memory bandwidth above ~64.
- **Starvation guard:** if a slot is `pending` for > 250 ms it's
  promoted to a synchronous fallback so a stuck worker doesn't freeze a
  Behavior Tree.

### Thread safety

- The slot's `State` is the only synchronization primitive. Game thread
  CAS from `idle → pending`; worker CAS from `pending → ready`.
- The coordinator owns the batch tensors (one allocation at startup, reused
  every frame). No allocations in the hot path.
- `UPCSPPolicySubsystem::Model` is a `TSharedPtr<NNE::IModelInstance>`; in
  practice the NNE CPU runtime is reentrant for distinct `RunSync` calls on
  different threads, but we serialize through the coordinator anyway to
  keep tensor lifetimes simple.

## Work Breakdown

1. **`FInferenceSlot` + `FInferenceCoordinator`** — alloc, batch tensors, atomic state machine. ~1.5 days.
2. **`UPCSPPolicySubsystem::SubmitInference(AgentIndex)`** — non-blocking submit API. ~0.5 day.
3. **`BTTask_PCSPDecision` refactor** — store pending state in Blackboard, return `InProgress` until the slot is `ready`. ~1 day.
4. **Spawner wires `AgentIndex` at `SpawnActorDeferred → FinishSpawning`** (same hook as the PersonaId fix). ~0.5 day.
5. **Starvation guard + synchronous fallback path.** ~0.5 day.
6. **Validation:** rerun 32 and 64 agent stress sessions; add a 128-agent and 256-agent test once the World Partition streaming source is wired. ~1.5 days.

Estimated total: **5 engineering days** including measurement.

## Validation criteria

| Metric | Baseline (synchronous, 64 agents) | Target (async batched) |
|---|---|---|
| Game thread `stat unit` while PIE active | ~3 ms frame, inference ~0.4 ms | ≤ 2.8 ms frame, inference ≤ 0.1 ms game thread |
| Worker wall-clock per frame at 64 agents | n/a | ≤ 0.5 ms |
| End-to-end inference latency (request→result) | 0 frames | ≤ 2 frames at 60 Hz |
| Decision throughput (interactions / agent / min) | 4.7 | ≥ 4.5 (no regression) |
| Slot starvation events / 10 min | n/a | 0 |

## Risk notes

- **NNE batch semantics.** The exported model declares `batch` as a dynamic axis (`opset_version=17`, `dynamic_axes={"obs": {0: "batch"}, ...}`). NNERuntimeORT CPU honours this, but the GPU runtime treats dynamic axes differently — if a future port targets `NNERuntimeORTDml`, retest batching before reusing this design.
- **TaskGraph vs `Async(EAsyncExecution::Thread)`.** A long-running coordinator is a poor fit for TaskGraph (which is meant for short tasks). Use a dedicated `FRunnable` or `FTickFunction` on a non-render thread group; benchmark before committing to either.
- **Determinism.** Async dispatch can reorder when results land. Each result is keyed by `AgentIndex` so logic is unaffected, but JSONL trace ordering may not match real-time decision order. Trajectory analyzer already keys on `t` not arrival order — no change needed.

## Cross-references

- `BTTask_PCSPDecision::ExecuteTask` — current synchronous call site.
- `UPCSPPolicySubsystem::RunInferenceWithLogits` — keep as the synchronous fallback.
- `APCSPAgentSpawner` — deferred-spawn pattern reused for AgentIndex assignment.
- NNE plugin: `Engine/Plugins/Experimental/NNERuntimeORT/Source/NNERuntimeORTCpu`.
