"""Run config for the CleanRL-style PPO trainer.

Defaults target the Phase 1 smoke validation: ``commons_harvest__open``,
8 parallel envs (7 players each), 1M env-steps. Hyperparameters mirror the
CleanRL ``ppo_atari_envpool`` reference where the action space and reward
scale are comparable.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class PPOConfig:
    # Environment ------------------------------------------------------------
    substrate: str = "commons_harvest__open"
    num_envs: int = 8
    num_players: int | None = None  # None → substrate default roster
    async_envs: bool = True

    # Rollout ----------------------------------------------------------------
    # ``num_steps`` is per-env per-update. Effective batch =
    # num_envs * num_players * num_steps.
    num_steps: int = 128
    total_env_steps: int = 1_000_000

    # Optimization -----------------------------------------------------------
    learning_rate: float = 2.5e-4
    anneal_lr: bool = True
    gamma: float = 0.99
    gae_lambda: float = 0.95
    update_epochs: int = 4
    num_minibatches: int = 4
    clip_coef: float = 0.1
    norm_adv: bool = True
    clip_value_loss: bool = True
    ent_coef: float = 0.01
    vf_coef: float = 0.5
    max_grad_norm: float = 0.5
    target_kl: float | None = None  # set, e.g., 0.03 to early-stop bad updates

    # Architecture -----------------------------------------------------------
    use_lstm: bool = False
    lstm_hidden: int = 256
    feature_dim: int = 256

    # System -----------------------------------------------------------------
    device: str = "auto"  # "cpu", "cuda", "auto"
    mixed_precision: bool = False
    seed: int = 1

    # Persona conditioning --------------------------------------------------
    persona_conditioning: str = "none"      # none|concat|film
    persona_embedding_dim: int = 32
    persona_source: str = "random"          # random|cached
    persona_assignment: str = "random"      # fixed|random|population
    persona_split: str = "train"            # registry split to draw from
    persona_population_kind: str | None = None  # None|train_only|heldout_only|mixed|random_pool
    persona_path: str = "research/meltingpot/personas/personas_v0.json"
    persona_cache_path: str | None = None
    persona_seed: int = 0
    persona_diagnostics_interval_updates: int = 50

    # Phase 3 trajectory consistency / diversity ---------------------------
    infonce_coef: float = 0.0               # 0 → disabled
    infonce_traj_dim: int = 64
    infonce_traj_hidden: int = 128
    infonce_temperature: float = 0.1
    infonce_include_reward: bool = True
    # Phase 5 §2: which subset of the persona vocabulary forms the InfoNCE
    # candidate pool during *training*. "full" (default, Phase 4/5 §1
    # behaviour) trains the head to push observed trajectories away from
    # every non-target slot — including held-out slots, which is the failure
    # mode identified in PHASE5_REPORT §5. "train" restricts the pool to
    # ``persona_split`` indices so held-out slots receive zero gradient
    # signal during training; the head's test-time decision on held-out
    # candidates is then governed by the embedding cosine geometry alone.
    infonce_candidate_pool: str = "full"    # full|train
    # Phase 5 §4: persona-balanced InfoNCE mini-batches. When True, each
    # InfoNCE opt step resamples the per-trajectory inputs so every present
    # persona contributes ``infonce_per_persona`` trajectories (with
    # replacement when the rollout under-samples a persona). PHASE4_REPORT
    # §10 named persona-balance as the most likely cause of the no-budget-
    # gain observation in retrieval. 0 → auto = ceil(B/K) where B is the
    # rollout batch and K is the number of distinct persona ids present.
    infonce_balanced_batch: bool = False
    infonce_per_persona: int = 0
    kl_diversity_coef: float = 0.0          # 0 → disabled
    kl_diversity_samples: int = 1           # # of shuffled-persona draws per mb
    traj_encoder_lr: float | None = None    # None → use main learning_rate

    # Logging / checkpointing ------------------------------------------------
    run_name: str | None = None
    run_dir: str = "research/meltingpot/runs"
    log_interval_updates: int = 1
    checkpoint_interval_updates: int = 50
    tb_logging: bool = True

    # Derived ----------------------------------------------------------------
    extra: dict[str, Any] = field(default_factory=dict)

    def derive(self) -> dict[str, int]:
        """Return derived sizes."""
        num_players = self.num_players or 0  # 0 means unknown until env built
        return {
            "num_players": num_players,
            "num_steps": self.num_steps,
            "num_envs": self.num_envs,
        }

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
