# MELTINGPOT_PLAN.md

**Implementation Checklist: PCSP × Melting Pot 2.0**

**Status:** Planning artifact. Treat each unchecked box as work to be scheduled, scoped, or rejected — not as a commitment.
**Training stack:** In-house CleanRL-style PPO (PyTorch, single-file, PettingZoo Parallel boundary). No Ray, no RLLib — see Phase 1 §"In-house PPO trainer" and Anti-Goals. The upstream RLLib reference (`examples/rllib/self_play_train.py`) is **rejected** for the reasons documented in `BUDGET.md` §5.
**Operating rule:** Update this checklist after non-trivial work; record decisions and results in `research/DONE.md` under a `MeltingPot` heading.
**Cross-references:** `MELTINGPOT_PROPOSAL.md` (motivation, hypotheses), `MELTINGPOT_FEAT.md` (architecture), `MELTINGPOT_RESEARCH_QUESTIONS.md` (paper-level claims).
**Branch convention:** All work for this program lands on `research/meltingpot-*` branches with PRs into `main`.

---

## Phase 0 — Scoping and Decision Gate

### Goals

Confirm engineering feasibility, compute budget, and substrate selection before committing the research program. Phase 0 may end in a deliberate decision to *defer* Melting Pot.

### Dependencies

- v3-large planning at least at draft stage.
- Internal compute capacity statement.

### Tasks

- [x] Inventory available compute: GPU count, GPU class, memory, wall-clock budget for the program. *(2026-05-14)*
- [x] Pin Melting Pot version (target: 2.x latest stable) and DM-Env / DMLab2D versions; record in `research/meltingpot/REQUIREMENTS.lock`. *(2026-05-14: dm-meltingpot 2.4.0, dmlab2d 1.0.0, dm-env 1.6, Python 3.11.15.)*
- [x] Install Melting Pot on the target training node and verify substrate instantiation. *(2026-05-14: 49 substrates load; `commons_harvest__simple` does not exist in 2.x — substituted `commons_harvest__open`. Single-process random-action throughput 1,574 env-steps/s.)*
- [ ] **REPLACED:** Reference RLLib PPO shakedown is rejected — `ray==2.5.0` is incompatible with `numpy>=1.24` (which `dm-meltingpot==2.4.0` requires). See `BUDGET.md` §5. New gate: in-house CleanRL-style PPO (Phase 1) completes a 1M-step shakedown on `commons_harvest__open`.
- [x] Time env throughput; extrapolate to per-substrate full-run cost and program-total compute cost; document in `research/meltingpot/BUDGET.md`. *(2026-05-14: 750–1,050 GPU-hours for Phase 3–5.)*
- [x] Read each candidate substrate's source, action set, observation spec, and intended evaluation populations. *(2026-05-14: 49 substrates enumerated with player counts, roles, held-out scenario counts.)*
- [x] Classify substrates by social-dilemma category (collective action, coordination, territorial, exploitation, mixed-motive). *(2026-05-14: see `SUBSTRATES.md` §2 — 7 categories.)*
- [x] Select 4–6 substrates for the program covering ≥3 categories. *(2026-05-14: 5 substrates across 4 categories — `commons_harvest__open`, `clean_up`, `prisoners_dilemma_in_the_matrix__arena`, `stag_hunt_in_the_matrix__repeated`, `territory__rooms`.)*
- [x] Decision review: proceed to Phase 1, or defer. *(2026-05-14: **PROCEED with amendments** — substitute `commons_harvest__open` for `__simple` everywhere; replace RLLib with in-house CleanRL-style PPO; see `research/DONE.md`.)*

### Outputs

- `research/meltingpot/REQUIREMENTS.lock`
- `research/meltingpot/BUDGET.md`
- `research/meltingpot/SUBSTRATES.md` (substrate selection rationale)
- Decision record in `research/DONE.md`

### Validation criteria

- Reference PPO shakedown completes without code modifications.
- Wall-clock extrapolation produces a number that fits inside committed compute.
- Substrate selection has documented rationale per category coverage.

---

## Phase 1 — Environment Wrappers and Data Plumbing

### Goals

Provide a clean `gym.Env`-shaped, vectorizable, persona-aware wrapper around Melting Pot substrates with no leakage from training into evaluation.

### Dependencies

- Phase 0 complete.

### Tasks

#### Wrapper layer

- [ ] Create `src/env/meltingpot/` module with `__init__.py`, `wrappers.py`, `substrate_factory.py`.
- [ ] Implement `make_substrate(name, *, roles, num_players, persona_assignment, seed)` factory mirroring `env_factory` interfaces threaded through v3 trainers.
- [ ] Wrap Melting Pot's `dm_env.Environment` into a vectorized API consumable by the existing PPO trainer (PettingZoo Parallel API recommended as the boundary).
- [ ] Add deterministic seeding path: substrate seed, role assignment, persona assignment, and policy seed must all be independently controllable from a single `RunSpec`.
- [ ] Add per-agent persona injection: every agent slot receives a `persona_id` and a precomputed `persona_embedding` at episode start; the wrapper appends the embedding to the observation tuple delivered to the policy.

#### Observation extraction

- [ ] Confirm observation modalities per substrate; for RGB-egocentric substrates standardize on `(H, W, 3) uint8` plus auxiliary scalars.
- [ ] Add a `WORLD.RGB` debug observation path for visualization (training disables it; evaluation enables it).
- [ ] Add an action-mask path where substrates expose available-action sets.
- [ ] Add a `social_state` extractor: per-step structured features (visible co-players, recent co-player actions, possessed resources) for use by metrics, *never* by the policy.

#### Action-space adaptation

- [ ] Confirm action spaces are flat `Discrete` per substrate; record per-substrate action ontology in `research/meltingpot/ACTIONS.md`.
- [ ] Implement an action-space mapping layer so the policy's action head can be substrate-agnostic during training (max action dim padded with masking).
- [ ] Add per-substrate semantic action labels (e.g., `MOVE_NORTH`, `ZAP`, `CONSUME`) for downstream interpretation.

#### Trajectory logging

- [ ] Define a binary trajectory format (`.npz` per episode or `.zarr` per run) capturing: per-step observations (downsampled RGB if size-prohibitive), actions, rewards, persona ID, persona embedding, co-player IDs, terminal flags, info dict (substrate-defined).
- [ ] Add async writer to keep training throughput unaffected.
- [ ] Add a `trajectory_loader` that supports random-access by `(persona_id, episode_id)` for the identification classifier and metrics.

#### Replay and visualization

- [ ] Add a `scripts/replay_meltingpot.py` that loads a trajectory and renders RGB frames into mp4.
- [ ] Add a `scripts/inspect_meltingpot_run.py` that loads a run's trajectories and emits a per-persona summary: return distribution, action histogram, social-event counts.

#### In-house PPO trainer (CleanRL-style)

Phase 0 ruled out the upstream RLLib reference trainer (`ray==2.5.0` × `numpy>=1.24` conflict; see `BUDGET.md` §5). Phase 1 owns the replacement.

- [ ] Create `src/training/cleanrl_ppo/` with a single-file PPO implementation modeled on CleanRL's `ppo_atari_envpool.py`: clipped objective, GAE, value clipping, entropy bonus, orthogonal init, learning-rate annealing.
- [ ] Boundary: PettingZoo Parallel API. The trainer must not import Ray, RLLib, or Tianshou; it consumes the Phase 1 wrapper directly.
- [ ] Vectorization: `gymnasium.vector.AsyncVectorEnv` (subprocess) over substrate replicas; per-agent observations stacked into a single `(num_envs × num_players, *obs)` batch for the policy forward pass.
- [ ] Architecture: IMPALA-CNN torso (3 blocks, channel widths [16, 32, 32]) → `(features + persona_embedding)` concat or FiLM → LSTM (cell size 256) → policy head (Categorical) + value head. Match the action-space-mask path from the wrapper layer.
- [ ] Multi-agent policy sharing: one shared policy parameterized by persona embedding (PCSP). For ablation `B3: independent-per-persona-PPO`, the same trainer instantiates a dict of per-persona policy heads keyed by `persona_id`.
- [ ] Mixed-precision toggle (bf16 forward, fp32 grads) for the RTX 6000 Ada path.
- [ ] Resumable training: checkpoint every `N` updates with full optimizer + LSTM state + RNG state.
- [ ] Logging: scalar metrics to `runs/.../logs.jsonl` (substrate-defined return, ep length, policy entropy, KL approx, value loss, frames/s); also mirror to W&B or TensorBoard (Phase 6 picks one).
- [ ] Smoke target (closes the Phase 0 reference-shakedown gate): 1M env-steps on `commons_harvest__open`, single GPU, no LoRA/persona conditioning, batch size 256, num_envs 8, must reach a non-trivial mean episode return (> random baseline) and complete without crashes.

### Trainer outputs

- `src/training/cleanrl_ppo/{trainer.py,ppo.py,model.py,buffer.py,config.py}`
- `scripts/run_cleanrl_ppo_smoke.py` (Phase 0 closeout shakedown)

### Outputs

- `src/env/meltingpot/`
- `research/meltingpot/ACTIONS.md`
- `scripts/replay_meltingpot.py`, `scripts/inspect_meltingpot_run.py`
- Smoke test: `scripts/test_env_meltingpot.py` (per-substrate sanity)

### Validation criteria

- All selected substrates instantiate, reset, step, and close cleanly.
- Persona embeddings reach the policy through the wrapper boundary and are recoverable from logged trajectories.
- Smoke test passes with deterministic outputs across two repeated seeds.

---

## Phase 2 — Persona Pipeline Adaptation

### Goals

Reuse the v3 persona infrastructure (frozen Qwen3-0.6B-Embed encoder + LoRA projection) on Melting Pot, with care for cross-environment encoder consistency.

### Dependencies

- Phase 1 wrappers complete.

### Tasks

- [ ] Decide whether Melting Pot uses the same persona corpus as v3 (`personas_300_v3.json`) or a Melting Pot-specific corpus. Default: shared corpus to maximize cross-environment comparability.
- [ ] If shared corpus: precompute embeddings under the existing frozen encoder and store in `research/meltingpot/embeddings/`.
- [ ] Add a persona-corpus extension protocol: append-only, embedding hash recorded.
- [ ] Build train/test persona splits matched against v3 splits to enable cross-environment comparisons.
- [ ] Document the encoder version, projection initialization, and any LoRA training schedule choices in `research/meltingpot/PERSONA_PIPELINE.md`.

### Outputs

- `research/meltingpot/embeddings/`
- `research/meltingpot/PERSONA_PIPELINE.md`

### Validation criteria

- Embedding hash matches the v3 hash on shared persona IDs.
- Splits are bit-identical to v3 splits where overlap exists.

---

## Phase 3 — Single-Substrate PCSP Training

### Goals

Reproduce the v3 PCSP architecture on one substrate (`commons_harvest__open` recommended), establish baselines, and re-confirm the InfoNCE consistency claim is load-bearing in a Melting Pot setting.

### Dependencies

- Phases 1–2.

### Tasks

- [ ] Port the v3 PCSP policy module to consume RGB observations: replace the symbolic state encoder with the IMPALA-CNN torso defined in the Phase 1 CleanRL trainer (`src/training/cleanrl_ppo/model.py`); keep FiLM/concat conditioning blocks unchanged.
- [ ] Implement a Melting Pot-compatible training script `scripts/run_pcsp_meltingpot.py` that drives the CleanRL trainer (`src/training/cleanrl_ppo`) — no RLLib, no Ray. Mirror the CLI surface of `scripts/run_pcsp_v3.py`.
- [ ] Reuse the Phase 1 `AsyncVectorEnv` rollout path; do not re-implement vectorization here. Confirm population composition (mixed personas across env replicas) is plumbed through the Phase 1 persona-injection hook.
- [ ] Re-implement the InfoNCE consistency loss against trajectory embeddings drawn from this substrate; recompute negative-sample pools per episode.
- [ ] Add the diversity regularizer with substrate-appropriate scaling.
- [ ] Run baselines: `PCSP-full`, `PCSP-no-consist`, `PCSP-no-diverse`, `PCSP-concat`, `B1: persona-only-prompt-no-RL`, `B3: independent-per-persona-PPO`.
- [ ] Run minimum 5 seeds per cell.
- [ ] Record return, identification accuracy, action distribution divergence.

### Outputs

- `scripts/run_pcsp_meltingpot.py`
- Run logs and trajectory dumps under `research/meltingpot/runs/phase3/`
- Phase-3 summary in `research/DONE.md`

### Validation criteria

- `PCSP-full` reaches a return within a documented margin of an unconditioned PPO baseline.
- Identification accuracy on `PCSP-full` exceeds chance and exceeds `PCSP-no-consist`.
- Seeds produce overlapping but distinct trajectories (no replay-style determinism bug).

---

## Phase 4 — Multi-Substrate Generalization

### Goals

Extend the working pipeline across all selected substrates with held-out persona and held-out co-player evaluation.

### Dependencies

- Phase 3 complete.

### Tasks

- [ ] Run `PCSP-full` and key ablations on all selected substrates.
- [ ] Build a trajectory-level identification classifier as a *fixed, frozen* evaluation tool per substrate: trained on training-population trajectories, evaluated on held-out trajectories.
- [ ] Run Melting Pot's standard held-out co-player evaluation protocol per substrate.
- [ ] Define held-out persona splits orthogonal to co-player splits; report all four cells (train-pop × train-persona, train-pop × test-persona, test-pop × train-persona, test-pop × test-persona).
- [ ] Compute per-substrate identification-vs-reward Pareto curves by sweeping the InfoNCE coefficient.
- [ ] Aggregate but do not collapse across substrates: report per-substrate primary metrics with CIs; report a substrate-wise summary table.

### Outputs

- `research/meltingpot/runs/phase4/`
- Identification classifiers under `research/meltingpot/classifiers/`
- Per-substrate result tables in `research/meltingpot/results/`

### Validation criteria

- All substrates have at least 5 seeds completed for `PCSP-full`.
- Classifier accuracy reported with bootstrap CI on held-out splits.
- Pareto curves are non-degenerate on ≥2 substrates.

---

## Phase 5 — Convention and Controllability Studies

### Goals

Execute H2, H3, H4 from `MELTINGPOT_PROPOSAL.md`.

### Dependencies

- Phase 4 complete.

### Tasks

#### Convention emergence (H2)

- [ ] Build a `Population` factory that composes populations from persona statistics (mean cooperativeness, dispersion, dominant archetype) using a persona-trait labeling drawn from `data/personas/personas_300_v3.json` metadata.
- [ ] Define convention metrics per substrate: turn-taking index, Gini of returns, defection rate, public-good provision rate, retaliation latency.
- [ ] Run a factorial population sweep: persona mean × persona dispersion × substrate × seed.
- [ ] Regress social-outcome metrics on persona-population statistics with mixed-effects models accounting for substrate and seed.
- [ ] Report variance explained, with CIs and multiple-testing correction.

#### Trajectory traceability under novel co-players (H3)

- [ ] Use Melting Pot's held-out evaluation populations.
- [ ] Compute identification accuracy when the trajectory's agent is embedded in a novel co-player population.
- [ ] Compare against in-distribution identification.
- [ ] Report gap, with CI.

#### Controllability (H4)

- [ ] Pre-register a set of persona edits with predicted directions of effect (e.g., add "shares resources with strangers" → expect cooperation rate ↑ in `commons_harvest`).
- [ ] Run matched-seed comparisons: same base persona, edited vs. unedited, identical seeds for environment and other agents.
- [ ] Report signed effect sizes with CIs; reject H4 if the sign distribution does not exceed chance after multiple-testing correction.

### Outputs

- `research/meltingpot/runs/phase5/`
- Pre-registration document `research/meltingpot/PREREG.md` (committed *before* edit experiments run)
- Result tables in `research/meltingpot/results/`

### Validation criteria

- Pre-registration committed to git prior to result generation; commit hash referenced in final paper.
- All effect sizes reported with seed-aware CIs.
- Statistical tests use appropriately conservative corrections (Bonferroni or Benjamini–Hochberg, documented choice).

---

## Phase 6 — Systems and Reproducibility Hardening

### Goals

Make the program reproducible by external readers and robust to operational failures.

### Dependencies

- Phases 3–5 ongoing.

### Tasks

#### Scalable rollout pipeline

- [ ] Stay on `gymnasium.vector.AsyncVectorEnv` until measured throughput becomes the bottleneck. Do not adopt Ray, RLLib, or any heavyweight orchestrator preemptively — Phase 0 documented why.
- [ ] If scaling becomes necessary, prefer (a) `torch.multiprocessing` actor pool over the existing CleanRL trainer, or (b) `EnvPool` if a Melting Pot adapter exists, before reaching for Ray. Benchmark the marginal SPS gain against engineering cost.
- [ ] Add rollout-worker checkpointing so multi-day runs survive node failure.
- [ ] Add GPU/CPU resource caps per worker and document them in `research/meltingpot/COMPUTE.md`.

#### Distributed PPO

- [ ] Implement distributed PPO with parameter-server or all-reduce backend (start with single-node multi-GPU, scale if needed).
- [ ] Verify learning curves match single-GPU within seed-level noise.

#### Experiment management

- [ ] Use a single experiment registry: each run has a `RunSpec` (substrate, population spec, persona split, seed, code commit, config hash) recorded under `research/meltingpot/registry/<run_id>.json`.
- [ ] Forbid uncommitted code at run launch.
- [ ] Add a `scripts/audit_runs.py` that verifies registry consistency and flags missing artifacts.

#### Seed reproducibility

- [ ] Centralize seeding through a single `seed_everything(spec)` call: numpy, torch, env, persona-shuffle, population-composition.
- [ ] Verify bit-level reproducibility of at least one run on a single GPU.
- [ ] Document irreducible nondeterminism sources (CuDNN, NCCL) and treat seeds as *statistical* reproducibility not bit reproducibility for multi-GPU runs.

#### Logging

- [ ] Standardize on a single logging stack (Weights & Biases or TensorBoard; pick one).
- [ ] Log scalars, histograms, sample trajectories, identification-classifier accuracy, Pareto-curve scatter, persona-edit effect sizes.
- [ ] Mirror logs to local `runs/.../logs.jsonl` so the program is not dependent on a third-party service.

### Outputs

- `research/meltingpot/registry/`
- `research/meltingpot/COMPUTE.md`
- `scripts/audit_runs.py`

### Validation criteria

- A new contributor can reproduce a Phase 3 run from a clean clone, using only `research/meltingpot/REQUIREMENTS.lock` and the registry entry.
- Audit script reports zero inconsistencies on the current registry.

---

## Phase 7 — Paper-Oriented Work

### Goals

Convert experiments into a defensible main-track paper.

### Dependencies

- Phases 4–5 substantively complete.

### Tasks

#### Figures

- [ ] Pipeline diagram (PCSP applied to Melting Pot): persona encoder → shared policy → substrate; mark the InfoNCE consistency block and the diversity regularizer.
- [ ] Per-substrate identification-vs-reward Pareto curves (Figure: 1 panel per substrate).
- [ ] Persona-population statistics → social-outcome scatter (Figure for H2).
- [ ] Pre/post persona-edit effect-size forest plot (Figure for H4).
- [ ] Trajectory t-SNE per substrate, colored by persona archetype.
- [ ] Qualitative case studies: 2–3 trajectories per substrate with action overlays.

#### Ablation study checklist

- [ ] InfoNCE on/off.
- [ ] Diversity regularizer on/off.
- [ ] FiLM vs concat conditioning.
- [ ] Frozen vs joint-trained persona projection.
- [ ] Persona embedding dimension sweep (small, default, large).
- [ ] Population composition: matched-persona vs mixed-persona training populations.
- [ ] Held-out persona vs held-out co-player axes (factorial).

#### Benchmark tables

- [ ] Per-substrate primary metrics: return, identification accuracy, convention metric, with bootstrap CIs.
- [ ] Substrate-wise summary table aggregating method rankings (Borda or similar; document choice).
- [ ] Comparison against published Melting Pot baselines where available, on the same substrates.

#### Statistical testing

- [ ] Bootstrap CIs (10,000 resamples) for all reported scalar metrics.
- [ ] Permutation tests for paired ablation comparisons.
- [ ] Multiple-testing correction across substrates and across hypotheses.
- [ ] Effect-size reporting (Cohen's d or analogous) alongside p-values.
- [ ] Pre-registration referenced for H4 edit experiments.

#### Writing

- [ ] Draft against `paper/meltingpot_main/main.tex` (new directory; do not co-mingle with `paper/cog2026_main/`).
- [ ] Method section grounded in `MELTINGPOT_FEAT.md`.
- [ ] Limitations section grounded in `MELTINGPOT_PROPOSAL.md` §5.
- [ ] Reproducibility section grounded in Phase 6 outputs.

### Outputs

- `paper/meltingpot_main/`
- Figure source files under `paper/meltingpot_main/figs/`
- Result tables under `paper/meltingpot_main/tables/`

### Validation criteria

- Every paper claim is traceable to a registry run.
- Every figure is regeneratable from logged artifacts via a documented script.
- Limitations section names at least one failure mode per substrate.

---

## Phase 8 — Open Release

### Goals

Public artifact release suitable for external reviewers and follow-up work.

### Dependencies

- Phase 7 complete; paper accepted or pre-submission.

### Tasks

- [ ] Public repository tag.
- [ ] Substrate configs and persona splits committed.
- [ ] Seed lists and `RunSpec` registry exported.
- [ ] Trajectory dumps for at least one substrate (subject to size limits; if prohibitive, release a sampling protocol).
- [ ] Reproducibility checklist completed per the venue's standard.
- [ ] License: MIT for code, CC-BY-4.0 for trajectory dumps (or whatever the substrate license requires).

### Outputs

- Tagged release on GitHub.
- Optional Zenodo DOI for archival.

### Validation criteria

- Clean-clone reproducibility on a single Phase 3 run verified by a non-author reviewer (internal).

---

## Cross-Cutting Tasks

These do not belong to a single phase but must be tracked.

### Documentation

- [ ] `research/meltingpot/README.md` index.
- [ ] Per-script docstrings.
- [ ] Decision log appended to `research/DONE.md` for each non-trivial methodological choice.

### Risk management

- [ ] Quarterly review: are H1–H5 still on track? If not, document the pivot.
- [ ] Compute burn-down tracked against `research/meltingpot/BUDGET.md`.
- [ ] Substrate quarantine: any substrate where identification collapses to chance under all conditions is moved to the "diagnostic-only" set and excluded from the headline claims (still reported).

### Coordination with v3-large and UE5 tracks

- [ ] No persona corpus changes without notifying both tracks.
- [ ] No encoder-projection changes that break v3 reproducibility unless versioned.
- [ ] Quarterly cross-track sync to keep observation schemas and action ontologies aligned where possible.

---

## Anti-Goals (Explicit De-scoping)

The following are *not* tasks in this plan and must be rejected if proposed:

- LLM-in-the-loop policy inference.
- Joint training of the persona encoder during PPO.
- Ray / RLLib / Tianshou or any other heavyweight RL framework as the training backbone. The training stack is the in-house CleanRL-style PPO defined in Phase 1. Phase 0 documented the cost of taking on Ray's dep graph; the program does not pay it.
- Communication-channel learning between agents.
- General-purpose MARL exploration improvements.
- Curriculum learning across substrates (each substrate is trained independently).
- Cross-substrate transfer experiments as a main claim (allowed as a side-bar finding only).
- Adversarial-policy / red-team studies (separate research program).
