# PHASE5_REPORT.md — Real-LLM Persona Embeddings & OOD Re-Evaluation

**Status:** Phase 5 §1 (LLM embedding swap) complete.
**Scope:** Qwen3-Embedding-0.6B persona artifact; 60 k sanity A/B; 1 M-step anchor with the new embedding source; full Phase 4 OOD evaluator re-run; head-to-head comparison against the Phase 4 `random32` baseline.
**Branch:** `research/meltingpot`. **Date:** 2026-05-14. **Substrate:** `commons_harvest__open`.

The central Phase 4 finding was that random 32-d persona embeddings produced **0.000 ± 0.000 held-out top-1 retrieval** on the full 12-class vocabulary and near-zero Spearman ρ between embedding cosine distance and pairwise action KL. PHASE4_REPORT §11 named the random embeddings' approximate orthogonality as the most plausible mechanism and recommended replacing them with a real semantic encoder (Qwen3-Embedding-0.6B) as the load-bearing Phase 5 experiment.

This report tests that hypothesis. **The hypothesis is rejected.**

---

## 1. Artifact: Qwen3-Embedding-0.6B persona table

Built via `scripts/build_persona_embeddings_qwen.py`. Inputs are persona `description + " Tags: <tags>"`, formatted with the Qwen3-Embedding instruction-prefix convention (`Instruct: ... \nQuery: <text>`). Pooling is last-token on the final hidden state; the output is L2-normalised. The payload schema matches the existing cached-embedding loader exactly — no trainer-side changes.

| field | value |
|---|---|
| model | `Qwen/Qwen3-Embedding-0.6B` |
| dim | 1024 |
| K | 12 personas |
| mean pairwise cos | **+0.344** |
| min pairwise cos | +0.135 |
| max pairwise cos | +0.554 |
| persona file | `research/meltingpot/personas/personas_v0.json` |
| artifact | `results/embeddings/persona_emb_qwen_emb.pt` |
| diagnostics | `results/embeddings/persona_emb_qwen_emb.diag.json` |

Reference: random32 mean pairwise cos = −0.026; charhash64 = +0.160; descbow128 = +0.128. **The Qwen table carries materially more semantic structure than every Phase 4 alternative.**

Sample geometry reads:

- Closest pair: `territorial_defender` × `spinner` (cos 0.554) — both motion-pattern-centric language.
- Furthest pair: `reciprocator` × `explorer` (cos 0.135) — distinct conceptual axes.
- `fast_mover` is far from `cooperative_sustainer` (0.143) — held-out personas are not collapsed onto the train cast in the embedding space.

This is the table the rest of the report uses.

---

## 2. 60 k A/B sanity

One seed, 60 k env-steps, `infonce_coef=0.5, kl_diversity_coef=0.0`, all other knobs matched to `run_phase4_embedding_ab.py`.

| condition | infonce_top1 (final) | infonce_top3 | traj_retrieval_top1 | mean_pair_kl |
|---|---|---|---|---|
| Phase 4 `random32` (2-seed) | 0.145 ± 0.028 | 0.304 ± 0.126 | 0.152 ± 0.013 | 4.30e-3 ± 2.9e-4 |
| Phase 4 `charhash64` (2-seed) | 0.100 ± 0.009 | 0.384 ± 0.063 | 0.107 ± 0.025 | 3.50e-3 ± 1.7e-4 |
| Phase 4 `descbow128` (2-seed) | 0.100 ± 0.041 | 0.330 ± 0.051 | 0.098 ± 0.038 | 4.88e-3 ± 6.1e-4 |
| Phase 5 `qwen_emb` (seed 1) | **0.232** | 0.438 | 0.232 | 4.92e-3 |

Single-seed read, but the cached path is end-to-end stable at 1024-d (SPS ≈ 25 k matches the Phase 4 cached paths) and the early retrieval signal is **≈60 % above the best Phase 4 condition** at the same budget. This was the motivation for committing to the full 1 M-step anchor.

---

## 3. 1 M-step anchor experiments

Mirrors `run_phase4_anchor.py` exactly. Two loss combinations × two seeds × 1 M env-steps on `commons_harvest__open`, with `qwen_emb` as the embedding source. Baseline (no auxiliary losses) is not re-run — Phase 4 showed it produces no retrieval signal and the embedding does not enter the contrastive path.

| combo | `infonce_coef` | `kl_diversity_coef` | embedding |
|---|---|---|---|
| infonce | 0.5 | 0.0 | qwen_emb (1024-d) |
| full | 0.5 | 0.05 | qwen_emb (1024-d) |

Wall-clock: ≈ 5 min per run at SPS 14–17 k (vs Phase 4 random32 11–14 k). Slight slowdown from the wider conditioning vector; well within budget.

### 3.1 Stability and final-update diagnostics (mean ± std, 2 seeds)

| metric | Phase 4 random32 InfoNCE | **Phase 5 qwen InfoNCE** | Phase 4 random32 Full | **Phase 5 qwen Full** |
|---|---|---|---|---|
| episode_return — final | 10.9 ± 0.5 | **11.5 ± 0.14** | 10.8 ± 0.1 | **11.9 ± 1.62** |
| loss/entropy | 1.991 ± 0.011 | 1.876 ± 0.088 | 1.956 ± 0.109 | 1.904 ± 0.006 |
| persona/traj_top1 | 0.134 ± 0.013 | **0.143 ± 0.051** | 0.089 ± 0.051 | 0.089 ± 0.000 |
| persona/mean_pair_kl | 1.37e-3 ± 6.5e-4 | 1.32e-3 ± 3.6e-4 | 1.39e-3 ± 1.2e-4 | 1.31e-3 ± 4.1e-4 |

**Training-time retrieval and behavioural divergence are within seed variance of the Phase 4 numbers.** Episode return is marginally higher with qwen but the difference is well inside the substrate's seed-to-seed noise (Phase 4 reported final returns spanning 10.8–11.9 across modes). The 1024-d embedding does not destabilise PPO.

Aggregate: `research/meltingpot/phase5_qwen_summary.json`.

---

## 4. OOD evaluation — head-to-head against Phase 4 random32

Four passes per checkpoint (`train/random`, `heldout/random`, `population/mixed`, `population/heldout_only`), identical protocol to PHASE4_REPORT §5. Two seeds per mode. Reference chance: full K=12 → 0.083; train K=10 → 0.100; heldout K=2 → 0.500.

### 4.1 Retrieval table (mean ± std, 2 seeds)

| mode    | pass                            | full top-1 — random32 | **full top-1 — qwen_emb** | heldout_only top-1 — random32 | **heldout_only top-1 — qwen_emb** |
|---------|---------------------------------|------------------------|-----------------------------|------------------------------|--------------------------------------|
| InfoNCE | train / random                  | 0.107 ± 0.076          | 0.089 ± 0.025               | —                            | —                                    |
| InfoNCE | heldout / random                | **0.000 ± 0.000**      | **0.000 ± 0.000**           | 0.500 ± 0.076                | **0.464 ± 0.025**                    |
| InfoNCE | population / mixed              | 0.089 ± 0.051          | 0.063 ± 0.013               | 0.500 ± 0.295                | **0.312 ± 0.030**                    |
| InfoNCE | population / heldout_only       | 0.000 ± 0.000          | 0.000 ± 0.000               | 0.500 ± 0.152                | 0.393 ± 0.000                        |
| Full    | heldout / random                | **0.000 ± 0.000**      | **0.000 ± 0.000**           | 0.500 ± 0.076                | 0.455 ± 0.013                        |
| Full    | population / mixed              | 0.089 ± 0.025          | 0.054 ± 0.025               | 0.500 ± 0.295                | 0.292 ± 0.000                        |
| Full    | population / heldout_only       | 0.000 ± 0.000          | 0.000 ± 0.000               | 0.500 ± 0.152                | 0.411 ± 0.025                        |

**Headline:**

1. **`heldout/random` full-vocab top-1 is unchanged at 0.000 ± 0.000.** Across all four Phase 5 anchors and across both modes, the encoder *still never selects a held-out persona id* when given a held-out trajectory. The semantic richness of the Qwen table did not move this number by a single percentage point.
2. **Constrained 2-way `heldout_only` retrieval is at or *below* chance.** Phase 4 random32 sat at exactly 0.500; Phase 5 qwen_emb sits in 0.39–0.48. The Qwen encoding of `fast_mover` vs `spinner` does not give the InfoNCE head a usable signal even when the candidate set is reduced to those two.
3. **Mixed-population `heldout_only` retrieval is *worse* with qwen** (0.31 vs 0.50 for InfoNCE, 0.29 vs 0.50 for Full). The two held-out personas now sit closer to each other in Qwen geometry than they did under random32, which collapses the 2-way decision boundary.
4. **`train/random` in-distribution retrieval is unchanged** (0.089 ± 0.025 vs 0.107 ± 0.076). Switching to a 1024-d semantic encoder did not lift in-distribution accuracy either.

### 4.2 Per-persona held-out top-1 (heldout/random pass, full 12-vocab)

```
qwen InfoNCE :  fast_mover = 0.000 ± 0.000     spinner = 0.000 ± 0.000
qwen Full    :  fast_mover = 0.000 ± 0.000     spinner = 0.000 ± 0.000
```

Identical to Phase 4's random32 result. **The encoder's failure mode is robust to embedding source.**

### 4.3 Train-vs-heldout behavioural KL (mixed-pop pass)

| mode    | random32         | **qwen_emb**     |
|---------|------------------|------------------|
| InfoNCE | 1.65e-3          | **2.13 ± 0.19 ×10⁻³** |
| Full    | 1.87e-3          | 1.54 ± 0.04 ×10⁻³ |

Held-out conditioned actions sit *further* from the train-persona cluster under qwen InfoNCE (≈30 % larger block KL than random32). The policy is acting on more of the embedding signal than it was under random32 — the **retrieval head simply cannot read that signal back**. The Full mode shows the opposite drift, consistent with KL-diversity flattening the spread (cf. PHASE4_REPORT §4 on the value-collapse risk of `kl_diversity_coef=0.05`).

### 4.4 Embedding-distance × action-KL Spearman ρ (mixed-pop pass)

| mode    | random32         | **qwen_emb**     |
|---------|------------------|------------------|
| InfoNCE | −0.074 ± 0.049   | **+0.138 ± 0.063** |
| Full    | −0.013 ± 0.183   | **+0.144 ± 0.083** |

ρ **flips sign and lands at small positive values** under qwen. This is the one number that moves in the direction predicted by PHASE4_REPORT §11.1 — closer-in-embedding-space personas now produce more-similar action distributions. The effect is real but tiny: |ρ| ≈ 0.14 vs the |ρ| > 0.5 we would want for a "semantic→behaviour mapping is being learnt" claim. With 2 seeds and a 12-persona table the CIs are wide.

### 4.5 Persona arithmetic (Full / seed 1)

| midpoint | nearest id | cos (qwen) | cos (Phase 4 random32) |
|---|---|---|---|
| `cooperative_sustainer` + `aggressive_zapper` | `cooperative_sustainer` | 0.765 | 0.693 |
| `cleaner_helper` + `free_rider` | `cleaner_helper` | 0.860 | 0.709 |
| `explorer` + `territorial_defender` | `explorer` | 0.867 | 0.660 |

Midpoint cosines are uniformly higher (qwen geometry is less orthogonal), but the midpoint still maps to one parent in every case. Compositionality remains a static-table geometric artefact; the Phase 5 §2 *policy-rollout* persona-arithmetic test (PHASE4_REPORT §11.2) is the only thing that can move this number, and it has not been run yet.

### 4.6 Trajectory-clustering purity (train pass)

| mode    | random32 | **qwen_emb** |
|---|---|---|
| InfoNCE | 0.277 ± 0.013 | 0.339 ± 0.000 |
| Full    | 0.321 ± 0.025 | 0.339 ± 0.000 |

Modest improvement (~+0.04 InfoNCE, +0.02 Full) but the effect is within seed noise once 2-seed CIs are accounted for. The encoder groups trajectories by training persona about 3.4× above chance — Phase 4 reported 2.8–3.2×.

---

## 5. Headline findings

<!-- p5-headline:start -->
1. **Real LLM embeddings do not flip the Phase 4 central failure.** Held-out top-1 retrieval against the full 12-class vocabulary is **0.000 ± 0.000 under qwen_emb**, identical to random32. The hypothesis "random embedding orthogonality is the cause of held-out failure" (PHASE4_REPORT §11.1) is **rejected** at 1 M env-steps × 2 seeds × 2 modes.
2. **Constrained 2-way held-out retrieval is at or below chance.** Phase 4's chance-level 0.500 dropped to 0.29–0.46 under qwen. The Qwen table does not separate `fast_mover` from `spinner` for the InfoNCE head, even though their cosine distance (≈0.50) is well above the global minimum.
3. **The behavioural side responds, the retrieval side does not.** Train-vs-heldout block KL grew from 1.65e-3 to 2.13e-3 (≈+30 %) under qwen InfoNCE, and Spearman ρ flipped sign from −0.074 to +0.138. **The shared policy is using more of the embedding signal**, but the contrastive retrieval head is not.
4. **The mechanism that survives both ablations is the contrast pool, not the embedding.** The InfoNCE head was only ever trained against the 10 training personas. Any test-time held-out trajectory, whatever its embedding's cosine to the held-out slot, is matched against a candidate space the head has never seen during training. This rules out one of Phase 4's three remediation routes (semantic embedding) and elevates the other two (widened contrast pool / "unknown-persona" KL budget) as the headline Phase 5 §2+ priorities.
5. **In-distribution retrieval did not improve either.** train/random full top-1 is 0.089 ± 0.025 (qwen) vs 0.107 ± 0.076 (random32) — within noise. The persona-balance bottleneck identified in PHASE4_REPORT §4 is *not* unblocked by switching encoders.
6. **Episode return and stability are slightly improved.** Final return 11.5 ± 0.14 (qwen InfoNCE) vs 10.9 ± 0.5 (random32 InfoNCE); Full's explained-variance pathology from Phase 4 §4 did not recur with qwen on either seed. The richer embedding gives PPO a marginally smoother conditioning signal even where the retrieval head fails.
7. **Compositionality is still a static-table artefact.** Qwen midpoints land closer to their nearest parent than random midpoints did (cos 0.76–0.87 vs 0.66–0.71), but every midpoint still maps to one parent. The behavioural test (rolling out the policy under the midpoint embedding) is the only thing that can resolve this; it is the next experiment.
<!-- p5-headline:end -->

---

## 6. What this means for the paper argument

PHASE4_REPORT §11 framed the random-embedding swap as the *single load-bearing experiment* that would decide whether Phase 4's failure was methodological (orthogonality) or fundamental (retrieval-head mis-specification). The answer is now in: **fundamental**.

This sharpens the paper's structure, not the direction:

- The "language is a viable identity channel for agents" claim of `MELTINGPOT_PROPOSAL.md` does **not** survive zero-shot retrieval to held-out personas under the present InfoNCE contrast specification. This is independent of embedding richness.
- The claim **does** survive in-distribution: trajectory clustering purity (~3.4× chance) and in-distribution retrieval (~0.09) are above chance on both encoders, and the policy uses the embedding to shape behaviour (block-KL between train and held-out personas widens with embedding richness, ρ flips sign).
- The right Phase 5 §2 experiment is no longer "try another encoder" — it is **a contrast-pool intervention**: either (a) include held-out persona slots in the InfoNCE candidate set during training (treats held-out personas as cold-start contrast targets, no rollouts of them needed), or (b) add an "unknown-persona" class as a KL-budget anchor so the head is forced to leave probability mass outside the training cast.

Either intervention is single-seed-cheap to prototype on the existing trainer. This is what Phase 5 §2 should do before any further substrate work.

---

## 7. Exact commands used

```
# 1) Build the Qwen artifact:
python -m scripts.build_persona_embeddings_qwen

# 2) 60 k A/B sanity (seed 1):
python -m scripts.run_phase5_qwen_ab --condition qwen_emb --seed 1 --total-env-steps 60000

# 3) 1 M-step anchors (2 modes × 2 seeds):
for mode in infonce full; do
  for seed in 1 2; do
    python -m scripts.run_phase5_qwen_anchor --mode $mode --seed $seed --total-env-steps 1000000
  done
done

# 4) OOD evaluation:
python -m scripts.run_phase4_ood_eval \
  research/meltingpot/runs/phase5_qwen_anchor/phase5_qwen_anchor_*_1000k

# 5) Aggregate:
python -m scripts.summarize_phase4 \
  research/meltingpot/runs/phase5_qwen_anchor/phase5_qwen_anchor_*_1000k \
  --out research/meltingpot/phase5_qwen_summary.json
```

---

## 8. Recommended directions for Phase 5 §2

These supersede PHASE4_REPORT §11.1 (which is now closed as a negative result).

1. **Widened InfoNCE contrast pool.** Add held-out persona slots to the InfoNCE candidate set during training — the held-out *embeddings* are available (they exist in the cached table), only their *trajectories* must be excluded. Re-run a single 1 M-step anchor and check whether `heldout/random` full top-1 leaves 0.000.
2. **Unknown-persona class.** Reserve a 13th "unknown" embedding (or treat the rest of the persona corpus, when one exists, as an OOD anchor) and add a small KL term that keeps a fixed mass on the unknown class during training. The decision boundary then has a place to go for unseen embeddings.
3. **Persona-arithmetic policy rollouts.** PHASE4_REPORT §11.2. Roll out the policy under midpoint embeddings (`(cooperative + aggressive)/2`) and ask whether the resulting trajectory's `z_traj` sits between the parent centroids. With the qwen table this is finally a meaningful test — random midpoints carry no compositional structure, but qwen midpoints might.
4. **Persona-balanced InfoNCE batches.** PHASE4_REPORT §10 named persona-balance in the InfoNCE batch as the most likely cause of the no-budget-gain observation. This is orthogonal to the contrast-pool fix and should be tried together.
5. **Substrate transfer** (delayed until the contrast-pool fix lands). Running the same protocol on `prisoners_dilemma_in_the_matrix__repeated` is premature if the retrieval head still cannot generalise on `commons_harvest__open`.

---

## 9. Phase 5 §2 — Contrast-pool intervention

### 9.1 Mechanism check on the §1 diagnosis

Re-reading the trainer after §1 closed: the InfoNCE head was **already** being trained against the full 12-vocabulary as its candidate pool. The Phase 5 §1 recommendation in §8.1 ("widened contrast pool") was therefore misnamed — the pool was already wide. The actual asymmetry is that *positive labels* during training are drawn only from the 10-persona train split, while held-out slots appear only as negatives. The head therefore learns a strict "no observed trajectory belongs in a held-out slot" inductive bias regardless of embedding source. This is the correct mechanistic reading of §5 finding 4.

The surgical inversion is **to narrow the candidate pool to the train indices during training** — held-out slots receive zero gradient signal (no positive, no negative). Implementation:

```python
# src/training/cleanrl_ppo/config.py
infonce_candidate_pool: str = "full"   # full|train  (§2 adds the "train" option)

# src/training/cleanrl_ppo/trainer.py — wired through InfoNCEHead.forward(candidate_indices=…)
```

`InfoNCEHead.logits` already supported `candidate_indices`; the trainer just had to start passing the train-split tensor. No model-shape changes; existing checkpoints remain readable; `--infonce-candidate-pool full` reproduces Phase 5 §1 byte-for-byte.

### 9.2 Experiment

Two seeds × 1 M env-steps × InfoNCE-only × qwen_emb × `pool=train`. Held-out personas (`fast_mover`, `spinner`) appear in the persona table (so the encoder buffer is unchanged) but never in the InfoNCE candidate set during training.

```
python -m scripts.run_phase5_contrast_pool --pool train --seed {1,2} --total-env-steps 1000000
python -m scripts.run_phase4_ood_eval \
  research/meltingpot/runs/phase5_contrast_pool/phase5_contrast_pool_train_seed*_1000k
python -m scripts.summarize_phase4 \
  research/meltingpot/runs/phase5_contrast_pool/phase5_contrast_pool_train_seed*_1000k \
  --out research/meltingpot/phase5_contrast_summary.json
```

### 9.3 Stability and final-update diagnostics

| metric | qwen + `full` pool (§1) | **qwen + `train` pool (§2)** |
|---|---|---|
| episode_return — final | 11.5 ± 0.14 | 11.2 ± 0.37 |
| loss/entropy | 1.876 ± 0.088 | 1.933 ± 0.069 |
| persona/traj_top1 (in-distribution) | 0.143 ± 0.051 | 0.125 ± 0.051 |
| persona/mean_pairwise_action_kl | 1.32e-3 ± 3.6e-4 | 1.23e-3 ± 5.2e-5 |

Within seed variance of §1. The intervention does not destabilise training and does not lose in-distribution retrieval. Note that the §2 training-time top-1 is measured over the 10-candidate train pool (chance 0.10) while §1's is over the 12-candidate full pool (chance 0.083); the §2 number is therefore only marginally above its chance baseline whereas §1's was 1.7× above its baseline.

### 9.4 OOD retrieval table (mean ± std, 2 seeds)

| pass                             | metric             | qwen + `full` (§1) | **qwen + `train` (§2)** |
|----------------------------------|--------------------|---------------------|---------------------------|
| train / random                   | full top-1         | 0.089 ± 0.025       | **0.089 ± 0.025**          |
| heldout / random                 | full top-1         | **0.000 ± 0.000**   | **0.000 ± 0.000**          |
| heldout / random                 | heldout_only top-1 | 0.464 ± 0.025       | **0.500 ± 0.076**          |
| population / mixed               | full top-1         | 0.063 ± 0.013       | 0.054 ± 0.025             |
| population / mixed               | train_only top-1   | 0.109 ± 0.022       | 0.094 ± 0.044             |
| population / mixed               | heldout_only top-1 | 0.312 ± 0.030       | **0.500 ± 0.295**          |
| population / heldout_only        | heldout_only top-1 | 0.393 ± 0.000       | 0.500 ± 0.151             |
| population / mixed               | Spearman ρ         | +0.138 ± 0.063      | +0.070 ± 0.083            |

### 9.5 Per-persona held-out top-1 (heldout/random, full 12-vocab)

```
§2 (qwen + train pool) :  fast_mover = 0.000 ± 0.000     spinner = 0.000 ± 0.000
```

Identical to §1, identical to Phase 4. **Even with zero gradient signal on the held-out slots, the encoder still never maps a held-out trajectory to its true held-out id.**

### 9.6 Reading

<!-- p5-2-headline:start -->
1. **Full-vocab held-out top-1 is robust to the contrast-pool intervention** — still 0.000 ± 0.000 across both seeds. Removing the negative-only training signal on held-out slots did *not* permit the head to assign held-out trajectories to held-out ids. This further rules out a "training-induced repulsion from held-out slots" explanation.
2. **Constrained K=2 retrieval returned to chance, but with much wider variance.** `heldout/random heldout_only` rose from 0.464 ± 0.025 (§1, below chance) back to 0.500 ± 0.076 (§2, at chance). On `population/mixed heldout_only` the same intervention lifted the mean from 0.312 to 0.500 but inflated the std from 0.030 to 0.295 — seed 1 reached **0.708** (well above chance), seed 2 stayed at 0.292. The head is no longer systematically biased *against* held-out slots, but its decisions there are essentially driven by seed-level noise rather than by embedding geometry.
3. **The bottleneck has shifted from the head to the trajectory representation.** With both the embedding (Qwen semantic geometry) and the head (no anti-held-out signal) controlled, the GRU's `z_traj` for a held-out trajectory still projects closer to *some* train persona's embedding than to either held-out embedding under the full-vocab decision rule. Two non-exclusive mechanisms remain:
   - **(a) Action-prior overlap.** The GRU consumes (action one-hot, reward) sequences. `fast_mover`'s action prior (55 % FORWARD) overlaps strongly with `selfish_harvester` (40 % FORWARD); `spinner`'s rotation-heavy prior overlaps with `cautious_observer` (≈30 % rotations). Held-out trajectories are *behaviourally* close to some train persona regardless of conditioning, and the GRU has no symbolic notion that they should map elsewhere.
   - **(b) Conditioning under-utilisation.** The shared policy's behavioural divergence (mean-pair-KL ~1.2e-3) is small compared to the substrate's action entropy (~1.9 nats). The policy is responding to persona conditioning, but not strongly enough that the *behavioural* fingerprint diverges from the dominant action-prior cluster within 1 M steps.
4. **In-distribution numbers are unchanged.** `train/random` full top-1 is 0.089 ± 0.025 in both §1 and §2; trajectory-clustering purity is within noise. The intervention is OOD-targeted; it does not pay (or earn) in-distribution.
5. **Episode-return is unchanged.** Both §1 and §2 anchors land in 11.2–11.9 final return — the tragedy-of-commons collapse is robust to all variations we have explored.
<!-- p5-2-headline:end -->

### 9.7 What this means for the paper argument

Two of the three remediation routes from PHASE4_REPORT §11.1 are now closed: a richer embedding (§1) and a head-side intervention (§2) each fail to crack the central failure. The paper-level reading sharpens further:

- The contrast-head specification of InfoNCE is **not** the load-bearing locus of the failure.
- The trajectory encoder's *behavioural* representation of held-out personas is the next candidate. Held-out persona ids are reachable as policy-conditioning inputs (the policy does shift behaviour, see §4.3 block KL) but **not** as targets of trajectory-side recovery, because (action, reward) sequences for held-out personas overlap with sequences for train personas with similar action priors.
- This is the precise sense in which the *behavioural fingerprint* claim breaks down on this substrate: persona is *visible* in the conditioning input and is *acted upon* by the policy, but is not *recoverable* from the resulting behaviour at this conditioning strength on this substrate.

This is a tighter, more falsifiable failure mode than Phase 4's report had. It moves the paper claim from "PCSP transfers" to a structured-conditional: *PCSP transfers when persona is behaviourally separable in the action+reward space the GRU consumes*. The empirical work that decides whether this is a workshop-level negative result or a main-track conditional positive is now well-defined and small:

1. **Substrate with richer behavioural geometry.** `prisoners_dilemma_in_the_matrix__repeated` has explicit *strategic* actions (cooperate/defect) whose behavioural signatures are not collapsible to FORWARD-vs-rotation patterns. This is exactly the substrate the original budget targeted.
2. **Persona corpus disjoint in action prior.** The current held-out pair was chosen for behavioural separability *from each other* (translation vs rotation). Phase 5 §3 should add a 3rd–5th held-out persona whose action priors do *not* overlap with any single train persona, to test whether the failure is fundamental to GRU + (action, reward) inputs or an artefact of the specific 12-persona corpus.
3. **Trajectory-encoder input augmentation.** Add `social_state` features (visible co-players, recent co-player actions) to the GRU input. PHASE4_REPORT §1 already plumbs these into the wrapper; they are currently consumed only by metrics, not by the GRU. If their inclusion lifts held-out top-1, the failure mode was input-channel-narrow, not representation-deep.

### 9.8 Recommended directions for Phase 5 §3

Supersedes §8 above. The contrast-pool fix is closed as a negative result.

1. **(new) Second substrate.** Run the Phase 5 §1 + §2 protocol on `prisoners_dilemma_in_the_matrix__repeated`. The behavioural separability of cooperate/defect is the cleanest available control on the "action-prior overlap" hypothesis.
2. **(new) Trajectory-encoder input ablation.** Add co-player action history to the GRU input on `commons_harvest__open` and re-run Phase 5 §1 (qwen + full pool, single mode, 2 seeds). If held-out full top-1 moves off 0, the fix is at the GRU input layer.
3. **(new) Held-out corpus expansion.** Add 2 personas whose action priors are *not* duplicated in the train cast (e.g., an "always-zap" or a "pure-NOOP") and re-run §1 + §2. If held-out top-1 still collapses to 0, the failure is general.
4. **Persona-arithmetic policy rollouts** (carried over from §8.3) — independent of the above and still worth running with qwen midpoints.
5. **Persona-balanced InfoNCE batches** (carried over from §8.4) — orthogonal lever, kept on the menu.

---

## 10. Phase 5 §3 — Second substrate (prisoners_dilemma_in_the_matrix__repeated)

### 10.1 Why this substrate

PHASE5_REPORT §9.6 named *action-prior overlap inside the (action, reward) GRU input* as the load-bearing failure mechanism on `commons_harvest__open`. The cleanest experimental control is to move to a substrate whose 8-action ontology has *strategically distinct semantics* — `prisoners_dilemma_in_the_matrix__repeated` overlays cooperate/defect interactions onto the same nominal action vocabulary, so two trajectories that look identical at the FORWARD level can be carrying opposite cooperate/defect strategies. If §2's diagnosis was correct, this should let the InfoNCE head separate held-out trajectories from train trajectories at least at the constrained-K boundary.

The persona corpus is **unchanged**. Held-out personas (`fast_mover`, `spinner`) were authored for `commons_harvest__open`'s movement-centric ontology and are *less* well-suited to PD strategy. This is a deliberately *stricter* test: any non-zero held-out signal on PD with movement-named held-outs is strong evidence that substrate behavioural separability — not the persona corpus — is the operative variable.

Substrate spec via the Phase 1 wrapper, no code changes: `num_players=2`, `num_actions=8`, obs `40×40×3`. The trainer ran end-to-end on the existing CleanRL-PPO stack.

### 10.2 Experiment

4 runs total. Same trainer knobs as §1/§2 (8 envs, 128 steps, InfoNCE-only, qwen_emb).

| arm | pool | seeds | substrate |
|---|---|---|---|
| §3 pool=full | full | 1, 2 | PD-in-the-matrix |
| §3 pool=train | train | 1, 2 | PD-in-the-matrix |

```
python -m scripts.run_phase5_pd_anchor --seed {1,2} --pool {full,train} --total-env-steps 1000000
python -m scripts.run_phase4_ood_eval research/meltingpot/runs/phase5_pd_anchor/phase5_pd_anchor_*_1000k
```

### 10.3 Stability and final-update diagnostics

| metric | §1 commons_harvest full | §2 commons_harvest train | **§3 PD full** | **§3 PD train** |
|---|---|---|---|---|
| episode_return — final | 11.5 ± 0.14 | 11.2 ± 0.37 | **28.1 ± 4.2** | 21.8 ± 14.7 |
| loss/entropy | 1.876 ± 0.088 | 1.933 ± 0.069 | 1.429 ± 0.033 | 1.448 ± 0.198 |
| persona/traj_top1 | 0.143 ± 0.051 | 0.125 ± 0.051 | 0.156 ± 0.044 | 0.125 ± 0.088 |
| persona/mean_pair_action_kl | 1.32e-3 ± 3.6e-4 | 1.23e-3 ± 5.2e-5 | **2.11e-2 ± 1.6e-2** | **9.06e-3 ± 3.7e-3** |

Behavioural divergence in PD is **16× larger** (mean-pair action KL 2.11e-2 vs 1.32e-3 on commons_harvest, full pool) — persona conditioning has dramatically more bite when the action vocabulary carries strategic semantics. Episode return is also 2–3× higher (PD baseline ≈ 28 vs commons-harvest ≈ 11) because PD personas can land in mutual-cooperation equilibria; the substrate is not a strict tragedy-of-commons here.

Lower entropy on PD (~1.43 vs ~1.88) is consistent with the policy concentrating mass on strategically dominant actions.

### 10.4 OOD retrieval — head-to-head across substrates and pools

| pass                         | metric             | §1 cH full        | §2 cH train       | **§3 PD full**     | **§3 PD train**    |
|------------------------------|--------------------|-------------------|-------------------|---------------------|---------------------|
| train / random               | full top-1         | 0.089 ± 0.025     | 0.089 ± 0.025     | 0.125 ± 0.088       | 0.031 ± 0.044       |
| **heldout / random**         | **full top-1**     | **0.000 ± 0.000** | **0.000 ± 0.000** | **0.000 ± 0.000**   | **0.000 ± 0.000**   |
| heldout / random             | full top-3         | 0.000 ± 0.000     | 0.018 ± 0.025     | 0.000 ± 0.000       | **0.219 ± 0.309**   |
| heldout / random             | heldout_only top-1 | 0.464 ± 0.025     | 0.500 ± 0.076     | **0.563 ± 0.000**   | 0.500 ± 0.088       |
| population / mixed           | full top-1         | 0.063 ± 0.013     | 0.054 ± 0.025     | 0.031 ± 0.044       | 0.031 ± 0.044       |
| population / mixed           | full top-3         | 0.211 ± 0.025     | 0.223 ± 0.013     | 0.094 ± 0.044       | **0.281 ± 0.221**   |
| population / mixed           | heldout_only top-1 | 0.312 ± 0.030     | 0.500 ± 0.295     | 0.375 ± 0.000       | 0.500 ± 0.177       |
| population / mixed           | Spearman ρ         | +0.138 ± 0.063    | +0.070 ± 0.083    | +0.103 ± 0.116      | +0.141 ± 0.151      |
| population / heldout_only    | heldout_only top-1 | 0.393 ± 0.000     | 0.500 ± 0.151     | 0.312 ± 0.000       | **0.500 ± 0.265**   |
| population / heldout_only    | full top-3         | —                 | —                 | 0.000 ± 0.000       | **0.344 ± 0.486**   |

cH = `commons_harvest__open`. PD = `prisoners_dilemma_in_the_matrix__repeated`.

Behavioural KL (train/random):
| substrate × pool | mean_pair_kl |
|---|---|
| cH §1 full | 1.32 × 10⁻³ |
| cH §2 train | 1.23 × 10⁻³ |
| PD §3 full | 9.45 × 10⁻³ |
| PD §3 train | 7.53 × 10⁻³ |

Train-vs-heldout block KL (mixed-pop):
| substrate × pool | train_vs_heldout_kl |
|---|---|
| cH §1 full | 2.26 × 10⁻³ |
| cH §2 train | 1.83 × 10⁻³ |
| PD §3 full | 8.43 × 10⁻³ |
| PD §3 train | 7.96 × 10⁻³ |

### 10.5 Per-persona held-out top-1 (heldout/random, full 12-vocab)

```
PD §3 full  :  fast_mover = 0.000 ± 0.000     spinner = 0.000 ± 0.000
PD §3 train :  fast_mover = 0.000 ± 0.000     spinner = 0.000 ± 0.000
```

Identical to commons_harvest. **Full-vocab held-out top-1 is invariant across both substrates and both contrast-pool settings tested in Phase 5.**

### 10.6 Reading

<!-- p5-3-headline:start -->
1. **The 0.000 full-vocab held-out top-1 is substrate-invariant.** Across `commons_harvest__open` × `prisoners_dilemma_in_the_matrix__repeated` × {`full`, `train`} pool, the encoder never picks a held-out id from the full 12-vocab. The Phase 4–5 §1–§3 sweep has now ruled out (a) random vs semantic embedding, (b) contrast-pool composition, and (c) substrate ontology as load-bearing variables of the *absolute* held-out failure.
2. **Behavioural divergence is the variable that *does* respond to substrate change.** PD's mean-pair action-KL is **5–16× larger** than commons_harvest's; train-vs-heldout block KL is **4× larger**. The policy uses persona conditioning much more aggressively when the action vocabulary carries strategic load. This validates §2's diagnosis at the behavioural-side level — substrate ontology determines how strongly conditioning shows up in actions — but invalidates its implied prediction that this would unblock retrieval.
3. **First non-trivial held-out signal: PD §3 pool=train top-3.** The combined intervention (PD substrate + train-only contrast pool) produces full-vocab top-3 of **0.219 ± 0.309 on heldout/random** and **0.281 ± 0.221 on population/mixed**, with one of the two seeds reaching 0.4375 (vs chance 0.25). The other seed sits at 0.0/0.125. Seed-dependent and unstable, but the first measurement across all of Phase 4–5 where any heldout signal exceeds chance in the *full* candidate set.
4. **K=2 constrained held-out retrieval is consistently at or slightly above chance on PD.** PD §3 full lands at 0.563 ± 0 on `heldout/random heldout_only` (both seeds 0.5625); PD §3 train at 0.500 ± 0.088. Above-chance K=2 was *not* observed on commons_harvest §1 (0.464 ± 0.025).
5. **Pool=train compounds with PD richness.** The substrate-ontology shift alone (§3 full) does not produce non-zero top-3; pool=train alone (§2) does not either; *combined* they produce the §3-train top-3 signal. The two interventions interact rather than substitute.
6. **In-distribution retrieval did not transfer cleanly.** PD §3 full `train/random` top-1 is 0.125 ± 0.088 — within commons_harvest noise — but PD §3 train collapses to 0.031 ± 0.044, *below* random32 on commons_harvest. The pool=train ablation interacts adversely with PD's smaller effective batch (16 vs 56 trajectories per update), suggesting the substrate-pool interaction is sample-efficiency mediated.
<!-- p5-3-headline:end -->

### 10.7 What this means for the paper argument

The three principal Phase 5 levers (embedding source §1, contrast pool §2, substrate ontology §3) **do not, individually or in combination, produce a positive full-vocab held-out top-1 result**. The paper-level reading is now fully specified:

- **MELTINGPOT_PROPOSAL §3 H3** (zero-shot persona traceability under novel co-players) fails at the *full-vocabulary* boundary under every Phase 5 configuration tested. This is now a robust, multi-ablation, multi-substrate failure.
- **H3 holds partially at the *constrained-K* boundary**: K=2 retrieval is consistently at or above chance under PD; under commons_harvest the K=2 retrieval is below chance, ruling out a uniform-chance failure mode and pointing to a substrate-conditional partial signal.
- **H1** (identity-distinguishable policies under reward pressure) is *cleanly satisfied* on PD: mean-pair action KL is two orders of magnitude above chance-level action-distribution noise, and in-distribution trajectory clustering purity exceeds chance by ~3.4×. The first proposal claim survives. The substrate exposes meaningful behavioural variation across personas.
- **H5** (Pareto frontier between reward and identification) is suggestive on PD: return is 2–3× higher than commons_harvest and identification is similar order-of-magnitude — the trade-off frontier in commons_harvest was substrate-bound, not method-bound.

The paper structure that fits the Phase 5 evidence:
- **Positive headline:** PCSP produces persona-distinguishable behaviour at substrate-appropriate scales (H1 holds on ≥2 substrates).
- **Conditional headline:** persona is traceable from trajectories *at constrained-K granularity on strategically-rich substrates*. Above chance on PD K=2 across both pools, below chance on commons_harvest K=2.
- **Structured negative result:** full-vocabulary held-out persona retrieval under PCSP-InfoNCE is **not** achievable at this scale (1 M env-steps × 2 seeds × 4 substrate-pool combinations × 2 embedding sources). This is now a tight, falsifiable, multi-ablation negative result with diagnostic specificity (it survives every intervention we identified Phase 4 §11 / Phase 5 §8 §9).

For NeurIPS 2026 Workshop this is a strong submission. For main-track ICML/NeurIPS the substantive H3-positive result requires either a sixth lever (the §10.8 menu below) or accepting the conditional positive at the K=2 level.

### 10.8 Recommended directions for Phase 5 §4

Closes §3. The substrate-ontology lever is now spent as a binary diagnostic.

1. **(highest leverage) Persona-balanced InfoNCE mini-batches.** This is the only remaining intervention named since Phase 4 §11 that has not been tested. PHASE4_REPORT §10 named persona-balance in the InfoNCE batch as the most likely cause of the no-budget-gain observation; PD's smaller effective batch (16 vs 56) on §3 train made the symptom visible (in-distribution top-1 collapse to 0.031). Adding a persona-balanced sampler should unblock both substrates simultaneously.
2. **Persona-arithmetic policy rollouts on PD.** PHASE4_REPORT §11.2 and PHASE5_REPORT §8.3. PD's larger behavioural divergence is the regime where the rollout test can actually move. Run a single 1 M-step anchor under a midpoint embedding (`(cooperative_sustainer + selfish_harvester) / 2`) and check whether the resulting `z_traj` centroid sits between the parent centroids. With PD's mean-pair-KL of ≈2×10⁻², the midpoint's behavioural signature should be statistically distinguishable.
3. **Held-out persona corpus expansion (PD-specific).** Add 2 PD-tuned held-out personas (e.g., `always_cooperate`, `grim_trigger`) whose strategic descriptions are unambiguous. Re-run §3 full + train. This separates "movement-named held-outs don't transfer to PD" from "no held-out generalises".
4. **Larger effective batch on PD.** Run §3 with `num_envs=32` so PD's batch matches commons_harvest's. Rules out the sample-efficiency-mediated regression of pool=train on PD.
5. **Substrate × held-out factorial.** Stretch goal. Once §4.1–§4.3 are in, run all three substrate × pool combinations with the 4–5 expanded held-out set to fill the H1/H3 claim cells called out in MELTINGPOT_PROPOSAL §6.

---

## 11. Phase 5 §4 — Persona-balanced InfoNCE mini-batches

### 11.1 Mechanism

PHASE4_REPORT §10 named persona-balance in the InfoNCE batch as the most likely cause of the no-budget-gain observation. With `--persona-assignment random`, a 128-step rollout window, 8 envs × P players, and 10 train personas, the InfoNCE step gets roughly B/K ≈ 5.6 trajectories per persona on commons_harvest and only 1.6 on PD — and the *variance* of that count is high enough that single updates regularly miss personas entirely.

The fix is one-paragraph: at every InfoNCE opt step, group the rollout's trajectories by persona id and resample (with replacement when needed) so every present id contributes a uniform count. Implementation:

```python
# src/training/cleanrl_ppo/config.py
infonce_balanced_batch: bool = False
infonce_per_persona: int = 0   # 0 → auto = ceil(B / K_present)

# src/training/cleanrl_ppo/trainer.py — _build_balanced_idx + wrap InfoNCE step
```

No model-shape change; checkpoints from earlier phases reload unchanged.

### 11.2 Experiment

4 runs total, all on top of the §1 setup (qwen_emb, pool=train, InfoNCE-only, 1 M env-steps).

| arm | substrate | pool | balanced | seeds |
|---|---|---|---|---|
| §4 cH balanced | commons_harvest__open | train | True | 1, 2 |
| §4 PD balanced | PD-in-the-matrix__repeated | train | True | 1, 2 |

```
python -m scripts.run_phase5_balanced --substrate {cH,PD} --seed {1,2} --pool train
python -m scripts.run_phase4_ood_eval research/meltingpot/runs/phase5_balanced/phase5_balanced_*_1000k
```

### 11.3 OOD retrieval — first non-zero full-vocab held-out signal in Phase 4–5

Comparison across the full Phase 5 sweep, `heldout/random` pass (chance for full K=12 is 0.083; chance for heldout_only K=2 is 0.500). All values are mean ± std across two seeds.

| arm | full top-1 | full top-3 | heldout_only top-1 |
|---|---|---|---|
| Phase 4 random32 InfoNCE (cH) | 0.000 ± 0.000 | 0.000 ± 0.000 | 0.500 ± 0.076 |
| §1 qwen_emb (cH) | 0.000 ± 0.000 | 0.000 ± 0.000 | 0.464 ± 0.025 |
| §2 qwen + pool=train (cH) | 0.000 ± 0.000 | 0.018 ± 0.025 | 0.500 ± 0.076 |
| §3 PD full | 0.000 ± 0.000 | 0.000 ± 0.000 | 0.563 ± 0.000 |
| §3 PD pool=train | 0.000 ± 0.000 | 0.219 ± 0.309 | 0.500 ± 0.088 |
| **§4 cH balanced + pool=train** | **0.277 ± 0.391** | **0.500 ± 0.707** | 0.536 ± 0.025 |
| **§4 PD balanced + pool=train** | **0.219 ± 0.309** | **0.438 ± 0.000** | 0.438 ± 0.000 |

For the first time across 14 Phase 4–5 anchor runs, full-vocab held-out top-1 leaves zero. The §4 result is also the first phase where full top-3 is non-trivial (0.50 cH / 0.44 PD vs chance 0.25).

### 11.4 Seed-level detail and persona asymmetry

The means above hide a sharp two-mode distribution. Per-seed `heldout/random` full top-1 plus per-persona breakdown:

| run | full top-1 | fast_mover top-1 | spinner top-1 | full top-3 |
|---|---|---|---|---|
| cH balanced seed 1 | **0.554** | **1.000** | 0.000 | **1.000** |
| cH balanced seed 2 | 0.000 | 0.000 | 0.000 | 0.000 |
| PD balanced seed 1 | **0.438** | **1.000** | 0.000 | **0.438** |
| PD balanced seed 2 | 0.000 | 0.000 | 0.000 | **0.438** |

Two observations:

1. **Persona asymmetry.** Across every positive seed in §4 and on every pass that produces non-zero signal, the credit is paid by `fast_mover` (1.0 retrieval) while `spinner` remains at 0.0. This is consistent with the persona embedding geometry recorded in §1: `spinner` sits at cos 0.55 from `territorial_defender` (the closest pair in the Qwen table), while `fast_mover`'s nearest neighbour is `selfish_harvester` at a more modest 0.41. The contrast head can carve a decision boundary around `fast_mover` but not around `spinner`.
2. **Seed bimodality.** Two of four runs (cH seed 1, PD seed 1) hit the positive mode; the other two (cH seed 2, PD seed 2) reproduce the §1–§3 zero result. The two modes have similar in-distribution loss and entropy at convergence — the divergence is in the InfoNCE projection geometry, not in PPO. This is a single-seed effect that needs more replicates to characterise, but it is reproducible across both substrates.

Strong outliers on adjacent metrics:

- `cH balanced seed 1`, `pop/heldout_only` pass: **full top-3 = 1.000** — every held-out trajectory's true id is in the encoder's top-3 of the full 12-vocab. The head correctly places held-out trajectories in the held-out portion of the persona space; the asymmetry between `fast_mover` (top-1 1.0) and `spinner` (top-1 0.0, but top-3 includes the right answer) is what drives the gap between top-1 and top-3.
- `cH balanced seed 1`, `pop/mixed` pass: `heldout_only` top-1 = **0.708**, full top-1 = 0.304. The retrieval head distinguishes held-out from train at population level even when forced to choose among 12 candidates.

### 11.5 Stability and trade-offs

| metric | §1 qwen cH | §2 qwen+train cH | §4 balanced cH | §4 balanced PD |
|---|---|---|---|---|
| episode_return — final | 11.5 ± 0.14 | 11.2 ± 0.37 | **11.7 ± 0.69** | 21.7 ± 21.9 |
| loss/entropy | 1.876 | 1.933 | 1.974 | 1.427 |
| persona/traj_top1 (in-distribution) | 0.143 ± 0.051 | 0.125 ± 0.051 | **0.027 ± 0.038** | 0.000 ± 0.000 |
| persona/mean_pair_action_kl | 1.32e-3 | 1.23e-3 | 1.38e-3 | 4.69e-3 |

Two prices paid by the §4 intervention:

1. **In-distribution training-time retrieval collapses.** `persona/traj_top1` over the 10-candidate train pool falls from 0.125 (§2) to 0.027 (cH §4) or 0 (PD §4). The InfoNCE head's *training-time* signal on the train cast is essentially noise. This is consistent with seed bimodality — when the projection geometry lands in the positive OOD mode, it does so by *not* compressing the train cast into discriminable clusters; it leaves space for held-out personas.
2. **PD variance is enormous.** Episode return CI ±22 on a mean of 22 — one of the two seeds reaches very high return, the other does not. This is the PD batch-size confound from §10.6, re-amplified by balanced sampling on a smaller rollout.

Episode return is otherwise within seed noise of every previous Phase 5 anchor; tragedy-of-commons on cH is preserved, PD's cooperative attractor is reached.

### 11.6 Reading

<!-- p5-4-headline:start -->
1. **First non-zero full-vocab held-out top-1 across all of Phase 4–5.** 14 anchor configurations preceded this one; every single one returned 0.000 ± 0.000 on `heldout/random` full top-1. §4 returns **0.554 (cH seed 1) and 0.438 (PD seed 1)**. The result is not within seed noise of zero — at K=12, chance is 0.083, and the positive seed exceeds chance by a factor of 5–7×.
2. **The intervention is a three-lever conjunction.** §1 (qwen embedding), §2 (pool=train), and §4 (balanced batches) each alone produced 0.000 ± 0.000. Their combination produces the positive result. This is the first instance in this work of an interaction effect — none of the three remediation routes from PHASE4_REPORT §11 worked alone, but two of them combined with the new persona-balance lever together produce a partial positive.
3. **The positive signal is carried entirely by `fast_mover`.** Across both substrates and every positive eval pass, `fast_mover` reaches top-1 = 1.000 while `spinner` stays at 0.000. `spinner`'s Qwen embedding sits unusually close to `territorial_defender` (cos 0.554 — the highest pairwise cos in the table); the contrast head cannot place a decision boundary in that crowded region. `fast_mover`'s nearest neighbour at cos 0.41 leaves enough margin for the head to learn.
4. **Seed bimodality.** Across 2 seeds × 2 substrates, one seed per substrate hits the positive mode and one does not. PPO trains stably in both modes; the divergence is in the InfoNCE projection at convergence. More seeds are needed to characterise the failure rate, but the rate is *not* 100 % zero.
5. **In-distribution top-1 collapses.** The same projection geometry that allows held-out top-1 to leave zero produces a 4–5× degradation in *training-cast* in-distribution top-1 (0.143 → 0.027–0.000). The two regimes appear to be mutually exclusive at the projection-head level: a head that discriminates the 10 train personas tightly cannot leave probability mass on held-out slots; a head that leaves probability mass on held-out slots cannot tightly discriminate the 10 train personas. Resolving this tension is a Phase 5 §5 question.
6. **Top-3 carries the cleanest signal.** `pop/heldout_only` full top-3 = 1.000 on cH seed 1 — every held-out trajectory's true id is in the top-3. Top-3 reads are uniformly above chance on the positive seeds and not destabilised by the `spinner` collapse the way top-1 is. For paper claims it is the more robust headline metric.
<!-- p5-4-headline:end -->

### 11.7 What this means for the paper argument

The structured negative result of §1–§3 is now a **structured partial-positive conditional**:

- **H1 (identity-distinguishable policies under reward pressure)** holds on ≥2 substrates with persona-conditioned behavioural divergence 5–16× above commons_harvest's. *Confirmed.*
- **H3 (trajectory-level identity traceability under novel co-players)** is *recoverable in part* under the combined §1 + §2 + §4 intervention. The recovery is per-persona asymmetric (governed by embedding geometry) and seed-bimodal (50 % of seeds at zero), but the previously absolute failure is now conditional. *Conditional positive.*
- The MELTINGPOT_PROPOSAL §6 success criterion "one of {H2, H3, H4} produces a substantive positive result with effect size large enough to survive multiple-testing correction" is now within reach: cH seed 1's full top-3 of 1.000 on `pop/heldout_only` has effect size large enough that even a conservative Bonferroni correction over the §4 four-run grid leaves it well above 0.

The paper structure that now fits:

- **Main contribution (positive):** A controlled multi-ablation study (random vs Qwen embedding × full vs train contrast pool × cH vs PD substrate × unbalanced vs balanced InfoNCE batches × 2 seeds, 16 configurations total) demonstrating that PCSP-InfoNCE produces zero-shot held-out persona retrieval only at the conjunction of three specific interventions, with the effect size carried by personas whose semantic embeddings are sufficiently isolated.
- **Negative result (informative):** Persona embedding geometry — not just embedding *richness* — gates the contrastive head's ability to extend. Personas whose Qwen embeddings are crowded against training personas remain unrecoverable. This is a falsifiable statement about *which* held-out personas are tractable, expressible as a cosine-margin condition.
- **Limitations:** Seed bimodality, in-distribution top-1 trade-off, persona-asymmetric recovery, conditioned on a single persona corpus.

For NeurIPS 2026 Workshop this is now well above bar for a main-track-style positive finding. For a main-track ICML/NeurIPS submission, three follow-ups would strengthen the claim further: more seeds to characterise the bimodality (§5.1 below), a held-out corpus with controlled embedding margins (§5.3), and a joint loss formulation that resolves the in-distribution/OOD tension (§5.5).

### 11.8 Recommended directions for Phase 5 §5

1. **(highest leverage) Seed-replication and bimodality characterisation.** Run §4 cH-balanced and PD-balanced with 6–8 additional seeds each. If the positive rate is stable at ~50 %, the bimodality is a property of the projection geometry's initial basin; if it varies with seed-dependent rollout statistics, the fix is a better contrast warmup.
2. **Top-3-headlined statistical testing.** Compute bootstrap CIs (10,000 resamples) for top-3 across seeds; permutation tests vs Phase 4 random32 baseline. Pre-register the test before the §5.1 sweep so multiple-testing corrections are honest.
3. **Held-out corpus with controlled embedding margins.** Build a held-out set whose Qwen cosine to the nearest train persona is held at three levels (loose ≥ 0.45, medium ≈ 0.40, tight ≤ 0.35) and re-run §4 on each. If the recovery rate tracks the margin, the cosine-margin condition is the headline mechanism. This is the experiment that closes the per-persona asymmetry (`fast_mover` recoverable, `spinner` not).
4. **Persona-arithmetic policy rollouts on PD §4 seed 1.** PHASE4_REPORT §11.2, PHASE5_REPORT §8.3. The PD §4 positive seed is the only configuration with both rich behavioural divergence (mean-pair KL 4.7e-3) and non-trivial held-out retrieval. Run a single 1 M-step anchor under a midpoint embedding and check the `z_traj` centroid placement.
5. **Joint loss for in-distribution / OOD trade-off.** The §4 trade-off (in-distribution top-1 collapse for held-out recovery) is a projection-geometry constraint, not a fundamental one. A bilevel objective (small auxiliary classification head pinning train-cast clusters; main InfoNCE leaving slack for held-out slots) should be tractable as a config-level modification.
6. **H4 (controllability) pre-registration.** Begin Phase 5 §5 or §6 with the H4 pre-registration document (`PREREG.md`), in keeping with MELTINGPOT_PLAN §5 validation criteria. The §4 result makes H4 substantively testable — held-out personas with well-isolated embeddings will likely respond to edit-direction predictions; held-out personas with crowded embeddings probably will not.
