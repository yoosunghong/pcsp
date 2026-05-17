# CNZOI UE5 Development Plan

This document is the active implementation plan for the Unreal Engine 5 side of PCSP. It is derived from `PCSP_UE5_Implementation_Plan.md` and should be updated whenever the UE5 architecture, task order, or research interface changes.

## Direction

Build a UE5 life-simulation sandbox that integrates Persona-Conditioned Shared Policy (PCSP) with Unreal-native AI systems. The core design is a hybrid decision stack:

1. PCSP chooses the high-level semantic intent.
2. Behavior Tree, Blackboard, EQS, AIController, and NavMesh execute that intent.
3. UE5 records rich trajectory traces for evaluation and human-readable demonstrations.

Movement is an execution detail, not a policy action. The policy should output semantic actions such as `EatQuick`, `FocusedWork`, `ExerciseSocial`, or `IdleReflect`; UE5 should resolve affordance targets, pathing, reservation, retry, and interaction execution.

## Current Targets

| Scale | World | Agents | Personas | Purpose |
| --- | --- | ---: | ---: | --- |
| Debug | Small district | 8 | 100 | Communication, reward, and behavior validation |
| Main | Medium district | 16 | 300-500 | Paper reproduction plus UE5 extension |
| Stress | Large district | 32-64 | 500+ | Scalability and real-time evaluation |

## Architecture Tasks

- Define an affordance-zone taxonomy for the UE5 level.
- Specify the Behavior Tree, Blackboard, and policy interface contract.
- Implement C++ components for persona state, needs, social context, observations, and trajectory logging.
- Implement affordance registration and lookup as a world-level service or subsystem.
- Implement custom Behavior Tree nodes for PCSP decisions, affordance movement, and interactions.
- Decide whether the first inference bridge uses a Python service, ONNX Runtime, or TorchScript.
- Keep the Python research implementation reproducible while adding UE-facing export or bridge code only where needed.

## Phase Roadmap

### Phase 0: Environment Redesign Documentation

- [ ] Summarize the Python Mini-Inzoi reward, observation, and action logic.
- [ ] Define the UE5 affordance taxonomy.
- [ ] Write the BT-Blackboard-Policy interface specification.
- [ ] Confirm Main and Stress scale targets.

### Phase 1: Continuous-Space Prototype

- [x] Build a Medium district level (`Content/PCSP/Maps/Map_PCSPDistrict_M.umap`)
      with one zone per category (Kitchen/Eat, Bedroom+Lounge/Rest, Office/Work,
      Library/Study, Gym/Exercise, Bathroom/Hygiene, SocialHub/Social, Park/Observe,
      Shop/Shop). Map uses World Partition; all gameplay actors (zones,
      interaction points, spawner) must have `Is Spatially Loaded = false` —
      see Phase 4 streaming note below.
- [x] Spawn and schedule 16 agents (C++ `APCSPAgentSpawner`, configurable `AgentCount`).
- [x] Create NavMesh, affordance zones, and interaction points
      (C++ `APCSPAffordanceZone`, `APCSPInteractionPoint`, `UPCSPAffordanceSubsystem` in place;
      all 10 zone instances + interaction points placed in map; NavMesh built).
- [x] Implement needs, social, and observation components
      (`UPCSPNeedsComponent`, `UPCSPSocialContextComponent`, `UPCSPObservationComponent`,
       `UPCSPPersonaComponent`, `UPCSPTrajectoryLogComponent`).
- [x] Build the baseline Blackboard-driven Behavior Tree skeleton
      (`BB_PCSPAgent` + `BT_PCSPAgent` authored in editor; `UBTTask_PCSPDecision` live and writing keys).

### Phase 2: Hybrid Behavior Tree Implementation

- [x] Implement `UBTTask_PCSPDecision` (Phase 1 stub, maps needs → action type).
- [x] Implement `UBTTask_MoveToAffordance` — queries subsystem, reserves interaction point, moves agent; retries up to MaxRetries times on path failure.
- [x] Implement `UBTTask_PerformInteraction` — waits InteractionDuration, applies needs satisfaction delta, releases reservation.
- [x] Add retry and reservation conflict handling (MoveToAffordance RetryCount + RecentFailureCount BB key; PerformInteraction checks reservation validity each tick).
- [x] Emergency branch for critical needs (UrgencyScore > 0.85 Blackboard Decorator, Observer Aborts = Both).
- [ ] Congestion handling — EQS or weighted zone scoring when multiple agents compete for the same zone (deferred to Phase 3 scaling work).
- [x] Zone-coverage fix for engine-integration experiment (2026-05-17):
      Park (Observe) and Gym (Exercise) were systematically unvisited.
      Resolution: agents now run on ONNX inference exclusively — heuristic
      fallback removed. (a) ONNX v3 indices 16-19 (movement, unused in UE)
      remapped to `LeisureOutdoor`/`ObserveCrowd` so the Observe category has
      a reachable action; (b) Gym (Exercise) is reachable via v3 indices 8/9
      which the policy already emits. If `pcsp_actor.onnx` or
      `persona_embeddings.json` is missing, `BTTask_PCSPDecision` now logs
      an Error and returns Failed — agents do not move rather than fall back
      to a heuristic surrogate.

### Phase 3: PCSP Policy Integration

- [x] Implement persona embedding cache loading (`UPCSPPersonaCache` — reads persona_embeddings.json).
- [x] Load projected persona vectors into `UPCSPPersonaCache`; `UPCSPPersonaComponent::GetPersonaId()` exposes 1-based ID.
- [x] Connect ONNX Runtime inference via `UPCSPPolicySubsystem` (NNE / NNERuntimeORT plugin).
      Graceful fallback to needs heuristic when model files are absent.
- [x] Align `UPCSPObservationComponent` to v3 33-dim schema (pos/time/needs/zone-onehot/social/routine/neighbors).
- [x] Export script: `research/scripts/export_pcsp_onnx.py` → pcsp_actor.onnx + persona_embeddings.json.
- [ ] Add async/batched inference (deferred — synchronous is sufficient for ≤16 agents at 60Hz).
- [x] Export reward and trajectory logs from `UPCSPTrajectoryLogComponent` (2026-05-17):
      Per-agent JSONL written to `Saved/PCSP/Logs/<YYYYMMDD_HHMMSS>/agent_p<id>_<actor>.jsonl`.
      Events: `decision`, `interaction_complete`, `interaction_failed`, `move_failed`.
      Each entry carries t, persona_id, pos, action, affordance, category, urgency, reward,
      and 8-need snapshot. Buffered + auto-flushed every 5s and on EndPlay.

### Phase 4: Scaling And Experiments

- [x] Decision throttle + failure backoff (2026-05-17): `BTTask_PCSPDecision`
      now caches the last action and only re-runs ONNX every
      `MinDecisionInterval` seconds (default 0.5s). Effective interval is
      multiplied by `(1 + RecentFailureCount)` so repeated MoveTo failures
      back off instead of hot-looping. UrgencyScore ≥ 0.85 bypasses the
      throttle. Removes the ~7.5 inferences/agent/s observed in the
      2026-05-17 run.
- [x] Spawner deferred-spawn fix (2026-05-17): `APCSPAgentSpawner` now uses
      `SpawnActorDeferred → set PersonaId → FinishSpawning` so
      `TrajectoryLog::BeginPlay` sees the correct PersonaId when naming the
      log file. Previously all log files were named `agent_p001_*` even though
      per-record `persona_id` was correct.
- [x] World Partition streaming fix (2026-05-17): all `BP_AffordanceZone`,
      `BP_InteractionPoint`, and `BP_PCSPAgentSpawner` instances in
      `Map_PCSPDistrict_M` set to `Is Spatially Loaded = false`. With no
      `WorldPartitionStreamingSource` present (16 AI-only pawns), spatially
      loaded zones outside the editor camera's startup streaming radius were
      never spawned, so `UPCSPAffordanceSubsystem` only registered 7 of 10
      zones — Kitchen/Gym/Shop never streamed in, producing 100% move_failed
      for Eat/Exercise/Shop. After the toggle: `FindBestZone` reports
      `reg=10,valid=10` every query.
- [x] Move-task failure isolation (2026-05-17): `UPCSPAffordanceSubsystem::FindBestZone`
      gained a diagnostic overload returning `FPCSPZoneSelectionDebug`
      (rejection enum + per-stage counts). `BTTask_MoveToAffordance` now
      labels every failure branch (`FindBestZone:<reason>`,
      `zone_no_free_interaction_point`, `interaction_point_reserve_race_lost`,
      `pathfinding_request_failed`, `path_follow_idle_short:dist=<cm>`) and
      writes `failure_reason`, `intended_zone`, `distance_to_target` to the
      JSONL. These are the fields the Phase 4 verification recipes below
      depend on.
- [x] Path-follow acceptance fix (2026-05-17):
      `FAIMoveRequest::SetReachTestIncludesAgentRadius(false)` in
      `BTTask_MoveToAffordance::TryBeginMove`. Without it, pathfollowing
      treats `AcceptanceRadius` as capsule-inclusive and stops at
      `AcceptanceRadius + AgentRadius (~40cm)` from the goal; our 2D distance
      success check then misses by 15–30 cm. Logs before fix clustered failures
      at `dist=313–331` for a 300 cm acceptance; after fix, `path_follow_idle_short`
      dropped from 2,414 to 84 events (−96.5%).
- [x] 16-agent baseline verified (2026-05-17, session `20260517_150713`,
      10 min PIE): 690 `interaction_complete` across 8 of 10 categories
      (Eat, Rest, Work, Study, Exercise, Hygiene, Social, Observe). Remaining
      55% failure rate is 90% `FindBestZone:AllOverCapacity` — capacity
      contention from 8 of 10 categories having only 1 zone each. This is
      the realistic-competition failure mode the throttle's `RecentFailureCount`
      backoff was designed for; not a blocker. Missing: Shop (policy emits
      `BrowseArea` at ~0.25% — almost never tried). Note: the `Leisure` enum
      value has no zone in the level — it was folded into Observe during the
      Phase 2 remap (v3 indices 16/18 emit `LeisureOutdoor`, which routes to
      the Park/Observe zone via `BTTask_MoveToAffordance::ActionToCategory`).
      Effective taxonomy is 9 categories, not 10.
- [x] Test 32 agents (2026-05-17, session `20260517_150713`, 32-agent window ~343s):
      Capacity raised from 4 to 8 on bottleneck zones before this run.
      Results: 1,049 `interaction_complete` across all 9 active categories
      (Shop appeared for the first time at 2 completions). The `Leisure` enum
      value has no zone in the level — see 16-agent note above. Failure rate collapsed from 55% to
      5.4%; 60 `move_failed` total, 91.7% `FindBestZone:AllOverCapacity` on Rest
      zones (Bedroom/Lounge still single-zone — primary bottleneck at 32 agents).
      Avg 32.8 interactions/agent over 343s (~4× throughput vs 16-agent baseline).
      Total reward: 347.85. Prerequisite for 64-agent run: add a second Rest zone
      or raise Rest capacity further to keep AllOverCapacity below 50%.
- [x] Stress test 64 agents — three-run progression (2026-05-17):
      **Run 1** session `20260517_150713` (1,490s, Rest cap=20, Social cap unchanged):
      9,833 `interaction_complete`, 69,421 `move_failed`, failure rate 87.6%.
      Dominant failure: `FindBestZone:AllOverCapacity` (65,618, 94.5%) — Social zone
      saturated at zone level. Total reward: 3,348.50. Fix: raise Social zone capacity.

      **Run 2** session `20260517_224132` (1,012s, Social cap raised):
      4,738 `interaction_complete`, 7,501 `move_failed`, failure rate 61.3%.
      `FindBestZone:AllOverCapacity` collapsed to 262; new dominant failure:
      `zone_no_free_interaction_point` on `PCSP.Zone.Rest` (7,219, 96.2%) —
      zone capacity raised but insufficient `BP_InteractionPoint` actors in Rest zone.
      Total reward: 1,663.45. Fix: add interaction points inside Rest zone.

      **Run 3** session `20260517_230327` (483s, Rest interaction points expanded):
      2,438 `interaction_complete` across all 9 active categories, only 43 `move_failed`,
      failure rate **1.7%** — residual `AllOverCapacity` spikes (42 events), not
      structural. Total reward: 835.30. Avg 38.1 interactions/agent (~4.7/agent/min).
      Category coverage: Social 876, Rest 856, Work 403, Hygiene 121, Study 62,
      Observe 52, Eat 47, Exercise 15, Shop 6 (Leisure enum has no zone — folded
      into Observe; see 16-agent note). 64-agent stress target validated.
- [ ] Automate zero-shot persona evaluation.
- [ ] Collect Spearman rho, policy KL, latency, path failure, and congestion metrics.
- [ ] Compare BT-only, RL-only, Hybrid-PCSP, Hybrid-NoConsist, and Hybrid-NoPersona settings.

### Phase 5: Paper And Portfolio Artifacts

- [ ] Prepare implementation diagrams.
- [ ] Capture rich trajectory clips.
- [ ] Prepare UE5 screenshots, performance tables, and architecture figures.
- [ ] Draft the paper extension section: "Engine-Integrated Hybrid Persona Control".

## Debug Log Map

When verifying a PIE session, check logs in this order. The first three are sufficient for the 16-agent baseline; the rest are scaling diagnostics.

### A. PIE startup — Output Log (Window ▸ Output Log)

Filter on `LogTemp`. Required lines on a healthy boot:

| Source | Expected line | What it confirms |
| --- | --- | --- |
| `UPCSPPolicySubsystem::Initialize` | `PCSPPolicySubsystem: ready (obs=33, persona_dim=64, n_actions=20)` | ONNX model + persona cache loaded. Missing → agents will freeze. |
| `UPCSPTrajectoryLogComponent::GetSessionDir` | `PCSPTrajectoryLog: session dir = .../Saved/PCSP/Logs/<stamp>` | Log directory created; emitted on first agent BeginPlay. |

Error lines that *must not appear*:
- `PCSPPolicySubsystem: pcsp_actor.onnx not found` — export missing.
- `PCSPPolicySubsystem: persona_embeddings.json not found` — export missing.
- `PCSPPolicySubsystem: invalid persona_id=N` — cache too small (need ≥16 personas).
- `BTTask_PCSPDecision: PCSPPolicySubsystem is not ready` — model load failed.

### B. Per-agent behavior — `Saved/PCSP/Logs/<stamp>/agent_p<id>_*.jsonl`

One file per spawned agent. Each line is a JSON object. Use these to answer Phase 4 verification questions:

| Question | jq / grep recipe |
| --- | --- |
| Are all 16 personas active? | `ls Saved/PCSP/Logs/<stamp>/` — expect 16 files. |
| Is every agent producing decisions? | `grep -c '"event":"decision"' agent_p*.jsonl` per file. |
| Is the action distribution non-degenerate? | `jq -r 'select(.event=="decision") \| .action' agent_p*.jsonl \| sort \| uniq -c` |
| Are Park (Observe) + Gym (Exercise) reached? | `jq -r 'select(.event=="interaction_complete") \| .category' \| sort \| uniq -c` — both `Observe` and `Exercise` must appear. |
| Reward accumulation per persona | `jq -s 'map(select(.event=="interaction_complete") \| .reward) \| add' agent_p001_*.jsonl` |
| Path-failure rate | `grep -c '"event":"move_failed"' agent_p*.jsonl` vs decision count. |
| Failure-cause breakdown | `jq -r 'select(.event=="move_failed") \| .failure_reason' agent_p*.jsonl \| cut -d: -f1 \| sort \| uniq -c`. Top-level reasons: `FindBestZone`, `path_follow_idle_short`, `pathfinding_request_failed`, `zone_no_free_interaction_point`, `interaction_point_reserve_race_lost`. A `FindBestZone:AllCategoryMismatch` spike means a zone class did not register — usually World Partition streaming. A `path_follow_idle_short:dist=<cm>` cluster well above `AcceptanceRadius` means the `SetReachTestIncludesAgentRadius(false)` call regressed or the InteractionPoint collision is inflating the stop distance. |
| Intended-zone audit | `jq -r 'select(.event=="move_failed") \| [.action, .intended_zone] \| @tsv' agent_p*.jsonl \| sort \| uniq -c`. If an action consistently has `intended_zone:""`, the chosen category has no registered zone (streaming/config issue). |
| Reservation contention | `grep -c '"event":"interaction_failed"' agent_p*.jsonl` (look for `reservation_stolen_mid_interaction`). |
| Emergency-branch firing | `jq 'select(.event=="decision" and .urgency > 0.85)' agent_p*.jsonl` |

### C. Runtime spot-checks (PIE)

- **`stat unit`** — frame time at 16 agents (baseline) vs 32 (Phase 4 target).
- **Gameplay Debugger (Apostrophe key)** — Blackboard keys per agent: `DesiredActionType`, `UrgencyScore`, `bAffordanceReserved`. Confirms BT decorator routing.
- **`showdebug ai`** — current MoveTo target / path status; correlates with `move_failed` entries.

### D. Cross-run analysis (offline)

Aggregate across many PIE sessions for the metrics named in [PLAN.md:90](PLAN.md):
- Spearman ρ — load all `decision` rows, group by `persona_id`, compare action histograms vs the research baseline.
- Policy KL — compute per-step softmax KL between this run and a reference run (requires logit export, not yet implemented).
- Latency — derive from `t` deltas on consecutive `decision` events per agent.

## Working Rules

- Treat this file as the active UE5 task plan.
- Keep `PROPOSAL.md` aligned with the high-level research and product rationale.
- Record completed tasks, decisions, result paths, failed attempts, and retraining requirements in `DONE.md`.
- If a UE5 change alters the Python research API, observation schema, action ontology, or training/export contract, also update `../../research/PLAN.md`.
- Do not commit Unreal-generated build/cache directories unless explicitly required.
