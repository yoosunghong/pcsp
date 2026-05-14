"""Deterministic persona splits and population-template builders (Phase 4).

The registry already declares ``train`` and ``heldout`` splits in
``personas_v0.json``. This module wraps that declaration with a small,
strict API used by the trainer and the OOD evaluator:

- ``split_indices(registry, split)``: indices for a named split,
  validating that ``train`` and ``heldout`` are disjoint.
- ``check_no_leakage(...)``: assert that a candidate pool drawn for the
  training assigner does not contain any held-out indices.
- ``build_population_templates(...)``: enumerate ``num_envs`` templates
  of length ``num_players`` for one of:
      * ``train_only``   — players sampled uniformly from train pool
      * ``heldout_only`` — players sampled uniformly from heldout pool
      * ``mixed``        — first ⌈P/2⌉ players from train, rest from heldout
      * ``random_pool``  — uniform sample from a caller-supplied pool

Templates are generated with a ``numpy.random.default_rng`` seeded from
the trainer's seed XOR a fixed salt ``0x4E55``; the call signature is
fully deterministic given that seed and the registry order.

The module never touches torch — it returns plain Python lists of
ints — so it is safe to import in eval-only contexts that do not load
the model.
"""

from __future__ import annotations

import numpy as np

from .registry import PersonaRegistry


TEMPLATE_KINDS = ("train_only", "heldout_only", "mixed", "random_pool")
_TEMPLATE_SALT = 0x4E55  # fixed salt for reproducibility of templates


def split_indices(registry: PersonaRegistry, split: str) -> list[int]:
    """Indices for a named split. Validates train/heldout disjointness."""
    if split == "all":
        return registry.all_indices()
    if split not in registry.splits:
        raise KeyError(f"Unknown split: {split!r}; have {sorted(registry.splits)}")
    # Validate train/heldout disjointness if both present.
    if {"train", "heldout"} <= set(registry.splits):
        train = set(registry.split_indices("train"))
        held = set(registry.split_indices("heldout"))
        overlap = train & held
        if overlap:
            names = [registry.index_to_id(i) for i in sorted(overlap)]
            raise ValueError(f"train/heldout overlap: {names}")
    return registry.split_indices(split)


def check_no_leakage(pool: list[int], heldout: list[int]) -> None:
    """Raise if any heldout index appears in pool (training assigner pool)."""
    bad = set(pool) & set(heldout)
    if bad:
        raise AssertionError(
            f"Leakage: heldout indices in training pool: {sorted(bad)}"
        )


def _rng(seed: int) -> np.random.Generator:
    return np.random.default_rng(np.uint64(seed) ^ np.uint64(_TEMPLATE_SALT))


def build_population_templates(
    registry: PersonaRegistry,
    *,
    kind: str,
    num_envs: int,
    num_players: int,
    seed: int,
    pool: list[int] | None = None,
) -> list[list[int]]:
    """Return ``num_envs`` templates, each of length ``num_players``.

    ``kind`` selects the composition rule; ``seed`` is XORed with a fixed
    salt so two callers that pass the same ``seed`` see the same
    templates regardless of any other RNG state.
    """
    if kind not in TEMPLATE_KINDS:
        raise ValueError(f"Unknown template kind: {kind!r}; have {TEMPLATE_KINDS}")
    rng = _rng(seed)
    train = split_indices(registry, "train") if "train" in registry.splits else registry.all_indices()
    heldout = split_indices(registry, "heldout") if "heldout" in registry.splits else []

    def draw(p: list[int], n: int) -> list[int]:
        if not p:
            raise ValueError("Cannot draw from empty pool.")
        return list(rng.choice(p, size=n, replace=True).astype(int))

    templates: list[list[int]] = []
    for _ in range(num_envs):
        if kind == "train_only":
            templates.append(draw(train, num_players))
        elif kind == "heldout_only":
            templates.append(draw(heldout, num_players))
        elif kind == "mixed":
            n_train = (num_players + 1) // 2
            n_held = num_players - n_train
            tmpl = draw(train, n_train) + draw(heldout, n_held)
            rng.shuffle(tmpl)
            templates.append(tmpl)
        elif kind == "random_pool":
            assert pool is not None, "random_pool requires a pool argument"
            templates.append(draw(pool, num_players))
    return templates


def split_summary(registry: PersonaRegistry) -> dict:
    """Compact dict-of-ids for logging into run config / report."""
    out = {"num_personas": registry.num_personas, "splits": {}}
    for name in registry.splits:
        ids = registry.splits[name]
        out["splits"][name] = {"size": len(ids), "ids": list(ids)}
    if {"train", "heldout"} <= set(registry.splits):
        train = set(registry.split_indices("train"))
        held = set(registry.split_indices("heldout"))
        out["leakage_check"] = {"overlap": sorted(train & held), "disjoint": not (train & held)}
    return out
