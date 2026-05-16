"""Persona embedding sources.

Phase 2 supports two sources:

- ``random``: deterministic Gaussian embeddings derived from
  ``hash(persona_id, dim, seed)``. Reproducible across hosts (uses
  ``numpy.random.default_rng`` seeded from a SHA-256 of the persona id).
- ``cached``: load a ``{"ids": [...], "embeddings": tensor}`` payload from a
  ``.pt`` or ``.npz`` file. Phase 3 will populate this with real LLM
  embeddings.

The encoder is *frozen*: the embedding table is a buffer, not a trained
parameter. The trainer never updates these vectors — only the downstream
projection / conditioning module is learnable. This is required so that
the persona representation remains a stable side-channel and so that
Phase 3's InfoNCE consistency loss has a fixed anchor space.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Iterable

import numpy as np
import torch
import torch.nn as nn

from .registry import PersonaRegistry


def _seed_from_id(persona_id: str, salt: int) -> int:
    h = hashlib.sha256(f"{salt}:{persona_id}".encode("utf-8")).digest()
    # Use first 8 bytes as unsigned int seed.
    return int.from_bytes(h[:8], byteorder="big", signed=False)


def _deterministic_vec(persona_id: str, dim: int, salt: int) -> np.ndarray:
    rng = np.random.default_rng(_seed_from_id(persona_id, salt))
    v = rng.standard_normal(dim).astype(np.float32)
    # L2-normalize so all personas sit on the unit sphere — this gives
    # the projection module a well-conditioned input regardless of dim.
    n = np.linalg.norm(v) + 1e-8
    return v / n


class PersonaEncoder(nn.Module):
    """Frozen persona embedding table indexed by persona integer id."""

    def __init__(self, embeddings: torch.Tensor, ids: list[str]) -> None:
        super().__init__()
        if embeddings.dim() != 2 or embeddings.shape[0] != len(ids):
            raise ValueError(
                f"Embedding shape {tuple(embeddings.shape)} inconsistent with "
                f"{len(ids)} persona ids."
            )
        self.register_buffer("table", embeddings.float())
        self.ids = list(ids)
        self.embedding_dim = int(embeddings.shape[1])

    def forward(self, persona_idx: torch.Tensor) -> torch.Tensor:
        return self.table.index_select(0, persona_idx.long())


def build_encoder(
    registry: PersonaRegistry,
    *,
    source: str = "random",
    embedding_dim: int = 32,
    cache_path: str | Path | None = None,
    seed: int = 0,
) -> PersonaEncoder:
    """Construct a frozen PersonaEncoder.

    Parameters
    ----------
    source:
        "random" → deterministic Gaussian per persona id.
        "cached" → load embeddings from ``cache_path``.
    embedding_dim:
        Only used for ``source="random"``.
    cache_path:
        Required for ``source="cached"``. Accepts ``.pt`` (torch save) or
        ``.npz`` payloads with keys ``ids`` (list of str) and ``embeddings``
        (2-D float array). Persona order is realigned to ``registry``.
    seed:
        Salt mixed into the per-persona hash for ``source="random"``.
    """

    ids = [p.id for p in registry.personas]
    if source == "random":
        mat = np.stack([_deterministic_vec(pid, embedding_dim, seed) for pid in ids], axis=0)
        return PersonaEncoder(torch.from_numpy(mat), ids)

    if source == "cached":
        if cache_path is None:
            raise ValueError("cache_path is required when source='cached'")
        cache_path = Path(cache_path)
        if cache_path.suffix == ".pt":
            blob = torch.load(cache_path, map_location="cpu", weights_only=False)
            cached_ids = list(blob["ids"])
            emb = torch.as_tensor(blob["embeddings"], dtype=torch.float32)
        elif cache_path.suffix == ".npz":
            blob = np.load(cache_path, allow_pickle=True)
            cached_ids = [str(x) for x in blob["ids"]]
            emb = torch.as_tensor(blob["embeddings"], dtype=torch.float32)
        else:
            raise ValueError(f"Unsupported cache format: {cache_path}")
        # Realign to registry order.
        index_map = {pid: i for i, pid in enumerate(cached_ids)}
        missing = [pid for pid in ids if pid not in index_map]
        if missing:
            raise KeyError(f"Cached embeddings missing persona ids: {missing}")
        order = torch.tensor([index_map[pid] for pid in ids], dtype=torch.long)
        return PersonaEncoder(emb.index_select(0, order), ids)

    raise ValueError(f"Unknown persona source: {source!r}")
