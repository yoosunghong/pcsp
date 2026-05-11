# DONE.md - PCSP Work Log and Results

This file holds completed work details, decisions, result paths, and experiment notes. `PLAN.md` is the compact active checklist.

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

- Confirmed the active direction as the PCSP paper in `paper/cog2026_vision/main.tex`.
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

- Updated `paper/cog2026_vision/main.tex` to shift the central claim from "FiLM > concat" to "InfoNCE consistency loss is load-bearing; conditioning architecture is secondary and split-dependent."
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

- Updated `paper/cog2026_vision/main.tex` to mention the unseen-combo result in the architecture paragraph.
- Standardized paper claims on the v3 zero-shot eval-driver/compositional ablation summaries, not the legacy CLI-only `test_60_v3` number.
- The unseen-combo result is reported as FiLM higher in point estimate but not statistically separated from concat because Wilson intervals overlap.
- Recompiled `paper/cog2026_vision/main.pdf`: clean 7-page PDF.
- Remaining warnings are the same minor layout warnings seen before this update: one underfull intro paragraph, one 8.3pt overfull LoRA equation line, and one bibliography underfull hbox.

---

## Stable Decisions

- Rich semantics remain display-only for v1/v2.
- v3 uses flat `Discrete(20)` actions.
- v3 checkpoints are incompatible with v1/v2 because action and observation dimensions changed.
- The InfoNCE trajectory consistency objective is the central load-bearing component.
- Conditioning architecture is a tunable, split-dependent design choice rather than the main claim.
- Diversity loss should be presented as a useful regularizer, not as a co-equal contributor to zero-shot persona identification.
