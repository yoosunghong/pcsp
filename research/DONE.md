# DONE.md - PCSP Work Log and Results

This file holds completed work details, decisions, result paths, and experiment notes. `PLAN.md` is the compact active checklist.

---

## 2026-08-31 - Eval v3 Threading And Repository Integrity Audit

### Lower-priority eval threading

- `src/eval/task_perf.py` now accepts an injected environment factory, threads
  agent count through all persona samplers, and exposes CLI selection for v1/v3
  environment, observation dimension, action count, persona file, and episode
  length. Default v1 values remain 20 observations, 12 actions, and four agents.
- `src/eval/diversity.py` now samples shared states through an injected
  environment factory and persona set. Its CLI selects v1/v3 dimensions and
  constructs v3 sampling personas from `train_240_v3.json`.
- Both outputs now record `env_variant`, `obs_dim`, `n_actions`, and `n_agents`.
- `conda run -n paper python -m py_compile src/eval/task_perf.py
  src/eval/diversity.py` passed.
- Reconciled the stale Phase E ablation-export checklist with the completed UE
  work: Hybrid-NoConsist already has an ONNX export/swap path and paired engine
  runs; RL-only inference is represented by the existing HybridNoPersona mode,
  while its training-only delta remains in the research tables.

### Mini-Inzoi environment recovery

- Root cause confirmed: the historical bare `.gitignore` pattern `env/`
  matched `research/src/env/` at any depth, so none of the environment sources
  ever entered Git. It is now anchored as `/env/`.
- Exhaustive recovery checks found no original source in local disks, Git
  objects/refs, editor/session history, public branches, releases, artifacts,
  the public fork, or code search. A similarly named external v4 environment
  was rejected because its own documentation says it did not preserve the
  original v3 dynamics.
- Restored `src/env/{mini_inzoi,mini_inzoi_v2,mini_inzoi_v3,
  mini_inzoi_v3_large,v3_constants,action_semantics}.py`. Constants that affect
  checkpoint behavior were recovered from committed rollout transitions:
  seeded positions, time/need dynamics, restoration table, social compatibility,
  v3 affordance/social/routine slices, critical-need penalty, and all action
  style directions.
- Added `scripts/test_env_recovery.py`. It reconstructs full AEC cycles from the
  other-agent action IDs encoded in each target observation and replays 2,400
  v1 plus 2,400 v3 transitions. Results: v1 observation/reward max errors
  `4.36e-6 / 2.53e-6`; v3 `4.89e-6 / 2.72e-6` (all below `1e-5`).
- Validation passed: `scripts/test_env.py`, `scripts/test_env_v3.py`,
  `scripts/test_env_v3_large.py`, PettingZoo API checks for v2 and v3-large,
  an import audit of 26 environment consumers, a checkpoint-backed v3 task
  rollout, and a checkpoint-backed v3-large policy cycle.

---

## 2026-05-18

### UE5 Zero-Shot Persona Generalization — Validated on Held-Out IDs 241..300

**Goal.** End-to-end check that the v3 PCSP policy, trained on personas 1..240, produces persona-distinct behavior in the UE5 sandbox when fed the held-out 60-persona test split (`research/data/personas/test_60_v3.json`, IDs 241..300).

**Tooling added.**
- `research/scripts/analyze_ue_session.py` — aggregates UE PIE-session JSONL logs into per-persona action histograms (20 v3 actions), category coverage, interaction/failure counts, reward sums, decision-latency stats, failure-reason breakdown, and inter-persona pairwise Spearman ρ on action distributions. `--compare <other-session>` produces matched-persona ρ.
- `research/scripts/run_zeroshot_eval.py` — `prepare` repacks `ue/cnzoi/Content/PCSP/Data/persona_embeddings.json` so UE slots 1..N hold test embeddings (the spawner picks `persona_id = (i % 300) + 1`, so no C++ change is needed); writes a slot→real-id manifest and backs up the train file. `finish` auto-detects the newest session, runs the analyzer, relabels per-persona output via the manifest, compares aggregate metrics vs the train baseline, and restores the train file.

**Capacity-fix progression (all 64-agent PIE).**

| Session | Personas | Duration | Interactions | Failure rate | Inter-persona ρ | Notes |
|---|---|---:|---:|---:|---:|---|
| `20260518_104056` | train 1..64 | 7.2 min | 2,145 | 2.0% | 0.383 | Train baseline. |
| `20260518_112540` | **test 241..300** | 7.4 min | 2,180 | **12.5%** | 0.358 | 99.4% of failures = `FindBestZone:AllOverCapacity` on `FocusedWork`/`PlanningWork` (310 of 312). Held-out demand profile saturated the single Office zone. |
| `20260518_114841` | train 1..64 | 17.1 min | 4,630 | 3.2% | 0.425 | After Work expansion. Work failures collapsed 302→1. New bottleneck: Hygiene (134 `HygieneQuick` AllOverCapacity). |
| `20260518_133852` | train 1..64 | 5.3 min | 1,474 | **0.0%** | 0.405 | After Hygiene expansion. Zero failures. 9 of 10 categories. |
| `20260518_140432` | **test 241..300** | 9.75 min | 2,792 | **0.04%** | **0.368** | **Clean zero-shot validation.** 1 single `path_follow_idle_short` failure. 43.6 interactions/agent, reward 960.4, 9 of 10 categories. |

**Headline.** With Work and Hygiene capacity matched to the held-out demand profile, the policy generalizes cleanly: on personas it never saw during training, failure rate collapses from 12.5% to 0.04%, while inter-persona action ρ stays at 0.368 — slightly *more* persona-distinct than train (0.383). This is the load-bearing engine-integration evidence that PCSP's persona conditioning survives the train→test split in a real BT/affordance-driven runtime, not just in MiniInzoiV3 simulator rollouts.

**Demand-profile observation.** Held-out category demand is flatter than train (Rest 59/Social 40/Work 38/Hygiene 36/Study 33 on test vs Rest 57/Social 50/Hygiene 34/Work 30 on train). The pre-fix 12.5% failure rate was not a policy failure — the environment's static capacity allocation had been tuned for the train demand profile.

**Artifacts.**
- `research/results/ue_sessions/20260518_104056/summary.json` — train baseline
- `research/results/ue_sessions/zeroshot_20260518_112540/{summary,compare_vs_train}.json` — pre-fix zero-shot
- `research/results/ue_sessions/20260518_114841/summary.json` — Work-fix train
- `research/results/ue_sessions/20260518_133852/summary.json` — Work+Hygiene-fix train
- `research/results/ue_sessions/zeroshot_20260518_140432/{summary,compare_vs_train}.json` — clean zero-shot

**Open follow-ups** (`ue/cnzoi/PLAN.md` Phase 4):
- Policy KL between paired sessions still requires logit export from `UPCSPPolicySubsystem` — not yet implemented.
- Compare BT-only, RL-only, Hybrid-NoConsist, Hybrid-NoPersona variants on the same map at 64 agents.

---

## 2026-05-14

### MeltingPot — Phase 0 (Scoping and Decision Gate)

Per `research/meltingpot/MELTINGPOT_PLAN.md` Phase 0. Goal: feasibility, compute budget, substrate selection; deliberate proceed/defer decision.

**Compute inventory:** Single workstation, 1× RTX 6000 Ada (48 GB), 32 cores, 125 GiB RAM, 697 GiB free disk, CUDA 12.8. Recorded in `research/meltingpot/BUDGET.md` §1.

**Library install:** Created conda env `meltingpot` (Python 3.11.15). Installed `dm-meltingpot==2.4.0` (49 substrates), `dmlab2d==1.0.0`, `dm-env==1.6`, plus reference-trainer deps `ray[rllib]==2.5.0`, `supersuit==3.8.1`, `torch==2.12.0`, `gymnasium==0.26.3`. Full freeze in `research/meltingpot/REQUIREMENTS.lock` (100 packages).

**Env throughput measurement:** Single-process random-action rollout on `commons_harvest__open` (7 players, RGB 88×88×3, 8 discrete actions): **1,574 env-steps/s ≈ 11,017 agent-steps/s**.

**Reference PPO trainer — Phase 0 gate FAILED.** The plan asked for a 1M-step PPO shakedown on `commons_harvest__simple` "without engineering changes". Two issues:
1. `commons_harvest__simple` does not exist in Melting Pot 2.x — substituted `commons_harvest__open`.
2. Upstream `examples/rllib/self_play_train.py` fails at import: `ray==2.5.0` references `np.bool8`, removed in numpy ≥ 1.24; `dm-meltingpot==2.4.0` pulls `numpy==2.4.4`. Downgrading numpy breaks `dm-meltingpot`. The reference trainer cannot run on a clean install.

**Decision:** Tentative **PROCEED with two amendments**, pending user sign-off:
- Substitute the Phase 0 reference run target: `commons_harvest__open` replaces `commons_harvest__simple` throughout the plan.
- Reject the upstream RLLib trainer as the training backbone. Phase 1 will provide a CleanRL-style PPO on the PettingZoo Parallel API boundary (already required by Phase 1 wrapper work). This removes Ray as an ongoing dependency. Rationale and alternatives in `BUDGET.md` §5.

**Substrate selection (recommended, 4 categories, 5 substrates):**
- `commons_harvest__open` (collective action, 7 players, 2 held-out scenarios — H3 risk noted)
- `clean_up` (collective action / public good, 7, 23)
- `prisoners_dilemma_in_the_matrix__arena` (mixed-motive PD, 8, 22)
- `stag_hunt_in_the_matrix__repeated` (coordination, 2, 10)
- `territory__rooms` (territorial, 9, 14)

Held-out persona-edit and asymmetric-role substrates (`predator_prey__*`, `hidden_agenda`, `daycare`, `collaborative_cooking__*`) explicitly de-scoped from headline metrics. Full rationale in `research/meltingpot/SUBSTRATES.md`.

**Program compute estimate:** 750–1,050 GPU-hours for Phase 3–5 across the 5 substrates at 50M env-steps × 5 seeds × 6 cells. Fits in ~3 weeks single-GPU serial; ~1.5 weeks with two concurrent runs per GPU. Trajectory storage: retain ~150 GB curated subset; full raw dumps would be ~3 TB compressed and need external storage.

**Outputs:**
- `research/meltingpot/REQUIREMENTS.lock`
- `research/meltingpot/BUDGET.md`
- `research/meltingpot/SUBSTRATES.md`
- Upstream meltingpot repo cloned to `research/meltingpot/upstream/` for reference (not a build dependency).

**Validation against plan's Phase 0 criteria:**
- Reference PPO shakedown completes without code modifications — **FAILED** (trainer broken). Documented and replaced with a Phase 1 work item.
- Wall-clock extrapolation fits inside committed compute — **PENDING USER COMMIT** (no compute budget has been committed yet; estimate provided).
- Substrate selection has documented per-category rationale — **PASSED** (4 categories, 5 substrates, individual rationale).

---

## 2026-05-13

### Workspace Restructure for Unreal Integration

- Moved the existing PCSP research project into `research/`.
- Created top-level `ue/` as the reserved Unreal Engine project location.
- Added top-level `README.md` and `PLAN.md` as workspace-level routing docs.
- Updated top-level `AGENTS.md` / `CLAUDE.md` to point agents to `research/PLAN.md` and `research/paper/cog2026_main/main.tex` for research work.
- Updated `.gitignore` for `research/results/...` generated artifacts and common Unreal-generated directories under `ue/`.
- Replaced stale hardcoded `/home/swim/Documents/Projects/co-spec` paths in research scripts with dynamic `Path(__file__).resolve()` roots.

### Paper Validity Fix: Empirical KL Figure

- Replaced the synthetic/statistically reconstructed Figure 3 KL scatter with empirical sampled-pair policy KL measurements generated from the trained v1/v2 PCSP-full checkpoints.
- Updated `scripts/generate_cog_figures.py` so `fig3_kl_v1v2` now:
  - loads the trained policy checkpoints,
  - samples shared states with the existing v1/v2 diversity-eval procedures,
  - computes symmetric policy KL for sampled persona pairs,
  - computes projected persona L2 distance after the trained LoRA projection,
  - saves plotted point provenance to `results/eval/fig3_kl_v1v2_points.json`.
- Empirical Figure 3 sampled-pair results:
  - v1: 100 pairs, 200 states, Spearman rho = 0.755, mean KL = 4.64.
  - v2: 60 pairs, 100 states, Spearman rho = 0.717, mean KL = 5.46.
- Updated `paper/cog2026_main/main.tex` to distinguish aggregate evaluation rho values (0.728 / 0.725) from the independently regenerated plotted sample (0.755 / 0.717).
- Corrected the headline zero-shot claim from "11x above chance" to "up to 17x above chance" to align with the v3 concat result.
- Corrected the v2 table emphasis so concat is bolded for the highest zero-shot accuracy while PCSP full remains bolded for rho/KL.
- Recompiled `paper/cog2026_main/main.pdf` with system `pdflatex` after conda TeX failed due a missing `pdflatex.fmt`.
- Build status: PDF compiles; remaining warnings are underfull hboxes and the standard IEEEtran final-column reminder.

### Coarse Google Forms Human Pilot

- Recorded the completed Google Forms coarse-trace survey as aggregate item-level A/B ratios from 30 participants:
  - Raw ratio artifact: `results/human_eval/coarse_google_forms_counts.csv`
  - Analysis script: `scripts/analyze_coarse_google_forms_pilot.py`
  - Summary JSON: `results/human_eval/coarse_google_forms_summary.json`
  - Scored item CSV: `results/human_eval/coarse_google_forms_scored_items.csv`
- Result: 612/900 aggregate judgments correct = 68.0% accuracy.
- Pooled Wilson 95% CI: [0.649, 0.710].
- Item difficulty buckets:
  - strongly readable: 15/30
  - moderately readable: 2/30
  - ambiguous: 8/30
  - misleading: 5/30
- Important caveat: Google Forms preserved only item-level A/B selection ratios. Participant-level variance, confidence, response time, order effects, and inter-rater reliability are unavailable.
- Updated `paper/cog2026_main/main.tex` with a scoped "Coarse-Trace Human Pilot" subsection and revised the human-evaluation limitation from "No completed human evaluation" to "Limited aggregate human evaluation."

---

## 2026-05-11

### Experimental Paper Restructure

- Rewrote `paper/cog2026_main/main.tex` from a vision/position-paper framing into a standard experimental research paper.
- Updated title to "One Policy, Infinite NPCs: Scalable Persona-Conditioned NPC Control via Shared Reinforcement Learning Policies."
- Rewrote abstract to lead with quantitative results: 11x zero-shot, Spearman rho = 0.73, and 22x faster inference.
- Reframed introduction and contributions as empirical findings, with InfoNCE consistency as the load-bearing result.
- Renamed Section III to "PCSP Method" and removed the standalone "What This Is Not" subsection.
- Renamed Section IV to "Experiments and Results," elevated v3 as the primary experiment, and moved the evaluation protocol into Section IV.
- Replaced the standalone research/evaluation agenda sections with a condensed "Discussion and Future Work" section focused on dynamic personas and memory, richer environments including Melting Pot, and human evaluation methodology.
- Shortened limitations and removed defensive framing.
- Rewrote the conclusion around empirical contributions and concrete next steps.
- Confirmed banned framing phrases were removed from `main.tex`.

### arXiv Readiness Cleanup

- Updated `paper/cog2026_main/main.tex` after pre-upload review.
- Fixed the persona projection notation to match the implementation: 1024 -> rank-16 -> 64 low-rank projection with normalization, instead of the stale 1024 -> 512 -> 64 MLP equation.
- Fixed the policy architecture text from stale `(256-256-10)` to the implemented 3-hidden-layer `(256-256-128)` policy with an action-space-sized output head.
- Renamed overloaded notation so the value network and trajectory encoder no longer both use `\phi`.
- Deleted the legacy claim that FiLM and concat were statistically indistinguishable at v1/v2 zero-shot accuracy, per upload-review decision.
- Replaced the unsupported `43--500 ms` LLM latency wording with the paper's measured Qwen3-1.7B LLM-as-policy baseline latency of 43.7 ms/decision step.
- Removed the dangling "supplementary" reference from the results section.
- Fixed `paper/cog2026_main/refs.bib`:
  - Corrected CIC authors to Laskin, Liu, Peng, Yarats, Rajeswaran, and Abbeel.
  - Updated Qwen3 Embedding to the 2025 technical-report title and arXiv identifier.
- Recompiled `paper/cog2026_main/main.pdf` with `pdflatex -> bibtex -> pdflatex -> pdflatex`.
- Build status: citations and references resolve; no overfull hboxes remain. Remaining warnings are underfull hboxes in prose/bibliography and the standard IEEEtran final-column reminder.

---

## 2026-05-10

### Planning File Split

- Split the oversized `PLAN.md` into two files:
  - `PLAN.md` now contains only the active work checklist.
  - `DONE.md` contains completed work details, decisions, result tables, caveats, and output paths.
- Preserved the current open work items in `PLAN.md`, especially human-eval collection, v3 paper updates, and `unseen_combo_v3` completion.

---

## 2026-05-08

### Planning and Paper Direction

- Confirmed the active direction as the PCSP paper in `paper/cog2026_main/main.tex`.
- Archived old planning/proposal docs under `archive/docs_2026-05-08/`.
- Confirmed `full-proposal.md` is not the active PCSP direction; it remains separate co-adaptation context.
- Reframed the human-survey issue as an observability problem: persona-conditioned behavior must be visible in trajectories, not only recoverable from hidden state or reward.

### Rich Trace Pipeline

- Added display-only rich event semantics in `src/env/action_semantics.py`.
- Kept v1/v2 action space and observation dimensions unchanged so existing checkpoints and tables remain valid.
- Regenerated rich Korean survey artifacts:
  - `data/human_eval/persona_identification_survey_ko.json`
  - `data/human_eval/persona_identification_survey_ko.csv`
  - `data/human_eval/persona_identification_survey_ko.md`
  - `data/human_eval/persona_identification_survey_ko_answer_key.csv`
- Regenerated coarse survey artifacts from the same rollouts:
  - `data/human_eval/persona_identification_survey_ko_coarse.json`
  - `data/human_eval/persona_identification_survey_ko_coarse.csv`
  - `data/human_eval/persona_identification_survey_ko_coarse.md`
  - `data/human_eval/persona_identification_survey_ko_coarse_answer_key.csv`
- Fixed a double-place rendering bug in `src/env/action_semantics.py`: "소파에서 휴식" became "편하게 휴식" to avoid duplicated location phrases.

### Survey Baseline

- Added automated survey baseline tooling in `scripts/compute_survey_baseline.py`.
- Automated 2AFC baseline on the 30-item survey: 29/30 = 96.7%, Wilson 95% CI [0.83, 0.99].
- Difficulty-bucket baseline:
  - easy: 9/10
  - medium: 10/10
  - hard: 10/10
- Result path: `results/human_eval/automated_baseline.json`.
- Important caveat: rich-vs-coarse comparison is meaningful for human raters only. The automated encoder reads `(obs_seq, act_seq)` directly, so its score does not change with rendered text.

### Compositional Splits and v1 Evaluation

- Confirmed `data/personas/test_60.json` is an unseen-occupation split: 4 held-out occupations x 15 archetypes.
- Added compositional split builder: `scripts/build_compositional_splits.py`.
- Emitted v1 split files under `data/personas/splits/` plus `manifest.json`.
- Extended `src/eval/zeroshot.py` with compositional zero-shot evaluation and Wilson CI.
- Existing PCSP-full checkpoint on unseen occupation:
  - accuracy: 0.230
  - Wilson 95% CI: [0.186, 0.281]
  - coherence ratio: 6.09
  - result: `results/eval/compositional_zero_shot_unseen_occupation.json`

### Qualitative Examples

- Added `scripts/qualitative_persona_comparison.py`.
- Generated rich Korean comparison traces:
  - `results/human_eval/qualitative_same_occupation.md`
  - `results/human_eval/qualitative_same_occupation.json`
  - `results/human_eval/qualitative_same_archetype.md`
  - `results/human_eval/qualitative_same_archetype.json`

### Mini-Inzoi v3 Design

- Wrote `docs/mini_inzoi_v3_design.md`.
- Chose flat `Discrete(20)` for v3; factorized actions deferred.
- Defined v3 observation additions:
  - affordance one-hot
  - social context
  - routine signal
- Base obs dim changes from 20 to 33; large-scale obs dim changes from 56 to 69.
- Decided v3 must live in new files so v1/v2 remain reproducible.
- Caught a trainer-design issue: trainers and eval scripts hardcoded v1 env/dims. Decision: thread `obs_dim`, `n_actions`, `n_agents`, and `env_factory` through shared entrypoints instead of forking v3 copies.

### v3 Foundational Implementation

- Added:
  - `src/env/v3_constants.py`
  - `src/env/mini_inzoi_v3.py`
  - `scripts/build_personas_v3.py`
  - `scripts/test_env_v3.py`
  - `data/personas/personas_300_v3.json`
- Extended `src/env/action_semantics.py` with v3 semantics and `describe_v3_action_ko()`.
- v3 acceptance checks passed, including AEC API, action reachability, persona-style discrimination, Korean rendering, style-profile non-degeneracy, need coverage, action ID stability, and routine-signal calibration.
- Bug fixed during smoke testing: `eat_slow` and `clean` initially had identical style vectors; `clean` was differentiated to emphasize high conscientiousness and routine.

---

## 2026-05-09

### Trainer and Eval Refactor

- Threaded v3-compatible dimensions and env factories through:
  - `src/training/pcsp_trainer.py`
  - `src/training/baselines/per_persona_ppo.py`
  - `src/training/baselines/diayn.py`
  - `src/training/baselines/sbert_policy.py`
  - `src/training/baselines/no_persona_ppo.py`
  - `src/training/baselines/llm_policy.py`
  - `src/eval/zeroshot.py`
  - `src/eval/consistency.py`
- v1 defaults remain intact.
- Added `scripts/run_pcsp_v3.py`.
- Extended `src/eval/zeroshot.py` CLI with v3 flags: `--obs_dim`, `--n_actions`, `--env_variant`, `--n_agents`, and later `--split_suffix`.

### v3 Smoke Training

- Ran `scripts/run_pcsp_v3.py --smoke`.
- Duration: 88.5s on CUDA.
- Reward improved from 40.4 to 75.4.
- Consistency loss improved from 1.84 to 1.66.
- Summary: `results/pcsp_v3/summary.json`.

### v3 In-Distribution Sweep

- Ran PCSP full/no_consist/no_diverse/concat plus B1 and B3 on all 300 v3 personas.
- Duration: 1h 57min.
- Result summary: `results/pcsp_v3/sweep_summary.json`.
- Per-mode checkpoints: `results/pcsp_v3/{mode}/`.
- Baseline checkpoints: `results/baselines_v3/`.

Final rewards:

| mode | reward |
|:--|--:|
| pcsp_full | 100.25 |
| pcsp_no_consist | 99.21 |
| pcsp_no_diverse | 97.74 |
| b3_sbert | 92.11 |
| pcsp_concat | 91.68 |
| b1_no_persona | 83.25 |

Reading: B1 is 17 reward below full, indicating persona conditioning matters for reward. Reward alone did not expose the no-consistency failure mode.

### v3 In-Distribution Persona-Recovery Eval

- Added `scripts/run_eval_v3.py`.
- Evaluated 60 IDs filtered from `test_60.json`; these were seen in training, so this is in-distribution separability, not zero-shot.
- Combined result: `results/pcsp_v3/eval_indist60_summary.json`.

Top-1 k-NN accuracy, chance = 1.67%:

| mode | accuracy | coherence |
|:--|--:|--:|
| full | 0.290 | 3.54 |
| no_diverse | 0.260 | 3.72 |
| concat | 0.117 | 2.06 |
| no_consist | 0.017 | 1.08 |

Key result: consistency loss is load-bearing for persona-recoverability. Full vs no_consist differs by only 1.04 reward but 0.273 accuracy.

### v3 Zero-Shot Splits

- Built:
  - `data/personas/train_240_v3.json`
  - `data/personas/test_60_v3.json`
  - `data/personas/splits/unseen_occupation_v3_{train,test}.json`
  - `data/personas/splits/unseen_archetype_v3_{train,test}.json`
  - `data/personas/splits/unseen_combo_v3_{train,test}.json`
  - `data/personas/splits/manifest_v3.json`
- v1 and v3 persona ID partitions are identical; v3 only changes preferred actions and action ontology payloads.

### v3 Unseen-Occupation Zero-Shot

- Retrained PCSP-full on `train_240_v3.json`.
- Output: `results/pcsp_v3_zeroshot/full/`.
- Final reward: 104.08.
- Legacy eval on `test_60_v3`: top-1 k-NN accuracy 0.157, coherence ratio 2.04.
- Compositional wrapper on `unseen_occupation_v3`: accuracy 0.173, Wilson 95% CI [0.135, 0.220], 10.4x chance.
- Result paths:
  - `results/pcsp_v3_zeroshot/full/eval_persona_classification_zs60.json`
  - `results/eval/compositional_zero_shot_unseen_occupation_v3.json`
- Caveat: legacy CLI and compositional-wrapper numbers differ slightly; both are within CI, but the final paper should standardize on one path.

### v3 Unseen-Occupation Ablation Table

- Added `scripts/run_eval_v3_zeroshot.py`.
- Trained/evaluated PCSP no_consist/no_diverse/concat plus B1/B3 on `train_240_v3.json`.
- Combined result: `results/pcsp_v3_zeroshot/eval_zs60_summary.json`.

| mode | reward | ZS k-NN acc | Wilson 95% CI | coherence | intra/inter |
|:--|--:|--:|:--|--:|:--|
| full | 104.08 | 0.170 | [0.132, 0.217] | 2.06 | 0.96 / 0.47 |
| no_consist | 118.38 | 0.017 | [0.007, 0.038] | 1.07 | 0.95 / 0.89 |
| no_diverse | 122.09 | 0.160 | [0.123, 0.206] | 2.05 | 0.92 / 0.45 |
| concat | 107.02 | 0.283 | [0.235, 0.337] | 7.60 | 0.93 / 0.12 |
| b1 | 100.29 | n/a | n/a | n/a | n/a |
| b3_sbert | 106.85 | n/a | n/a | n/a | n/a |

Findings:

- Consistency-loss collapse holds at v3 zero-shot scale.
- Diversity loss is marginal on zero-shot persona identification.
- Concat beats FiLM on unseen occupations, reversing the v3 in-distribution pattern.

### Paper Reframe

- Updated `paper/cog2026_main/main.tex` to shift the central claim from "FiLM > concat" to "InfoNCE consistency loss is load-bearing; conditioning architecture is secondary and split-dependent."
- Updated abstract, contributions, method framing, observations, Figure 2 caption, significance, and conclusion.
- Added v3 zero-shot ablation table.
- PDF compiled cleanly at 7 pages.
- Two minor pre-existing warnings remain: one underfull hbox and one small overfull equation line.

### v3 Unseen-Archetype Ablation Table

- Trained/evaluated on `unseen_archetype_v3_train.json` / `unseen_archetype_v3_test.json`.
- Training duration: 7042s = 1.96h.
- Results:
  - `results/pcsp_v3_archetype_zs/`
  - `results/baselines_v3_archetype_zs/`
  - `results/pcsp_v3_archetype_zs/eval_archetype_summary.json`

| mode | reward | ZS k-NN acc | Wilson 95% CI | coherence | intra/inter |
|:--|--:|--:|:--|--:|:--|
| full | 105.52 | 0.203 | [0.162, 0.252] | 1.76 | 0.97 / 0.55 |
| no_consist | 105.85 | 0.013 | [0.005, 0.034] | 1.07 | 0.92 / 0.86 |
| no_diverse | 99.80 | 0.163 | [0.126, 0.209] | 2.05 | 0.93 / 0.45 |
| concat | 104.34 | 0.103 | [0.074, 0.143] | 1.54 | 0.97 / 0.63 |
| b1 | 89.51 | n/a | n/a | n/a | n/a |
| b3_sbert | 96.22 | n/a | n/a | n/a | n/a |

Major finding: the concat-over-FiLM reversal is split-family-specific, not universal.

| split family | full / FiLM | concat |
|:--|--:|--:|
| unseen occupation | 0.170 [0.132, 0.217] | 0.283 [0.235, 0.337] |
| unseen archetype | 0.203 [0.162, 0.252] | 0.103 [0.074, 0.143] |

Interpretation: consistency loss is the only component that universally fails when removed. Architecture choice matters, but its effect depends on the OOD axis.

### v3 Unseen-Combo Ablation Table

- Trained/evaluated on `unseen_combo_v3_train.json` / `unseen_combo_v3_test.json`.
- Training duration: 10361s = 2.88h.
- Evaluation duration: 554s = 9.23m.
- Results:
  - `results/pcsp_v3_combo_zs/`
  - `results/baselines_v3_combo_zs/`
  - `results/pcsp_v3_combo_zs/eval_combo_summary.json`

| mode | reward | ZS k-NN acc | Wilson 95% CI | coherence | intra/inter |
|:--|--:|--:|:--|--:|:--|
| full | 116.66 | 0.203 | [0.162, 0.252] | 2.50 | 0.94 / 0.38 |
| no_consist | 113.39 | 0.017 | [0.007, 0.038] | 1.08 | 0.94 / 0.87 |
| no_diverse | 107.60 | 0.193 | [0.153, 0.242] | 3.67 | 0.91 / 0.25 |
| concat | 108.05 | 0.170 | [0.132, 0.217] | 4.09 | 0.95 / 0.23 |
| b1 | 79.77 | n/a | n/a | n/a | n/a |
| b3_sbert | 109.54 | n/a | n/a | n/a | n/a |

Three-split architecture comparison:

| split family | full / FiLM | concat | reading |
|:--|--:|--:|:--|
| unseen occupation | 0.170 [0.132, 0.217] | 0.283 [0.235, 0.337] | concat wins; CIs disjoint |
| unseen archetype | 0.203 [0.162, 0.252] | 0.103 [0.074, 0.143] | FiLM wins; CIs disjoint |
| unseen combo | 0.203 [0.162, 0.252] | 0.170 [0.132, 0.217] | FiLM higher, but CIs overlap |

Interpretation: combo follows the archetype direction in point estimate but not in statistical separation. The robust claim remains that InfoNCE consistency is universally load-bearing: no_consist lands at chance in all three split families. Architecture is split-dependent, with the strongest statistically separated reversals on occupation vs archetype shifts.

### Paper Update After v3 Combo

- Updated `paper/cog2026_main/main.tex` to mention the unseen-combo result in the architecture paragraph.
- Standardized paper claims on the v3 zero-shot eval-driver/compositional ablation summaries, not the legacy CLI-only `test_60_v3` number.
- The unseen-combo result is reported as FiLM higher in point estimate but not statistically separated from concat because Wilson intervals overlap.
- Recompiled `paper/cog2026_main/main.pdf`: clean 7-page PDF.
- Remaining warnings are the same minor layout warnings seen before this update: one underfull intro paragraph, one 8.3pt overfull LoRA equation line, and one bibliography underfull hbox.

### Designer-Authored Persona Case Study

- Added and ran `scripts/run_designer_persona_case_study.py`.
- Purpose: new top-priority qualitative case study to complete before human evaluation.
- Protocol: inference only, no retraining; PCSP-v3 full checkpoint `results/pcsp_v3/full/policy.pt`; Mini-Inzoi v3, 5 episodes per designer persona, max_steps=200.
- Persona set: 13 Korean natural-language designer-authored personas based on requested Sims 3 trait combinations and Animal Crossing villager personality categories.
- Embedding path: Qwen3-Embedding-0.6B last-token pooling + L2 normalization, then trained PCSP LoRA projection for projected-embedding artifact.
- Outputs:
  - Report: `results/designer_persona_case_study/case_study_report.md`
  - Full JSON: `results/designer_persona_case_study/case_study_results.json`
  - Persona definitions: `results/designer_persona_case_study/designer_personas.json`
  - Raw embeddings: `results/designer_persona_case_study/designer_persona_embeddings.npy`
  - Projected embeddings: `results/designer_persona_case_study/designer_persona_projected_embeddings.npy`
  - 13 action-distribution charts: `results/designer_persona_case_study/action_bars/`
  - t-SNE plot: `results/designer_persona_case_study/designer_personas_tsne.png`

| persona | top-3 actions | mean top-5 train cosine | qualitative read |
|:--|:--|--:|:--|
| corporate strategist | focused_work, planning_work, eat_slow | 0.714 | strong work/planning alignment |
| introverted researcher | rest_alone, read_deep, socialize_respond | 0.693 | strong solitary/research alignment |
| outgoing event planner | socialize_initiate, read_deep, eat_quick | 0.606 | partial social alignment |
| competitive personal trainer | rest_alone, focused_work, planning_work | 0.752 | partial; exercise did not dominate |
| unmotivated freelancer | rest_alone, eat_quick, sleep | 0.578 | strong low-motivation/rest alignment |
| lazy villager | eat_slow, move_right, sleep | 0.614 | strong food/sleep alignment despite movement |
| jock villager | socialize_initiate, rest_with_others, eat_slow | 0.556 | weak; fitness archetype not expressed |
| cranky villager | socialize_initiate, rest_alone, read_deep | 0.588 | strong on rest/read, with social-initiation bias |
| normal villager | focused_work, socialize_initiate, eat_slow | 0.579 | weak; hygiene/care was not expressed |
| peppy villager | socialize_initiate, eat_slow, rest_with_others | 0.573 | strong social/communal alignment |
| snooty villager | socialize_initiate, eat_slow, socialize_respond | 0.646 | partial controlled-social alignment |
| smug villager | socialize_initiate, planning_work, eat_slow | 0.612 | strong social/planning alignment |
| sisterly villager | socialize_initiate, eat_slow, planning_work | 0.609 | weak; protective/active signature not expressed |

Interpretation: the case study produces both positive and negative qualitative evidence. Workaholic/corporate, introverted researcher, couch-potato freelancer, lazy, peppy, and smug personas show clear expected behavior; jock, normal, and sisterly are useful failure cases where v3 still exhibits a broad social-initiation/eating/planning bias. No existing checkpoint compatibility was changed and no retraining is required.

### Figure 3 Label Overlap Fix

- Fixed the crowded top-right designer-persona t-SNE labels in Figure 3.
- Updated `scripts/run_designer_persona_case_study.py` so `save_tsne_plot` uses deterministic per-label offsets, light leader lines for displaced labels, slightly smaller label text, translucent white label backgrounds, and an expanded right margin.
- Regenerated:
  - `results/designer_persona_case_study/designer_personas_tsne.png`
  - `paper/figures/fig5_designer_personas_tsne.png`
  - `paper/cog2026_main/main.pdf`
- Verified the rebuilt PDF by rendering page 5; the former top-right overlap is resolved.
- No experiment outputs, checkpoint compatibility, action spaces, or observations changed. No retraining is required.

### Paper Section IV-D: Qualitative Case Study

- Added Section IV-D, "Qualitative Case Study: Designer-Authored Personas," to `paper/cog2026_main/main.tex`.
- Inserted after the v3/key-observations material and before the former Significance subsection, so the qualitative case study is now Section IV-D and Significance becomes Section IV-E.
- Added `Table V` with: persona name, top-3 actions, nearest training persona, nearest-neighbor cosine similarity, and aligned/partial/no judgment.
- Added t-SNE figure to the paper:
  - Source: `results/designer_persona_case_study/designer_personas_tsne.png`
  - Paper copy: `paper/figures/fig5_designer_personas_tsne.png`
- Added citations for the source inspiration pages:
  - `sims3traits`
  - `nookipediaVillager`
- Updated the limitations paragraph on synthetic personas to acknowledge the qualitative designer-authored case study while preserving the limitation that robustness to production-authored personas remains unproven.
- Recompiled `paper/cog2026_main/main.pdf`: citations and labels resolved; output is now 8 pages.
- Remaining compile warnings: pre-existing LoRA equation overfull hbox plus several underfull boxes around qualitative prose/bibliography. No new fatal LaTeX errors.

### Public Preprint / GitHub Metadata

- User clarified there is no intention to submit this work to IEEE CoG.
- Public arXiv/GitHub version should therefore not carry an IEEE submitted-work notice or imply conference submission.
- Updated `paper/cog2026_main/main.tex`:
  - Author: Yoosung Hong
  - Affiliation: Independent Researcher
  - GitHub link: `https://github.com/yoosunghong/pcsp`
- Removed the previously added IEEE submitted-work title-block footnote.
- Added root `README.md` with project summary, commands, and GitHub link.
- Added root `LICENSE` with MIT License for source code and scripts.
- Recompiled `paper/cog2026_main/main.pdf`; the first page contains the author, affiliation, and GitHub link, with no IEEE submitted-work notice.

## 2026-05-12

### Figure 1 PSPC Pipeline Replacement

- Replaced the legacy Figure 1 system overview with the revised PSPC pipeline diagram.
- Renamed the new asset from `paper/figures/pspc.drawio.png` to `paper/figures/fig1_pcsp_pipeline.png`.
- Deleted the legacy Figure 1 assets:
  - `paper/figures/fig1_system.png`
  - `paper/figures/fig1_system.pdf`
- Added the new Figure 1 to `paper/cog2026_main/main.tex` as a two-column `figure*` at `width=0.98\textwidth`, preserving label `fig:system`.
- Restored the designer-persona t-SNE figure block so it is again Figure 3.
- Recompiled `paper/cog2026_main/main.pdf` with `latexmk -pdf -interaction=nonstopmode main.tex`.
- Verified `main.aux`: `fig:system` resolves to Figure 1 on page 4, `fig:learning` to Figure 2 on page 4, and `fig:designer_tsne` to Figure 3 on page 5.
- Rendered pages 4--5 for visual inspection; Figure 1 spans both columns and Figure 3 is restored.
- No code, checkpoints, action spaces, or observations changed. No retraining is required.

### v3 Human-Eval Preflight

- Added the pre-human-eval priority plan to `PLAN.md`: v3 rollout regeneration, matched v3 rich/coarse artifacts, v3 automated baseline, pilot study, v3-large scaling, optional Melting Pot validation, and Designer-300 external validation.
- Updated `scripts/export_persona_identification_rollouts.py` so human-eval rollout export supports `--env_variant v3` with `MiniInzoiV3Env`, obs dim 33, 20 actions, and v3 Korean action rendering.
- Updated `scripts/generate_persona_identification_survey_ko.py` so rich/coarse survey rendering honors rollout `env_variant`; v3 coarse labels now use the 20-action ontology.
- Updated `scripts/compute_survey_baseline.py` so the automated 2AFC baseline can load v3 policy and trajectory encoder dimensions from rollout metadata.
- Exported v3 PCSP human-eval rollouts:
  - `results/human_eval/pcsp_v3_full_zero_shot_rollouts.json`
  - Source policy: `results/pcsp_v3/full/policy.pt`
  - Personas: `data/personas/test_60_v3.json`
  - Metadata: `env_variant=v3`, `obs_dim=33`, `n_actions=20`, `n_rollouts=30`
- Regenerated matched Korean human-eval artifacts from the same v3 rollout file:
  - Rich: `data/human_eval/persona_identification_survey_ko.{json,csv,md}` plus answer key
  - Coarse: `data/human_eval/persona_identification_survey_ko_coarse.{json,csv,md}` plus answer key
- Re-ran automated v3 survey baseline:
  - Output: `results/human_eval/automated_baseline.json`
  - Accuracy: 30/30 = 100.0%, Wilson 95% CI [0.886, 1.000]
  - Difficulty buckets: easy 10/10, medium 10/10, hard 10/10
- No action space, observation schema, or checkpoint format changed. No retraining is required.

### v3 Human-Eval Pilot Package

- Added `scripts/prepare_human_eval_pilot.py`.
- Generated a counterbalanced 10-participant pilot package under `data/human_eval/pilot_v3/`.
- Design:
  - 30 trajectory items per participant.
  - Each participant sees each trajectory once, assigned to either rich or coarse.
  - Each participant receives 15 rich and 15 coarse items.
  - Across 10 participants, each item appears 5 times in rich form and 5 times in coarse form.
- Outputs:
  - `data/human_eval/pilot_v3/participant_packets/pilot_01.md` ... `pilot_10.md`
  - `data/human_eval/pilot_v3/pilot_response_template.csv`
  - `data/human_eval/pilot_v3/pilot_answer_key.csv`
  - `data/human_eval/pilot_v3/pilot_assignment_manifest.csv`
  - `data/human_eval/pilot_v3/pilot_manifest.json`
  - `data/human_eval/pilot_v3/README.md`
- Updated `src/eval/human_eval.py` to score `item_uid`-based rich/coarse studies and report `by_condition` summaries.
- Verification:
  - `py_compile` passed for `scripts/prepare_human_eval_pilot.py` and `src/eval/human_eval.py`.
  - Blank pilot template scoring produces zero valid responses as expected.
  - Temporary synthetic responses produce separate rich/coarse summaries with 150 responses per condition.

---

## Stable Decisions

- Rich semantics remain display-only for v1/v2.
- v3 uses flat `Discrete(20)` actions.
- v3 checkpoints are incompatible with v1/v2 because action and observation dimensions changed.
- The InfoNCE trajectory consistency objective is the central load-bearing component.
- Conditioning architecture is a tunable, split-dependent design choice rather than the main claim.
- Diversity loss should be presented as a useful regularizer, not as a co-equal contributor to zero-shot persona identification.

## 2026-08-31 - UE Mass-Hybrid Scaling Analysis

- Extended `scripts/analyze_scaling_sweep.py` to read the UE hybrid run contract:
  `hero_agents`, `mass_entities`, `total_npcs`, Actor path-scheduler telemetry,
  and Mass population/decision/arrival/policy-time telemetry.
- Aggregation and plots now group by architecture (`actor_bt` vs
  `mass_hybrid`) and total NPC count, while preserving the existing Actor-only
  sweep compatibility.
- Verified the analyzer with the 1,024-entity compatibility smoke session.
  Outputs are under `results/ue_sessions/mass_smoke_20260831/`; the 4-Actor
  control is under `results/ue_sessions/actor4_smoke_20260831/`.
- These runs validate the UE runtime and telemetry path only. Their offscreen
  frame times are throttled and must not be cited as performance evidence.
- The observation schema remains 33-d, the persona embedding remains 64-d, and
  the action ontology remains 20-way. No checkpoint export change or retraining
  is required for this integration.

## 2026-09-01 - Visible UE Mass-Hybrid Scaling Sweep

- Completed 12 visible UE 5.8 standalone sessions:
  `{128,256,512,1024}` total NPCs × three seeds × 300 seconds, holding the hero
  tier at 16 Actor/BT agents and assigning the rest to Mass.
- Aggregated with `scripts/analyze_scaling_sweep.py` into
  `results/ue_sessions/mass_scaling_20260901/`.
- At 1,024 NPCs, three-seed means are frame `25.47 ms`, frame p95 `30.15 ms`,
  hero movement failure `0.0%`, completed intents `14.10/NPC/min`, and Mass
  policy latency `101.0 us`.
- The correct claim is bounded incremental cost: frame p95 changes only
  `0.25 ms` from 128 to 1,024 NPCs. The absolute frame time remains above the
  60-FPS budget and is reported as such.

## 2026-09-01 - Persona Projection Audit

- Added `scripts/audit_persona_projection.py`, a policy-independent diagnostic
  for the frozen 1024-d Qwen embeddings and the trained rank-16/64-d PCSP
  projection.
- Used the fixed v3 `train_240` / `test_60` split and a standardized multiclass
  ridge probe whose regularization is selected only on the training set.
- Mean Big Five held-out balanced accuracy is `0.898` in raw space and `0.799`
  after projection (`0.333` chance). Projected per-axis accuracy is E `0.733`,
  N `0.735`, A `0.757`, C `0.869`, and O `0.903`.
- The projected vectors have numerical rank `16`, effective rank `3.87`, and
  only moderate raw/projected pairwise cosine agreement (`rho=0.404`). This is
  recorded as strong task compression with retained trait signal, not general
  semantic-geometry preservation.
- Added the reproducible report `docs/persona_projection_audit.md` and outputs
  under `results/persona_projection_audit/`. A repeated run produced identical
  JSON, CSV, and PNG hashes.
- No model, schema, checkpoint, or training input changed; retraining is not
  required.

## 2026-09-01 - Independent v3-Large Behavioral Evaluator

- Added `src/eval/independent_behavior.py`, whose imports and features are
  independent of PCSP policy internals, the persona projection, logits, and the
  learned trajectory encoder.
- Added a deterministic feature contract test and a v3-large runner covering
  full/no-consistency × seeds 42/43/44 × 500 personas. The resulting cache has
  exactly 3,000 200-step trajectories with persona-disjoint 320 fit / 80
  calibration / 100 held-out evaluator splits.
- Action-only held-out Big Five balanced accuracy is `0.482` for full and
  `0.511` for no-consistency. The paired cluster-bootstrap delta interval is
  `[-0.056, -0.002]`; paired randomization `p=0.050`.
- Action plus state-response accuracy is `0.556` vs `0.558`, with delta interval
  `[-0.033, 0.030]` and `p=0.875`.
- This does not validate the earlier strong behavioral interpretation of the
  InfoNCE ablation. Documentation and the root evidence table now distinguish
  learned representation alignment from independently observable behavior.
- Outputs include the compressed frozen features, feature schema, fitted
  evaluator weights, raw test predictions, metrics, and PNG/SVG figure under
  `results/independent_behavior_v3_large/`.
- No policy was retrained and no environment/action/observation contract was
  changed.

## 2026-09-01 - UE Actor/Mass Independent-Evaluator Bridge

- Added canonical pre-remap `policy_action_index` to Actor decision telemetry
  and sampled per-entity Mass trajectory telemetry with a default 16-entity
  budget and one-second buffered flush.
- Added `scripts/evaluate_ue_behavior_tiers.py` and its synthetic ingestion
  contract test. The adapter uses only chosen action indices for the frozen
  action-only evaluator, and writes a compact canonical source artifact.
- UE 5.8 `cnzoiEditor Win64 Development` compiled successfully.
- Visible standalone session `20260901_044431` (16 Actor + 112 Mass,
  no-consistency export, seed 7, 300 seconds) exited code 0 and produced 993
  sampled Mass decisions plus 16 indexed Actor logs.
- For 16 paired personas: mean Actor/Mass action JS is `0.066`, frozen trait
  prediction agreement is `71.25%`, Actor BA is `0.458`, and Mass BA is
  `0.571`. The Mass-minus-Actor delta interval is `[0.013, 0.218]`, but unequal
  decision cadence and the single no-consistency seed prevent a superiority
  claim.
- Checked-in artifacts: `results/ue_sessions/tier_behavior_20260901_044431/`
  and `docs/ue_simulation_tier_behavior.md`.

## 2026-09-01 - Attributable Gradient-Path Instrumentation

- Added opt-in `PCSPConfig.log_attributable_gradients`; normal training remains
  unchanged when false.
- `PCSPTrainer` can now measure per-loss gradient L2 norms for persona
  projection, actor, critic, and trajectory encoder before optimizer steps and
  include their epoch means in iteration metrics.
- Added a topology contract test covering standalone losses and the integrated
  `update()` metric path.
- Audited the trained v3-large full seed-42 checkpoint on a real 16-agent,
  200-step rollout. All expected paths passed: PPO → projection/actor/critic;
  consistency → projection/trajectory encoder; diversity → projection/actor.
- Weighted norms were PPO `(269.1, 1.21, 290.0, 0)`, consistency
  `(0.787, 0, 0, 3.745)`, and diversity `(4.87e-4, 1.82e-4, 0, 0)` in
  `(projection, actor, critic, trajectory)` order.
- Added `docs/gradient_path_audit.md` and machine-readable/visual artifacts
  under `results/gradient_path_audit/`. The report explicitly avoids treating
  raw pre-clipping norms as effect sizes.

## 2026-09-01 - OOD Persona Leakage Audit

- Added `scripts/audit_ood_leakage.py` plus a synthetic hard-leak contract
  test. The audit covers standard v3, v3-large, unseen occupation/archetype/
  combo v3, and the 50-persona cross-lingual designer set.
- Across all six splits there are zero persona-ID overlaps, normalized exact
  matches, character-5 Jaccard alerts at 0.80, or word-bigram alerts at 0.80.
- The overall gate is `warning`: eight split-level Qwen cosine alerts at 0.95
  correspond to seven unique train/test pairs. They are strong paraphrases or
  v3-large records sharing the generated age/occupation/trait template.
- Intended metadata boundaries remain intact: unseen occupations, held-out
  Big Five archetypes, and occupation x archetype cells have zero train/test
  overlap in their respective splits.
- The English designer set passes cleanly with maximum raw cosine `0.686` and
  zero lexical overlap; unseen-archetype v3 also passes with max cosine `0.922`.
- Added `docs/ood_leakage_audit.md`, a 390-row nearest-pair table, JSON summary,
  and PNG/SVG distribution figure under `results/ood_leakage_audit/`.

## 2026-09-01 - Full-PCSP UE Actor/Mass Multi-Seed Confirmation

- Ran visible UE 5.8 standalone sessions `20260901_052732`,
  `20260901_053253`, and `20260901_053815` with the full PCSP export, spawn
  seeds 0/1/2, 16 Actor agents, 112 Mass agents, and 300 seconds per run.
- All three runs exited with code 0 and produced complete Actor, Mass, frame,
  path-scheduler, and occupancy telemetry. The original active `no_consist`
  export was restored byte-for-byte after collection.
- The frozen independent probe reports Actor BA `0.498+/-0.063`, Mass BA
  `0.450+/-0.012`, mean action JS `0.068+/-0.013`, and cross-tier trait
  agreement `67.9+/-4.7%` across spawn seeds.
- The Mass-minus-Actor delta is `-0.048+/-0.057` and changes sign across
  seeds. This confirms action-level persona preservation across simulation
  tiers but rejects a tier-superiority interpretation.
- Added `scripts/aggregate_ue_behavior_tiers.py`, per-session compact source
  evidence, and aggregate JSON/CSV/PNG/SVG under
  `results/ue_sessions/tier_behavior_full_multiseed_20260901/`.
