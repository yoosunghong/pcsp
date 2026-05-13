"""
Build compositional zero-shot splits for §4.3 of PLAN.md.

The 300-persona dataset is a 20-occupation × 15-Big-Five-archetype grid with
exactly one persona per cell. Three split families are derived:

  unseen_occupation:  4 occupations × 15 archetypes = 60 test
                      (matches the existing train_240 / test_60 split content)
  unseen_archetype:   3 archetypes × 20 occupations = 60 test
                      (held-out personality structures, all occupations seen)
  unseen_combo:       60 random cells where both occupation and archetype
                      appear in train at other cells (the easier condition)

Outputs:
  data/personas/splits/{family}_train.json
  data/personas/splits/{family}_test.json
  data/personas/splits/manifest.json

Usage:
    conda run -n paper python scripts/build_compositional_splits.py
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TRAIT_KEYS = ("E", "N", "A", "C", "O")


def _archetype(p: dict[str, Any]) -> tuple[str, ...]:
    return tuple(p["big_five"][k] for k in TRAIT_KEYS)


def _set_split(personas: list[dict[str, Any]], test_ids: set[int]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    train, test = [], []
    for p in personas:
        clone = dict(p)
        if int(p["id"]) in test_ids:
            clone["split"] = "test"
            test.append(clone)
        else:
            clone["split"] = "train"
            train.append(clone)
    return train, test


def _assert_compositional(train: list[dict[str, Any]], test: list[dict[str, Any]], mode: str) -> None:
    train_occs = {p["occupation"] for p in train}
    train_arcs = {_archetype(p) for p in train}
    test_occs = {p["occupation"] for p in test}
    test_arcs = {_archetype(p) for p in test}

    if mode == "unseen_occupation":
        assert test_occs.isdisjoint(train_occs), "unseen_occupation: test occupations must not appear in train."
        assert test_arcs.issubset(train_arcs), "unseen_occupation: every test archetype must appear in train."
    elif mode == "unseen_archetype":
        assert test_arcs.isdisjoint(train_arcs), "unseen_archetype: test archetypes must not appear in train."
        assert test_occs.issubset(train_occs), "unseen_archetype: every test occupation must appear in train."
    elif mode == "unseen_combo":
        # Both axes must appear elsewhere in train.
        assert test_occs.issubset(train_occs), "unseen_combo: every test occupation must appear in train."
        assert test_arcs.issubset(train_arcs), "unseen_combo: every test archetype must appear in train."
    else:
        raise ValueError(f"Unknown mode {mode!r}.")


def build_unseen_occupation(
    personas: list[dict[str, Any]],
    held_out_occupations: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    held = set(held_out_occupations)
    test_ids = {int(p["id"]) for p in personas if p["occupation"] in held}
    train, test = _set_split(personas, test_ids)
    _assert_compositional(train, test, "unseen_occupation")
    return train, test


def build_unseen_archetype(
    personas: list[dict[str, Any]],
    held_out_archetypes: list[tuple[str, ...]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    held = set(held_out_archetypes)
    test_ids = {int(p["id"]) for p in personas if _archetype(p) in held}
    train, test = _set_split(personas, test_ids)
    _assert_compositional(train, test, "unseen_archetype")
    return train, test


def build_unseen_combo(
    personas: list[dict[str, Any]],
    n_test: int,
    rng: random.Random,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    # Pick n_test cells whose occupation and archetype each have ≥2 cells total
    # (so removing one still leaves ≥1 in train). With 20×15=300 and one per
    # cell, every occupation has 15 cells and every archetype has 20, so any
    # cell can be safely held out — the constraint is just that we don't hold
    # out so many cells that an occupation or archetype loses all of train.
    by_occ: dict[str, list[int]] = {}
    by_arc: dict[tuple[str, ...], list[int]] = {}
    for p in personas:
        by_occ.setdefault(p["occupation"], []).append(int(p["id"]))
        by_arc.setdefault(_archetype(p), []).append(int(p["id"]))

    pool = [int(p["id"]) for p in personas]
    rng.shuffle(pool)

    test_ids: set[int] = set()
    occ_used: dict[str, int] = {k: 0 for k in by_occ}
    arc_used: dict[tuple[str, ...], int] = {k: 0 for k in by_arc}

    for pid in pool:
        if len(test_ids) >= n_test:
            break
        p = next(x for x in personas if int(x["id"]) == pid)
        occ = p["occupation"]
        arc = _archetype(p)
        # Keep ≥1 train cell for each axis.
        if occ_used[occ] + 1 >= len(by_occ[occ]):
            continue
        if arc_used[arc] + 1 >= len(by_arc[arc]):
            continue
        test_ids.add(pid)
        occ_used[occ] += 1
        arc_used[arc] += 1

    if len(test_ids) < n_test:
        raise RuntimeError(f"Could only assemble {len(test_ids)} unseen_combo cells (wanted {n_test}).")

    train, test = _set_split(personas, test_ids)
    _assert_compositional(train, test, "unseen_combo")
    return train, test


def _write_split(out_dir: Path, family: str, train: list[dict[str, Any]], test: list[dict[str, Any]], suffix: str = "") -> dict[str, Any]:
    train_path = out_dir / f"{family}{suffix}_train.json"
    test_path = out_dir / f"{family}{suffix}_test.json"
    with open(train_path, "w", encoding="utf-8") as f:
        json.dump(train, f, indent=2, ensure_ascii=False)
    with open(test_path, "w", encoding="utf-8") as f:
        json.dump(test, f, indent=2, ensure_ascii=False)
    return {
        "family": family,
        "train_path": str(train_path.relative_to(ROOT)),
        "test_path": str(test_path.relative_to(ROOT)),
        "n_train": len(train),
        "n_test": len(test),
        "test_persona_ids": sorted(int(p["id"]) for p in test),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--personas", default="data/personas/personas_300.json")
    ap.add_argument("--existing_test", default="data/personas/test_60.json",
                    help="Used to recover the held-out occupations for unseen_occupation.")
    ap.add_argument("--out_dir", default="data/personas/splits")
    ap.add_argument("--out_suffix", default="",
                    help="Optional suffix inserted before _train.json/_test.json "
                         "(e.g. '_v3' to coexist with the default v1 splits).")
    ap.add_argument("--manifest_name", default="manifest.json",
                    help="Name of the manifest file written under --out_dir.")
    ap.add_argument("--n_unseen_archetype", type=int, default=3)
    ap.add_argument("--n_unseen_combo", type=int, default=60)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    with open(ROOT / args.personas, encoding="utf-8") as f:
        personas = json.load(f)
    with open(ROOT / args.existing_test, encoding="utf-8") as f:
        existing_test = json.load(f)

    out_dir = ROOT / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    held_out_occupations = sorted({p["occupation"] for p in existing_test})

    # 1. unseen_occupation — match the existing test_60 exactly so the current
    #    PCSP-full checkpoint's evaluation carries over without retraining.
    uo_train, uo_test = build_unseen_occupation(personas, held_out_occupations)

    # 2. unseen_archetype — pick n archetypes deterministically from the seed.
    rng = random.Random(args.seed)
    all_archetypes = sorted({_archetype(p) for p in personas})
    held_out_archetypes = rng.sample(all_archetypes, args.n_unseen_archetype)
    ua_train, ua_test = build_unseen_archetype(personas, held_out_archetypes)

    # 3. unseen_combo — random cells with both axes covered in train.
    rng_combo = random.Random(args.seed + 1)
    uc_train, uc_test = build_unseen_combo(personas, args.n_unseen_combo, rng_combo)

    manifests = [
        _write_split(out_dir, "unseen_occupation", uo_train, uo_test, args.out_suffix),
        _write_split(out_dir, "unseen_archetype", ua_train, ua_test, args.out_suffix),
        _write_split(out_dir, "unseen_combo", uc_train, uc_test, args.out_suffix),
    ]
    for m, info in zip(manifests, [
        {"held_out_occupations": held_out_occupations},
        {"held_out_archetypes": [list(a) for a in held_out_archetypes],
         "trait_order": list(TRAIT_KEYS)},
        {"seed": args.seed + 1, "n_test": args.n_unseen_combo},
    ]):
        m.update(info)

    manifest = {
        "source_personas": str(Path(args.personas)),
        "source_existing_test": str(Path(args.existing_test)),
        "n_personas": len(personas),
        "trait_order": list(TRAIT_KEYS),
        "splits": manifests,
        "notes": (
            "unseen_occupation reproduces the existing train_240/test_60 split, so "
            "PCSP-full checkpoints trained on train_240 can be evaluated on this "
            "split without retraining. unseen_archetype and unseen_combo require "
            "fresh training runs on their train splits before zero-shot results "
            "can be reported."
        ),
    }
    with open(out_dir / args.manifest_name, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(json.dumps(manifest, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
