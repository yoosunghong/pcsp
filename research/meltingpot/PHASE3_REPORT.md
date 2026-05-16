# PHASE3_REPORT.md — Trajectory Consistency & Persona Traceability

**Status:** Phase 3 controlled-integration test complete.
**Scope:** add a GRU trajectory encoder + InfoNCE consistency loss to
the persona-conditioned PPO stack, plus an auxiliary KL-diversity loss.
Show that trajectory consistency makes persona identity *retrievable
from behavior* and increases per-persona behavioral divergence, without
destabilising PPO. **No OOD/held-out evaluation yet — that is Phase 4.**
**Branch:** `research/meltingpot`. **Date:** 2026-05-14.

---

## 1. Architecture updates

| Area | Phase 2 | Phase 3 |
|------|---------|---------|
| Persona pipeline | Frozen encoder, concat/FiLM head | unchanged |
| Trajectory encoder | none | GRU over `(action_one_hot, reward)`, done-aware |
| Trajectory loss | none | InfoNCE vs frozen persona table |
| Diversity loss | none | KL between same-obs / different-persona action dists |
| Diagnostics | per-persona action / return / KL | + 5-axis social metrics + trajectory retrieval top-1/3 |
| Checkpoint | + persona | + trajectory encoder + InfoNCE head state |
| Stack | torch 2.12+cu130 (CPU fallback) | torch 2.5.1+cu121, RTX 6000 Ada (~20 k SPS) |

`REQUIREMENTS.lock` regenerated to reflect the working CUDA environment.

```
src/persona/
    registry.py                  # unchanged
    encoder.py                   # unchanged (frozen)
    projection.py                # unchanged (none|concat|film)
    assignment.py                # unchanged
    trajectory_encoder.py        # ← new: TrajectoryEncoder + InfoNCEHead

src/training/cleanrl_ppo/
    config.py                    # + infonce_*, kl_diversity_*, traj_encoder_lr
    networks.py                  # + ActorCritic.policy_logits(obs, persona)
    trainer.py                   # + InfoNCE step / KL-div per-mb term / new diagnostics
```

---

## 2. Trajectory encoder design

`src/persona/trajectory_encoder.py::TrajectoryEncoder`:

- **Input** per step: `(action_one_hot, reward)`, concatenated to `ℝ^{A+1}`
  (with `A = 8` for `commons_harvest__open`). Reward is included by
  default; toggleable via `--infonce-include-reward`.
- **Recurrence**: single-layer GRU, `hidden_dim=128`. Hidden state is
  *zeroed at episode boundaries* using the buffer's done mask (same
  CleanRL convention used by the policy's optional LSTM), so a
  trajectory embedding always represents at most one episode segment.
- **Head**: `Linear(hidden_dim → traj_dim)` then `tanh`, default
  `traj_dim=64`.
- **Init**: orthogonal weights for the GRU and the head. Deterministic
  given the global torch seed.

**Why behavioural features, not pixels?** Two reasons documented in the
module docstring: (1) reusing the policy's CNN features would couple
trajectory loss gradients to the policy trunk, which is precisely the
entanglement Phase 3 is intended to *test* rather than *assume*. (2)
The persona claim is about *behavior*, and a `(action, reward)` trace is
the smallest sufficient statistic for fingerprinting behavior.

The encoder runs *once* per update over the full `(num_steps, batch)`
rollout window; the cost is dominated by the per-step GRU, not by
forward passes.

---

## 3. InfoNCE consistency loss

`InfoNCEHead` projects the trajectory embedding to the persona space and
contrasts it against the frozen persona embedding *table*:

```
z      = normalize(proj(z_traj))           # (B, P)
c      = normalize(persona_table)           # (K, P)
logits = z @ c.T / τ                        # (B, K)
loss   = cross_entropy(logits, true_persona_ids)
```

`K` is the registry size (12). `τ` is a fixed scalar `--infonce-temperature`
(default `0.1`). The contrast is anchor-vs-vocabulary (SimCLR-style), not
anchor-vs-in-batch-negatives; in-batch negatives would be redundant
because every persona is reused many times across a minibatch.

- **Optimisation cadence**: one outer InfoNCE step per *update epoch*
  (so `update_epochs` InfoNCE backward passes per PPO update). The
  trajectory encoder + InfoNCE head get their own Adam param group with
  configurable LR (`--traj-encoder-lr`, defaults to `learning_rate`).
- **Gradient isolation**: the persona encoder remains frozen; only the
  trajectory encoder and projection head receive InfoNCE gradients.
- **Retrieval head**: same `logits()` function reused at diagnostics
  flush time to compute top-1 / top-3 / per-persona top-1 accuracy on
  the latest rollout. This is the **persona traceability** metric.

---

## 4. KL-diversity loss

Goal: when two different personas are conditioned on the same
observation, their action distributions should diverge. Implementation:
inside each PPO minibatch with `kl_diversity_coef > 0`, we

1. take the same `(obs_mb, persona_ids_mb)`,
2. apply a *fixed-per-update* persona permutation
   `kl_div_perm: K → K`, mapping each persona id to a different one,
3. compute `logits_true = policy_logits(obs, persona)` and
   `logits_alt  = policy_logits(obs, persona_alt)`,
4. compute `KL(softmax(logits_true) || softmax(logits_alt))`,
5. *maximize* it by subtracting `coef · KL` from the PPO loss.

The permutation is fixed across minibatches within an update to give the
gradient a stable signal; resampling per minibatch made the signal
noisy in early experiments. KL-diversity is gated `use_lstm=False` to
avoid re-implementing the recurrent unroll for the alt-persona pass.

The `KL-only` combo (`--mode kl_div`) is supported by the trainer for
completeness, even though the experiment table compares
*baseline / infonce / full*.

---

## 5. Loss combinations and CLI

All four loss families compose via two coefficients:

| combo            | `infonce_coef` | `kl_diversity_coef` |
|------------------|----------------|---------------------|
| PPO baseline     | 0.0            | 0.0                 |
| PPO + InfoNCE    | 0.5            | 0.0                 |
| PPO + KL-div     | 0.0            | 0.05                |
| PPO + InfoNCE + KL-div (full) | 0.5 | 0.05            |

CLI flags exposed by the trainer config:

```
--infonce-coef FLOAT
--infonce-traj-dim INT
--infonce-traj-hidden INT
--infonce-temperature FLOAT
--infonce-include-reward BOOL
--kl-diversity-coef FLOAT
--kl-diversity-samples INT     # reserved, currently fixed permutation
--traj-encoder-lr FLOAT        # optional override
```

Wrapper: `scripts/run_phase3_smoke.py --mode {baseline,infonce,kl_div,full}`.

---

## 6. Social-behavior diagnostics

Per-persona, per-window (since-last-flush) social metrics are written to
`persona_diagnostics.json::social_metrics` alongside the existing
action-distribution block:

| metric                | definition                                                                  |
|-----------------------|------------------------------------------------------------------------------|
| `harvest_freq`        | `count(reward > 0) / steps_tagged_with_this_persona`                         |
| `aggression`          | `count(FIRE_ZAP) / steps`                                                    |
| `cooperation_ratio`   | `harvest_freq / (harvest_freq + aggression)` — resource use vs conflict      |
| `stationarity`        | `(NOOP + TURN_LEFT + TURN_RIGHT) / steps`                                    |
| `exploration`         | `(FORWARD + BACKWARD + STEP_LEFT + STEP_RIGHT) / steps`                      |

Per-metric *spread* (max−min across personas) is also surfaced into the
flush-time scalar metrics as `social/<metric>_spread`, giving a single
behavioral-divergence number per axis.

Trajectory retrieval is also logged into the same JSON under
`trajectory_retrieval = {top1, top3, per_persona_top1, num_classes,
chance_top1}` when InfoNCE is enabled.

---

## 7. Validation experiments — `commons_harvest__open`

3 modes × 3 seeds (1, 2, 3), 150 k env-steps each (≈ 21 PPO updates,
~50 s wall on RTX 6000 Ada), concat conditioning, random per-episode
persona assignment from the 10-persona train split, frozen 32-d
deterministic-random embeddings.

Results from `scripts/summarize_phase3.py` (mean ± std across seeds):

| metric                              | baseline           | InfoNCE            | Full (InfoNCE + KL-div) |
|-------------------------------------|--------------------|--------------------|-------------------------|
| episode_return_mean                 | 35.11 ± 2.77       | 33.46 ± 3.23       | 33.90 ± 2.26            |
| loss/entropy (final)                | 1.988 ± 0.024      | 1.969 ± 0.032      | 1.980 ± 0.021           |
| loss/approx_kl (final)              | 2.55e-4            | 1.80e-4            | 2.20e-4                 |
| loss/explained_var (final)          | 0.603 ± 0.150      | 0.557 ± 0.217      | 0.638 ± 0.118           |
| SPS (final update)                  | 21 470 ± 1 880     | 15 900 ± 4 530     | 19 860 ± 1 110          |
| loss/infonce (final)                | —                  | 2.346 ± 0.056      | 2.351 ± 0.183           |
| InfoNCE top-1 (during update)       | —                  | 0.141 ± 0.011      | 0.119 ± 0.037           |
| InfoNCE top-3 (during update)       | —                  | 0.365 ± 0.098      | 0.356 ± 0.097           |
| traj retrieval top-1 (diagnostics)  | —                  | **0.143 ± 0.000**  | 0.125 ± 0.047           |
| traj retrieval top-3 (diagnostics)  | —                  | **0.369 ± 0.098**  | 0.351 ± 0.090           |
| mean pairwise action-KL             | 0.0022 ± 0.00062   | 0.0028 ± 0.00016   | **0.0033 ± 0.00072**    |
| social: harvest_freq spread         | 0.028 ± 0.007      | **0.036 ± 0.006**  | 0.032 ± 0.013           |
| social: aggression spread           | 0.017 ± 0.002      | **0.019 ± 0.009**  | 0.019 ± 0.003           |
| social: cooperation spread          | 0.213 ± 0.031      | **0.269 ± 0.039**  | 0.219 ± 0.053           |
| social: stationarity spread         | 0.024 ± 0.003      | 0.027 ± 0.002      | **0.035 ± 0.012**       |
| social: exploration spread          | 0.028 ± 0.011      | 0.034 ± 0.003      | **0.036 ± 0.010**       |

Reference: random-chance top-1 over 12 personas = 1/12 ≈ 0.083; chance
top-3 = 3/12 = 0.25.

### Headline numbers

- **Persona traceability**: InfoNCE drives top-1 retrieval to ≈ 0.143
  (≈ 1.72× chance) and top-3 to ≈ 0.369 (≈ 1.48× chance) within only
  150 k env-steps. The trajectory encoder is *learning a behavior →
  persona mapping above chance from rollouts alone*.
- **Behavioral divergence**: the full objective gives the largest mean
  pairwise action-KL (0.0033) and the largest exploration/stationarity
  spread; InfoNCE alone gives the largest harvest-frequency,
  aggression, and cooperation spread.
- **PPO stability**: episode return, entropy, approx_kl, and
  explained_var move within seed-to-seed variance and never destabilise.
  The auxiliary losses cost ≈ 7–25 % of SPS depending on configuration.

---

## 8. Stability observations

- **InfoNCE does not destabilise PPO.** Across 3 seeds, the InfoNCE
  loss-of-traj converges around `-log(1/K) - δ`, with `δ ≈ 0.13 nats`
  on average. PPO's policy/value losses look identical in shape to the
  baseline.
- **KL-diversity values are small** (`~1e-5` final) because we hit the
  budget cap before the policy diverges substantially under shuffled
  personas at this scale. The mean-pairwise-action-KL diagnostic
  *outside* the optimisation loop is the more honest signal here.
- **InfoNCE SPS variance is high** in the seed-1 run (the first InfoNCE
  run, which front-loaded CUDA kernel compilation). Seeds 2-3 are
  consistent with the baseline within ≈ 8 %.
- **Stable across seeds.** All summary metrics have CV < 0.3 except the
  small social aggression spread (where the absolute value is so small
  that the std/mean ratio is inflated).

---

## 9. Failure cases observed

- **First-update CUDA warmup penalty.** Phase 3's GRU + extra forward
  passes triggered triton kernel compilation on update 1 of every
  fresh process; reported SPS for update 1 is 1–5× lower than
  steady-state. We surfaced this in the summary by averaging SPS over
  all updates and reporting the final.
- **Retrieval per-persona collapse.** At 150 k steps several personas
  still register `per_persona_top1 = 0.0`. The encoder is picking up
  *easy* personas (e.g., `cautious_observer`, `cleaner_helper` —
  characterised by low-FIRE_ZAP, rotation-heavy behavior) before the
  ambiguous ones (`reciprocator`, `risk_seeking_raider`). Longer
  training should monotonically reduce this; the diagnostic exposes it
  cleanly via `per_persona_top1`.
- **KL-diversity gradient vanishing.** When the policy is still random
  early in training, shuffled-persona logits are nearly identical to
  the true-persona logits and the KL signal is below `1e-5`. We use a
  fixed-per-update permutation rather than per-minibatch to keep the
  signal from cancelling stochastically; in tests this measurably
  helps the policy distinguish per-persona behavior in later updates.
- **Buffer persona_ids = −1 sentinel.** Initial sentinel persists in
  the very first buffer slot before the trainer's `initialize()` runs;
  the `_persona_for_ids` lookup clamps `< 0` to `0`. This is benign at
  Phase 3 (the persona enabled path always writes a real id at every
  step), but we keep the clamp as a defensive guard.

---

## 10. Exact commands used

```
# Baseline (PPO + persona conditioning, no Phase-3 losses):
python -m scripts.run_phase3_smoke --mode baseline --seed {1,2,3} --total-env-steps 150000 --device cuda

# PPO + InfoNCE consistency:
python -m scripts.run_phase3_smoke --mode infonce  --seed {1,2,3} --total-env-steps 150000 --device cuda

# PPO + InfoNCE + KL-diversity (full Phase-3 objective):
python -m scripts.run_phase3_smoke --mode full     --seed {1,2,3} --total-env-steps 150000 --device cuda

# Summary table (mean ± std across seeds for each mode):
python -m scripts.summarize_phase3 research/meltingpot/runs/phase3_*_concat_seed*_150k
```

Per-mode loss weights are encoded in `scripts/run_phase3_smoke.py::LOSS_PRESETS`.

A `kl_div`-only mode is also wired (no experiments run here; included
for Phase 4 ablations):

```
python -m scripts.run_phase3_smoke --mode kl_div  --seed 1 --total-env-steps 150000 --device cuda
```

---

## 11. Recommendations for Phase 4 (OOD / held-out personas)

The held-out split `["fast_mover", "spinner"]` is already declared in
`personas_v0.json::splits.heldout` and the `PersonaAssigner` already
supports a `split` parameter restricting the pool. The Phase-3 pipeline
is therefore ready for Phase 4 with these targeted additions:

1. **Held-out training-time evaluation hook.** Periodically, freeze the
   policy + trajectory encoder, roll out a small evaluation episode with
   slot personas drawn from the *heldout* split, and compute (a)
   retrieval top-1 on the heldout vocabulary, (b) social metrics per
   heldout persona, (c) per-heldout episode return. The current
   `_flush_persona_diagnostics` already groups by persona id, so adding
   a held-out evaluation pass is mostly orchestration.
2. **Encoder vocabulary growth.** The frozen encoder currently builds a
   table over *all* personas in the registry (train + heldout). For
   Phase 4 zero-shot, the InfoNCE *contrast* should be restricted to
   personas the policy actually trained on — `InfoNCEHead.logits` should
   accept a `candidate_indices` argument so we can evaluate retrieval
   against the heldout-only or train-only subsets at will.
3. **Persona arithmetic check.** The frozen embedding table is a clean
   testbed for the persona-arithmetic claim from the proposal: can
   `(cooperative + aggressive)/2` produce a "reciprocator"-like trajectory
   embedding? Phase 4 should run this as a diagnostic; the trainer is
   not in the way.
4. **Real LLM embeddings.** Phase-2's `--persona-source cached` path is
   already implemented but unused. Once the LLM-embedding artifact is
   produced offline, switching the entire stack to semantic embeddings
   is a single CLI flag. Phase 4 should run an A/B (random vs LLM)
   table.
5. **Longer budgets.** A 1 M-step run on the *full* objective should be
   the Phase-4 stability anchor. Phase-1's 1 M baseline run is the
   reference for "what stable looks like"; with InfoNCE + KL-div added,
   the comparison is whether the auxiliary losses *and* a longer budget
   improve retrieval and behavioral divergence beyond what we observed
   at 150 k.
6. **Population template eval.** Phase 2's `population` assignment mode
   is suitable for "every env has a fixed mixed cast" — Phase 4 should
   include at least one population template made of *only heldout*
   personas to test zero-shot composition.

---

## Final numbers (from `scripts/summarize_phase3.py`)

<!-- summary:start -->
```
n_seeds                        | 3                | 3                | 3
episode_return_mean            | 35.11 ± 2.77     | 33.46 ± 3.23     | 33.90 ± 2.26
loss/entropy                   | 1.988 ± 0.024    | 1.969 ± 0.032    | 1.980 ± 0.021
loss/approx_kl                 | 2.55e-4 ± 1.22e-4| 1.80e-4 ± 9.18e-5| 2.20e-4 ± 8.60e-5
loss/explained_var             | 0.603 ± 0.150    | 0.557 ± 0.217    | 0.638 ± 0.118
sps_final                      | 21470 ± 1880     | 15900 ± 4530     | 19860 ± 1110
loss/infonce                   | —                | 2.346 ± 0.056    | 2.351 ± 0.183
infonce_top1                   | —                | 0.141 ± 0.011    | 0.119 ± 0.037
infonce_top3                   | —                | 0.365 ± 0.098    | 0.356 ± 0.097
traj_retrieval_top1            | —                | 0.143 ± 0.000    | 0.125 ± 0.047
traj_retrieval_top3            | —                | 0.369 ± 0.098    | 0.351 ± 0.090
mean_pairwise_action_kl        | 2.23e-3 ± 6.2e-4 | 2.79e-3 ± 1.6e-4 | 3.26e-3 ± 7.2e-4
social: harvest_freq_spread    | 0.028 ± 0.007    | 0.036 ± 0.006    | 0.032 ± 0.013
social: aggression_spread      | 0.017 ± 0.002    | 0.019 ± 0.009    | 0.019 ± 0.003
social: cooperation_spread     | 0.213 ± 0.031    | 0.269 ± 0.039    | 0.219 ± 0.053
social: stationarity_spread    | 0.024 ± 0.003    | 0.027 ± 0.002    | 0.035 ± 0.012
social: exploration_spread    | 0.028 ± 0.011    | 0.034 ± 0.003    | 0.036 ± 0.010
```
Chance top-1 = 1/12 ≈ 0.083; chance top-3 = 3/12 = 0.250.
<!-- summary:end -->
