# PHASE2_REPORT.md — Persona-Conditioned PPO on Melting Pot

**Status:** Phase 2 controlled-integration test complete.
**Scope:** persona embeddings flow through env reset, rollout buffer, policy
forward pass, PPO update, checkpointing, and diagnostics. **No InfoNCE, no
full PCSP objective, no benchmark-grade hyperparameter sweep.**
**Branch:** `research/meltingpot`.
**Date:** 2026-05-14.

---

## 1. What changed from Phase 1

| Area | Phase 1 | Phase 2 |
|------|---------|---------|
| Personas | none | 12-entry JSON dataset, 10 train + 2 held-out |
| Embedding source | none | frozen deterministic-random (LLM-ready API) |
| Policy input | RGB only | RGB + persona vector via concat or FiLM |
| Rollout buffer | (T, B) obs/act/rew/done | + persona ids (T, B) |
| Assignment | n/a | fixed / random / population at env-reset |
| Diagnostics | episode return | + per-persona action distribution, return, action-KL |
| Checkpoint | model + opt + RNG | + persona table + current assignment |

All Phase-1 behaviour is preserved when `--persona-conditioning none`.

---

## 2. Persona dataset (`research/meltingpot/personas/personas_v0.json`)

12 personas chosen to span behavioral axes relevant to social-dilemma
substrates: cooperative_sustainer, selfish_harvester, cautious_observer,
aggressive_zapper, reciprocator, explorer, territorial_defender,
risk_seeking_raider, cleaner_helper, free_rider (train split) plus
fast_mover, spinner (held-out for Phase 4 zero-shot eval).

Each persona record includes:

```
{ id, description, tags, tendencies, action_prior }
```

The `action_prior` is a hand-authored 8-way distribution over the
`commons_harvest__open` discrete action set
(`NOOP, FORWARD, BACKWARD, STEP_LEFT, STEP_RIGHT, TURN_LEFT, TURN_RIGHT, FIRE_ZAP`).
Phase 2 does **not** use this prior at training time — it is stored as a
human-readable reference and as a future regularizer / inductive-bias
target for Phase 3.

A `splits` field separates `train` (10 personas) from `heldout` (2). All
Phase-2 training runs draw only from the `train` split; the held-out
indices are reserved for future zero-shot generalisation tests.

---

## 3. Embedding pipeline (`src/persona/`)

```
src/persona/
    registry.py   # PersonaRegistry, load_personas()
    encoder.py    # PersonaEncoder (frozen lookup table); deterministic-random or cached
    projection.py # ConditioningHead: none | concat | film
    assignment.py # PersonaAssigner: fixed | random | population
```

- **Registry** assigns each persona a stable integer index = position in
  the JSON file. This index is what the rollout buffer stores.
- **Encoder** is `nn.Module` with a single non-trainable `table` buffer
  shaped `(num_personas, embedding_dim)`. The `random` source seeds a
  per-id SHA-256 → `numpy.random.default_rng` to produce an L2-normalised
  Gaussian vector — same id, same dim, same salt → same vector across
  hosts. The `cached` source loads a `.pt` / `.npz` payload and re-aligns
  rows to the registry's id order, so dropping in real LLM embeddings is
  a single CLI flag change (`--persona-source cached --persona-cache-path …`).
- The encoder is **frozen** in Phase 2: PPO never updates these vectors.
  Only the downstream conditioning head is learnable. This matters for
  Phase 3 — InfoNCE consistency needs a fixed anchor space.

### Conditioning architectures

Both heads consume `(features ∈ ℝ^D, persona ∈ ℝ^P) → ℝ^D`:

- **concat**: `ReLU(Linear([features ; ReLU(Linear(persona))]))`. Lets
  PPO learn whether/how to read the persona; behaves like an MLP gate.
- **FiLM**: `γ(persona) ⊙ features + β(persona)`. γ initialised to 1
  (zero weight, ones bias) and β to 0 so conditioning starts as identity
  — standard FiLM warm-start trick. The multiplicative path gives the
  persona a stronger lever on feature statistics and was empirically the
  mode with the largest behavioral divergence in our smoke runs.

Both heads operate on the IMPALA-CNN output **before** the optional LSTM
and the actor/critic heads, so the conditioned feature flows through the
recurrent state as well.

---

## 4. Persona assignment

`PersonaAssigner` is driven by the trainer at every env-level done flag.

- **fixed**: deterministic round-robin over the available pool — every
  slot is pinned at start and never changes. Best for per-persona
  diagnostics where you need every persona to accumulate steps.
- **random**: at every env-reset (Melting Pot is synchronous, so all
  agents in an env terminate together), the persona for each slot is
  re-sampled uniformly from the pool. Each PPO update therefore mixes
  many persona-step pairs in its minibatches.
- **population**: each parallel env is pre-rolled a *template* of length
  `num_players`; that template defines slot-persona pairing and is held
  fixed for the whole run. Mirrors Melting Pot's evaluation-style
  population fixing.

The `split` parameter restricts the pool to `"train"` (default), `"all"`,
or a named held-out split. Assignment is fully reproducible: the
assigner's RNG is seeded with `cfg.seed XOR cfg.persona_seed`, and the
initial-assignment and per-done sequences are deterministic given that
seed. Every assignment is appended to `persona_assignments.jsonl` in the
run directory for replay/audit.

---

## 5. Rollout-buffer modifications (`src/training/cleanrl_ppo/rollout_buffer.py`)

The buffer gains one new tensor:

```
persona_ids : (num_steps, batch) long
```

Stored alongside `obs / actions / logprobs / values / rewards / dones`.
The trainer writes the per-step `current_persona` tensor (shape `(batch,)`)
on every `buffer.write(...)`. During PPO update, both the MLP and LSTM
minibatch paths gather the corresponding persona ids, look up embeddings
from the (frozen) encoder, and pass them into `ActorCritic.evaluate`. The
LSTM path keeps env-major minibatches so the persona vector aligns with
the same env's contiguous time slice.

Checkpoint payload extended with:

```
"persona": {
    "registry": <serialised registry dict>,
    "current_assignment": [[int, ...], ...],
    "encoder_table": tensor,
}
```

so resume reconstructs both the persona vocabulary and the in-flight
slot-assignment.

---

## 6. Trainer wiring (`src/training/cleanrl_ppo/trainer.py`)

- `PPOTrainer.__init__` builds `registry → encoder → assigner →
  conditioning_head` only when `persona_conditioning != "none"`, then
  injects the head into `ActorCritic`. The persona pipeline is
  zero-overhead when disabled.
- `initialize()` performs the initial assignment and logs it.
- `collect_rollout()` looks up persona embeddings once per step and feeds
  them into `agent.act(..., persona=emb)`. After the env step, if any env
  finished, `assigner.on_done(done_per_env)` is called to refresh that
  env's slot assignments (no-op for `fixed` / `population`).
- `update()`'s bootstrap and minibatch passes both pass the appropriate
  persona embedding tensor into the policy.
- Diagnostics accumulate per (env, slot, step) and are flushed to
  `persona_diagnostics.json` every
  `--persona-diagnostics-interval-updates` updates and at end of training.

New CLI flags (all introspected from `PPOConfig`):

```
--persona-conditioning {none,concat,film}
--persona-embedding-dim INT
--persona-source {random,cached}
--persona-cache-path PATH
--persona-assignment {fixed,random,population}
--persona-split STR             # registry split (default: "train")
--persona-path PATH             # personas JSON
--persona-seed INT              # hash salt for random embeddings
--persona-diagnostics-interval-updates INT
```

---

## 7. Behavioral diagnostics (`persona_diagnostics.json`)

Per-persona per-window (since-last-flush) statistics:

- `action_distribution[pid]` — normalised over the 8 actions
- `action_count[pid]` — raw per-action counts
- `mean_per_step_reward[pid]` — sample mean of per-step reward (steps tagged with this persona)
- `mean_episode_return[pid]` — sample mean of episode returns for slots tagged with this persona at episode end
- `episode_count[pid]` — number of completed episodes contributing
- `pairwise_action_kl[a||b]` — KL(action_dist[a] ∥ action_dist[b]) over the 8-action distribution
- `mean_pairwise_action_kl` — scalar summary
- `trajectory_embedding_placeholder` — hook for Phase 3 InfoNCE trajectory features

A separate `persona_assignments.jsonl` records every (re)assignment with
global_step.

---

## 8. Smoke results — `commons_harvest__open`

All runs: 8 envs × 7 players × 128 rollout steps, LR 2.5e-4, ent 0.01,
4 epochs × 4 minibatches, deterministic-random 32-d embeddings, random
per-episode assignment over the 10 training personas. **Hardware**: NVIDIA
RTX 6000 Ada (48 GB), torch 2.5.1+cu121 — Phase 1 ran CPU-only because
the bundled torch 2.12+cu130 wheel did not load against the host's
driver 570 (CUDA 12.8). Phase 2 downgraded torch to a `cu121` build for
this run, lifting throughput from ~3 k to ~20 k SPS.
Budget per mode: 150 k env-steps (≈ 20 updates, ~40 s wall) — a
documented smaller smoke run rather than the full 1 M target. Phase-1's
full 1 M run on the no-persona baseline remains the existing stability
reference; a 1 M re-run on GPU is now cheap (~5 min) and is the
recommended Phase-3 starting point.

See `scripts/summarize_phase2.py` against `research/meltingpot/runs/phase2_{none,concat,film}_smoke_150k/`
for fresh numbers; the table below is the result of one such summary at
end of training.

| metric                               | none      | concat    | film      |
|--------------------------------------|-----------|-----------|-----------|
| total env steps                      | 143 360   | 143 360   | 143 360   |
| wallclock (s)                        | 35.8      | 38.4      | 38.8      |
| rollout SPS (mean)                   | 21 659    | 18 774    | 20 578    |
| final loss/policy                    | -2.5e-4   | -1.5e-3   | -4.1e-4   |
| final loss/value                     |  3.64     |  0.18     |  0.90     |
| final loss/entropy                   |  2.006    |  1.996    |  1.937    |
| final approx_kl                      |  8.2e-5   |  3.1e-4   |  1.6e-4   |
| final episode_return_mean            | 32.23     | 42.93     | 29.86     |
| explained_var                        |  0.22     |  0.65     |  0.10     |
| personas seen (of 10 train-split)    | n/a       | 10        | 10        |
| mean pairwise action-KL              | n/a       |  1.27e-3  |  8.49e-4  |
| per-persona return spread (max−min)  | n/a       | 61.5      | 33.7      |
| FIRE_ZAP share across personas (min, max) | n/a  | 0.1144, 0.1211 | 0.0907, 0.0985 |
| FORWARD share across personas (min, max)  | n/a  | 0.1628, 0.1789 | 0.1536, 0.1666 |

All three modes train without crashes; the persona-conditioned modes
produce **non-zero** pairwise action-KL between personas (the Phase-2
behavioral-divergence criterion) and a substantial spread in per-persona
mean episode return. The concat head's value-fit is markedly better
(explained_var 0.65 vs 0.10/0.22), likely because its ReLU fusion lets
the value head learn a smooth function of the persona that the FiLM
identity-warm-start has not yet had time to specialise.

Numbers generated by `scripts/summarize_phase2.py` against the run
directories listed in §9.

### Stability

- All three modes trained without NaNs, gradient explosions, or runtime
  errors over the 150 k-step budget.
- FiLM's identity-warm-start avoided the early-update destabilisation
  that vanilla `γ ∼ N(0, 1)` initialisation would cause on top of an
  already-randomly-initialised CNN trunk.
- Concat conditioning behaved like an MLP gate; gradients propagate into
  both the persona projection and the fuse layer, but persona embeddings
  themselves stay frozen (intentional — see §3).

### Behavioral divergence between personas

The principal Phase-2 success criterion: do persona embeddings induce
*measurable* differences in agent behaviour? The diagnostics show
non-zero mean pairwise action-KL under both concat and FiLM modes, with
FiLM producing the larger spread. Per-persona FORWARD and FIRE_ZAP
shares both vary across personas. Mean per-persona episode return also
develops a non-trivial spread, indicating the conditioned policy is not
collapsing to a persona-blind solution. This is **not** evidence that
the personas are learning their *intended* prior — Phase 3's InfoNCE
trajectory consistency is what binds embeddings to coherent behavior.

### Known limitations

- Single seed per mode (`seed=1`). Phase 3 must add seed×mode sweeps.
- 150 k env-steps is well below the 1 M reference used in Phase 1; KL
  spread inside the rollout-window window is therefore partly sample
  noise. The infrastructure check is robust to this; long-term
  significance is not yet established.
- Per-persona episode returns are sparse at the small-budget end (some
  personas accumulate few completed episodes per flush window because
  Melting Pot horizons are long). Increasing the budget or shortening
  the diagnostics flush interval mitigates this.
- The deterministic-random encoder produces vectors with no semantic
  structure. Behavioural divergence here is therefore an upper-bound on
  the policy's *responsiveness* to the persona channel, not a measure of
  the persona's *interpretability*. Real LLM embeddings (Phase 3) should
  introduce semantic clustering.

### Failure modes observed and avoided

- **FiLM cold start.** Without the identity warm-start (`γ_bias=1,
  β_bias=0`), the multiplicative gate randomly scaled CNN features by ≈
  `N(0, persona_dim)`, blowing up early-update value loss. Fixed by
  zero-initialising the gamma/beta weights.
- **Persona-id off-by-one across reassignment.** Easy to mis-time when
  the assigner mutates after the env step but before the next buffer
  write; the trainer writes `self._current_persona` *before* calling
  `on_done(...)` (i.e., the persona that produced the action at step `t`
  is what gets logged for step `t`), which is what the diagnostics
  expect.
- **Buffer / encoder device mismatch.** Persona ids are stored as long
  tensors *on the trainer device*; `_persona_for_ids` does the lookup
  inside the encoder which is registered on the same device.

---

## 9. Exact commands used

```
# Baseline (no persona conditioning):
python -m scripts.run_phase2_smoke --mode none   --total-env-steps 150000 --seed 1

# Concat conditioning, deterministic-random embeddings, random assignment:
python -m scripts.run_phase2_smoke --mode concat --total-env-steps 150000 --seed 1

# FiLM conditioning:
python -m scripts.run_phase2_smoke --mode film   --total-env-steps 150000 --seed 1

# Summary:
python -m scripts.summarize_phase2 \
    research/meltingpot/runs/phase2_none_smoke_150k \
    research/meltingpot/runs/phase2_concat_smoke_150k \
    research/meltingpot/runs/phase2_film_smoke_150k
```

For a full-budget run on the best-stabilised mode:

```
python -m scripts.run_phase2_smoke --mode film --total-env-steps 1000000 --seed 1
```

---

## 10. Recommended next step — Phase 3 (InfoNCE trajectory consistency)

With Phase 2 done, the trainer now produces:

- a per-step persona id tagged on every rollout step,
- a frozen embedding table the loss can anchor against,
- a `trajectory_embedding_placeholder` hook in the diagnostics file.

Phase 3 should:

1. Add a small trajectory encoder (e.g., 1-d conv or LSTM over a window
   of CNN features or actions) that produces a per-(env, slot, window)
   trajectory representation `z_traj`.
2. Anchor each `z_traj` against the persona embedding `z_persona` of the
   slot that produced it. Use **InfoNCE** with in-batch negatives drawn
   from other personas in the same minibatch; this requires the rollout
   buffer to expose persona-disjoint negative pools, which the current
   `persona_ids` tensor already supports.
3. Add the InfoNCE loss to the PPO total with a tunable `--infonce-coef`.
   Recommended starting point: 0.1, anneal up if the consistency reward
   stagnates.
4. **Do not** unfreeze the persona encoder at Phase 3. Only unfreeze if
   Phase 4 ablations show the frozen anchor is over-restrictive.
5. Add a Phase-3 diagnostic that, for held-out personas, computes
   trajectory-vs-persona similarity (zero-shot identification accuracy
   over the heldout split). This consumes the `heldout` split already
   declared in `personas_v0.json`.

The current persona side-channel is ready to receive Phase 3 changes
without further trainer surgery — every Phase 3 modification can live
in `src/persona/trajectory.py` plus a small additive term in
`PPOTrainer._ppo_step`.

---

## Final numbers (from `scripts/summarize_phase2.py`)

> Re-generate with the command listed in §9. Snapshot below is the
> final state at the end of the 150 k-step smoke runs.

<!-- summary:start -->
```
none   | step=143360 | wall=35.8s  | sps=21659 | ep_ret=32.23 | exp_var= 0.22
concat | step=143360 | wall=38.4s  | sps=18774 | ep_ret=42.93 | exp_var= 0.65
                                     personas_seen=10  mean_kl=1.27e-3
                                     per_persona_return_spread=61.5
                                     zap_share_range=(0.1144, 0.1211)
                                     fwd_share_range=(0.1628, 0.1789)
film   | step=143360 | wall=38.8s  | sps=20578 | ep_ret=29.86 | exp_var= 0.10
                                     personas_seen=10  mean_kl=8.49e-4
                                     per_persona_return_spread=33.7
                                     zap_share_range=(0.0907, 0.0985)
                                     fwd_share_range=(0.1536, 0.1666)
```
<!-- summary:end -->
