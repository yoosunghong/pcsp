"""Persona registry: loads ``personas_v0.json`` and exposes a stable ordering.

The registry is the authoritative source of persona ids and the index used
by the rest of the pipeline. A persona's integer index is its position in
the ``personas`` list of the loaded JSON file — this index is what the
rollout buffer stores and what the encoder uses to look up embeddings.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


DEFAULT_PERSONA_PATH = "research/meltingpot/personas/personas_v0.json"


@dataclass
class Persona:
    id: str
    description: str
    tags: list[str]
    tendencies: dict[str, str]
    action_prior: list[float] | None = None


@dataclass
class PersonaRegistry:
    path: str
    personas: list[Persona]
    splits: dict[str, list[str]] = field(default_factory=dict)
    action_labels: list[str] | None = None

    @property
    def num_personas(self) -> int:
        return len(self.personas)

    def id_to_index(self, persona_id: str) -> int:
        for i, p in enumerate(self.personas):
            if p.id == persona_id:
                return i
        raise KeyError(f"Unknown persona id: {persona_id!r}")

    def index_to_id(self, idx: int) -> str:
        return self.personas[idx].id

    def split_indices(self, split: str) -> list[int]:
        if split not in self.splits:
            raise KeyError(f"Unknown split: {split!r}")
        return [self.id_to_index(pid) for pid in self.splits[split]]

    def all_indices(self) -> list[int]:
        return list(range(self.num_personas))

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "num_personas": self.num_personas,
            "ids": [p.id for p in self.personas],
            "splits": self.splits,
        }


def load_personas(path: str | Path = DEFAULT_PERSONA_PATH) -> PersonaRegistry:
    data = json.loads(Path(path).read_text())
    personas = [
        Persona(
            id=p["id"],
            description=p["description"],
            tags=list(p.get("tags", [])),
            tendencies=dict(p.get("tendencies", {})),
            action_prior=list(p["action_prior"]) if "action_prior" in p else None,
        )
        for p in data["personas"]
    ]
    splits = dict(data.get("splits", {}))
    if not splits:
        splits = {"train": [p.id for p in personas]}
    return PersonaRegistry(
        path=str(path),
        personas=personas,
        splits=splits,
        action_labels=data.get("action_space", {}).get("labels"),
    )
