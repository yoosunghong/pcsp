# CNZOI UE5 Development Log

Use this file to record completed UE5 work, important implementation decisions, generated artifact paths, failed attempts, and follow-up requirements.

## 2026-05-13

- Created UE5-specific planning documents under `ue/cnzoi/`.
- Established `PLAN.md` as the active UE5 implementation plan.
- Established `PROPOSAL.md` as the high-level rationale and scope document.
- Established `DONE.md` as the UE5 progress and decision log.

## Decision Log

Record durable decisions here.

| Date | Decision | Rationale | Follow-up |
| --- | --- | --- | --- |
| 2026-05-13 | Use a hybrid PCSP + Behavior Tree architecture. | PCSP should choose high-level persona-conditioned intent while UE5 handles tactical execution, navigation, interaction, and recovery. | Specify the Blackboard contract before implementing BT tasks. |
| 2026-05-13 | Treat movement as a Behavior Tree execution node, not a policy action. | This keeps policy capacity focused on semantic behavior and leaves continuous movement to NavMesh and BT logic. | Implement `UBTTask_MoveToAffordance`. |
| 2026-05-13 | Target 16 agents for the main prototype and 32-64 agents for stress testing. | This matches and extends the research scale while demonstrating engine integration value. | Add performance and latency logging early. |

## 2026-05-13 - Phase 1 C++ Scaffold

Branch: `ue5/phase1-prototype`. Added the Phase 1 C++ scaffold under `Source/cnzoi/PCSP/`:

- `PCSP/PCSPTypes.h` - `EPCSPActionType` (20 actions), `EPCSPAffordanceCategory`, `EPCSPNeed`, `FPCSPDecision`, and a `PCSPBlackboard::` namespace of canonical Blackboard key names (Blackboard asset must match).
- `PCSP/Components/` - `UPCSPNeedsComponent` (8 needs with per-need decay/critical config), `UPCSPSocialContextComponent` (radius-based nearby summary + affinity map), `UPCSPObservationComponent` (fixed-length 40-d vector: needs + day phase + social summary, padded for Phase 2/3 fields), `UPCSPPersonaComponent` (id/text/projected vector skeleton), `UPCSPTrajectoryLogComponent` (action/affordance/reward entries).
- `PCSP/Affordance/` - `APCSPInteractionPoint` (reservation), `APCSPAffordanceZone` (gameplay-tag + category + capacity + child interaction points, registers with subsystem in BeginPlay), `UPCSPAffordanceSubsystem` (`UWorldSubsystem`, `FindBestZone`/`GetZonesByCategory`).
- `PCSP/Agent/` - `APCSPAgentCharacter` (composes all five components), `APCSPAIController` (runs assigned `BehaviorTreeAsset` on possession).
- `PCSP/Sim/` - `APCSPSimGameMode` (defaults pawn + controller), `APCSPAgentSpawner` (`AgentCount=16`, NavMesh-aware random reachable points with non-NavMesh fallback).
- `PCSP/BT/BTTask_PCSPDecision` - Phase 1 stub that writes `DesiredActionType` + `UrgencyScore` from the most urgent need; Phase 2/3 replaces the body with the PCSP shared policy inference call.
- `Source/cnzoi/cnzoi.Build.cs` - added `NavigationSystem`, `GameplayTags`, `GameplayTasks` to `PublicDependencyModuleNames` and added the PCSP subdirectories to `PublicIncludePaths`.

### Editor-side follow-ups still required for Phase 1

- Create `Content/PCSP/Maps/Map_PCSPDistrict_M.umap` (Medium district geometry).
- Drop in a `RecastNavMeshBoundsVolume`; verify NavMesh build.
- Place `APCSPAffordanceZone` instances with `ZoneTag`/`Category`/child interaction points covering Eat / Rest / Work / Study / Exercise / Hygiene / Social / Leisure / Shop.
- Author `BB_PCSPAgent` Blackboard with keys exactly matching `PCSPBlackboard::` (DesiredActionType as enum, DesiredAffordanceTag as gameplay tag, TargetActor, TargetLocation, InteractionStyle, UrgencyScore, RecentFailureCount, SocialTargetActor, CurrentZoneTag, bAffordanceReserved).
- Author `BT_PCSPAgent` Behavior Tree skeleton matching the layout in section 6.2 of `PCSP_UE5_Implementation_Plan.md`; root selector with Emergency / Persona / Idle branches; the Persona branch begins with `BTTask_PCSPDecision`.
- Place one `APCSPAgentSpawner` per spawn cluster; set `AgentClass` to a BP child of `APCSPAgentCharacter` whose controller defaults to a BP child of `APCSPAIController` with `BehaviorTreeAsset = BT_PCSPAgent`.
- Set the World Settings `GameMode Override` to `APCSPSimGameMode` (or a BP child).

### Decisions

| Date | Decision | Rationale | Follow-up |
| --- | --- | --- | --- |
| 2026-05-13 | Observation vector is fixed at 40 floats with explicit slots for needs (8) + time (2) + social (5) and a zero-padded tail. | Matches the 32-48 dim target from the implementation plan and gives stable shapes for Python parity / future ONNX export. | Fill remaining slots in Phase 2 (zone occupancy, affordance availability, routine, persona memory hooks). |
| 2026-05-13 | Affordances are exposed via `UWorldSubsystem` rather than `GameInstanceSubsystem`. | Affordance set is per-level; per-world lifetime avoids stale references across map loads. | Confirm before adding cross-map persistence. |
| 2026-05-13 | Reservation lives on `APCSPInteractionPoint`, not on the zone. | Allows multiple agents in one zone while still serializing interactions at a specific seat / station / station-point. | Add reservation timeout in Phase 2 to avoid deadlock. |

## 2026-05-13 - PCSP Public/Private Layout

- Moved PCSP headers to `Source/cnzoi/PCSP/Public/` and PCSP implementation files to `Source/cnzoi/PCSP/Private/`, preserving the existing `Affordance`, `Agent`, `BT`, `Components`, and `Sim` subdirectories.
- Updated `Source/cnzoi/cnzoi.Build.cs` with explicit PCSP public and private include paths so short includes such as `#include "PCSPTypes.h"` resolve from nested PCSP headers.
- Verified with `Build.bat cnzoiEditor Win64 Development -Project=D:\Github\pcsp\ue\cnzoi\cnzoi.uproject -WaitMutex -NoHotReload`; result succeeded.

## 2026-05-18 - Policy Logit Export + KL Compare

Closed the last open analytics item in Phase 4.

- `UPCSPPolicySubsystem::RunInferenceWithLogits` returns the raw 20-dim
  logit vector alongside the argmax action; the original `RunInference`
  path is unchanged.
- `BTTask_PCSPDecision` calls the new entry point and forwards logits to
  `UPCSPTrajectoryLogComponent::RecordDecisionWithLogits`. Throttled
  "reuse last action" hits do not call inference and therefore do not
  emit logits — only fresh decisions produce a `logits` field.
- `decision` JSONL rows now carry `"logits":[20 floats]` (spot-checked
  on `agent_p001_*.jsonl` in `Saved/PCSP/Logs/20260518_151255/`).
- `research/scripts/analyze_ue_session.py` softmaxes each row's logits
  into a running per-agent mean; `analyze_session()` aggregates that
  into a decision-weighted per-persona policy distribution.
  `--compare` adds `kl_ab`, `kl_ba`, and `kl_symmetric` per matched
  persona plus `per_persona_kl_mean/median`.
- **Verification** — paired PIE runs `20260518_145353` vs `20260518_151255`
  (64 agents, ~5.7min each, same train personas):
  matched personas = 64, mean Spearman ρ = 0.648, mean symmetric KL =
  0.712 nats (median 0.475). Per-persona spread is wide
  (pid=1 KL = 0.086, pid=2 KL = 2.726) — driven by short-window
  need-trajectory variance, as expected. Wrote
  `research/results/ue_sessions/kl_20260518_151255/{summary,compare}.json`.

## Open Follow-ups

- Define the first UE5 affordance taxonomy.
- Write the BT-Blackboard-Policy interface contract.
- Decide the initial inference bridge: Python service, ONNX Runtime, or TorchScript.
- Confirm which Python artifacts are required for UE5 runtime loading.
- Phase 4 ablations: BT-only, RL-only, Hybrid-PCSP, Hybrid-NoConsist,
  Hybrid-NoPersona comparison runs (last remaining Phase 4 item).
  Runtime ablations (HybridPCSP / BTOnly / HybridNoPersona) are wired
  via the `pcsp.PolicyMode` CVar — see Phase 4 entry in PLAN.md.
  Hybrid-NoConsist and RL-only still need new ONNX exports from
  `research/`.

## 2026-05-18 - Runtime Ablation Results

Three back-to-back 64-agent PIE runs, identical map/persona set,
`pcsp.PolicyMode` cycled between modes. Sessions:
`20260518_153310` (HybridPCSP), `20260518_154015` (BTOnly),
`20260518_154827` (HybridNoPersona). Aggregate:
`research/results/ue_sessions/ablation_20260518_154827/ablation.json`.

| mode             | n_int | fail% | reward | rho_ref | KL_ref | rho_intra |
| ---------------- | ----: | ----: | -----: | ------: | -----: | --------: |
| HybridPCSP       |  2077 |  0.0% |  708.9 |     ref |      - |     0.368 |
| BTOnly           |  1152 | 87.6% |  395.2 |   0.319 |      - |     0.989 |
| HybridNoPersona  |  1752 | 13.3% |  573.9 |   0.539 |  1.049 |     0.990 |

Findings:
- Persona embedding is load-bearing — inter-persona action dispersion
  collapses from 0.368 → 0.990 the moment the embedding is zeroed.
  Throughput -16%, reward -19%. The policy is genuinely conditioning
  on the embedding, not on needs alone.
- BTOnly's 87.6% failure rate is 8,062 / 8,148 `FindBestZone` failures
  — 64 agents synchronize on the single most-urgent need each tick,
  so they pile into the same zone and bounce off `AllOverCapacity`.
  Category coverage drops to 6 of 10 (Exercise/Study/Shop/Observe
  never reached). Throughput -45%, reward -44%.
- BTOnly KL vs reference is suppressed because its logits are zero
  by construction — KL would just measure distance from uniform.
- HybridNoPersona vs HybridPCSP symmetric KL = 1.05 nats; for context,
  self-vs-self KL on two HybridPCSP runs was 0.71 nats (Phase 4 KL
  verification entry above).

## 2026-05-18 - Phase 0 Documentation + Phase 5 Artifacts

Cleared the remaining Phase 0 docs and the doc-only portion of Phase 5 in
one pass.

**Phase 0:**
- [docs/phase0/research-environment-summary.md](docs/phase0/research-environment-summary.md)
  — UE-facing summary of v3 action ontology, 33-d observation schema, reward
  function (training-only), persona splits, and the ONNX I/O contract. Pins
  the four things UE must keep stable across research updates: I/O shapes,
  action ID ordering, need ordering, persona-slot ordering.
- [docs/phase0/affordance-taxonomy.md](docs/phase0/affordance-taxonomy.md)
  — Canonical 10-category roster with per-zone capacity targets and the
  empirical provenance (Phase 4 stress-run progressions) for those numbers.
  Documents the `Leisure`-folded-into-`Observe` quirk and the
  `Is Spatially Loaded = false` World Partition rule.
- [docs/phase0/bt-blackboard-policy-contract.md](docs/phase0/bt-blackboard-policy-contract.md)
  — Wire format between policy / blackboard / BT. Every blackboard key
  (type, writers, readers, lifecycle), the policy interface
  (`RunInference` + `RunInferenceWithLogits` + `pcsp.PolicyMode` CVar),
  the three-branch BT structure, and per-task contracts for
  `BTTask_PCSPDecision` / `MoveToAffordance` / `PerformInteraction`.
- [docs/phase0/scale-targets.md](docs/phase0/scale-targets.md)
  — Confirms Debug/Main/Stress targets with reference runs: 16 verified
  in 2026-05-17 baseline, 32 at 5.4% failure, 64 at 1.7% failure (Run 3),
  held-out 64 at 0.04% (`20260518_140432`). Also enumerates what 128+
  would need (async batched inference, more zones, WP streaming sources).

**Phase 5:**
- [docs/phase5/diagrams.md](docs/phase5/diagrams.md) — 5 Mermaid diagrams:
  system overview (research→UE→analysis), per-decision sequence diagram,
  BT subtree with failure branches, three-layer affordance system,
  ablation runtime switch. Render via mermaid-cli for paper inclusion.
- [docs/phase5/paper_extension.md](docs/phase5/paper_extension.md) — draft
  of the paper extension section ("Engine-Integrated Hybrid Persona
  Control"). 7 sub-sections plus figure/table inventory marking which
  artifacts still need PIE capture (X.5/X.6/X.7 — screenshots and video).

**Training-side ablation spec** added to `research/PLAN.md` Phase E. Lists
the two ONNX exports still needed for the full ablation table
(`Hybrid-NoConsist` and `RL-only`) with concrete recipes — `no_consist`
reuses `export_pcsp_onnx.py` as-is; `RL-only` (baseline B1) needs a
new wrapper because B1 has no persona-conditioning layer.

**Docs index** ([docs/index.md](docs/index.md)) updated with all six new
doc links.

## 2026-05-18 - Runtime Ablation Switch

- Added `EPCSPPolicyMode { HybridPCSP, BTOnly, HybridNoPersona }` to
  `PCSPTypes.h`. Selected at inference time via console variable
  `pcsp.PolicyMode` (0/1/2). Switch from PIE console between runs —
  no rebuild needed.
- `UPCSPPolicySubsystem::RunInference` branches on the mode:
  - `BTOnly` skips ONNX entirely and returns `NeedsHeuristic(Obs)`;
    logits are emitted as a zero vector so the JSONL schema stays
    uniform.
  - `HybridNoPersona` zeroes `PersonaBuffer` before the NNE bind.
    Same architecture and model, just an empty persona slot.
  - `HybridPCSP` is unchanged (default).
- `UPCSPTrajectoryLogComponent::BeginPlay` writes
  `"policy_mode":"<name>"` into each agent's `session_start` row so
  analysis tooling can label runs.
- `research/scripts/analyze_ue_session.py` surfaces `policy_mode` in
  the per-session summary; `compare_ablations.py` aggregates N
  sessions into one table (interactions, failure rate, reward,
  inter-persona dispersion, ρ + symmetric KL vs reference). BTOnly
  KL vs reference is reported as `null` because its logits are zero
  by construction.

## 2026-05-18 - Intra-Session Persona-Distance vs Action-KL

- Added `research/scripts/analyze_persona_distance_vs_kl.py`. Reads a
  session `summary.json` (per-persona `policy_probs` from logits, with
  fallback to the 20-bin action histogram) and the active
  `persona_embeddings.json`, then for every persona pair computes
  cosine distance over the 64-d embedding vs symmetric KL over the
  policy distribution and reports the Spearman ρ between the two
  pairwise vectors. Optional `--manifest` arg handles held-out slot
  remapping. Output written next to the session summary as
  `persona_distance_vs_kl.json` with `n_pairs`, `spearman_rho`,
  `pearson_r`, plus the full scatter table for follow-up plotting.
- Results across the four logit-bearing 64-agent sessions:
  - `noconsist_ablation_20260518` (Full PCSP, 2,016 pairs):
    ρ = 0.236, mean cos-dist 0.532, mean KL 1.78.
  - `noconsist_only_20260518` (NoConsist checkpoint, same map): ρ = 0.569.
  - `kl_20260518_151255` (Full PCSP): ρ = 0.257.
  - `btonly_detail` (BTOnly, sanity check): ρ = 0.007 with KL ≡ 0 —
    expected, since BTOnly emits zero logits and bypasses the persona
    vector entirely.
- Headline: in-engine ρ ≈ 0.24-0.26 for the consistency-trained
  checkpoint, well below the paper's research-side ρ ≈ 0.73 — the BT
  + capacity contention layer compresses the persona signal at
  execution time. Interestingly the NoConsist checkpoint scores
  *higher* (0.57) here, mirroring the v1/v3 "reward hides the
  failure" pattern: removing the consistency loss does not collapse
  the engine-level persona separability metric, even though
  research-side analysis flags it. Worth noting in the paper
  extension's limitations section.
