"""
Swap the active UE5 PCSP ONNX + persona embeddings between ablations.

Reads from `research/results/export_ue5/pcsp_actor_<tag>.onnx` (and
`persona_embeddings_<tag>.json`) and copies them to the UE5 content paths the
PCSPPolicySubsystem hardcodes:
  ue/cnzoi/Content/PCSP/Models/pcsp_actor.onnx
  ue/cnzoi/Content/PCSP/Data/persona_embeddings.json

Also writes `ue/cnzoi/Content/PCSP/Models/active_ablation.txt` so the next PIE
session can log which model is loaded.

Usage
-----
    python research/scripts/swap_ue5_onnx.py full
    python research/scripts/swap_ue5_onnx.py no_consist

After swapping, restart PIE so PCSPPolicySubsystem::Initialize reloads the
model. Pair the two resulting Saved/PCSP/Logs sessions with
`analyze_ue_session.py --compare` to get matched-persona symmetric KL between
PCSP and NoConsist policies in-engine.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "research" / "results" / "export_ue5"
UE_MODEL = ROOT / "ue" / "cnzoi" / "Content" / "PCSP" / "Models" / "pcsp_actor.onnx"
UE_EMB   = ROOT / "ue" / "cnzoi" / "Content" / "PCSP" / "Data"   / "persona_embeddings.json"
ACTIVE_TAG_FILE = ROOT / "ue" / "cnzoi" / "Content" / "PCSP" / "Models" / "active_ablation.txt"

VALID_TAGS = {"full", "no_consist"}


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in VALID_TAGS:
        print(f"Usage: python {Path(__file__).name} <{' | '.join(sorted(VALID_TAGS))}>")
        sys.exit(2)

    tag = sys.argv[1]
    src_onnx = SRC_DIR / f"pcsp_actor_{tag}.onnx"
    src_emb  = SRC_DIR / f"persona_embeddings_{tag}.json"

    for p in (src_onnx, src_emb):
        if not p.exists():
            print(f"[ERROR] missing: {p}")
            print("Run scripts/export_pcsp_onnx_ablations.py first.")
            sys.exit(1)

    UE_MODEL.parent.mkdir(parents=True, exist_ok=True)
    UE_EMB.parent.mkdir(parents=True, exist_ok=True)

    shutil.copy2(src_onnx, UE_MODEL)
    shutil.copy2(src_emb,  UE_EMB)
    ACTIVE_TAG_FILE.write_text(tag + "\n", encoding="utf-8")

    print(f"[swap] active ablation -> {tag}")
    print(f"  {UE_MODEL}")
    print(f"  {UE_EMB}")
    print("Restart PIE to reload the model.")


if __name__ == "__main__":
    main()
