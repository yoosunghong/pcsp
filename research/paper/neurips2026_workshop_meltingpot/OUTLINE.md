# Workshop Paper Outline — PCSP on Melting Pot

**Working title:** *Persona-Conditioned Shared Policies under Multi-Agent Strategic Pressure: Cross-Substrate Identity, Held-Out Generalization, and an Embedding-Margin Condition*

**Target:** NeurIPS 2026 Workshop (Cooperative AI / Agentic AI). Deadline 2026-08-29.

**Length budget:** 8 pages excluding references (NeurIPS workshop standard). Aim 6 pages main + 2 pages results detail + appendix.

**Author:** Yoosung Hong.

---

## 1. Why this paper, given results to date

What we *have* (PHASE5_REPORT §1–§12):

- **H1 confirmed on 3 substrates with separated CIs** (cH n=2, PD n=2, stag n=3): mean pairwise action-KL on train/random pass at 0.0016 / 0.0094 / 0.0147 with non-overlapping bootstrap CIs. Closes MELTINGPOT_PROPOSAL §6 first criterion.
- **H3 substantive positive on cH at n=8:** held-out top-3 0.480 [0.257, 0.696]; top-1 0.364 [0.192, 0.554]. PHASE5_REPORT §12 closes MELTINGPOT_PROPOSAL §6 third criterion at the top-3 boundary.
- **Bimodality characterization (n=8 cH, n=8 PD):** sharp two-attractor distribution at the projection head; PPO is stable in every seed. Mechanistic positive finding.
- **Embedding-margin condition:** persona `spinner` (cos 0.554 from `territorial_defender`, the highest pairwise cosine in the corpus) is unrecoverable on 0/16 seeds × 2 substrates. Predicts when held-out recovery succeeds.
- **In-distribution / OOD trade-off:** the §4 configuration that recovers held-out personas pays at chance on in-distribution top-3 (0.225 [0.181, 0.281] vs 0.250 chance).

What we *don't* have:
- H5 Pareto frontier (PHASE5 §13 H5 sweep returns degenerate frontier on cH and stag — frame as bounded-scope negative if mentioned at all).
- H4 controllability (PREREG.md committed 2026-05-15; runs not yet executed). Out of scope for workshop version.
- H2 convention emergence. Out of scope.

What this scopes to:
- A **focused, multi-result workshop paper** centered on H1+H3 positives plus the bimodality / embedding-margin mechanistic story. No H5, no H4, no H2.

## 2. Story arc

> *Q:* Does linguistically-expressed identity survive multi-agent strategic pressure on Melting Pot?
> *A:* Yes — across three substrates from distinct categories, with cleanly separated bootstrap CIs (H1). Held-out persona recovery is achievable but conditional on an embedding-margin condition: it succeeds for personas with isolated semantic embeddings and fails for crowded ones. The mechanism is not PPO instability but a sharp two-attractor distribution at the InfoNCE projection head.

The arc avoids overclaiming (H5 negative is named in §Limitations) and converts the bimodality finding from "noise" to "characterized phenomenon with a falsifiable per-persona predictor" (the embedding-margin condition).

## 3. Section plan (numbered to match `main.tex`)

1. **Introduction (1 p)**
   - Identity-conditioned RL needs to be tested under strategic pressure
   - PCSP framework — single shared policy, frozen LLM persona embedding, PPO + InfoNCE consistency
   - Three contributions: (a) H1 cross-substrate, (b) H3 held-out at n=8, (c) embedding-margin condition + bimodality characterization
2. **Background and method (1 p)**
   - PCSP method recap (cite Mini-Inzoi paper or describe in 1 paragraph)
   - Melting Pot 2.4.0; substrate selection (3 categories: CPR, mixed-motive matrix, coordination)
   - Persona corpus v0 (12 personas, train 10 / heldout 2), Qwen3-Embedding-0.6B
3. **Experimental setup (0.75 p)**
   - Training config (1 M env-steps, 8 envs, PPO+InfoNCE preset, λ_InfoNCE=0.5)
   - Diagnostics protocol: OOD eval with 4 passes (train/random, heldout/random, all/population/mixed, all/population/heldout_only)
4. **H1 — Cross-substrate identity under strategic pressure (1.25 p)**
   - Headline table: cH/PD/stag mean_pair_kl on train/random with bootstrap CIs (Table 1)
   - Per-substrate seed-level scatter (Figure 1)
   - Reading: separated CIs across 3 substrates from distinct categories
5. **H3 — Held-out persona retrieval (1.5 p)**
   - The §4 balanced-pool intervention (PHASE5_REPORT §11)
   - n=8 results on cH (top-3 0.480 [0.257, 0.696])
   - PD secondary (n=8, 25 % landing rate, top-3 0.297 [0.078, 0.539])
   - Comparison vs Phase 4 random32 baseline (0 across the board)
6. **Bimodality and the embedding-margin condition (1.25 p)**
   - The two-attractor finding (Figure 2: histogram of per-seed full top-1)
   - PPO stability across seeds (negative result on a confounder)
   - Embedding-margin condition: spinner (cos 0.554) unrecoverable on 16/16; fast_mover recoverable on 7/16
7. **Discussion (0.5 p)**
   - In-distribution vs OOD trade-off (named, scoped, points to joint-loss future work)
   - Why the contribution is methodological *and* empirical
8. **Limitations (0.25 p)**
   - 12 personas, 3 substrates, no H4/H5/H2 in this version
   - H5 sweep returned degenerate Pareto in tested configurations (single sentence)
9. **Conclusion (0.25 p)**

## 4. Figures and tables

| ref | content | source |
|---|---|---|
| Table 1 | H1 cross-substrate `mean_pair_kl` with bootstrap CIs | PHASE5_REPORT §12, today's stag results |
| Table 2 | H3 cH n=8 OOD retrieval (heldout/random + population/heldout_only) | PHASE5_REPORT §12.3 |
| Table 3 | Persona-margin × recovery rate | PHASE5_REPORT §12.5 |
| Figure 1 | Seed-level mean_pair_kl scatter, 3 substrates | derive from `phase5_*_summary.json` + new stag runs |
| Figure 2 | Bimodality histogram of cH and PD per-seed full top-1 | PHASE5_REPORT §12.4 raw values |
| Figure 3 | Persona-cosine vs per-persona heldout top-1 (the embedding-margin scatter) | persona_emb_qwen_emb.pt + phase5_balanced OOD results |

## 5. What stays out

- Latency (Mini-Inzoi paper claim, not load-bearing here).
- Mini-Inzoi v1/v2/v3 results except as one-paragraph "prior work" reference.
- Human eval (irrelevant for Melting Pot identity claim).
- H5 Pareto plot (negative; one-sentence mention in Limitations).
- H4 and PREREG (committed but not yet executed).
- Any persona-arithmetic / joint-loss exploration (out of scope for this paper).

## 6. Re-use plan from `cog2026_main/`

Reuse:
- `\PCSP` macro definition + persona-encoding paragraph (Method §2)
- InfoNCE consistency loss equation block
- Refs to PCSP/PPO/InfoNCE/CleanRL

Replace entirely:
- All experiments and figures
- Intro framing (NPC scaling → social-agent identity)
- Related work (drop life-sim, add Melting Pot + cooperative AI)
