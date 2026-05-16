# BUDGET.md — Phase 0 Compute Estimate

**Status:** Phase 0 deliverable. Numbers in this file are extrapolations from a single measured datapoint, not a contract.
**Updated:** 2026-05-14
**Cross-references:** `MELTINGPOT_PLAN.md` (Phase 0), `REQUIREMENTS.lock` (pinned env), `SUBSTRATES.md` (selection).

---

## 1. Compute inventory

Single workstation. No cluster access assumed for Phase 0–3.

| Resource | Value |
|---|---|
| GPU | 1× NVIDIA RTX 6000 Ada Generation (48 GB VRAM) |
| GPU driver / CUDA | 570.133.07 / CUDA 12.8 |
| CPU | 32 logical cores |
| RAM | 125 GiB |
| Disk free | 697 GiB on `/` (NVMe) |
| OS | Linux 5.15 |

Wall-clock budget for the program: **not yet committed**. This document supplies the per-run cost so a budget can be set in the Phase 0 decision review.

---

## 2. Environment throughput (measured)

Single-process, random actions, no policy.

| Substrate | Players | Obs (per agent) | Env-steps/s | Agent-steps/s |
|---|---|---|---|---|
| `commons_harvest__open` | 7 | RGB 88×88×3 + scalars | **1,574** | **11,017** |

Method: 1,000 sequential env-steps after reset, `meltingpot.substrate.build`, `seed=0`, no batching.
Caveat: this is one substrate. Matrix-game substrates (e.g. `prisoners_dilemma_in_the_matrix__repeated`) are typically 2–3× faster (smaller maps, no rendering of large grids); territory/paintball substrates are typically 1.5–2× slower. Re-measure per substrate before committing a per-substrate budget.

---

## 3. PPO-step extrapolation

The plan asked for a 1M-step PPO shakedown on `commons_harvest__simple`. **`commons_harvest__simple` does not exist in Melting Pot 2.x**; the available variants are `commons_harvest__open`, `__closed`, `__partnership`. We use `__open` as the substitute.

The reference RLLib trainer (`examples/rllib/self_play_train.py` from the upstream repo, pinned to `ray[rllib]==2.5.0`) **does not run on a clean install** — see §5. Therefore the 1M-step shakedown number below is an *extrapolation* from env throughput plus standard PPO overhead, not a measurement.

Assumed PPO overhead, single GPU, IMPALA/NatureCNN-scale model (~1M params) + 256-cell LSTM, batched across rollout workers:

| Throughput regime | env-steps/s/GPU | Source |
|---|---|---|
| Env-only single-process (measured) | 1,574 | §2 |
| Env-only, 8-process subproc vec | ~8,000–10,000 | linear-ish scaling, capped by Python GIL boundaries |
| PPO with CNN+LSTM, on-policy, 1 GPU | ~3,000–6,000 | RLLib reference numbers on similar substrates |

1M env-step shakedown wall-clock estimate: **3–6 minutes** with a working PPO trainer at 3–6 k SPS.

50M env-step "single substrate, single seed" PCSP run (Phase 3 target): **2.3–4.6 hours**.

Phase 3–4 program total (5 substrates × 5 seeds × 6 cells [`PCSP-full`, `PCSP-no-consist`, `PCSP-no-diverse`, `PCSP-concat`, B1, B3]):
- Cells × seeds × substrates = 150 runs.
- Wall-clock per run ≈ 3 hours mid-estimate → **~450 GPU-hours**.
- Fits in ~3 weeks of single-GPU wall-clock if runs are serial. With 2 substrates running concurrently on the 48 GB card (separate processes, ~20 GB each), ~1.5 weeks.

These numbers do not include Phase 5 (population sweeps, persona edits) which scale multiplicatively with the number of population statistics and edit sets. Plan an additional **~300–600 GPU-hours** for Phase 5 at the factorial sizes implied by `MELTINGPOT_PLAN.md`.

**Total Phase 3–5 program estimate: 750–1,050 GPU-hours.**

---

## 4. Storage budget

Per Phase 1 trajectory format (`.npz` per episode, downsampled RGB), assuming:
- Episode length 1,000 steps × 7 agents = 7,000 agent-step records
- Per-step: 8-bit 88×88×3 RGB (23 KB) + persona embedding (4 KB float32 768-dim) + scalars (~0.5 KB) ≈ 28 KB
- Per episode ≈ 200 MB raw → ~30 MB compressed

For the Phase 3–4 program (150 runs × ~5,000 episodes/run): **~22 TB raw, ~3 TB compressed**.

Disk currently free: 697 GB. Trajectory dumps must go to external storage or be sampled. Recommendation: keep raw trajectories for **2 substrates × 2 ablations × 2 seeds** as a public release set; for the rest, log only summary statistics + a 5 % episode subsample. Estimated retained: **~150 GB**.

---

## 5. Reference-trainer engineering gap

The Phase 0 plan calls for verifying that "a reference PPO run on `commons_harvest__simple` completes a 1M-step shakedown without engineering changes."

**Result: gate FAILED.**

- The substrate `commons_harvest__simple` does not exist in Melting Pot 2.x. Substituted `commons_harvest__open`.
- The upstream reference trainer at `examples/rllib/self_play_train.py` requires `ray[rllib]==2.5.0` (released June 2023) and `gymnasium==0.26.3`. These resolve and install on Python 3.11 alongside `dm-meltingpot==2.4.0`.
- Importing the trainer fails: `ray.tune.logger.tensorboardx` references `np.bool8`, removed in numpy ≥ 1.24. `dm-meltingpot==2.4.0` pulls `numpy==2.4.4`. Downgrading numpy breaks `dm-meltingpot`.

Implication: the upstream RLLib example cannot serve as the project's training backbone without one of:
1. **Pinning to an older `dm-meltingpot` tag** that ships with `numpy<1.24`. Likely Melting Pot 2.1 or earlier. Cost: lose any substrate-set or substrate-config changes shipped in 2.2–2.4.
2. **Patching Ray 2.5.0** (`np.bool8` → `np.bool_`, similar small fixes). Engineering cost: hours, not days, but counts as "engineering changes" the Phase 0 gate explicitly forbids. Maintainability cost: ongoing patches as numpy/python evolve.
3. **Writing an in-house PPO trainer** on the PettingZoo Parallel API boundary (CleanRL-style, single-file PPO with CNN+LSTM). Engineering cost: ~1–2 weeks. Decoupled from Ray/RLLib version churn entirely. Aligns with `MELTINGPOT_FEAT.md`'s preferred boundary.

**Recommendation: option 3.** Justification: Phase 1 already requires a PettingZoo Parallel wrapper; bolting CleanRL-PPO on that boundary is incremental cost relative to the wrapper, and removes Ray as a dependency. Option 1 is acceptable as a short-term fallback for sanity-checking against published Melting Pot baseline numbers in Phase 4.

---

## 6. What this budget does NOT cover

- Multi-GPU / distributed PPO (Phase 6). Need re-estimation if scale-out is invoked.
- LLM persona-encoder forward passes. Frozen Qwen3-0.6B-Embed precomputation is one-shot and cheap (≤ 1 GPU-hour for 300 personas).
- Identification-classifier training (Phase 4). Cheap relative to PPO; estimate 1–2 GPU-hours per substrate.
- Pre-registered persona-edit experiments (Phase 5, H4). Scales with `(#edits × #base_personas × #seeds)`; not yet specified.
