# PREREG.md — H4 Persona-Edit Controllability Pre-Registration

**Status:** Pre-registration committed before any persona-edit runs.
**Date:** 2026-05-15.
**Owner:** PCSP/MeltingPot project.
**Cross-references:** `MELTINGPOT_PROPOSAL.md` §3 H4, `MELTINGPOT_RESEARCH_QUESTIONS.md` E1–E3, `MELTINGPOT_PLAN.md` §Phase 3 Controllability.
**Required by:** `MELTINGPOT_PLAN.md` §Validation; `PHASE5_REPORT.md` §12.9 priority 2.

---

## 1. Hypothesis (H4)

> Editing persona text in a semantically interpretable direction produces signed shifts in substrate-defined social-outcome metrics consistent with the edit direction, under matched environment seeds and matched co-player composition, with effect sizes that survive multiple-testing correction.

### Primary claim (binomial)

Across the pre-registered set of 30 (persona × edit) pairs evaluated on their primary substrate, the fraction of pairs whose signed effect agrees with the predicted direction exceeds the 0.5 chance line with a binomial 95 % CI lower bound strictly above 0.5.

### Secondary claim (per-edit effect sizes)

Per-pair Cohen's d on the substrate's primary social-outcome metric, bootstrap-CI'd over matched seeds, with Benjamini–Hochberg FDR control at q = 0.10 across the 30 pairs.

### Failure modes (named in advance)

- **F1 (null):** Sign agreement at chance, FDR-adjusted significant pairs ≤ 2/30. Reading: text edits are not a causal control surface.
- **F2 (coarse surface):** Sign agreement above chance (≥ 0.65) but FDR-significant pairs ≤ 5/30. Reading: persona is an average-direction surface, not a per-edit-reliable one.
- **F3 (encoder-only):** Random-magnitude-matched embedding perturbations (control C1 below) reproduce the same sign agreement. Reading: any effect is encoder-geometric, not semantic.

---

## 2. Frozen artifacts

The following are frozen at pre-registration time and will not change:

- **Persona corpus:** `research/meltingpot/personas/personas_v0.json` (12 personas, splits {train: 10, heldout: 2}).
- **Embedding source:** `results/embeddings/persona_emb_qwen_emb.pt` (Qwen3-Embedding-0.6B, used in PHASE5_REPORT §1 onward).
- **Training configuration:** `scripts/run_phase5_qwen_anchor.py --mode infonce` for cH, `scripts/run_phase5_pd_anchor.py --pool full` for PD, `scripts/run_phase5_stag_anchor.py --pool full` for stag. 1 M env-steps, InfoNCE-only.
- **Co-player composition:** matched per-(substrate, seed) — every (base, edited) pair runs the *same* co-player persona assignments under the same env seed.

Any post-registration change to the above invalidates the test and must be documented as an amendment with a new pre-registration timestamp.

---

## 3. Edit axes and predicted-direction rubric

Five edit axes, each with two polarities (positive / negative), applied to a subset of the 10 training personas. An edit is the addition or replacement of one phrase in the persona's `description` field; `tags`, `tendencies`, and `action_prior` are *not* modified. Edits are derived from `MELTINGPOT_RESEARCH_QUESTIONS.md` E1/E2 axis prominence.

| axis | + polarity addition | – polarity addition | primary metric (cH) | primary metric (PD/stag) |
|---|---|---|---|---|
| A1 Cooperativeness | "shares resources with strangers" | "refuses to share with strangers" | apple-share rate to non-self | cooperate-action frequency |
| A2 Aggression | "frequently zaps competitors" | "avoids zapping under any circumstance" | per-step zap rate | retaliation latency (steps) |
| A3 Risk tolerance | "enters contested high-yield zones without hesitation" | "stays away from contested zones" | contested-tile residency | stag-action frequency (risky payoff) |
| A4 Patience | "waits for apples to mature before harvesting" | "harvests apples regardless of maturity" | unripe-harvest rate (inverse-signed) | turn-taking index |
| A5 Sociability | "stays close to other agents" | "keeps maximum distance from other agents" | mean nearest-neighbour distance (inverse-signed) | proximity-conditional cooperation |

**Predicted-direction signs** are committed in `PREREG_EDITS.json` (Section 6) at the granularity of (persona_id, axis, polarity).

---

## 4. Substrates and primary metrics

Three substrates from PHASE5_REPORT, each with one *frozen primary* social-outcome metric. Secondary metrics are reported but not used for the binomial test.

| substrate | primary social-outcome metric | rationale |
|---|---|---|
| `commons_harvest__open` | per-episode unripe-harvest rate (fraction of apple-picks on tiles whose regrowth timer < threshold) | most prominent CPR sustainability signal; engages A1, A4 directly |
| `prisoners_dilemma_in_the_matrix__repeated` | per-episode cooperate-action frequency | direct PD action-channel signal; engages A1, A3 |
| `stag_hunt_in_the_matrix__repeated` | per-episode stag-action frequency | risky-payoff coordination signal; engages A1, A3 |

cH is the primary-test substrate; PD and stag are used for E3 cross-substrate transfer (Section 7).

---

## 5. Experimental protocol

### 5.1 Matched-seed comparison

For each (persona, edit) pair:

1. **Base run:** 1 M-step PCSP-InfoNCE training with the unedited persona corpus, on `cH`, with seed s.
2. **Edited run:** identical training, with the persona's `description` field replaced by the edited text, on `cH`, with the same seed s. Co-player persona assignment is reproduced from base via `--persona-assignment-seed`.
3. **Evaluation:** identical OOD eval pass (`scripts/run_phase4_ood_eval.py`) on both checkpoints, then compute the primary metric over the same 1024-step eval rollout window.
4. **Effect:** `Δ = metric(edited) − metric(base)`. Predicted sign for the (persona, axis, polarity) tuple is committed in `PREREG_EDITS.json`.

Seeds: s ∈ {1, 2, 3} per pair (matched bootstrap CIs feasible with 3-seed paired samples; see PHASE5_REPORT §12 precedent).

### 5.2 Sample size

- **30 (persona, edit) pairs** on cH primary substrate. Approximate composition: 6 personas × 5 axes = 30. The 6 personas are drawn from the 10-persona train split, selected for tag diversity (one persona per dominant tendency cluster).
- **10 of those pairs** replicated on PD and stag for E3 cross-substrate transfer.
- Total: 30 + 10 + 10 = 50 (persona, edit, substrate) cells. Each cell = 3 seeds × 2 conditions (base, edited) = 6 runs. Total runs: 300. At ~5 min/run, ~25 GPU-hours (BUDGET §H4).

### 5.3 Controls

- **C1 (encoder ablation, F3 test):** For 10 randomly drawn pairs, replace the edited-text embedding with `base_embedding + ε` where `ε` is sampled from a Gaussian with covariance matched to the empirical (edited − base) embedding-shift distribution. If C1's sign agreement ≥ the semantic edits' sign agreement, declare F3.
- **C2 (held-out-only edit):** Apply the same edits to the 2 held-out personas (`fast_mover`, `spinner`). Reports controllability on personas the model never saw during training.

---

## 6. Frozen edit list

The full pre-registered (persona_id, axis, polarity, predicted_sign, primary_metric) table is committed alongside this document as `research/meltingpot/PREREG_EDITS.json` at the same git commit as PREREG.md. Any change to that JSON after the commit invalidates the corresponding rows of the test.

The 30 cH primary-substrate pairs span:
- 6 personas: `cooperative_sustainer`, `selfish_harvester`, `aggressive_zapper`, `cautious_observer`, `reciprocator`, `territorial_defender`
- 5 axes × 2 polarities = 10 edits, but each persona receives only 5 polarities (the polarity that *contradicts* its dominant tag, so signed predictions are non-trivial)

---

## 7. Cross-substrate transfer (E3)

For the 10 (persona, edit) pairs replicated on PD and stag, compute the Pearson correlation of signed effect sizes across substrate pairs:
- corr(cH, PD), corr(cH, stag), corr(PD, stag).
- Pre-registered threshold for E3 success: ≥ 2 of 3 correlations ≥ 0.5 with 95 % bootstrap-CI lower bound > 0.

---

## 8. Statistical plan

- **Primary test:** binomial test on 30 cH-primary pairs against p₀ = 0.5, two-sided, with a 95 % Clopper–Pearson CI. Reject H₀ if lower CI bound > 0.5.
- **Effect-size test:** paired bootstrap CI per pair (10 000 resamples) on `Δ`; BH-FDR at q = 0.10 across the 30 pairs.
- **Control tests:** C1 binomial reported next to the primary; F3 declared if C1 sign-agreement ≥ primary sign-agreement.
- **No HARKing:** the predicted sign per pair is the sign committed in `PREREG_EDITS.json` at this commit. Any post-hoc re-signing invalidates that pair.

---

## 9. Out of scope

- Multi-axis composite edits (registered separately if H4 single-axis succeeds).
- Persona-edit ablations on H5 Pareto-frontier substrates.
- Edits that change `action_prior` numerically — that is a different intervention class (action-prior controllability) and is registered separately.

---

## 10. Amendment log

Any change after the initial commit must be logged here with date, change, and justification. An amendment dated after the first H4 run invalidates the rows it touches.

- 2026-05-15 — Initial registration. No prior H4 runs exist in `research/meltingpot/runs/`.
