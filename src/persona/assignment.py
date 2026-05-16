"""Persona assignment strategies.

Phase 2 supports three modes; all are reproducible given the trainer seed.

- ``fixed``: persona[slot] is determined at construction time from a
  deterministic round-robin over the available persona indices. The
  assignment never changes across episodes. Useful for per-persona
  diagnostics where you want each agent slot pinned to a known persona.
- ``random``: at every episode boundary (env-reset) the affected
  agent-slots get a fresh persona sampled uniformly from the available
  pool.
- ``population``: each parallel env is assigned a *template* — an
  ordered tuple of persona indices, length ``num_players``. The template
  defines the persona of each slot in that env and is held fixed across
  episodes (mirroring Melting Pot's "population" eval style).

A ``split`` parameter restricts the pool to a registry split (default
``"train"``); ``"all"`` uses every persona. The held-out split is reserved
for Phase 4 zero-shot evaluation.

Assignment is driven by the trainer at env-reset and at every per-(env,
slot) ``done`` flag. The assigner exposes ``initial()`` for the first
reset and ``on_done(done_mask)`` for in-episode rollover; both return the
current ``(num_envs, num_players)`` persona-index array.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .registry import PersonaRegistry
from .splits import build_population_templates, check_no_leakage, split_indices


@dataclass
class PersonaAssigner:
    mode: str
    num_envs: int
    num_players: int
    pool: list[int]          # available persona indices
    rng: np.random.Generator
    templates: list[list[int]] | None = None
    _current: np.ndarray | None = None

    def initial(self) -> np.ndarray:
        if self.mode == "fixed":
            slots = self.num_envs * self.num_players
            assignment = np.array(
                [self.pool[i % len(self.pool)] for i in range(slots)],
                dtype=np.int64,
            ).reshape(self.num_envs, self.num_players)
        elif self.mode == "random":
            assignment = self.rng.choice(
                self.pool, size=(self.num_envs, self.num_players), replace=True
            ).astype(np.int64)
        elif self.mode == "population":
            assert self.templates is not None and len(self.templates) == self.num_envs
            assignment = np.array(self.templates, dtype=np.int64)
        else:
            raise ValueError(f"Unknown assignment mode: {self.mode!r}")
        self._current = assignment
        return assignment.copy()

    def on_done(self, done_env_mask: np.ndarray) -> np.ndarray:
        """``done_env_mask``: bool array shape ``(num_envs,)``.

        Returns the post-reset persona assignment ``(num_envs, num_players)``.
        Only ``random`` mode mutates on done; ``fixed`` and ``population``
        keep their initial assignment forever.
        """
        assert self._current is not None
        if self.mode == "random":
            for env_idx in np.where(done_env_mask)[0]:
                self._current[env_idx] = self.rng.choice(
                    self.pool, size=self.num_players, replace=True
                ).astype(np.int64)
        return self._current.copy()

    @property
    def current(self) -> np.ndarray:
        assert self._current is not None
        return self._current.copy()


def build_assigner(
    registry: PersonaRegistry,
    *,
    mode: str,
    num_envs: int,
    num_players: int,
    seed: int,
    split: str = "train",
    population_kind: str | None = None,
) -> PersonaAssigner:
    """Build a persona assigner.

    Parameters
    ----------
    split:
        Which registry split to draw the pool from (``train``, ``heldout``,
        ``all``). For ``mode="population"`` with a non-default
        ``population_kind`` (``mixed``, ``heldout_only``, ``train_only``)
        the ``split`` parameter is ignored — the kind drives composition.
    population_kind:
        Composition rule for population templates. Default ``None`` keeps
        legacy behaviour (random sample from ``split``'s pool). Other
        kinds delegate to :func:`splits.build_population_templates` and
        ignore ``split``.
    """
    pool = split_indices(registry, split)
    if not pool:
        raise ValueError(f"Persona pool for split={split!r} is empty.")

    # Leakage check: if split=='train', assert no heldout id ever appears.
    if split == "train" and "heldout" in registry.splits:
        check_no_leakage(pool, registry.split_indices("heldout"))

    rng = np.random.default_rng(seed)

    templates: list[list[int]] | None = None
    if mode == "population":
        if population_kind is None or population_kind == "random_pool":
            templates = build_population_templates(
                registry,
                kind="random_pool",
                num_envs=num_envs,
                num_players=num_players,
                seed=seed,
                pool=pool,
            )
        else:
            templates = build_population_templates(
                registry,
                kind=population_kind,
                num_envs=num_envs,
                num_players=num_players,
                seed=seed,
            )

    return PersonaAssigner(
        mode=mode,
        num_envs=num_envs,
        num_players=num_players,
        pool=list(pool),
        rng=rng,
        templates=templates,
    )
