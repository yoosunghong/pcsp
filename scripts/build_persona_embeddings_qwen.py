"""Phase 5 — build a real-LLM persona embedding artifact (Qwen3-Embedding-0.6B).

This produces a `.pt` payload that drops into the existing cached-embedding
path (`build_encoder(..., source="cached", cache_path=...)`) with no
trainer-side changes. Phase 4's surrogate path (`charhash64`, `descbow128`)
is left intact for the A/B baseline.

The headline question we are setting up:

    Does swapping random32 for a real semantic embedding produce
    (a) non-zero held-out top-1 retrieval on `heldout/random`, and
    (b) a non-trivial positive Spearman rho between embedding cosine
        distance and pairwise action-KL on `mixed-pop` rollouts?

Phase 4 reported 0.000 ± 0.000 and ~0 respectively for random32 — those
are the two numbers this artifact is designed to flip.

Pooling: Qwen3-Embedding models use last-token pooling on the final hidden
state with a left-padded input; that is what we replicate here. We also
support an optional instruction prefix per the model card convention
(``Instruct: ... \\nQuery: <text>``), defaulting to an instruction that
ties the embedding to behavioural style.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from transformers import AutoModel, AutoTokenizer

from src.persona import load_personas


DEFAULT_INSTRUCTION = (
    "Given a description of an agent's behavioural tendencies, "
    "encode its identity for downstream policy conditioning."
)


def _last_token_pool(last_hidden: torch.Tensor, attn_mask: torch.Tensor) -> torch.Tensor:
    # Qwen3-Embedding convention: take the last non-padded token's hidden state.
    # Works for both left- and right-padded inputs by indexing on the mask.
    seq_lens = attn_mask.sum(dim=1) - 1
    batch_idx = torch.arange(last_hidden.size(0), device=last_hidden.device)
    return last_hidden[batch_idx, seq_lens]


def _format_text(description: str, tags: list[str], instruction: str) -> str:
    body = description.strip()
    if tags:
        body = body + " Tags: " + ", ".join(tags) + "."
    return f"Instruct: {instruction}\nQuery: {body}"


@torch.no_grad()
def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--persona-path", default="research/meltingpot/personas/personas_v0.json")
    p.add_argument("--out-dir", default="results/embeddings")
    p.add_argument("--model", default="Qwen/Qwen3-Embedding-0.6B")
    p.add_argument("--instruction", default=DEFAULT_INSTRUCTION)
    p.add_argument("--max-length", type=int, default=512)
    p.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    p.add_argument("--name", default="qwen_emb", help="Artifact suffix written to disk.")
    args = p.parse_args()

    reg = load_personas(args.persona_path)
    ids = [pp.id for pp in reg.personas]
    texts = [_format_text(pp.description, pp.tags, args.instruction) for pp in reg.personas]

    print(f"[qwen_emb] loading model {args.model} on {args.device} ...")
    tok = AutoTokenizer.from_pretrained(args.model, padding_side="left")
    mdl = AutoModel.from_pretrained(args.model, torch_dtype=torch.float32).to(args.device).eval()

    enc = tok(
        texts,
        padding=True,
        truncation=True,
        max_length=args.max_length,
        return_tensors="pt",
    ).to(args.device)
    out = mdl(**enc)
    pooled = _last_token_pool(out.last_hidden_state, enc["attention_mask"])
    pooled = F.normalize(pooled, p=2, dim=1).cpu().float()
    mat = pooled.numpy()
    dim = int(mat.shape[1])
    print(f"[qwen_emb] embeddings shape={mat.shape} dim={dim}")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"persona_emb_{args.name}.pt"
    torch.save({"ids": ids, "embeddings": torch.from_numpy(mat)}, path)

    # Diagnostics: pairwise cosine, distance to random32 reference if present.
    m = mat / (np.linalg.norm(mat, axis=1, keepdims=True) + 1e-8)
    K = m.shape[0]
    sim = m @ m.T
    iu = np.triu_indices(K, k=1)
    mean_cos = float(sim[iu].mean())
    min_cos = float(sim[iu].min())
    max_cos = float(sim[iu].max())

    # Per-pair table (for the report).
    pair_table = []
    for i in range(K):
        for j in range(i + 1, K):
            pair_table.append({"a": ids[i], "b": ids[j], "cos": float(sim[i, j])})
    pair_table.sort(key=lambda r: r["cos"], reverse=True)

    diag = {
        "name": args.name,
        "model": args.model,
        "dim": dim,
        "mean_pairwise_cos": mean_cos,
        "min_pairwise_cos": min_cos,
        "max_pairwise_cos": max_cos,
        "top5_closest_pairs": pair_table[:5],
        "top5_furthest_pairs": pair_table[-5:],
    }
    diag_path = out_dir / f"persona_emb_{args.name}.diag.json"
    diag_path.write_text(json.dumps(diag, indent=2))
    print(json.dumps(diag, indent=2))
    print(f"[qwen_emb] wrote {path}")
    print(f"[qwen_emb] wrote {diag_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
