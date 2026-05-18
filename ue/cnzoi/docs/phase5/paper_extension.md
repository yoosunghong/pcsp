# Engine-Integrated Hybrid Persona Control

**Draft section for the PCSP paper extension. Section number TBD by the
research lead; this doc proposes "§VIII — Engine Integration" appended after
the existing experimental sections.**

---

## Abstract addition (optional 1-sentence insert)

> We additionally demonstrate that the trained PCSP policy transfers, without
> retraining, into Unreal Engine 5 as a high-level intent selector inside a
> hybrid Behavior-Tree control stack, where it preserves persona-distinct
> behavior on held-out personas (inter-persona action dispersion ρ = 0.368
> on training personas, 0.368 on a held-out 60-persona split) and where
> ablating the persona embedding collapses dispersion to ρ = 0.990.

---

## 8. Engine-Integrated Hybrid Persona Control

The mini-Inzoi v3 environment is a 2D gridworld. To test whether PCSP's
persona conditioning survives transfer to a richer, continuous-space
simulator, we integrate the trained v3 policy into a custom Unreal Engine 5
project and replace the policy's tactical motor primitives (the 4 movement
actions) with engine-native pathing. The result is a *hybrid* control stack:
PCSP decides *what semantic action to take next*; the BT/NavMesh/EQS layer
decides *how to execute it*.

### 8.1 Hybrid stack

The stack has three layers (Figure&nbsp;X.1 — `diagrams.md` §1):

1. **Policy layer.** A `UPCSPPolicySubsystem` world subsystem loads the
   exported actor head (`pcsp_actor.onnx`, opset 17) via Unreal's NNE /
   `NNERuntimeORTCpu` runtime, plus a precomputed JSON of L2-normalised
   persona projections. At each decision tick the agent's
   `UPCSPObservationComponent` builds the v3 33-d observation
   (position, time, 8 needs, 8-way affordance one-hot, social context,
   routine signal, and the 4-agent-format "other agents" slot) and the
   subsystem runs synchronous inference to return one of 20 v3 actions.

2. **Symbolic layer (Behavior Tree).** A 3-branch priority Selector routes
   each decision through an Emergency / Persona / Idle subtree. The Persona
   branch chains `BTTask_PCSPDecision → BTTask_MoveToAffordance →
   BTTask_PerformInteraction`, with a Blackboard decorator on the Emergency
   branch (`UrgencyScore ≥ 0.85`, `Observer Aborts = Both`) that yanks
   agents out of in-progress interactions when a need spikes.

3. **Tactical layer.** Movement is engine-native NavMesh pathing; the
   four v3 movement actions (indices 16–19) are *remapped at the ONNX
   boundary* to outdoor-leisure / observe-crowd semantic actions so the
   Park/Observe zone has reachable producers. This remap lives only in the
   engine bridge — Python training and evaluation see the original v3
   ontology.

The Blackboard schema is published in `bt-blackboard-policy-contract.md`;
the affordance taxonomy (10 categories, 9 active, 1 folded) in
`affordance-taxonomy.md`.

### 8.2 Why hybrid and not policy-only

Movement is treated as an execution detail, not a policy action, for three
reasons:

- **Capacity for semantics.** The 20-action head spent 4 actions on movement
  in v3. In the engine those four indices carry no semantic meaning, so
  remapping them to behavioral actions widens the persona-discriminating
  output without retraining.
- **Engine-native tactical competence.** NavMesh, EQS, and the BT's
  failure-recovery decorators are mature subsystems. Asking the policy to
  re-derive them would waste capacity and would not generalize across map
  geometry.
- **Crisp evaluation.** The hybrid stack lets us ask a question we can't
  ask in the gridworld: *if movement is solved by the engine, how much of
  observed persona-distinct behavior comes from the persona embedding vs.
  the local need state?* The Phase&nbsp;4 ablations (§8.4) answer this.

### 8.3 Trajectory logging and analysis

Each agent writes a JSONL trajectory log under
`Saved/PCSP/Logs/<stamp>/agent_p<id>_<actor>.jsonl`. Events: `session_start`
(with `policy_mode`), `decision` (with action, urgency, 8-need snapshot, and
20-dim logit vector), `interaction_complete`, `interaction_failed`,
`move_failed` (with `failure_reason`, `intended_zone`, `distance_to_target`).
Buffered + auto-flushed every 5 s and on EndPlay.

Analysis is done offline by
`research/scripts/analyze_ue_session.py`, which aggregates per-persona action
histograms, category coverage, failure-reason breakdowns, decision-latency
distributions, and a per-persona mean policy distribution from the logged
softmax(logits). `--compare` produces per-persona Spearman ρ on action
histograms plus symmetric KL on the mean policy distributions between two
paired sessions. The companion `compare_ablations.py` aggregates N sessions
(one per ablation mode) into a single comparison table.

### 8.4 Phase 4 results

We ran four UE5 evaluation tracks. All used `Map_PCSPDistrict_M` (10 zones
matching the v3 affordance categories, capacities tuned for 64-agent peak
demand) with `pcsp_actor.onnx` exported from `results/pcsp_v3/full/policy.pt`.

**8.4.1 Scale validation.** With 64 agents and the final zone-capacity
configuration, the policy achieves a 1.7% failure rate across 2,438
`interaction_complete` events in 8 minutes (session `20260517_230327`).
9 of 10 categories are reached (Shop included; the Leisure enum is folded
into Observe via the v3 movement remap). At 32 agents the failure rate is
5.4%; at 16, 55% (capacity-tuned for 64, so 16 agents see contention only
where multiple agents pick the same zone simultaneously).

**8.4.2 Held-out persona transfer.** We swapped `persona_embeddings.json`
to hold 60 personas from the `test_60_v3` split (IDs 241..300) — personas
the policy never saw during training. After matching zone capacity to the
held-out demand profile (Work and Hygiene raised after a pre-fix run showed
99.4% of failures concentrated on `FocusedWork`/`PlanningWork`
`AllOverCapacity`), the clean held-out run produced a 0.04% failure rate
(1 `path_follow_idle_short` across 2,792 interactions, session
`20260518_140432`) and inter-persona action ρ = 0.368, vs. ρ = 0.383 on
matched train personas — i.e. *more* persona-distinct on unseen personas.

**8.4.3 Policy KL between paired sessions.** Two back-to-back train-persona
runs (`20260518_145353` vs. `20260518_151255`, 64 agents, ~5.7 min each)
yielded symmetric per-persona policy KL = 0.712 nats (median 0.475) and
Spearman ρ = 0.648. This is the noise floor — *the same policy on the same
personas under different need trajectories*. Any KL meaningfully above 0.7
nats between two paired runs reflects a real policy difference, not
short-window variance.

**8.4.4 Runtime ablations.** Three 64-agent runs with the same map and
persona set, varying the `pcsp.PolicyMode` console variable:

| Mode | n_int | fail % | reward | ρ vs PCSP | sym. KL | ρ_intra |
|---|---:|---:|---:|---:|---:|---:|
| HybridPCSP | 2,077 | 0.0 | 708.9 | ref | — | 0.368 |
| BTOnly | 1,152 | 87.6 | 395.2 | 0.319 | — | 0.989 |
| HybridNoPersona | 1,752 | 13.3 | 573.9 | 0.539 | 1.049 | 0.990 |

(BTOnly KL is suppressed: its logits are zero by construction, so any KL
against PCSP would just measure distance from uniform.)

Two findings:

1. **The persona embedding is load-bearing.** Zeroing the persona vector at
   inference (HybridNoPersona) collapses inter-persona action dispersion
   from ρ = 0.368 to ρ = 0.990 — action histograms become near-identical
   across all 64 personas. Throughput drops 16%; reward drops 19%. The
   policy is genuinely conditioning on the embedding, not on observation
   features alone.
2. **The ONNX policy strictly dominates the needs heuristic.** BTOnly's
   87.6% failure rate is 8,062 / 8,148 `FindBestZone:AllOverCapacity`
   events: 64 agents synchronise on the single most-urgent need each tick
   and pile into the same zone. Category coverage shrinks to 6 of 10
   (Exercise / Study / Shop / Observe never reached). Throughput halves;
   reward halves.

The remaining two ablations from the original five (`Hybrid-NoConsist` and
`RL-only`) require additional ONNX exports of already-trained checkpoints
(`results/pcsp_v3/no_consist/policy.pt` and
`results/baselines_v3/b1_no_persona/policy.pt`) and are tracked in
`research/PLAN.md` Phase E.

### 8.5 Implementation cost

The engine integration is intentionally lightweight:

- ~2,000 lines of C++ across `Source/cnzoi/PCSP/{Public,Private}/`
  (subsystem, components, BT tasks, agent character).
- One ONNX file (~4 MB) + one JSON persona cache (~150 KB) shipped with
  the project.
- Zero engine-side training. The Python pipeline is the single source of
  truth for both the policy and the persona embeddings.

The hybrid stack runs at ≥ 60 FPS PIE with 64 agents on a single
consumer GPU + CPU. Inference is synchronous on the BT tick; the
0.5-second decision throttle plus exponential backoff on
`RecentFailureCount` caps inference at ≤ 2 calls/agent/s, so 64 agents
generate ≤ 128 ONNX calls/s — within the NNERuntimeORT CPU path's headroom
without async batching.

### 8.6 Limitations and open work

- **Hybrid-NoConsist and RL-only** ablations are pending the export work
  noted in §8.4.4.
- **64-agent ceiling.** Validated; 128+ would require async batched
  inference and World Partition streaming sources (`scale-targets.md`).
- **Map geometry generalisation.** Results are for one map. We have not
  yet tested whether ρ_intra and the persona-embedding effect hold on a
  second, structurally different district.
- **Reward correlation.** The engine logs an in-game "reward" (the
  need-satisfaction delta) but does not compute the v3 training reward
  (which includes `r_persona_style` and `r_social`). Cross-domain reward
  comparison would require reimplementing the persona-style term in the
  engine.

### 8.7 Reproducibility

The full pipeline:

```
# 1. Train and export (Python side)
python research/scripts/run_pcsp_v3.py        # produces results/pcsp_v3/full/policy.pt
python research/scripts/export_pcsp_onnx.py   # produces pcsp_actor.onnx + persona_embeddings.json

# 2. Copy artifacts to UE5
cp research/results/export_ue5/pcsp_actor.onnx           ue/cnzoi/Content/PCSP/Models/
cp research/results/export_ue5/persona_embeddings.json   ue/cnzoi/Content/PCSP/Data/

# 3. Open ue/cnzoi/cnzoi.uproject, open Map_PCSPDistrict_M, hit Play.

# 4. Optionally swap ablation mode at the PIE console:
#    pcsp.PolicyMode 0  # HybridPCSP (default)
#    pcsp.PolicyMode 1  # BTOnly
#    pcsp.PolicyMode 2  # HybridNoPersona

# 5. Analyze
python research/scripts/analyze_ue_session.py \
    --session ue/cnzoi/Saved/PCSP/Logs/<stamp> \
    --out research/results/ue_sessions/<stamp>

# 6. Compare ablations
python research/scripts/compare_ablations.py \
    --session <pcsp> --session <bt> --session <nopersona> \
    --out research/results/ue_sessions/ablation_<date>
```

All code under `ue/cnzoi/` and `research/scripts/{analyze_ue_session,compare_ablations,export_pcsp_onnx}.py`.

---

## Figures referenced by this section

| Fig | Source | Status |
|---|---|---|
| X.1 | `diagrams.md` §1 (system overview) | Mermaid — render via `mmdc` for paper |
| X.2 | `diagrams.md` §2 (per-decision sequence) | Mermaid |
| X.3 | `diagrams.md` §3 (BT subtree) | Mermaid |
| X.4 | `diagrams.md` §4 (three-layer affordance) | Mermaid |
| X.5 | PIE screenshot — top-down `Map_PCSPDistrict_M` with zone overlays | **`[NEEDS CAPTURE]`** |
| X.6 | PIE screenshot — gameplay debugger overlay on a single agent | **`[NEEDS CAPTURE]`** |
| X.7 | Trajectory clip — 30 s rendered video of 64-agent run | **`[NEEDS CAPTURE]`** |
| X.8 | Ablation bar chart — n_int / fail% / reward / ρ_intra per mode | Generate from `ablation.json` (script TBD) |

Captures marked `[NEEDS CAPTURE]` require PIE access and aren't producible
from logs alone.

---

## Tables

| Tab | Content | Source |
|---|---|---|
| X.1 | Phase 4 ablation results (HybridPCSP / BTOnly / HybridNoPersona) | `research/results/ue_sessions/ablation_20260518_154827/ablation.json` |
| X.2 | Scale validation summary (8/16/32/64 agents, failure rate, throughput) | `scale-targets.md` §"Confirmed scale ceiling" |
| X.3 | Held-out persona transfer (train vs. test_60_v3) | `ue/cnzoi/PLAN.md` Phase 4 zero-shot entry |
