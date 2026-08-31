# Trajectory Observability Pipeline

**Status:** Live since Phase 3. This document is a portfolio-format
description of the existing system rather than a forward-looking plan.
**Owner:** AI / Tools Programmer

## Problem

A persona-conditioned policy is only as useful as the trajectories you can
read back out of it. Three audiences need different views of the same
rollout:

1. **The researcher** wants per-decision action distributions, paired with
   the persona embedding that drove each choice, so paper-grade metrics
   (Spearman ρ persona-distance vs behavioral KL, per-persona top-k
   retrieval) can be computed from a PIE session.
2. **The engine programmer** wants to know *why* a specific BT task
   failed — which zone, which interaction point, which sub-stage of
   MoveTo, with enough numeric detail to reproduce in editor.
3. **The designer / portfolio reader** wants a coarse, human-readable
   trace ("agent 7 had Social=0.91 urgency and went to SocialHub").

The pipeline below feeds all three from a single per-decision log row.

## Pipeline

```
┌─────────────────────────┐         ┌──────────────────────────────┐
│  UPCSPPolicySubsystem   │ logits  │  UPCSPTrajectoryLogComponent │
│  ::RunInferenceWith     │────────►│   ::RecordDecisionWithLogits │
│    Logits()             │ [20]    │                              │
└─────────────────────────┘         │  buffered queue,             │
                                    │  flush every 5 s or EndPlay  │
                                    └──────────────┬───────────────┘
                                                   │ JSONL
                                                   ▼
       Saved/PCSP/Logs/<YYYYMMDD_HHMMSS>/agent_p<id>_<actor>.jsonl
                                                   │
                                                   ▼
                       research/scripts/analyze_ue_session.py
                                  │
                  ┌───────────────┼───────────────┐
                  ▼               ▼               ▼
            summary.json     compare.json    per-persona action
              (totals,         (matched-       histograms / KL /
               coverage,        persona ρ,     latency
               dispersion)      symmetric KL)
```

## Wire format

One JSON object per line. Event types: `session_start`, `decision`,
`interaction_complete`, `interaction_failed`, `move_failed`.

```jsonc
// decision
{
  "t": 12.43,
  "event": "decision",
  "persona_id": 7,
  "pos": [413.2, -88.1],
  "action": "SocializeInitiate",
  "policy_action_index": 6,              // canonical v3 index before UE remap
  "category": "Social",
  "urgency": 0.91,
  "needs": { "hunger": 0.32, "sleep": 0.61, "social": 0.18, ... },
  "logits": [-1.2, 0.4, ..., 0.07],   // 20-dim, softmax for policy dist
  "policy_mode": "HybridPCSP",
  "active_ablation": "full"
}

// move_failed
{
  "t": 12.78,
  "event": "move_failed",
  "persona_id": 7,
  "action": "EatQuick",
  "intended_zone": "Kitchen_01",
  "failure_reason": "FindBestZone:AllOverCapacity",
  "distance_to_target": 821.4
}
```

The `logits` field is the load-bearing addition for paper metrics — it
lets the offline analyzer compute symmetric KL between policy
distributions across paired sessions without re-running inference.

Mass background entities use a sampled companion stream,
`mass_trajectories.jsonl`. By default the lowest 16 stable indices emit a row
per decision with `persona_id`, `policy_action_index`, executed `action`,
position, and eight needs. `pcsp.MassTrajectorySampleCount` changes the sample
budget; zero disables it. Rows are appended during the existing one-second Mass
telemetry flush rather than written individually.

The canonical action index lets
`research/scripts/evaluate_ue_behavior_tiers.py` apply the frozen independent
action-only probe to Actor and Mass tiers without consuming policy logits. The
first 300-second bridge validation is documented in
`research/docs/ue_simulation_tier_behavior.md`.

## Design choices worth noting

- **Buffered flush + EndPlay drain.** A naïve per-decision file write
  serializes the game thread on disk. The component buffers up to 5 s of
  events and flushes from an async task; on `EndPlay` it forces a
  synchronous drain so a Ctrl+C in PIE doesn't lose the last seconds.
- **Filename keyed on `persona_id`, not `AgentIndex`.** The 2026-05-17
  spawner fix (`SpawnActorDeferred → SetPersonaId → FinishSpawning`)
  exists specifically so the log filename matches the persona that drove
  the trajectory. Without it, all 16 agents' files were named
  `agent_p001_*` even though per-record `persona_id` was correct — a
  silent data corruption that took a day to find.
- **Failure reasons are enum-tagged strings.** `FindBestZone:AllOverCapacity`,
  `zone_no_free_interaction_point`, `interaction_point_reserve_race_lost`,
  `pathfinding_request_failed`, `path_follow_idle_short:dist=<cm>`. The
  `FPCSPZoneSelectionDebug` diagnostic struct returns these from
  `UPCSPAffordanceSubsystem::FindBestZone` so the BT task doesn't have to
  guess.
- **One log directory per PIE session.** Stamped `YYYYMMDD_HHMMSS`. The
  zero-shot eval (`research/scripts/run_zeroshot_eval.py prepare/finish`)
  auto-detects the most recent directory whose `mtime` is after
  `prepare`, so the user only has to remember to "run PIE" between the
  two commands.

## Analyzer output

`research/scripts/analyze_ue_session.py --session <dir>` produces
`summary.json`:

- `totals`: decisions, interactions, failures, reward sum.
- `category_coverage`: counts per affordance category.
- `failure_reason_totals`: enum → count.
- `latency`: per-agent decision interval mean / std.
- `persona_dispersion`: pairwise Spearman ρ across persona action
  histograms (lower = more persona-distinct).
- `per_persona[*]`: histograms, reward, decision count, action / category
  breakdown.

With `--compare <other_dir>`, also emits `compare.json`:

- `n_common_personas`.
- `per_persona_rho_*`: matched-persona Spearman ρ.
- `per_persona_kl_*`: symmetric KL between the two policies' per-persona
  action distributions, softmaxed from the logged logits.

This is the artifact the paper's UE5 section cites for both the
ablation table and the zero-shot replication.

## What this enables

- **Paper Tables (Mini-Inzoi → UE5 mirror):** the same per-persona
  histograms, KL divergences, and Spearman ρ that drive Tables III–V in
  `research/paper/cog2026_main/main.tex` are computable from the JSONL
  alone — no re-instrumentation.
- **Ablation paired runs:** the NoConsist ablation (2026-05-18) compares
  full-PCSP vs NoConsist ONNX over the same 64 personas via `--compare`,
  producing a single line of evidence for §VI without writing new code.
- **Debug-log map in `PLAN.md`:** every failure reason in
  `failure_reason_totals` maps to a documented `jq` recipe and a root
  cause (World Partition streaming, NavMesh acceptance radius, reservation
  race, etc.).

## Implemented 2026-05-23

- **Per-session `active_ablation` row.** The swap script
  (`research/scripts/swap_ue5_onnx.py`) writes
  `Content/PCSP/Models/active_ablation.txt`; the trajectory log component now
  reads this at `BeginPlay` and emits it on the `session_start` row so pairing
  across runs doesn't depend on filesystem inspection.
- **Intra-session persona-distance vs action-KL analyzer.**
  `research/scripts/analyze_persona_distance_vs_kl.py` ingests
  `summary.json` (per-persona `policy_probs` from logits, with fallback to
  the 20-bin action histogram) plus the active `persona_embeddings.json`
  and reports pair-wise Spearman ρ / Pearson r between persona cosine
  distance and symmetric policy KL. Output now carries
  `session_active_ablation` so the headline ρ ≈ 0.73 paper claim can be
  compared per ablation without filesystem inspection.
- **Coarse trace renderer.**
  `research/scripts/render_session_trace.py` reads the per-agent JSONL
  and emits chronological events (`DECIDE` / `INTERACT` / `MFAIL` /
  `IFAIL`) or a compressed `schedule` of completed interactions only.
  Supports `--persona` / `--from` / `--until` / `--group-by` for
  portfolio walkthroughs; pure stdlib, no UE runtime.

## Cross-references

- `Source/cnzoi/PCSP/Public/Components/PCSPTrajectoryLogComponent.h` — public API.
- `Source/cnzoi/PCSP/Private/Components/PCSPTrajectoryLogComponent.cpp` — buffered flush, EndPlay drain.
- `Source/cnzoi/PCSP/Public/PCSPTypes.h` — `FPCSPZoneSelectionDebug`, failure-reason enums.
- `research/scripts/analyze_ue_session.py` — offline aggregator.
- `research/scripts/analyze_persona_distance_vs_kl.py` — paper-claim
  ρ ≈ 0.73 mirror inside UE; outputs `session_active_ablation` for
  matched comparisons across ablation pairs.
- `research/scripts/render_session_trace.py` — chronological /
  schedule-style trace renderer for portfolio walkthroughs.
- `PLAN.md` §"Debug Log Map" — `jq` recipes for the failure-reason taxonomy.
