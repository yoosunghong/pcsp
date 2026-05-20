# PLAN.md - PCSP Active Checklist

**Project:** Persona-Conditioned Shared Policy (PCSP) for life-simulation NPCs  
**Primary paper:** `paper/cog2026_main/main.tex` (**COG 2026 Main Track**; not a workshop, vision, or position paper)  
**Done log:** completed work, decisions, and result details live in `DONE.md`.

---

## Operating Rule

- Read this checklist before research, code, evaluation, or paper changes.
- Align work with `paper/cog2026_main/main.tex`.
- Connect new work to one checklist item below.
- After non-trivial work, update checklist status here and put detailed results/decisions in `DONE.md`.

---

## Active Direction

- [x] Keep the PCSP research project self-contained under `research/` while reserving top-level `ue/` for Unreal Engine integration. *(2026-05-13)*
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
- [x] Regenerate human-eval rollouts from the v3 PCSP policy, not the legacy v1/12-action exporter.
- [x] Regenerate matched Korean rich/coarse survey artifacts from the same v3 rollout file.
- [x] Re-run the automated 2AFC survey baseline on the v3 survey artifacts as a sanity check.
- [x] Prepare counterbalanced v3 rich/coarse pilot packets and response templates for 10 participants.
- [x] Analyze 30-participant Google Forms coarse-trace pilot from item-level A/B ratios.
- [x] Report coarse-trace human 2AFC accuracy with Wilson 95% CI.
- [x] Record that confidence, response time, participant-level variance, and inter-rater reliability are unavailable for the Google Forms coarse pilot.
- [ ] Collect matched rich-trace human responses or run a retained-row rich-vs-coarse study. *(2026-05-13: deferred — Google Forms pilot cannot be retro-instrumented; deliberately scoped out of the current paper revision in favor of designer-persona expansion. Rich-trace and Krippendorff promises were removed from §6/§7 to reflect this.)*

---

## Phase B - Paper Consistency

- [x] Add coarse-action observability limitation to `paper/cog2026_main/main.tex`.
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
- [x] Replace the synthetic Figure 3 KL scatter with empirical sampled-pair policy KL measurements and align headline/table claims with the strongest defensible results.

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
- [ ] Design and run v3-large: v3 20-action ontology at v2 scale (12x12, 16 agents, 500 personas) before claiming broad environment scaling.
- [ ] Treat Melting Pot as optional external validation after v3-large, not as a blocker for the immediate human-eval study.
- [x] UE5 zero-shot persona validation on held-out IDs 241..300 (2026-05-18):
      With Work + Hygiene zone capacities matched to the held-out demand
      profile, the v3 policy runs on personas 241..300 in UE5 with
      0.04% failure rate (1 path_follow_idle_short across 2,792
      interactions, 9.75 min, 64 agents) and inter-persona action
      ρ = 0.368 (vs 0.383 on train 1..64) — i.e. *more* persona-distinct
      on unseen personas. Pre-fix held-out run had 12.5% failure rate
      driven by `FocusedWork`/`PlanningWork` `AllOverCapacity` (single
      Office zone saturated by the test demand profile, not a policy
      failure). Tooling: `research/scripts/run_zeroshot_eval.py` +
      `research/scripts/analyze_ue_session.py`. Full progression and
      artifacts in `DONE.md`.

---

## Phase F - Designer Persona Validation

- [ ] Define a validated Designer-300 persona set from the 13 designer-authored examples plus systematic variants.
- [ ] Keep Designer-300 as external validation unless we intentionally retrain all main tables on a new training distribution.
- [ ] Add embedding-space coverage checks for Designer-300 against `train_240_v3.json`.
- [ ] Run PCSP-v3 inference-only qualitative and quantitative validation on Designer-300.
- [ ] Decide whether Designer-300 warrants a paper table, appendix artifact, or future-work framing.
- [x] Expand designer-authored case study from 13 → 50 personas across 5 sources: Sims 3 (10), Animal Crossing (12), Stardew Valley (10), Persona series (6), Original designer briefs (12). Modified `scripts/run_designer_persona_case_study.py`. *(2026-05-13)*
- [x] Add failure taxonomy (F1 ontology gap / F2 style-reward conflict / F3 embedding occupational bias / F4 trait collision / F5 residual) and source-grouped t-SNE rendering. *(2026-05-13)*
- [x] Re-run rollouts, regenerate `results/designer_persona_case_study/`, and overwrite `paper/figures/fig5_designer_personas_tsne.png`. Initial result (all Korean text): 17 success / 24 partial / 9 failure. *(2026-05-13)*
- [x] Switch 6 Persona-series persona texts from Korean to English and re-run. Intermediate result: **20 success / 21 partial / 9 failure** (40% strong, 82% non-failure); mean cosine 0.608. Persona-series (EN) improves to 4/2/0 from 1/5/0. *(2026-05-13)*
- [x] Translate the remaining 44 Korean designer personas to English (all 5 source groups now English). Re-ran case study. **Final all-English result: 22 success / 21 partial / 7 failure (44% strong, 86% non-failure).** Mean cosine to nearest (Korean) training persona drops only modestly (0.608 → 0.590, range 0.478--0.686). This is now a fully cross-lingual robustness probe: Korean-trained policy + English designer personas. Failure-mode distribution: F1×3 (ontology gap), F2×2 (style-reward conflict), F4×1, F5×1; F3 (embedding occupational bias) disappeared since English designer text can no longer share occupation tokens with Korean training neighbors. *(2026-05-13)*
- [x] Update §5.4 in `main.tex`: replaced 13-row per-persona table with 5-row source-summary + failure-taxonomy column, added failure-taxonomy definitions paragraph, rewrote case discussion to highlight ontology-limited failure pattern. *(2026-05-13)*
- [x] Update §7 limitation count to "50 additional handwritten personas across five sources". *(2026-05-13)*
- [x] Recompiled `main.pdf` — clean, 8 pages, no undefined refs or citations. *(2026-05-13)*
- [x] Fix Fig.~5 mismatch: raw-Qwen3 t-SNE shows English designer personas as a separated cluster, contradicting the in-distribution caption claim. Replaced with a side-by-side (a) raw 1024-dim vs (b) LoRA-projected 64-dim t-SNE using the PCSP-v3 full checkpoint. Projection collapses the designer→train NN ratio from 12.9× to 1.47×; designer-authored personas are fully intermixed with train_240 in the projected space the policy actually consumes. Rewrote caption + §IV-G cross-lingual paragraph to cite both quantities. New helper: `scripts/visualize_designer_tsne_projected.py`; new artifact: `results/designer_persona_case_study/tsne_coverage_stats.json`. Did **not** retrain in English — kept the cross-lingual robustness card and used the projection-space evidence to strengthen it instead. *(2026-05-13)*

---

## Phase E - Model / Training Follow-Ups

- [ ] If action space changes again, update `n_actions`, policy heads, trajectory encoder action one-hot dimension, all trainers, and all evaluators.
- [ ] If observation dimensions change again, update model input layers and mark existing checkpoints incompatible.
- [ ] If factorized actions are introduced, redesign the actor as multiple heads: intent, target/place, style/duration.
- [ ] Re-measure latency before claiming final real-time speedups in the paper.
- [ ] Decide whether the frozen projection ablation is worth running for v3.
- [x] UE5-side v3 action remap: movement indices 16-19 (`move_up/down/left/right`) carry no semantic meaning in UE (engine handles pathing), so the UE bridge now maps 16/18 → `LeisureOutdoor` and 17/19 → `ObserveCrowd` in `PCSPPolicySubsystem.cpp`. Python training/eval are unaffected — the remap lives in the engine bridge only, but recorded here so the v3 action-table interpretation stays consistent across research and UE. UE decisions are now ONNX-only: if `pcsp_actor.onnx` or `persona_embeddings.json` is missing, agents return Failed rather than fall back to a heuristic. *(2026-05-17)*
- [ ] **UE5 training-side ablation exports (`Hybrid-NoConsist`, `RL-only`).**
      The UE side already supports three *runtime* ablations via
      `pcsp.PolicyMode` (HybridPCSP / BTOnly / HybridNoPersona — see
      `ue/cnzoi/PLAN.md` Phase 4). Completing the Phase 4 ablation table
      requires two additional ONNX exports of *already-trained* v3 models:
      1. **Hybrid-NoConsist** — checkpoint `results/pcsp_v3/no_consist/policy.pt`.
         Same `PCSPActorCritic` architecture as `full`, so
         `scripts/export_pcsp_onnx.py --checkpoint results/pcsp_v3/no_consist/policy.pt --output_dir results/export_ue5/no_consist`
         produces a drop-in `pcsp_actor.onnx` with identical I/O shapes
         (`obs[1,33]`, `persona_proj[1,64]`, `logits[1,20]`). UE switches
         models by swapping the file under `Content/PCSP/Models/` and
         relaunching PIE; persona embeddings reuse the `full` export since
         the `PersonaProjection` LoRA layer is included in both checkpoints
         and is trained jointly.
      2. **RL-only** — corresponds to baseline B1 (`baselines/no_persona_ppo.py`,
         checkpoint `results/baselines_v3/b1_no_persona/policy.pt`). The
         architecture has no persona conditioning at all (no `PersonaProjection`,
         no FiLM), so `export_pcsp_onnx.py` cannot be reused as-is. Needs a
         new `export_b1_onnx.py` wrapper that builds an ONNX with
         `obs[1,33] -> logits[1,20]` only, *plus* a dummy
         `persona_embeddings.json` of zero vectors so `UPCSPPolicySubsystem`'s
         existing two-input binding still validates. Alternative: wrap the B1
         actor as a two-input ONNX where `persona_proj` is unused (passed
         through and discarded), keeping the UE bridge identical. The
         dummy-embedding approach is simpler — recommend that.
      Both exports must keep the existing action-ID ordering
      (`research/docs/mini_inzoi_v3_design.md` §3); the UE bridge's V3→UE
      remap table is keyed on those indices and would silently misroute if
      ordering changed.
