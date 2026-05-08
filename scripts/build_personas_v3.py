"""Generate data/personas/personas_300_v3.json from personas_300.json.

Implements the v1 → v3 preferred_actions mapping table from
docs/mini_inzoi_v3_design.md §8.1. Deterministic: re-running yields a byte-
identical file.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "personas" / "personas_300.json"
DST = ROOT / "data" / "personas" / "personas_300_v3.json"

# Mapping table: v1_action -> {bf_level: [v3_action_ids]}
# Modulator axis is encoded in MODULATOR.
MODULATOR: dict[int, str | None] = {
    0: "C", 1: "C", 2: "C",
    3: "E", 4: "E",
    5: "O",
    6: None,
    7: "E",
}

EXPANSION: dict[int, dict[str, list[int]]] = {
    0: {"high": [0, 1], "mid": [0],     "low": [0]},        # work
    1: {"high": [3],    "mid": [2, 3],  "low": [2]},        # eat
    2: {"high": [4],    "mid": [4, 5],  "low": [5]},        # sleep
    3: {"high": [6, 7], "mid": [6, 7],  "low": [7]},        # socialize
    4: {"high": [8],    "mid": [8, 9],  "low": [9]},        # exercise
    5: {"high": [10, 11], "mid": [10, 11], "low": [11]},    # read
    6: {"high": [12],   "mid": [12],    "low": [12]},       # clean
    7: {"high": [14],   "mid": [13, 14], "low": [13]},      # rest
}


def expand_v1_action(v1_action: int, big_five: dict[str, str]) -> list[int]:
    axis = MODULATOR[v1_action]
    if axis is None:
        return list(EXPANSION[v1_action]["mid"])
    level = big_five.get(axis, "mid")
    if level not in ("high", "mid", "low"):
        level = "mid"
    return list(EXPANSION[v1_action][level])


def map_persona(p: dict) -> list[int]:
    bf = p.get("big_five") or {}
    out: set[int] = set()
    for a in p.get("preferred_actions", []):
        a = int(a)
        if a in EXPANSION:
            out.update(expand_v1_action(a, bf))
    if bf.get("O") == "high":
        out.add(15)  # explore
    return sorted(out)


def main() -> None:
    personas = json.loads(SRC.read_text(encoding="utf-8"))
    for p in personas:
        p["preferred_actions"] = map_persona(p)
    DST.write_text(
        json.dumps(personas, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    n = len(personas)
    avg = sum(len(p["preferred_actions"]) for p in personas) / max(n, 1)
    print(f"wrote {DST.relative_to(ROOT)} ({n} personas, avg {avg:.2f} preferred v3 actions)")


if __name__ == "__main__":
    main()
