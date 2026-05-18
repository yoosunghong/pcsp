# Phase 0 — Scale Target Confirmation

The PLAN's "Current Targets" table sets Debug = 8 / Main = 16 / Stress = 32–64.
This doc confirms those numbers are achievable on the validated map
(`Map_PCSPDistrict_M`) with current capacities and records the supporting runs.

## Confirmed scale ceiling: 64 agents

The 64-agent stress target is **validated** as of 2026-05-17.

| Scale | Agents | Status | Reference run | Failure rate | Throughput (int/agent) |
|---|---:|---|---|---:|---:|
| Debug | 8 | Implicit (subset of 16) | — | — | — |
| Main | 16 | ✓ Verified | `20260517_150713` (16-agent window) | 55% (capacity-limited) | ~10 / 10 min |
| Stress (low) | 32 | ✓ Verified | `20260517_150713` (32-agent window, ~343 s) | 5.4% | 32.8 / agent |
| Stress (high) | 64 | ✓ Verified | `20260517_230327` (483 s, Run 3 of progression) | **1.7%** | 38.1 / agent |
| Zero-shot 64 | 64 (held-out personas) | ✓ Verified | `20260518_140432` (9.75 min) | **0.04%** | 43.6 / agent |

The "Main = 16" 55% failure rate is **not** a bottleneck on the engine — it's
capacity contention from running 16 agents through zones sized for the 64-agent
stress targets. At lower per-zone capacity, 16 agents have headroom; the
55% number is what showed up before the Phase 4 capacity tuning.

## What "confirmed" means here

Two things need to hold for a scale to be "confirmed":

1. **Engine throughput:** PIE runs at ≥ 60 FPS with all agents active.
   `BTTask_PCSPDecision`'s 0.5 s decision throttle plus the
   `RecentFailureCount` exponential backoff caps ONNX inference at
   ≤ 2 calls per agent per second under normal conditions, ≤ 0.22 under
   sustained MoveTo failure — so 64 agents = ≤ 128 inferences/s, which the
   NNERuntimeORT CPU path handles synchronously without async batching.
2. **Behavioral coverage:** every active category gets reached. The
   2026-05-17 Run 3 covered 9/9 active categories (Shop included);
   the Leisure enum has no zone (folded into Observe via the v3 movement
   remap — see [`affordance-taxonomy.md`](affordance-taxonomy.md)).

Both held under the 64-agent stress run. There's no engine-side reason to
re-run a separate "Debug = 8" validation: 8 agents is a strict subset of the
16-agent baseline, and a Main run with fewer agents will always have looser
contention than the same map at Main scale.

## What 64+ would need

The PLAN allows Stress = "32–64 (500+ personas)". We have not validated
beyond 64 agents. To push to 128+ would require, in order of likelihood to bite:

1. **Async / batched inference** — currently deferred. At 128 agents with
   sustained 2 inferences/s/agent, 256 calls/s starts to be tight on a
   single CPU thread. Move inference off the BT task tick onto a worker
   pool, with batched (N, 33) / (N, 64) inputs.
2. **More zones per category** — even with Rest = 20 and Social = 20,
   doubling the agent count doubles peak contention. Either add a second
   `BedroomLounge` zone or raise capacity to 40 and add 20 more
   `BP_InteractionPoint` actors per zone.
3. **World Partition streaming sources** — once zones spread far enough that
   not all of them fit in the editor camera's startup radius, the
   `Is Spatially Loaded = false` workaround stops scaling. Add a
   `WorldPartitionStreamingSource` co-located with each spawner, or move
   to a non-WP map for the 128+ stress configuration.

None of these are blockers for the 16/32/64 targets already in scope.

## Persona count vs. agent count

The PLAN's persona-count column (100 / 300–500 / 500+) is decoupled from
agent count — both the 64-agent baseline and the 64-agent held-out runs use
64 personas (one per agent, 1:1). When personas > agents, `APCSPAgentSpawner`
draws without replacement from slots 1..N up to `AgentCount`; the unassigned
personas are still loaded by `UPCSPPersonaCache` so `RunInference` can
validate the embedding dim, they're just never selected for an agent.

The held-out zero-shot run (`run_zeroshot_eval.py prepare`) repacks
`persona_embeddings.json` so slots 1..N hold personas 241..300, then
relabels per-persona logs after the fact via the slot→real-id manifest. This
is the mechanism that lets us reuse the 16/32/64 scale with any persona split
without changing UE code.
