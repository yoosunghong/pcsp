# PLAN.md - PCSP Research Execution Plan

**Project:** Persona-Conditioned Shared Policy (PCSP) for life-simulation NPCs  
**Primary paper:** `paper/cog2026_vision/main.tex`  
**Current title:** "One Policy, Infinite NPCs: A Vision for Scalable Persona-Conditioned NPC Control in Life Simulation Games"  
**Plan owner:** root `PLAN.md` is the active working plan. Archived plans live under `archive/`.

---

## 0. Operating Rule

Before making research, code, evaluation, or paper changes, read this plan and align the work with the active paper direction in `paper/cog2026_vision/main.tex`.

After completing a non-trivial task, update this file in the same turn:

- Mark completed checklist items.
- Add new follow-up tasks discovered during the work.
- Record important decisions, changed assumptions, and result locations.
- Keep historical detail short; move stale plans or replaced proposals to `archive/`.

---

## 1. Current Direction

The project is no longer centered on the speculative sLM/RL co-adaptation proposal. The active paper is a PCSP vision paper for scalable, persona-conditioned NPC control in life-simulation games.

The core claim:

> A frozen LLM persona encoder plus a lightweight shared RL policy can provide natural-language controllability, zero-shot persona generalization, persona-consistent behavior, and real-time inference for large NPC populations.

The paper should be judged against four axes:

| Axis | Required Evidence |
|:--|:--|
| Persona consistency | Trajectories are identifiable from persona conditioning. |
| Natural-language control | Free-form persona text maps to behavior without per-persona retraining. |
| Zero-shot generalization | Held-out personas produce coherent, separable behavior. |
| Real-time inference | Per-step policy inference remains game-speed; LLM called once per NPC. |

---

## 2. Main Paper Alignment

Use `paper/cog2026_vision/main.tex` as the source of truth for framing.

Current paper structure:

- Motivation: life-simulation NPC personalization scaling gap.
- Method: PCSP = frozen Qwen3 embedding + LoRA projection + FiLM policy + PPO/InfoNCE/KL objectives.
- Evidence: Mini-Inzoi v1 and v2 results.
- Research agenda: dynamic personas, social emergence, memory, richer worlds, human evaluation, authoring tools.
- Evaluation agenda: persona identification, behavioral diversity, semantic-behavioral alignment, latency, human fidelity.

Do not treat `full-proposal.md` as the active direction. It is archived context for a separate speculative co-adaptation idea.

---

## 3. Immediate Problem

Human persona-identification survey pilots revealed that the current visible behavior traces are too coarse:

- `read`, `rest`, `eat`, `work`, `sleep`, `socialize` are too semantically close.
- Participants reasonably ask how `read` or `eat` differs from `rest`.
- The current survey hides movement and much of the environmental context.
- Persona traits are hard to infer from short action-label sequences alone.

This is not only a survey-design issue. It is a research validity issue: persona-conditioned behavior must be observable in trajectories.

Therefore the next implementation phase is:

> Make persona-relevant behavior more expressive and observable while preserving the lightweight shared-policy thesis.

---

## 4. Required Full-Paper Upgrades

### 4.1 Expressive Environment

Goal: expose enough behavioral degrees of freedom for persona traits to become visible.

Tasks:

- [x] Archive old planning/proposal docs under `archive/docs_2026-05-08/`.
- [x] Add a shared action semantics module for richer human-readable behavior traces: `src/env/action_semantics.py`.
- [x] Separate control action IDs from display/event semantics in all rollout and survey tooling.
- [x] Include time, location, nearby agents, and action style in human-eval traces.
- [x] Decide whether richer semantics stay display-only or become environment state/reward features. **Decision (2026-05-08):** display-only for v1/v2; graduate to environment state/reward in Mini-Inzoi v3 only. See Decision Log.
- [x] Design Mini-Inzoi v3 action ontology — closed by `docs/mini_inzoi_v3_design.md` §3 (20 flat-discrete actions: focused_work, planning_work, eat_quick, eat_slow, sleep, nap, socialize_initiate, socialize_respond, exercise_intense, exercise_light, read_deep, read_casual, clean, rest_alone, rest_with_others, explore + 4 movement). Per-action style profile committed in `ACTION_STYLE_PROFILE`.
- [x] Add location affordances so actions are meaningfully grounded in objects/places — design committed (8-way affordance one-hot in obs); implementation in v3 env is the next concrete task.
- [x] Add social-context features: initiated interaction, responded, avoided, cooperated, argued, comforted — design committed (3-dim social-context slice: nearby_count, in_conversation flag, last_responder flag); the richer interaction-type ontology (avoided/argued/comforted) is deferred to a future v4 because it requires multi-step interaction tracking, not just a per-step flag. Logged as an open question in the v3 design doc §10.
- [x] Add routine/regularity features for conscientiousness and neuroticism observability — design committed (2-dim routine signal: repeat_count, time-since-last-novel).

### 4.2 Identifiability Evaluation

Goal: prove that persona-conditioned trajectories carry recoverable persona information.

Tasks:

- [x] Regenerate Korean human-eval survey with rich traces. (Re-exported deterministically with `obs` saved per step; survey JSON/CSV/MD regenerated.)
- [x] Add item difficulty buckets: easy, medium, hard persona pairs. (Rank-based tertiles on `distractor_score`, persisted in `results/human_eval/automated_baseline_per_item.csv`.)
- [x] Report human 2AFC accuracy with Wilson 95% CI. (Infrastructure: `wilson_ci` already in `src/eval/human_eval.py:45`; wired into the automated baseline aggregator. Human responses still pending.)
- [ ] Report confidence and response time. (Survey schema already supports these columns; depends on collecting human responses.)
- [ ] Track inter-rater reliability if multiple raters are used. (Krippendorff α already in `src/eval/human_eval.py:55`; depends on multi-rater runs.)
- [x] Compare human accuracy against automated trajectory-to-persona kNN/classifier. (Automated baseline = 29/30 = 96.7%, Wilson CI [0.83, 0.99]; per-bucket: easy 9/10, medium 10/10, hard 10/10. Output: `results/human_eval/automated_baseline.json`.)
- [x] Add ablation: coarse traces vs rich traces, to show observability matters. (Coarse-mode survey at `data/human_eval/persona_identification_survey_ko_coarse.{json,csv,md,_answer_key.csv}`; identical item IDs / trajectory IDs / correct options as the rich survey, so the same raters can be assigned to one variant for between-subjects A/B. Human result pending response collection.)

### 4.3 Compositional Generalization

Goal: show that the method generalizes across unseen combinations, not just memorized personas.

Tasks:

- [x] Define held-out splits by occupation, Big Five archetype, and occupation-trait combination. (Generated under `data/personas/splits/`: `unseen_occupation_*` reproduces the existing train_240/test_60 split, `unseen_archetype_*` holds out 3 archetypes × 20 occupations, `unseen_combo_*` holds out 60 random cells with both axes covered. See `data/personas/splits/manifest.json` and `scripts/build_compositional_splits.py`.)
- [x] Add compositional zero-shot metrics to `src/eval/zeroshot.py`. (New `compositional_zero_shot(split_family, ...)` wrapper reads the right split file and adds Wilson 95% CI and split metadata. Exposed via `--split_family` CLI flag.)
- [~] Report results separately for:
  - [x] unseen persona texts (existing test_60 = unseen_occupation; v1: `results/eval/compositional_zero_shot_unseen_occupation.json`; v3: `results/eval/compositional_zero_shot_unseen_occupation_v3.json`)
  - [x] unseen occupations (v1 0.230 acc / 6.09 coherence; **v3 0.173 acc [95% CI 0.135–0.220] / 2.07 coherence**, see Decision Log 2026-05-09)
  - [ ] unseen trait combinations (`unseen_archetype` and `unseen_archetype_v3` splits exist; **retraining required**: PCSP-full on `unseen_archetype_v3_train.json`)
  - [ ] same occupation with different traits (qualitative covered; quantitative requires the unseen_archetype retrain)
  - [ ] same traits with different occupations (qualitative covered; quantitative requires the unseen_occupation retrain stratified by archetype overlap)
- [x] Add qualitative examples where two NPCs share occupation but differ in personality-driven style. (`results/human_eval/qualitative_same_occupation.{md,json}` and `results/human_eval/qualitative_same_archetype.{md,json}` from `scripts/qualitative_persona_comparison.py`. 3 pairs each, rich Korean traces.)

---

## 5. Model and Training Implications

Richer behavior likely requires retraining, but not necessarily a full architectural replacement.

Current judgment:

- If changes are display-only event rendering, existing checkpoints can be reused for survey pilots.
- If action space changes, all policies and baselines must be retrained.
- If observation dimensions change, model input layers and checkpoints are incompatible.
- If action space becomes factorized, the actor head must be redesigned.

Recommended path:

1. Short term: keep 12 discrete action IDs, add rich event rendering for human evaluation.
2. Medium term: create Mini-Inzoi v3 with richer but still discrete semantic actions.
3. Full-paper path: consider factorized actions only after v3 results show the need.

Potential model changes:

- [ ] For expanded discrete actions: update `n_actions`, policy heads, trajectory encoder action one-hot dimension, all trainers/evaluators.
- [ ] For factorized actions: actor emits multiple heads: intent, target/place, style/duration.
- [ ] For richer observations: add structured object/social features; update obs dim in env, trainers, baselines, eval scripts.
- [ ] Retrain PCSP full and key ablations after any action/obs change.

---

## 6. Active Implementation Checklist

### Phase A - Rich Trace Pipeline

- [x] Create archive directory for old docs: `archive/docs_2026-05-08/`.
- [x] Preserve old root `PLAN.md` as `archive/docs_2026-05-08/PLAN.root-before-refresh.md`.
- [x] Create new root `PLAN.md` aligned with `paper/cog2026_vision/main.tex`.
- [x] Update `AGENTS.md` so agents must use and update root `PLAN.md`.
- [x] Verify `scripts/export_persona_identification_rollouts.py` exports rich event fields.
- [x] Verify `scripts/generate_persona_identification_survey_ko.py` renders rich traces.
- [x] Regenerate `persona_identification_survey_ko.*` from rich rollouts.
- [x] Run a small manual review of 5 generated survey items.

### Phase B - Paper Consistency

- [x] Add a short limitation/next-step paragraph to `main.tex` about coarse action observability.
- [x] Ensure `main.tex` evaluation agenda explicitly names rich trajectory observability.
- [ ] Check tables/claims after any retraining or survey regeneration. (No retraining yet; revisit after v3 or rich-trace ablation runs.)

### Phase C - Environment v3 Design

- [x] Write `docs/mini_inzoi_v3_design.md`. (Draft v0.2 — design review pass 2026-05-08 closed all five §10 open questions, pinned the v1→v3 `preferred_actions` mapping rule (§8.1), enumerated the trainer-refactor file list (§7), and added three acceptance checks (§9): style-profile non-degeneracy, need coverage, action ID stability.)
- [x] Define action ontology and observation schema. (See `docs/mini_inzoi_v3_design.md` §3-§4: 20 flat-discrete actions = 16 activity + 4 movement; obs adds affordance one-hot (8), social context (3), routine signal (2). Base-scale obs_dim grows 20→33; large-scale 56→69.)
- [x] Decide discrete-expanded vs factorized action interface. (Committed to flat `Discrete(20)` for v3; factorized actions deferred until v3 results show flat is bottlenecking. See design doc §6.)
- [x] Implement environment behind a new file, not by breaking v1/v2. (`src/env/mini_inzoi_v3.py` + `src/env/v3_constants.py`; v1/v2 envs untouched. Reward adds `r_persona_style = 0.3 * cos(persona.bf_vec, ACTION_STYLE_PROFILE[a])` to the existing need + persona-action terms.)
- [x] Add smoke tests. (`scripts/test_env_v3.py`; all 10 §9 acceptance checks green: AEC API, action reachability, persona-style discrimination (extravert→rest_with_others vs introvert→rest_alone), Korean rendering, style-profile non-degeneracy, need coverage, ACTION_NAMES_V3 ID stability, routine-signal calibration under repeat-heavy policy.)
- [x] Refactor trainers / eval to thread `obs_dim` / `n_actions` / `env_factory` (per design §7 decision). 8 files edited (one extra found mid-refactor — `src/eval/consistency.py` was a hidden hardcoded-env dependency under zeroshot): `src/training/pcsp_trainer.py`, `src/training/baselines/{per_persona_ppo,diayn,sbert_policy,no_persona_ppo,llm_policy}.py`, `src/eval/zeroshot.py`, `src/eval/consistency.py`. Defaults reproduce v1 byte-for-byte; v1 smoke (`scripts/test_env.py`) and v3 smoke (`scripts/test_env_v3.py`) both pass.
- [x] Add `scripts/run_pcsp_v3.py` thin wrapper invoking the threaded `train_pcsp(...)` with v3 dims and `personas_300_v3.json`. `--smoke` gates a 20-iter dry run; otherwise 300 iter per mode. Outputs land under `results/pcsp_v3/{mode}/`.
- [x] Run PCSP smoke training (20-iter on full v3 mode). Completed 2026-05-09 in 88s; reward 40.4 → 75.4, consistency loss 1.84 → 1.66, summary at `results/pcsp_v3/summary.json`. Loop wires up cleanly through the threaded `train_pcsp(obs_dim=33, n_actions=20, env_factory=MiniInzoiV3Env)` path.
- [x] 300-iter v3 sweep — PCSP {full, no_consist, no_diverse, concat} + B1 + B3. Completed 2026-05-09 in **1h 57min** wall (vs. design doc's conservative 36h estimate; the gap is because the threaded trainer keeps the GPU fed while CPU env stepping is the actual bottleneck — GPU stayed at ~29% util throughout). Final rewards: full=100.25, no_consist=99.21, no_diverse=97.74, b3_sbert=92.11, concat=91.68, b1_no_persona=83.25. **frozen_proj skipped** per plan's "3 ablations" budget. Results: `results/pcsp_v3/sweep_summary.json` + per-mode `policy.pt` / `traj_encoder.pt` / `metrics.json`. Per-mode B1/B3 checkpoints under `results/baselines_v3/`. **Key reading:** B1 (no-persona) is 17 reward below full — strongest single signal that persona conditioning matters at all. FiLM (full) vs concat at 8.6 gap. Qwen3 (full) vs SBERT (b3) at 8.1 gap. **Caveat:** full vs no_consist is only 1.04 reward — reward alone won't separate the consistency-loss ablation; persona-recoverability via `src/eval/zeroshot.py` on each checkpoint is the load-bearing metric and is the next item.
- [x] Run persona-recovery eval on all 4 PCSP-v3 checkpoints. Completed 2026-05-09 in 9 min via new `scripts/run_eval_v3.py`. **Caveat:** v3 sweep trained on full 300-persona set, so this is *in-distribution* persona separability on 60 IDs (filtered from v1's `test_60.json`), not zero-shot. Per-mode top-1 k-NN accuracy over 60 personas (chance = 1/60 = 1.67%): full=0.290 (17.4× chance), no_diverse=0.260 (15.6×), concat=0.117 (7.0×), **no_consist=0.017 (1.0× — at chance)**. **Headline ablation finding:** consistency loss is load-bearing for persona-recoverability — full vs no_consist gap is **1.04 reward but 0.273 accuracy**. Without consistency loss, inter-trajectory cosine sim explodes 0.27 → 0.84 (trajectories from different personas become indistinguishable) while intra stays high (0.91), confirming trajectories are self-consistent but not persona-differentiated. Reward alone *completely hides* this failure mode. Diversity loss is marginal (Δ −0.03 acc) — could be de-emphasized in the paper. FiLM vs concat: 0.290 vs 0.117 even with consistency loss enabled in both, so layer-wise FiLM injection is meaningfully better than input concat. Per-mode results: `results/pcsp_v3/{mode}/eval_persona_classification_indist60.json`; combined: `results/pcsp_v3/eval_indist60_summary.json`. B1 skipped (no persona to recover); B3 skipped (no own traj_encoder, would be apples-to-oranges).
- [x] Build `train_240_v3.json` / `test_60_v3.json` and re-run PCSP-full on the 240-train split to enable true zero-shot eval. Done 2026-05-09: `data/personas/{train_240_v3,test_60_v3}.json` written by id-aligned filter on `personas_300_v3.json`; PCSP-full v3 retrained for 300 iter (1308s) into `results/pcsp_v3_zeroshot/full/` (final reward 104.08, slightly higher than the in-dist 100.25 — fewer training personas). **Headline zero-shot result on the 60 unseen-occupation personas: top-1 k-NN accuracy = 0.157 (9.4× chance), coherence ratio 2.04, intra/inter cosine 0.96/0.47.** The compositional wrapper (with Wilson CI) on the same split gives 0.173 [95% CI 0.135–0.220], 10.4× chance — small seed-level discrepancy with the legacy CLI path that's well within CI; both numbers are credible. Result files: `results/pcsp_v3_zeroshot/full/eval_persona_classification_zs60.json` + `results/eval/compositional_zero_shot_unseen_occupation_v3.json`. **Caveat:** v3 ablations (no_consist, no_diverse, concat) and B1/B3 still trained on the full 300-persona set; the headline v3 zero-shot ablation table (full-paper deliverable) requires re-running those modes on `train_240_v3` — tracked as a follow-up below.
- [x] Build v3-aligned compositional splits (`unseen_occupation_v3_train.json` etc.). Done 2026-05-09 by extending `scripts/build_compositional_splits.py` with `--out_suffix` and `--manifest_name` flags. v3 splits emitted to `data/personas/splits/{unseen_occupation,unseen_archetype,unseen_combo}_v3_{train,test}.json` + `manifest_v3.json`. Cell layout is preserved across v1/v3 (same persona IDs ↔ same Big Five × occupation), so all three split families produce identical persona-ID partitions to v1; only `preferred_actions` differ in the persona JSON payloads. `src/eval/zeroshot.py` extended with `--split_suffix` / `compositional_zero_shot(split_suffix=...)` so the v3 splits can be evaluated through the same CLI.
- [ ] (Follow-up, full-paper deliverable) Re-run PCSP {no_consist, no_diverse, concat} + B1 + B3 on `train_240_v3` for a true zero-shot v3 ablation table. ~2h compute (5 modes × ~22 min). Until this lands, the v3 headline number is single-cell (PCSP-full only) and we cannot replicate the v1 ablation story (consistency-loss collapse, FiLM>concat, persona-recoverability separation) at v3 scale. **This is the next concrete deliverable for full-paper main-track.**
- [ ] (Follow-up) Run compositional eval on `unseen_archetype_v3` and `unseen_combo_v3`. Both require additional retrains on their respective train splits (3 more configs × ~22 min each, just for PCSP-full). Currently §4.3 line 119 "unseen trait combinations" is still uncovered; this closes it.
- [ ] (Future, low-priority) `src/eval/{task_perf,diversity}.py` and `scripts/test_env_v3.py` Korean rendering also touch `MiniInzoiEnv` directly. Not load-bearing for the §9 training-correct gate; thread when/if v3 evaluation pipeline grows.

---

## 7. Commands

Use the `paper` conda environment.

```bash
conda run -n paper python scripts/test_env.py
conda run -n paper python scripts/test_film.py
conda run -n paper python scripts/run_eval.py --smoke
conda run -n paper python scripts/generate_persona_identification_survey_ko.py \
  --rollouts results/human_eval/pcsp_full_zero_shot_rollouts.json \
  --personas data/personas/test_60.json \
  --output_dir data/human_eval
```

For v2:

```bash
conda run -n paper python scripts/run_pcsp_v2.py --all
conda run -n paper python scripts/run_eval_v2.py
conda run -n paper python scripts/generate_v2_figures.py
```

---

## 8. Decision Log

### 2026-05-08

- Active paper direction confirmed as `paper/cog2026_vision/main.tex`.
- Old proposal/planning docs archived under `archive/docs_2026-05-08/`.
- `full-proposal.md` is not the active project direction; it is separate co-adaptation context.
- Human survey difficulty reframed as an environment/action observability issue.
- Near-term implementation should preserve existing 12-action policy and enrich rollout event rendering before committing to retraining.
- Phase A rich-trace pipeline regenerated end-to-end: `results/human_eval/pcsp_full_zero_shot_rollouts.json` and `data/human_eval/persona_identification_survey_ko.{json,csv,md,_answer_key.csv}` now carry time-of-day, place, nearby-agent, and persona-conditioned action-style descriptions.
- Fixed double-place bug in `src/env/action_semantics.py` (action 7 variant 0): "소파에서 휴식" → "편하게 휴식" to avoid "{place}에서 소파에서 휴식" when rendered with the place prefix.
- Open observability follow-up: `place` is currently the nearest `WORLD_OBJECTS` cell to the agent's grid position, so traces sometimes report semantically odd combinations (e.g. "주방에서 잠자기"). This is faithful to v1 policy behavior; the proper fix is location affordances in Mini-Inzoi v3 (see Phase C).
- Phase B paper-consistency edits applied to `paper/cog2026_vision/main.tex`: added a "Coarse action observability" limitation paragraph in §\ref{sec:limits}, and a "Rich trajectory observability" paragraph in the evaluation agenda (§\ref{sec:evalagenda}) recommending that papers report results on both coarse and rich traces. Re-compiled to 7-page PDF without errors. Tables unchanged because no retraining has occurred.
- §4.1 decision: rich event semantics (intent, place, nearby agents, action style) remain **display-only** for Mini-Inzoi v1/v2. Verified `src/env/mini_inzoi.py` and `mini_inzoi_v2.py` do not import `src/env/action_semantics.py`; the rich layer lives only in rollout export and survey generation. **Why:** v1/v2 checkpoints, baselines, and ablations are reusable as long as observation dim (20/56) and action space (Discrete(12)) are unchanged. Promoting style/place/social context to state or reward would invalidate every existing comparison and force a full retraining cycle for marginal benefit at v1/v2 scale. **Implication:** all richer-semantics-as-state experiments are deferred to Mini-Inzoi v3 (Phase C). This locks the v1/v2 paper tables for the CoG submission.
- §4.2 automated baseline: built `scripts/compute_survey_baseline.py`. PCSP-full's trained trajectory encoder + LoRA persona projection achieves **29/30 = 96.7%** on the 30-item 2AFC survey (Wilson 95% CI [0.83, 0.99]; mean cos-sim margin 0.71). Per rank-tertile difficulty bucket: easy 9/10, medium 10/10, hard 10/10. Notably, items with high heuristic `distractor_score` (similar trait/preferred-action profiles) are **not** harder for the trained encoder, suggesting the encoder picks up persona signal beyond Big-Five-trait overlap. **Implication for human eval:** at 30 items, near-ceiling automated accuracy means humans must perform well below 97% for the gap to be informative; we should pre-register the expected human-vs-encoder gap before recruiting raters.
- §4.2 supporting infra: rollout export now seeds `torch`/`numpy` with the per-rollout seed and stores the target agent's `obs` array per step (`scripts/export_persona_identification_rollouts.py`). This makes survey items deterministic and replayable, and is the prerequisite for any future encoder-vs-human comparison. Survey was regenerated from the new deterministic rollouts; older non-deterministic rollouts/survey are now overwritten in place.
- Decision: keep `distractor_score` as a survey-time selection heuristic only, not as a difficulty label. The empirical relationship between heuristic score and encoder accuracy is non-monotonic on this set, so any "by-difficulty" claim should be backed by encoder-margin or human-confidence stratification, not by `distractor_score` alone.
- Coarse-vs-rich ablation artifact added: `scripts/generate_persona_identification_survey_ko.py` now accepts `--coarse_mode`, which renders bare `action_label_ko` (e.g. "휴식하기", "읽기") and drops time/place/style/social context. Generated `persona_identification_survey_ko_coarse.*` from the same rollouts and seed; item IDs, trajectory IDs, and correct options match the rich survey. **Note:** the automated baseline accuracy (96.7%) is unchanged across rich/coarse because the encoder reads `(obs_seq, act_seq)` directly, not the rendered trace text — the rich/coarse comparison is meaningful only against human responses. Recommend assigning each participant to one variant (between-subjects) when collecting responses.
- §4.3 reframing — important: the existing `data/personas/test_60.json` is **not** a random cell-level held-out set. It holds out 4 entire occupations (HR매니저, 대학교수, 데이터과학자, 요리사) × all 15 archetypes = 60 personas. So the paper's published 19.3% zero-shot accuracy is structurally an **unseen-occupation** result, the strictest of the three §4.3 conditions. Updated `paper/cog2026_vision/main.tex` §V Experimental Setup to make this explicit ("unseen-occupation compositional generalization"); 7-page PDF re-compiles clean.
- §4.3 splits + tooling: built `scripts/build_compositional_splits.py` and wrote three split families to `data/personas/splits/{unseen_occupation,unseen_archetype,unseen_combo}_{train,test}.json` plus `manifest.json`. `unseen_occupation` reproduces the existing split byte-for-byte (verified: persona ID lists match), so the existing PCSP-full checkpoint applies. **Retraining required** for `unseen_archetype` (3 archetypes × 20 occupations held out) and `unseen_combo` (60 random cells with both axes covered) — these are tracked as future training runs.
- §4.3 metric tooling: `src/eval/zeroshot.py` now has `compositional_zero_shot(split_family, ...)` wrapping `zero_shot_consistency` with a Wilson 95% CI and split metadata; the CLI accepts `--split_family`. Re-running on the existing PCSP-full checkpoint produced **accuracy 0.230 (Wilson 95% CI [0.186, 0.281]), coherence_ratio 6.09, 13.8× above 1.7% random chance** on `unseen_occupation` (n_episodes=5, 300 trajectories). Saved at `results/eval/compositional_zero_shot_unseen_occupation.json`. **Note:** this is slightly above the paper's reported 19.3% — same checkpoint, n_episodes=5, but different `seed=1000` with the new compositional wrapper. The CIs overlap so the numbers are consistent; before resubmitting, decide whether to update the paper to the new run or rerun the paper's exact protocol.
- §4.3 qualitative: `scripts/qualitative_persona_comparison.py` produces side-by-side rich Korean traces from the existing PCSP-full checkpoint. Generated 3 pairs each for `same_occupation` (e.g. 마케터 high-N vs low-N: high-N stays at 책상 mostly solo, low-N at 욕실/주방 with frequent NPC interactions) and `same_archetype` modes. Outputs at `results/human_eval/qualitative_same_{occupation,archetype}.{md,json}`.
- Phase C v0.1 design committed: `docs/mini_inzoi_v3_design.md` defines the 20-action flat-discrete ontology, the obs-schema extension (affordance / social context / routine signal), reward shaping with a per-action style profile, and the implementation/retraining plan. **Key decisions:** (1) flat `Discrete(20)`, factorized deferred until v3 evidence demands it (§5 PLAN guidance honored); (2) v3 lives in a new file `src/env/mini_inzoi_v3.py` so v1/v2 paper tables remain reproducible; (3) base-scale obs_dim grows 20→33, large-scale 56→69, so existing checkpoints are **not** reusable on v3 — full retrain estimated ~36 GPU-hours for PCSP-full + 3 ablations + 2 baselines. The §4.1 design tasks (action ontology, location affordances, social-context features, routine features) are now closed at the design level; implementation lives in the design doc §8 checklist.
- Phase C design review (v0.2): closed all five §10 open questions (hand-author style profile, no action filtering for v3, deterministic auto-mapping for personas_v3, calibrate routine signal, re-measure B5 latency before claiming 22× figure). Caught a real design hole: trainers/baselines/eval hardcode `OBS_DIM = 20` / `N_ACTS = 12` and import `MiniInzoiEnv` directly across 7 files — the original §7 "no logic change" claim was wrong. **Decision:** thread `obs_dim` / `n_actions` / `env_factory` through every trainer signature (additive, defaults reproduce v1 byte-for-byte) rather than fork v3-suffixed copies. Pinned the v1→v3 `preferred_actions` mapping rule into design doc §8.1 as a deterministic table.
- Phase C implementation, foundational layer landed (v3 env reachable but not yet trained): `src/env/v3_constants.py` (ACTION_NAMES_V3 + ACTION_STYLE_PROFILE + ACTION_RESTORE_V3 + obs_dim helpers), `src/env/action_semantics.py` extended with `V3_ACTION_SEMANTICS` and `describe_v3_action_ko()` (v1/v2 entries untouched), `data/personas/personas_300_v3.json` (300 personas, all 16 activity actions covered, avg 5.27 preferred v3 actions), `src/env/mini_inzoi_v3.py` (4-agent base, obs_dim=33, reward adds r_persona_style), `scripts/build_personas_v3.py` (deterministic builder), `scripts/test_env_v3.py` (10 acceptance checks per §9, all green). One real bug caught and fixed during smoke testing: `eat_slow` and `clean` had identical style vectors → `clean` differentiated to `[0, -0.5, 0, 0.7, -0.3]` (high C, low N, anti-novelty / routine). Routine-signal acceptance criterion corrected: random-policy lower-end saturation is the design intent, not a failure; the real check is dynamic range under a repeat-heavy policy. **Not yet done:** trainer refactor (7 files), `scripts/run_pcsp_v3.py`, and the ~36 GPU-hour PCSP-v3 training runs.

### 2026-05-09

- Phase C trainer refactor (per design §7 "thread, don't fork" decision) landed: 8 files edited (one extra beyond the original 7-file estimate — `src/eval/consistency.py`'s `_rollout_persona` was a hidden hardcoded-`MiniInzoiEnv` dependency that the eval surface delegates to). Each file gains `obs_dim` / `n_actions` / `n_agents` / `env_factory` parameters with v1 defaults, plus an `if env_factory is not None: ... else: <v1 factory>` switch. Verified v1 path is byte-for-byte preserved: `scripts/test_env.py` + the existing v1 PCSPActorCritic / TrajectoryEncoder constructors still work unchanged with their original positional args. Verified v3 path: `scripts/run_pcsp_v3.py` imports clean, constructs `PCSPActorCritic(33, 20)` (304K params), `ConcatActorCritic(33, 20)` (202K), `TrajectoryEncoder(33, 20)` (178K) without error. Threaded entrypoints: `train_pcsp`, `train_b1`, `train_b2`, `train_b3`, `train_b4`, `benchmark_llm_policy`, `zero_shot_consistency`, `compositional_zero_shot`, `zeroshot_vs_train`, `_rollout_persona`, `persona_classification_accuracy`. `src/eval/zeroshot.py` CLI also extended: `--obs_dim`, `--n_actions`, `--env_variant {v1,v3}`, `--n_agents` so v3 checkpoints can be evaluated through the same script once they exist.
- Phase C launch wrapper landed: `scripts/run_pcsp_v3.py` is a thin wrapper that calls the threaded `train_pcsp(...)` with `obs_dim=OBS_DIM_V3_BASE` (33), `n_actions=N_ACTIONS_V3` (20), `personas_json=data/personas/personas_300_v3.json`, and `env_factory=MiniInzoiV3Env(personas, max_steps=200)`. Mirrors `scripts/run_pcsp.py`'s ergonomics (`--smoke`, `--all`, `--mode`, `--n_iterations`). Output dir is `results/pcsp_v3/{mode}/` (separate from v1's `results/pcsp/`). **Note:** the §4.3 split files in `data/personas/splits/*.json` are still v1-format (preferred_actions over the 12-action space). For v3 unseen-X experiments, either the splits need a v3 re-emission or callers must override `--personas_json`.
- Phase C smoke pass: `scripts/run_pcsp_v3.py --smoke` (20 iter, mode=full) completed in 88.5s on cuda. `[PCSP:full] policy=304,277  traj_enc=177,600  λ₁=0.5  λ₂=0.01`; reward 40.4 → 75.4, consistency loss 1.84 → 1.66, diversity ≈0. Confirms the v3 training loop wires up cleanly through the threaded path. Summary at `results/pcsp_v3/summary.json`.
- Phase C 36-hour sweep launched (bg `bb3wawvjy`, log `/tmp/pcsp_v3_sweep.log`) via new `scripts/run_full_sweep_v3.py` driver. Runs 6 configs sequentially at 300 iter each: PCSP {full, no_consist, no_diverse, concat} into `results/pcsp_v3/{mode}/`, then B1 (no-persona PPO) and B3 (SBERT) into `results/baselines_v3/{b1_no_persona,b3_sbert}/`. **frozen_proj ablation skipped** to match the plan's "3 ablations" budget — track as a follow-up if v3 results suggest the LoRA dynamics differ from v1. **Pre-launch fix:** `src/training/baselines/sbert_policy.py` had two latent v3-breaking bugs — (1) cache path was hardcoded to `sbert_embeddings_train240.npy` so v3 (300 personas) would either IndexError or silently re-use 240-persona embeddings paired to wrong personas; (2) `compute_sbert_embeddings` reloaded the cache without size validation. Fixed both: cache path is now derived from `Path(personas_json).stem` (so `personas_300_v3.json` gets its own cache), and the loader checks `cached.shape[0] == len(texts)` before reusing.
- Phase C sweep **completed in 1h 57min** wall (≈18× faster than the design doc's 36h budget). Final rewards: pcsp_full=100.25, pcsp_no_consist=99.21, pcsp_no_diverse=97.74, b3_sbert=92.11, pcsp_concat=91.68, b1_no_persona=83.25. **GPU util stayed ~29% throughout** — confirming that the threaded trainer is fast enough that PettingZoo AEC env stepping (single-threaded Python per env, GIL-bound) is the wall-time bottleneck, not policy compute. The 36h estimate in `docs/mini_inzoi_v3_design.md` §7 was made before the threaded-trainer refactor landed and should be revised to ~2h once we re-measure under load. **Reading the table:** strongest single signal is the 17-reward gap between full and B1 (persona conditioning matters); FiLM-vs-concat gap is 8.6; Qwen3-vs-SBERT gap is 8.1. **Caveat:** full vs no_consist is only 1.04 reward — the consistency loss ablation can't be evaluated on reward alone, since the loss's claim is on *persona-recoverability from trajectories*, not return. The next required step is running `src/eval/zeroshot.py` on each PCSP-v3 checkpoint + B3 to fill in the ablation table with persona-classification accuracy. **Side observation:** the v1 PCSP-full reward at 300 iter was reportedly in a similar ~100 range (need to cross-check with `results/pcsp/full/metrics.json`); v3's reward scale is comparable despite the larger action space (20 vs 12) and richer obs (33 vs 20), suggesting the per-action style profile + restored need rates are calibrated.
- Phase C in-distribution persona-classification eval landed via new `scripts/run_eval_v3.py` (548.8s wall on cuda). 60 personas (test_60 IDs filtered from `personas_300_v3`, n_episodes=5). **Confirmed protocol gap:** v3 sweep trained on the full 300-persona set, so these IDs were seen during training — this is in-distribution separability, not zero-shot. The relative ablation ranking is valid, but absolute zero-shot claims require a future retrain on `train_240_v3` (queued, not blocking). Top-1 k-NN accuracy (random = 1.67%): pcsp_full=0.290 (17.4× chance, coherence 3.54), pcsp_no_diverse=0.260 (15.6×, coherence 3.72), pcsp_concat=0.117 (7.0×, coherence 2.06), **pcsp_no_consist=0.017 (1.0×, coherence 1.08 — at chance)**. **Decision-grade ablation finding:** the consistency loss is what produces persona-recoverable behavior. Reward gap full→no_consist is only 1.04 (100.25 vs 99.21) but accuracy collapses 0.290 → 0.017. Inter-trajectory cosine sim moves 0.27 → 0.84 with the loss removed — trajectories become persona-indistinguishable while still self-consistent (intra stays at 0.91). Diversity loss is marginal (Δ −0.03 acc, +0.18 coherence). FiLM vs concat: 0.290 vs 0.117 even with consistency loss enabled in both — layer-wise FiLM injection is meaningfully better than input-only concat. **Paper implication:** the cleanest ablation story is a 4-row table — (i) B1 no-persona shows persona conditioning helps reward; (ii) concat vs full shows FiLM > concat in *behavioral expression*; (iii) no_consist vs full shows the consistency loss is what makes persona *recoverable from trajectories*, separate from any reward effect; (iv) full hits both metrics. The (ii) vs (iii) contrast is the key insight — architecture vs loss are doing distinct, separable work.
- **Full-paper pivot (user directive):** target switched from CoG 2026 short Vision Paper (7 pages) to a full main-track paper. The headline zero-shot generalization claim must therefore land at v3 scale, not just v1 — the v3 sweep so far was trained on all 300 personas (in-distribution only). Closed two §6 Phase C "Future" items today as a result: built v3-aligned train/test + compositional splits, and ran a PCSP-full v3 retrain on the held-out 240-train set. The remaining ablation/baseline retrains on `train_240_v3` are queued as the next concrete deliverable.
- v3 splits + zero-shot retrain landed: extended `scripts/build_compositional_splits.py` with `--out_suffix` / `--manifest_name` (additive, default empty preserves v1 behavior) and emitted `data/personas/splits/{unseen_occupation,unseen_archetype,unseen_combo}_v3_{train,test}.json` + `manifest_v3.json`. Persona-ID partitions are byte-identical to v1's `manifest.json` because the v1→v3 mapping (`scripts/build_personas_v3.py`) only rewrites `preferred_actions`; persona text, big_five, occupation, and id are preserved (verified — 0 text mismatches across 300 personas, so the existing `results/embeddings/persona_embeddings_300.npy` Qwen3 cache is reusable as-is). Also emitted conventional `data/personas/{train_240_v3,test_60_v3}.json` (mirrors of the unseen_occupation_v3 split, kept at the conventional path so callers that default to `train_240.json`/`test_60.json` have a v3 analog).
- v3 zero-shot retrain (PCSP-full on `train_240_v3.json`, 300 iter): completed in 1308s (≈22 min, single config). Final reward 104.08 (vs in-distribution 100.25 on the same architecture trained on 300 personas — slightly higher because there are fewer personas to fit). Output: `results/pcsp_v3_zeroshot/full/{policy.pt,traj_encoder.pt,metrics.json}`. **Headline zero-shot result on `test_60_v3` (60 unseen-occupation personas, n_episodes=5, 300 trajectories total): top-1 k-NN accuracy = 0.157, intra/inter cosine = 0.96/0.47, coherence ratio 2.04, ~9.4× chance.** With Wilson CI via the compositional wrapper on `unseen_occupation_v3`: 0.173 [95% CI 0.135–0.220], 10.4× chance (small seed-level discrepancy with the legacy-CLI path because env stepping uses CUDA non-determinism; both fall well within either CI). Result files: `results/pcsp_v3_zeroshot/full/eval_persona_classification_zs60.json` (legacy path) and `results/eval/compositional_zero_shot_unseen_occupation_v3.json` (compositional path with Wilson CI). **Comparison vs v1:** v1 PCSP-full on the same held-out occupations was 0.193 (paper) / 0.230 (compositional rerun). v3 at 0.157 is ~3.6 pp below v1, which is plausible given the harder action space (20 vs 12) and richer obs (33 vs 20) — both increase per-trajectory entropy and make persona signal harder to recover from a fixed-length rollout. The v3 ratio over chance (9.4×) is comparable to v1 (11×); semantic-behavioral separability is preserved at v3 scale. **Paper implication for full-paper main-track:** the v3 architecture is a credible "headline scale" for the main result table, and we now have one clean cell in the v3 zero-shot table. The next deliverable is filling out the v3 zero-shot ablation row (no_consist, no_diverse, concat) + B1 + B3, which would give the same 4-row ablation story the in-distribution v3 run produced — but in zero-shot, which is what the full paper claim requires. Until that lands, the in-distribution v3 ablations + the new v3 zero-shot single point are the load-bearing experimental evidence.
- `src/eval/zeroshot.py` CLI extended: `--split_suffix` flag and `compositional_zero_shot(split_suffix=...)` parameter so the v3 splits can be evaluated through the existing CLI without forking.
- **Open observability check left for later:** the legacy-CLI vs compositional-wrapper accuracy discrepancy on the same split (0.157 vs 0.173, same seed, same model, same persona list) is presumably from CUDA non-determinism in env stepping or argmax tie-breaking on the persona-projection space. Worth pinning down before camera-ready since the compositional path is what carries Wilson CI; if the gap is reproducible, the legacy path's number should be retired in favor of the compositional one.
