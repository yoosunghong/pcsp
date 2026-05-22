"""Generate data/personas/personas_500_v3.json from personas_500.json.

Mirrors scripts/build_personas_v3.py but operates on the 500-persona file used
for v3-large training. Also writes matched train_400_v3.json / test_100_v3.json
splits derived from the per-persona "split" field already present in the
source.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SRC = ROOT / "data" / "personas" / "personas_500.json"
DST = ROOT / "data" / "personas" / "personas_500_v3.json"
DST_TRAIN = ROOT / "data" / "personas" / "train_400_v3.json"
DST_TEST  = ROOT / "data" / "personas" / "test_100_v3.json"

# Reuse the mapping table from build_personas_v3.py.
MODULATOR = {
    0: "C", 1: "C", 2: "C",
    3: "E", 4: "E",
    5: "O",
    6: None,
    7: "E",
}
EXPANSION = {
    0: {"high": [0, 1], "mid": [0],     "low": [0]},
    1: {"high": [3],    "mid": [2, 3],  "low": [2]},
    2: {"high": [4],    "mid": [4, 5],  "low": [5]},
    3: {"high": [6, 7], "mid": [6, 7],  "low": [7]},
    4: {"high": [8],    "mid": [8, 9],  "low": [9]},
    5: {"high": [10, 11], "mid": [10, 11], "low": [11]},
    6: {"high": [12],   "mid": [12],    "low": [12]},
    7: {"high": [14],   "mid": [13, 14], "low": [13]},
}


def expand_v1_action(v1_action: int, big_five: dict) -> list[int]:
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
        out.add(15)
    return sorted(out)


def main() -> None:
    personas = json.loads(SRC.read_text(encoding="utf-8"))
    for p in personas:
        p["preferred_actions"] = map_persona(p)
    DST.write_text(json.dumps(personas, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")

    train = [p for p in personas if p.get("split") == "train"]
    test  = [p for p in personas if p.get("split") == "test"]
    DST_TRAIN.write_text(json.dumps(train, ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8")
    DST_TEST.write_text(json.dumps(test, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")

    n = len(personas)
    avg = sum(len(p["preferred_actions"]) for p in personas) / max(n, 1)
    print(f"wrote {DST.relative_to(ROOT)} ({n} personas, avg {avg:.2f} v3 actions)")
    print(f"  train: {len(train)}  test: {len(test)}")


if __name__ == "__main__":
    main()
