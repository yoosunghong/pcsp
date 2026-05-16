# MELTINGPOT_FEAT.md

**Technical Architecture Specification: PCSP × Melting Pot**

**Status:** Specification document. Defines the engineering contracts the implementation must meet.
**Cross-references:** `MELTINGPOT_PROPOSAL.md` (motivation), `MELTINGPOT_PLAN.md` (phased work), `MELTINGPOT_RESEARCH_QUESTIONS.md` (claims).
**Audience:** Implementers, code reviewers, and external reproducers.

---

## 1. Scope

This document specifies the architecture of the PCSP integration with Melting Pot 2.0. It is not a literature review and not a result report. It defines:

- The persona encoding pipeline carried from v3.
- The shared policy architecture and its conditioning strategies.
- The trajectory encoder used by the InfoNCE consistency objective.
- The diversity regularizer.
- The Melting Pot adaptation layer (observation, action, partial observability, population).
- The metric implementations.
- The experiment configurations (training, rollout, evaluation).
- The repository structure.

Anything not specified here is intentionally left to implementer judgment. Anything specified here must not be changed without a recorded decision.

---

## 2. Core System Design

### 2.1 Persona encoder pipeline

The persona pipeline is reused unchanged from v3 to preserve cross-environment comparability.

```
persona_text: str
    │
    ▼
┌────────────────────────────────────────────────────────────┐
│  Qwen3-0.6B-Embed (frozen)                                 │
│    f_LLM: str → R^{d_LLM}, d_LLM = 1024 (model-dependent)  │
└────────────────────────────────────────────────────────────┘
    │
    ▼
┌────────────────────────────────────────────────────────────┐
│  LoRA-adapted projection W_proj : R^{d_LLM} → R^{d_p}      │
│    d_p ∈ {64, 128, 256} (sweep param; default 128)         │
│    Implemented as a 2-layer MLP with LoRA-style low-rank   │
│    adapters; trained jointly with the policy.              │
└────────────────────────────────────────────────────────────┘
    │
    ▼
persona_embedding: e_p ∈ R^{d_p}
```

Contracts:

- `f_LLM` is **frozen** for the duration of all reported experiments. Any change requires a versioned re-run.
- Persona text is tokenized exactly once per persona at corpus build time; the resulting embedding is cached. Runs read cached embeddings, not the encoder.
- The projection `W_proj` is *the only* persona-side learned component. Its parameter count must be reported in the paper.
- Persona embeddings are L2-normalized at the projection output. Downstream conditioning blocks assume unit-norm.

### 2.2 Shared policy architecture

The policy is shared across all personas: a single set of weights produces all behavior, with persona entering only through the conditioning channel.

```
Observation o_t (RGB egocentric H×W×3 + scalar aux)
    │
    ▼
┌───────────────────────────┐
│  Visual encoder (CNN)     │   IMPALA-style or NatureCNN
│  Output: z_v ∈ R^{d_v}    │   d_v = 256
└───────────────────────────┘
    │
    ▼
┌───────────────────────────┐
│  Aux-scalar embedding     │   small MLP, output d_aux = 32
└───────────────────────────┘
    │
    ▼
concat(z_v, z_aux) → z ∈ R^{d_v + d_aux}
    │
    ▼
┌───────────────────────────┐
│  Conditioning block       │   FiLM (default) or concat
│  (consumes e_p)           │
└───────────────────────────┘
    │
    ▼
┌───────────────────────────┐
│  Recurrent core (LSTM)    │   hidden d_h = 256, 1 layer
└───────────────────────────┘
    │
    ├─► Policy head (Linear → softmax over Discrete(A))
    └─► Value head (Linear → R)
```

Contracts:

- A *single* set of policy weights is shared across all personas, all training-population co-players, and all training seeds *within* a substrate. (Cross-substrate weights are not shared in the default configuration; see §6.)
- Persona conditioning *must* be applied through the conditioning block. It must not be concatenated to raw observation pixels.
- LSTM state is per-agent, per-episode. It is reset at episode boundaries. It is not shared across personas.
- The value head is also persona-conditioned (it sees the same `z'` post-conditioning). Persona-blind value heads are a documented ablation, not the default.

### 2.3 Conditioning strategies

Two variants are first-class:

#### FiLM (default)

```
Given z ∈ R^{d_z} and e_p ∈ R^{d_p}:
  (γ, β) = MLP_film(e_p) ∈ R^{2 d_z}
  z'    = γ ⊙ z + β
```

- `MLP_film` is a 2-layer MLP with hidden 2 d_z.
- Applied at the post-encoder layer by default. A multi-site variant (applied at *every* recurrent step) is a documented ablation.
- Initialized so that γ ≈ 1, β ≈ 0 at step 0 (small final-layer init) to start as an identity transform.

#### Concat

```
z' = MLP_concat([z; e_p]) ∈ R^{d_z}
```

- `MLP_concat` is a 2-layer MLP, hidden = d_z + d_p.
- Documented as ablation; the v3 result is that concat vs. FiLM is split-dependent. Carry that finding forward and report both.

#### Other variants (ablations only)

- **Cross-attention.** Treat `e_p` as a memory of size 1 and attend from `z`. Reserved for ablation.
- **Prompt-prefix.** Prepend `e_p` as a "virtual token" to the recurrent core's input sequence. Reserved for ablation.
- **No conditioning (`B0`).** Discard `e_p` entirely; trained only with reward and (optionally) diversity loss. Required baseline.

### 2.4 Trajectory encoder

Used for the InfoNCE consistency loss. *Not* used by the policy at inference time.

```
Trajectory τ = (o_1, a_1, o_2, a_2, ..., o_T, a_T)
    │
    ▼
Per-step features f_t = [CNN(o_t); embed(a_t)] ∈ R^{d_f}
    │
    ▼
┌──────────────────────────────────┐
│  Trajectory encoder              │
│  Causal Transformer, 4 layers,   │
│  d_model = 128, 4 heads          │
│  Pool: attention-weighted mean   │
└──────────────────────────────────┘
    │
    ▼
g(τ) ∈ R^{d_g}, d_g = d_p = 128 (matched to persona dim)
```

Contracts:

- Trajectory encoder weights are *separate* from policy weights. They are trained jointly via the InfoNCE objective but do not produce actions.
- The CNN inside the trajectory encoder is *not* shared with the policy CNN. Sharing was tested in v3 and produced gradient interference; it is excluded.
- For long trajectories (T > 256), randomly sample a fixed-length sub-trajectory each minibatch.
- Output `g(τ)` is L2-normalized.

### 2.5 InfoNCE consistency objective

```
L_InfoNCE = - E_{τ, p}[ log  exp( <g(τ), e_p> / τ_temp )
                            / Σ_{p'} exp( <g(τ), e_{p'}> / τ_temp ) ]
```

Where:

- `τ_temp` is the InfoNCE temperature (default 0.1; sweep ∈ {0.05, 0.1, 0.2}).
- Negatives `p'` are sampled from the persona corpus *within* the minibatch (in-batch negatives), with at least 256 negatives per anchor.
- Optionally, a hard-negative mining pass selects personas whose embeddings are nearest in `e_p`-space; reserved for a documented ablation.

Contracts:

- `L_InfoNCE` is added to the PPO loss with coefficient `α_consist` (default 1.0; primary sweep variable for Pareto-frontier studies).
- `g(τ)` gradients flow into the trajectory encoder. They do *not* flow into the policy parameters by default. This isolation is the load-bearing v3 design choice and is preserved.
- An alternative coupling (gradients flow into policy too) is a documented ablation; v3 results suggested it destabilizes training.

### 2.6 Diversity regularizer

Encourages *behavioral* diversity across personas to prevent posterior collapse where the policy ignores `e_p`.

```
L_div = - E_{p, p' ~ corpus, p ≠ p'} [ D( π(·|s, e_p), π(·|s, e_{p'}) ) ]
```

Where:

- `D` is symmetric KL between policy action distributions evaluated at *the same* state `s`.
- Sampled at randomly chosen states from the rollout buffer.
- Coefficient `α_div` (default 0.01; sweep documented).

Contracts:

- Diversity is a *regularizer*, not a primary objective. A run with `α_div = 0` is the required ablation.
- Diversity must not be evaluated at states where the action mask collapses choices; mask-collapse states are excluded.

### 2.7 Total objective

```
L = L_PPO + α_consist · L_InfoNCE + α_div · L_div
```

PPO loss is standard (clipped surrogate, value loss with coefficient 0.5, entropy bonus 0.01 by default).

---

## 3. Melting Pot Adaptation

### 3.1 Observation handling

Melting Pot substrates expose per-agent observations as a dict, typically including:

- `RGB`: egocentric view, `(11, 11, 3)` or similar, `uint8`.
- `READY_TO_SHOOT`, `INVENTORY`, etc.: substrate-specific scalars.
- `WORLD.RGB`: the full world view (privileged; *not* fed to the policy).

The wrapper produces:

```
obs = {
  "rgb":  uint8 (H, W, 3),
  "aux":  float32 (d_aux,),   # substrate-specific scalars, masked to a fixed dim with NaN→0 zero-fill
  "mask": uint8 (A,),         # action mask, 1 = available
  "persona_embedding": float32 (d_p,),  # injected by wrapper from corpus cache
}
```

The policy CNN ingests `rgb` after a `uint8 → float32 / 255.0` normalization. `aux` is fed through the small MLP. `mask` gates the policy output softmax.

### 3.2 Social-state representation

The wrapper exposes a `social_state` dict *to the trajectory logger and metrics*, **never** to the policy:

```
social_state = {
  "visible_players": list[int],
  "recent_actions": list[list[int]],   # last K actions per visible player
  "resources_held": dict[str, int],
  "events": list[Event],               # substrate-defined events for this step
}
```

Contracts:

- The policy must not consume `social_state`. Doing so would leak privileged state and confound the partial-observability claim.
- Metrics (e.g., convention emergence) consume `social_state` from the trajectory log.

### 3.3 Temporal context handling

The recurrent core (LSTM) handles within-episode temporal context. The trajectory encoder handles cross-step pooling for the InfoNCE loss but is not used at inference.

Cross-episode memory is *not* supported in the default configuration. Each episode is a fresh LSTM init. Cross-episode persona consistency is the responsibility of the *embedding*, not of recurrent state.

### 3.4 Partial observability

Egocentric RGB is the primary partial-observability stress. The policy must work with no global state. The conditioning embedding is the only persistent identity signal.

Contracts:

- No oracle observations to the policy.
- No teacher-forcing or behavioral cloning against an oracle agent.

### 3.5 Population-level conditioning

Populations are constructed by sampling personas from a `PopulationSpec`:

```
PopulationSpec = {
  "size": int,
  "persona_pool": list[persona_id],
  "sampling": "uniform" | "weighted" | "fixed",
  "weights": optional[dict[persona_id, float]],
  "trait_distribution": optional[dict[trait_name, distribution_spec]],
}
```

For factorial population sweeps (H2), the `trait_distribution` parameter samples personas to match a target mean and dispersion on a designated trait axis (e.g., cooperativeness, risk aversion).

Population composition is logged with the trajectory; reviewers can reconstruct it from the registry entry.

---

## 4. Metrics

### 4.1 Semantic-behavior alignment

Definition: correlation between a persona's *embedding-space* neighborhood and its *behavioral* neighborhood.

```
For personas (p, q):
  d_emb(p, q)  = 1 - cos(e_p, e_q)
  d_beh(p, q)  = mean over (s ∈ shared state sample) of JS-divergence(π(·|s, e_p), π(·|s, e_q))

alignment = Spearman(d_emb, d_beh) over the persona corpus.
```

Reported as a scalar per substrate with bootstrap CI.

### 4.2 Trajectory–persona mutual information

Lower-bounded via the InfoNCE classifier (the trajectory encoder + cosine to persona embeddings, evaluated as a soft classifier):

```
I(τ; p) ≥ log K - L_InfoNCE_eval
```

Where `K` is the number of personas in the evaluation pool. Reported with the evaluation pool size noted; numbers are not comparable across pool sizes.

### 4.3 Convention emergence

Per substrate, a substrate-specific scalar capturing equilibrium sharpness:

- `commons_harvest`: Gini of returns × (1 − rate_of_resource_extinction).
- `clean_up`: rate of public-good provision; cooperator/defector partition stability.
- `coordination_room`: fraction of population converging on the same coordination point; entropy of equilibrium distribution.
- `territory`: territorial-claim stability across episodes.

Each metric is documented in `research/meltingpot/METRICS.md` with the exact computation.

### 4.4 Social specialization

The degree to which different personas in the same population occupy different behavioral roles:

```
specialization = 1 - mean_pairwise(JS-divergence(action_histogram(p_i), action_histogram(p_j))) / max_JS
```

Higher means more specialized; near 0 means all personas behave identically.

### 4.5 Policy divergence

Per persona pair, the symmetric KL of policy outputs at sampled states; reported as a population-level histogram, not a single number.

### 4.6 Identity consistency

Identification accuracy of the trajectory classifier on held-out trajectories. Two variants:

- **Closed-set:** the classifier picks among the training-persona pool.
- **Open-set (recommended):** the classifier outputs a similarity to each persona embedding; identification accuracy is computed only on personas the classifier *also* sees during evaluation.

Both reported separately. Bootstrap CIs across episodes.

---

## 5. Experiment Configurations

### 5.1 Baselines

| Name | Description | Role |
| :-- | :-- | :-- |
| `PCSP-full` | Default architecture, FiLM, consistency + diversity. | Primary method. |
| `PCSP-concat` | Concat conditioning, otherwise default. | Conditioning ablation. |
| `PCSP-no-consist` | `α_consist = 0`. | Consistency ablation. |
| `PCSP-no-diverse` | `α_div = 0`. | Diversity ablation. |
| `B0-unconditioned` | No persona signal, single shared policy. | Persona-blind floor. |
| `B1-prompt-only` | Persona text concatenated to observation as one-hot ID; no encoder. | Encoder ablation. |
| `B2-per-persona-PPO` | One PPO policy per persona, trained independently. | Specialist ceiling. |
| `B3-population-play` | Standard Melting Pot baseline (e.g., A3C / PPO with no persona signal). | External-baseline anchor. |

`B2` is a ceiling not a competitor: it has O(N_personas) parameters and is included to show how much PCSP gives up by sharing.

### 5.2 Training configs

Defaults per substrate; substrate-specific overrides documented per run.

```yaml
ppo:
  rollout_length: 128
  num_envs: 64
  num_epochs: 4
  minibatch_size: 1024
  clip_eps: 0.2
  gae_lambda: 0.95
  gamma: 0.99
  entropy_coef: 0.01
  value_coef: 0.5
  lr: 3e-4
  lr_schedule: linear_decay_to_0
  total_env_steps: 5e8   # per substrate, per seed; reduce for ablations
optim:
  optimizer: adam
  betas: [0.9, 0.999]
  eps: 1e-5
  grad_clip: 0.5
persona:
  d_p: 128
  conditioning: film
trajectory_encoder:
  layers: 4
  d_model: 128
  heads: 4
losses:
  alpha_consist: 1.0
  alpha_div: 0.01
  infonce_temp: 0.1
```

### 5.3 Rollout configs

```yaml
rollout:
  num_workers: 32
  envs_per_worker: 2
  population_spec:
    size: <substrate-specific>
    sampling: "weighted"
    persona_pool: train_persona_split
  episode_cap: substrate-default
  trajectory_logging: enabled
  log_downsample_rgb: true
  downsample_to: [22, 22]
```

### 5.4 Evaluation splits

Two orthogonal axes:

- **Persona split:** `train_persona` vs. `test_persona`. Test personas have *no* gradient pass during training.
- **Population split:** `train_population` (composed of policies seen in training) vs. `test_population` (Melting Pot's held-out evaluation populations: focal player among unfamiliar co-players, exploiter pairs, etc.).

The 2×2 grid of (persona × population) is the standard evaluation cell.

### 5.5 Held-out persona protocols

- 60/40 train/test split of personas per substrate (mirroring `train_240_v3 / test_60_v3` proportions).
- Stratification: maintain trait-distribution balance across splits.
- Re-use v3 splits where persona corpus overlaps.

### 5.6 Held-out population protocols

- Use Melting Pot's standard evaluation populations.
- Augment with `test_persona` agents drawn from PCSP itself (i.e., test personas embedded in test populations).
- Report all four cells.

---

## 6. Directory Structure

```
research/
  meltingpot/
    MELTINGPOT_PROPOSAL.md
    MELTINGPOT_PLAN.md
    MELTINGPOT_FEAT.md            # this file
    MELTINGPOT_RESEARCH_QUESTIONS.md
    REQUIREMENTS.lock
    BUDGET.md
    SUBSTRATES.md
    ACTIONS.md
    PERSONA_PIPELINE.md
    METRICS.md
    COMPUTE.md
    PREREG.md                     # committed before H4 edit experiments run
    README.md
    embeddings/                   # cached persona embeddings
      <encoder_hash>/
        personas_300_v3.npz
    classifiers/                  # frozen identification classifiers per substrate
      <substrate>/<run_id>.pt
    registry/                     # one JSON per run
      <run_id>.json
    runs/
      phase3/<run_id>/
      phase4/<run_id>/
      phase5/<run_id>/
    results/
      tables/
      figures/
src/
  env/
    meltingpot/
      __init__.py
      wrappers.py
      substrate_factory.py
      observation_adapters.py
      population.py
  models/
    meltingpot/
      visual_encoder.py
      policy.py
      trajectory_encoder.py
  algo/
    meltingpot/
      pcsp_ppo.py
      infonce.py
      diversity.py
  eval/
    meltingpot/
      identification_classifier.py
      convention_metrics.py
      controllability_eval.py
scripts/
  run_pcsp_meltingpot.py
  run_eval_meltingpot.py
  replay_meltingpot.py
  inspect_meltingpot_run.py
  audit_runs.py
  test_env_meltingpot.py
paper/
  meltingpot_main/
    main.tex
    figs/
    tables/
    refs.bib
```

Contracts:

- `research/meltingpot/` is for documents, results, and registry only. No source code.
- `src/env/meltingpot/`, `src/models/meltingpot/`, `src/algo/meltingpot/`, `src/eval/meltingpot/` are isolated namespaces. They may import from `src/env/`, `src/models/`, etc., but must not modify v3 code paths.
- v3 code paths under `src/env/mini_inzoi_v3.py` and friends remain frozen for the purposes of Mini-Inzoi reproducibility.

---

## 7. Implementation Contracts and Invariants

These are not optional. Violations are bugs.

1. The persona encoder is frozen. No gradient flows into Qwen3-0.6B-Embed.
2. The persona projection `W_proj` is the only persona-side learned component.
3. The policy CNN does not share weights with the trajectory encoder CNN.
4. Trajectory encoder gradients do not flow into the policy by default.
5. The policy does not consume `social_state`.
6. All run launches require a clean git tree; commit hash is recorded in the registry.
7. Persona embeddings are L2-normalized.
8. Action masks are honored by the policy at evaluation time.
9. Random seeds are derived from the `RunSpec` via a single `seed_everything` call.
10. No multi-substrate weight sharing in the default configuration.

---

## 8. Performance and Resource Targets

Targets are *engineering goals* for sanity-checking, not paper claims.

- Throughput (per substrate, single 8×A100 node): ≥10k env-steps/sec aggregate.
- Memory per GPU: ≤40 GB at default config.
- Persona-embedding lookup: O(1) per agent per episode; embeddings precomputed and cached.
- Trajectory logging overhead: ≤5% of training wall-clock.

If targets are missed by >2×, treat as a Phase 6 task.

---

## 9. Open Engineering Questions

These are not closed; document the decision when made.

- Frame stacking vs. LSTM-only memory. v3 uses no frame stacking; Melting Pot baselines vary.
- IMPALA CNN vs. NatureCNN. Default IMPALA; NatureCNN is the documented fallback.
- Single-agent training (one PCSP agent + frozen co-players) vs. self-play (population of PCSP agents). Default: self-play with mixed personas. Single-agent training is a documented ablation.
- Whether the value head should be persona-conditioned (default: yes; ablation: no).
- Whether to use centralized critics (CTDE). Default: decentralized critics. Centralized critics are a follow-up.

These open questions are flagged here so reviewers can see what was resolved at implementation time.
