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

Usage
-----
    # Copy from training PC first:
    #   results/pcsp_v3/full/policy.pt
    #   results/pcsp_v3/no_consist/policy.pt
    #   results/embeddings/persona_embeddings_300.npy

    conda run -n paper python scripts/export_pcsp_onnx_ablations.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPORT_SCRIPT = ROOT / "scripts" / "export_pcsp_onnx.py"
OUT_DIR = ROOT / "results" / "export_ue5"

ABLATIONS = [
    ("full",       "results/pcsp_v3/full/policy.pt"),
    ("no_consist", "results/pcsp_v3/no_consist/policy.pt"),
]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    embeddings = ROOT / "results" / "embeddings" / "persona_embeddings_300.npy"

    if not embeddings.exists():
        print(f"[ERROR] Embeddings not found: {embeddings}")
        print("Copy from training PC: results/embeddings/persona_embeddings_300.npy")
        sys.exit(1)

    for tag, ckpt_rel in ABLATIONS:
        ckpt = ROOT / ckpt_rel
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
