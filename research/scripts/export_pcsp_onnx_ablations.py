"""
Export PCSP v3 ablation checkpoints to ONNX, named for UE5 swap workflow.

Produces two ONNX files in `results/export_ue5/`:
  pcsp_actor_full.onnx        — full PCSP (PPO + InfoNCE + KL diversity)
  pcsp_actor_no_consist.onnx  — λ_consist = 0 ablation

Both share the same I/O contract (obs[1,33], persona_proj[1,64] -> logits[1,20])
so the UE5 PCSPPolicySubsystem can run paired sessions by swapping the file at
`ue/cnzoi/Content/PCSP/Models/pcsp_actor.onnx` (see swap_ue5_onnx.py).

Each export also writes its own persona_embeddings JSON (the LoRA projection
matrices A,B differ between the two checkpoints, so the projected embeddings
do too):
  persona_embeddings_full.json
  persona_embeddings_no_consist.json

Checkpoint locations
--------------------
Checkpoints + embeddings live at the *repository root* `results/` directory
(not under `research/results/`):
    <repo>/results/pcsp_v3/full/policy.pt
    <repo>/results/pcsp_v3/no_consist/policy.pt
    <repo>/results/embeddings/persona_embeddings_300.npy

Exports are written to `<repo>/research/results/export_ue5/` so they sit next to
the rest of the research artifacts.

Usage
-----
    conda run -n paper python research/scripts/export_pcsp_onnx_ablations.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPT_DIR    = Path(__file__).resolve().parent          # research/scripts
RESEARCH_ROOT = SCRIPT_DIR.parent                         # research
REPO_ROOT     = RESEARCH_ROOT.parent                      # <repo>
EXPORT_SCRIPT = SCRIPT_DIR / "export_pcsp_onnx.py"
OUT_DIR       = RESEARCH_ROOT / "results" / "export_ue5"

ABLATIONS = [
    ("full",       REPO_ROOT / "results" / "pcsp_v3" / "full"       / "policy.pt"),
    ("no_consist", REPO_ROOT / "results" / "pcsp_v3" / "no_consist" / "policy.pt"),
]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    embeddings = REPO_ROOT / "results" / "embeddings" / "persona_embeddings_300.npy"

    if not embeddings.exists():
        print(f"[ERROR] Embeddings not found: {embeddings}")
        print("Copy from training PC: results/embeddings/persona_embeddings_300.npy")
        sys.exit(1)

    for tag, ckpt in ABLATIONS:
        if not ckpt.exists():
            print(f"[SKIP] {tag}: checkpoint not found at {ckpt}")
            continue

        tag_dir = OUT_DIR / f"_tmp_{tag}"
        tag_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n[{tag}] exporting {ckpt}")
        result = subprocess.run(
            [sys.executable, str(EXPORT_SCRIPT),
             "--checkpoint", str(ckpt),
             "--embeddings", str(embeddings),
             "--output_dir", str(tag_dir)],
            check=False,
        )
        if result.returncode != 0:
            print(f"[ERROR] {tag} export failed (rc={result.returncode})")
            continue

        actor_src = tag_dir / "pcsp_actor.onnx"
        emb_src   = tag_dir / "persona_embeddings.json"
        actor_dst = OUT_DIR / f"pcsp_actor_{tag}.onnx"
        emb_dst   = OUT_DIR / f"persona_embeddings_{tag}.json"

        actor_src.replace(actor_dst)
        emb_src.replace(emb_dst)
        tag_dir.rmdir()
        print(f"[{tag}] -> {actor_dst.name}, {emb_dst.name}")

    print()
    print("Next: swap into UE5 via")
    print("  python scripts/swap_ue5_onnx.py full")
    print("  python scripts/swap_ue5_onnx.py no_consist")


if __name__ == "__main__":
    main()
