"""
Zero-shot UE5 persona evaluation orchestrator.

Workflow:
  1. python research/scripts/run_zeroshot_eval.py prepare
     -> backs up ue/cnzoi/Content/PCSP/Data/persona_embeddings.json
        as persona_embeddings.train.json
     -> writes a new persona_embeddings.json in which UE slots 1..N
        hold the held-out test_60_v3 personas, so the spawner
        (which cycles persona_id = (i % 300) + 1 for i in 0..AgentCount-1)
        actually sees zero-shot personas at agent indices 0..N-1.
     -> writes persona_embeddings.zeroshot_manifest.json mapping
        UE slot -> real test persona ID for downstream relabeling.

  2. Run a 64-agent PIE session in UE5. Stop when done.

  3. python research/scripts/run_zeroshot_eval.py finish
     -> auto-detects the newest Saved/PCSP/Logs/<stamp>/ session.
     -> runs analyze_ue_session.py against it.
     -> relabels per-persona output using the manifest.
     -> compares vs the train-persona baseline session.
     -> restores persona_embeddings.json from the backup.

Outputs (finish):
  research/results/ue_sessions/zeroshot_<stamp>/summary.json
  research/results/ue_sessions/zeroshot_<stamp>/compare_vs_train.json
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "research" / "scripts"))

UE_DATA_DIR    = ROOT / "ue" / "cnzoi" / "Content" / "PCSP" / "Data"
EMB_PATH       = UE_DATA_DIR / "persona_embeddings.json"
EMB_BACKUP     = UE_DATA_DIR / "persona_embeddings.train.json"
MANIFEST_PATH  = UE_DATA_DIR / "persona_embeddings.zeroshot_manifest.json"

PERSONAS_DIR   = ROOT / "research" / "data" / "personas"
TEST_SPLIT     = PERSONAS_DIR / "test_60_v3.json"
TRAIN_SPLIT    = PERSONAS_DIR / "train_240_v3.json"

LOGS_DIR       = ROOT / "ue" / "cnzoi" / "Saved" / "PCSP" / "Logs"
RESULTS_DIR    = ROOT / "research" / "results" / "ue_sessions"

TRAIN_BASELINE_SESSION = "20260518_104056"
N_AGENTS_DEFAULT = 64


def _load_json(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def prepare(n_agents: int) -> None:
    if not EMB_PATH.exists():
        raise SystemExit(f"missing {EMB_PATH}")
    if not TEST_SPLIT.exists():
        raise SystemExit(f"missing {TEST_SPLIT}")

    if EMB_BACKUP.exists() and MANIFEST_PATH.exists():
        print(f"[prepare] manifest already present at {MANIFEST_PATH}")
        print(f"          (run `finish` first, or delete the manifest to redo)")
        return

    full = _load_json(EMB_PATH)
    embeddings = full["embeddings"]
    if len(embeddings) < 300:
        raise SystemExit(
            f"{EMB_PATH} has only {len(embeddings)} embeddings; expected 300."
        )

    test_personas = _load_json(TEST_SPLIT)
    test_ids = [p["id"] for p in test_personas]  # length 60, range 241..300
    if not test_ids:
        raise SystemExit("test_60_v3.json is empty")

    # Build the swapped slot table.
    # UE spawner: agent i -> persona_id = (i % 300) + 1, embeddings[persona_id - 1]
    # We want agent i in [0, n_agents) -> a test embedding.
    # Plan: slot k (1-based) for k in 1..n_agents holds test_ids[(k-1) % len(test_ids)];
    #       slots n_agents+1..300 keep their original (train) embedding.
    new_embeddings = list(embeddings)  # copy
    manifest = {
        "n_agents_target": n_agents,
        "test_split_file": str(TEST_SPLIT.relative_to(ROOT)),
        "n_test_personas": len(test_ids),
        "slot_to_real_persona_id": {},  # ue_slot (1-based, str) -> real persona id
    }
    for k in range(1, n_agents + 1):
        real_id = test_ids[(k - 1) % len(test_ids)]
        new_embeddings[k - 1] = embeddings[real_id - 1]
        manifest["slot_to_real_persona_id"][str(k)] = real_id

    # Backup + write.
    if not EMB_BACKUP.exists():
        shutil.copy2(EMB_PATH, EMB_BACKUP)
        print(f"[prepare] backed up   -> {EMB_BACKUP}")
    out = dict(full)
    out["embeddings"] = new_embeddings
    EMB_PATH.write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"[prepare] wrote zero-shot persona_embeddings.json (UE slots 1..{n_agents} swapped)")
    print(f"[prepare] manifest    -> {MANIFEST_PATH}")
    print()
    print("Now: open UE5, run PIE with 64 agents for ~7 min, stop.")
    print("Then: python research/scripts/run_zeroshot_eval.py finish")


def _find_latest_session(after_session: str | None) -> Path:
    if not LOGS_DIR.exists():
        raise SystemExit(f"no logs dir at {LOGS_DIR}")
    sessions = sorted(p for p in LOGS_DIR.iterdir() if p.is_dir())
    if not sessions:
        raise SystemExit(f"no sessions in {LOGS_DIR}")
    if after_session:
        sessions = [s for s in sessions if s.name > after_session]
        if not sessions:
            raise SystemExit(
                f"no session newer than {after_session} found under {LOGS_DIR}"
            )
    return sessions[-1]


def finish() -> None:
    if not MANIFEST_PATH.exists():
        raise SystemExit(
            f"no manifest at {MANIFEST_PATH} — did you run `prepare` first?"
        )
    manifest = _load_json(MANIFEST_PATH)
    slot_to_real = {int(k): int(v) for k, v in manifest["slot_to_real_persona_id"].items()}

    session = _find_latest_session(after_session=TRAIN_BASELINE_SESSION)
    print(f"[finish] using session: {session.name}")

    from analyze_ue_session import analyze_session, compare_sessions  # type: ignore

    summary = analyze_session(session)

    # Relabel ue_slot -> real test persona id
    for row in summary["per_persona"]:
        ue_slot = row["persona_id"]
        real_id = slot_to_real.get(ue_slot)
        row["ue_slot"] = ue_slot
        row["persona_id"] = real_id if real_id is not None else ue_slot
        row["is_zeroshot_persona"] = real_id is not None
    summary["relabeled_via_manifest"] = True
    summary["manifest"] = manifest

    out_dir = RESULTS_DIR / f"zeroshot_{session.name}"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    print(f"[finish] summary  -> {out_dir / 'summary.json'}")

    # Compare against train baseline
    train_summary_path = RESULTS_DIR / TRAIN_BASELINE_SESSION / "summary.json"
    if train_summary_path.exists():
        train_summary = _load_json(train_summary_path)
        cmp = compare_sessions(train_summary, summary)
        # NB: compare matches on persona_id — train uses IDs 1..64 (train),
        # zeroshot is relabeled to 241..300 (test). No common IDs, so the
        # per-persona ρ table will be empty. The useful diff is at the
        # AGGREGATE level: inter-persona action ρ, category coverage,
        # failure-rate. Emit those instead.
        agg = {
            "train_session":          TRAIN_BASELINE_SESSION,
            "zeroshot_session":       session.name,
            "n_personas_train":       train_summary["n_personas"],
            "n_personas_zeroshot":    summary["n_personas"],
            "failure_rate_train":     train_summary["totals"]["failure_rate"],
            "failure_rate_zeroshot":  summary["totals"]["failure_rate"],
            "interactions_per_agent_train":    train_summary["totals"]["interactions_per_agent"],
            "interactions_per_agent_zeroshot": summary["totals"]["interactions_per_agent"],
            "inter_persona_rho_train":    train_summary["persona_dispersion"]["pairwise_action_rho_mean"],
            "inter_persona_rho_zeroshot": summary["persona_dispersion"]["pairwise_action_rho_mean"],
            "category_coverage_train":    train_summary["category_coverage"],
            "category_coverage_zeroshot": summary["category_coverage"],
            "matched_persona_compare":    cmp,  # expected empty (disjoint IDs)
        }
        (out_dir / "compare_vs_train.json").write_text(json.dumps(agg, indent=2))
        print(f"[finish] compare  -> {out_dir / 'compare_vs_train.json'}")
        print(f"         failure rate: train={agg['failure_rate_train']:.3f}  "
              f"zeroshot={agg['failure_rate_zeroshot']:.3f}")
        print(f"         inter-persona action rho: train={agg['inter_persona_rho_train']:.3f}  "
              f"zeroshot={agg['inter_persona_rho_zeroshot']:.3f}")
        print(f"         interactions/agent: train={agg['interactions_per_agent_train']:.1f}  "
              f"zeroshot={agg['interactions_per_agent_zeroshot']:.1f}")
    else:
        print(f"[finish] (no baseline at {train_summary_path}; skipping compare)")

    # Restore the train embedding file so future PIE runs are unaffected.
    if EMB_BACKUP.exists():
        shutil.copy2(EMB_BACKUP, EMB_PATH)
        MANIFEST_PATH.unlink(missing_ok=True)
        EMB_BACKUP.unlink(missing_ok=True)
        print(f"[finish] restored {EMB_PATH} from backup; manifest removed")


def restore() -> None:
    if not EMB_BACKUP.exists():
        print(f"[restore] no backup found at {EMB_BACKUP}; nothing to do")
        return
    shutil.copy2(EMB_BACKUP, EMB_PATH)
    MANIFEST_PATH.unlink(missing_ok=True)
    EMB_BACKUP.unlink(missing_ok=True)
    print(f"[restore] restored {EMB_PATH}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["prepare", "finish", "restore"])
    ap.add_argument("--n_agents", type=int, default=N_AGENTS_DEFAULT)
    args = ap.parse_args()
    if args.mode == "prepare":
        prepare(args.n_agents)
    elif args.mode == "finish":
        finish()
    else:
        restore()


if __name__ == "__main__":
    main()
