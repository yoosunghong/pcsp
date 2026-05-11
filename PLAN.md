# PLAN.md - PCSP Active Checklist

**Project:** Persona-Conditioned Shared Policy (PCSP) for life-simulation NPCs  
**Primary paper:** `paper/cog2026_vision/main.tex`  
**Done log:** completed work, decisions, and result details live in `DONE.md`.

---

## Operating Rule

- Read this checklist before research, code, evaluation, or paper changes.
- Align work with `paper/cog2026_vision/main.tex`.
- Connect new work to one checklist item below.
- After non-trivial work, update checklist status here and put detailed results/decisions in `DONE.md`.

---

## Active Direction

- [ ] Keep the paper centered on PCSP: frozen LLM persona encoder, lightweight shared RL policy, and trajectory-level persona consistency.
- [ ] Do not treat `full-proposal.md` as the active direction.
- [ ] Prioritize observable persona-conditioned behavior in rich trajectories.
- [ ] Treat InfoNCE consistency as the load-bearing claim; treat conditioning architecture as split-dependent.

---

## Phase A - Rich Trace Pipeline

- [x] Archive old planning/proposal docs under `archive/docs_2026-05-08/`.
- [x] Add shared action semantics module: `src/env/action_semantics.py`.
- [x] Separate control action IDs from display/event semantics.
- [x] Export rich rollout fields: time, location, nearby agents, action style, and observations.
- [x] Regenerate Korean rich survey artifacts: `data/human_eval/persona_identification_survey_ko.*`.
- [x] Regenerate Korean coarse survey artifacts: `data/human_eval/persona_identification_survey_ko_coarse.*`.
- [x] Add automated survey baseline and item difficulty buckets.
- [x] Run designer-authored qualitative case study before human eval: Sims 3 / Animal Crossing personas, v3 PCSP inference, action bars, nearest-neighbor similarity, and t-SNE.
- [ ] Collect human responses for rich vs coarse survey variants.
- [ ] Report human 2AFC accuracy with Wilson 95% CI.
- [ ] Report confidence and response time.
- [ ] Track inter-rater reliability if multiple raters are used.

---

## Phase B - Paper Consistency

- [x] Add coarse-action observability limitation to `paper/cog2026_vision/main.tex`.
- [x] Add rich trajectory observability to the evaluation agenda.
- [x] Add v3 zero-shot ablation table to `main.tex`.
- [x] Reframe paper away from "FiLM > concat" and toward "InfoNCE consistency is load-bearing".
- [x] Update paper text with the `unseen_archetype_v3` reversal: FiLM beats concat on unseen archetypes while concat beats FiLM on unseen occupations.
- [x] Update paper claims after `unseen_combo_v3` completes.
- [x] Standardize on the v3 zero-shot eval-driver/compositional ablation summaries for paper accuracy claims; retire the legacy CLI-only number from paper claims.
- [x] Recompile and inspect final PDF after all v3 compositional updates.
- [x] Add Section IV-D qualitative case study for designer-authored Sims 3 / Animal Crossing personas, with table and t-SNE figure.
- [x] Prepare public arXiv/GitHub metadata: author, affiliation, GitHub link, README, and MIT software license.
- [x] Fix arXiv-readiness review issues in `main.tex`/`refs.bib`: projection notation, policy dimensions, legacy architecture claim, latency wording, and citation metadata.
- [x] Restructure `main.tex` from a vision/position-paper framing into a standard experimental-paper framing while preserving existing results.
- [x] Fix Figure 3 designer-persona t-SNE label overlap and recompile `main.pdf`.
- [x] Replace Figure 1 with the PSPC pipeline diagram, render it as a two-column figure, restore Figure 3, and recompile `main.pdf`.

---

## Phase C - Mini-Inzoi v3 Environment

- [x] Write `docs/mini_inzoi_v3_design.md`.
- [x] Define v3 action ontology and observation schema.
- [x] Commit to flat `Discrete(20)` actions for v3; defer factorized actions.
- [x] Implement v3 without breaking v1/v2: `src/env/mini_inzoi_v3.py`, `src/env/v3_constants.py`.
- [x] Add v3 action semantics and Korean rendering.
- [x] Build `data/personas/personas_300_v3.json`.
- [x] Add and pass v3 smoke tests: `scripts/test_env_v3.py`.
- [x] Refactor trainers/evaluators to thread `obs_dim`, `n_actions`, `n_agents`, and `env_factory`.
- [x] Add `scripts/run_pcsp_v3.py`.
- [x] Add `scripts/run_full_sweep_v3.py`.
- [x] Add v3 zero-shot eval driver: `scripts/run_eval_v3_zeroshot.py`.
- [ ] Thread v3 support through lower-priority eval scripts that still import `MiniInzoiEnv` directly: `src/eval/task_perf.py`, `src/eval/diversity.py`, and any remaining v3 rendering checks.

---

## Phase D - v3 Training and Evaluation

- [x] Run v3 PCSP smoke training.
- [x] Run in-distribution v3 sweep: PCSP full/no_consist/no_diverse/concat + B1 + B3.
- [x] Run in-distribution v3 persona-recovery eval.
- [x] Build `train_240_v3.json` and `test_60_v3.json`.
- [x] Build v3 compositional splits under `data/personas/splits/`.
- [x] Run unseen-occupation v3 zero-shot retrain and ablation table.
- [x] Run unseen-archetype v3 retrain and ablation table.
- [x] Finish `unseen_combo_v3` sweep and eval.
- [x] Add `unseen_combo_v3` findings to `DONE.md`.
- [ ] Cross-check whether the v3 legacy CLI vs compositional-wrapper accuracy discrepancy is reproducible.
- [ ] Consider a focused follow-up analysis of architecture generalization gaps by split family.

---

## Phase E - Model / Training Follow-Ups

- [ ] If action space changes again, update `n_actions`, policy heads, trajectory encoder action one-hot dimension, all trainers, and all evaluators.
- [ ] If observation dimensions change again, update model input layers and mark existing checkpoints incompatible.
- [ ] If factorized actions are introduced, redesign the actor as multiple heads: intent, target/place, style/duration.
- [ ] Re-measure latency before claiming final real-time speedups in the paper.
- [ ] Decide whether the frozen projection ablation is worth running for v3.
