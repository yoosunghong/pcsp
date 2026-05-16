"""Phase 4 — build cached persona embedding artifacts.

We do not have a real LLM available in this environment, so Phase 4's
"frozen LLM" branch is filled by *deterministic semantic-content
surrogates* — feature-hashed text representations of the persona
descriptions and tags. The interfaces and downstream effects are
identical to a real LLM artifact: the trainer loads a ``.pt`` payload
with ``ids`` and ``embeddings`` keys, the encoder buffer is frozen, and
the rest of the stack treats it as a black box.

This script writes one ``.pt`` file per requested representation under
``results/embeddings/`` so the trainer can be pointed at it via
``--persona-source cached --persona-cache-path <path>``.

Representations:

- ``random32``     : deterministic Gaussian, salted by persona id (identical
                     to the default ``--persona-source random`` route, but
                     materialised on disk for parity).
- ``charhash64``   : feature-hashed character 3-grams of
                     ``description + " ".join(tags)``. 64-d, L2-normalised.
- ``descbow128``   : hashed bag-of-tokens (whitespace + tag list) into
                     128-d, with a per-token IDF-like dampening
                     ``1 / sqrt(1 + token_count)`` so frequent words do not
                     dominate. L2-normalised.

The point is *not* to compete with a real LLM — it is to give the
Phase 4 A/B a third axis (random vs short-semantic vs long-semantic)
that we can run without external API access, while leaving the cached
path code-tested end-to-end.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import torch

from src.persona import load_personas


def _hash_bucket(token: str, mod: int, salt: str) -> int:
    h = hashlib.sha256(f"{salt}:{token}".encode("utf-8")).digest()
    return int.from_bytes(h[:8], "big", signed=False) % mod


def _char_ngrams(s: str, n: int = 3) -> list[str]:
    s = "^" + s.lower() + "$"
    return [s[i : i + n] for i in range(len(s) - n + 1)]


def _l2(v: np.ndarray) -> np.ndarray:
    n = float(np.linalg.norm(v))
    return v if n < 1e-8 else v / n


def _build_charhash(ids: list[str], texts: list[str], dim: int, salt: str) -> np.ndarray:
    out = np.zeros((len(ids), dim), dtype=np.float32)
    for i, t in enumerate(texts):
        for ng in _char_ngrams(t, n=3):
            j = _hash_bucket(ng, dim, salt)
            # Signed feature: hash → sign in {-1, +1} so collisions don't
            # always reinforce. Standard feature-hashing trick.
            sign = 1.0 if _hash_bucket(ng, 2, salt + "_sign") == 0 else -1.0
            out[i, j] += sign
        out[i] = _l2(out[i])
    return out


def _build_descbow(ids: list[str], texts: list[str], dim: int, salt: str) -> np.ndarray:
    out = np.zeros((len(ids), dim), dtype=np.float32)
    for i, t in enumerate(texts):
        toks = t.lower().replace(",", " ").replace(".", " ").split()
        counts: dict[str, int] = {}
        for tok in toks:
            counts[tok] = counts.get(tok, 0) + 1
        for tok, c in counts.items():
            j = _hash_bucket(tok, dim, salt)
            sign = 1.0 if _hash_bucket(tok, 2, salt + "_sign") == 0 else -1.0
            # idf-like dampening
            out[i, j] += sign * (1.0 / np.sqrt(1.0 + c))
        out[i] = _l2(out[i])
    return out


def _build_random(ids: list[str], dim: int, salt: int) -> np.ndarray:
    out = np.zeros((len(ids), dim), dtype=np.float32)
    for i, pid in enumerate(ids):
        h = hashlib.sha256(f"{salt}:{pid}".encode("utf-8")).digest()
        seed = int.from_bytes(h[:8], "big", signed=False)
        rng = np.random.default_rng(seed)
        v = rng.standard_normal(dim).astype(np.float32)
        out[i] = _l2(v)
    return out


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--persona-path", default="research/meltingpot/personas/personas_v0.json")
    p.add_argument("--out-dir", default="results/embeddings")
    p.add_argument("--salt", default="phase4")
    args = p.parse_args()

    reg = load_personas(args.persona_path)
    ids = [p.id for p in reg.personas]
    texts = [
        (p.description + " " + " ".join(p.tags)).strip() for p in reg.personas
    ]

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    artifacts = {
        "random32":   _build_random(ids, 32, salt=0),
        "charhash64": _build_charhash(ids, texts, dim=64, salt=args.salt),
        "descbow128": _build_descbow(ids, texts, dim=128, salt=args.salt),
    }

    manifest = {}
    for name, mat in artifacts.items():
        path = out_dir / f"persona_emb_{name}.pt"
        torch.save({"ids": ids, "embeddings": torch.from_numpy(mat)}, path)
        manifest[name] = {"path": str(path), "shape": list(mat.shape), "dim": int(mat.shape[1])}
        print(f"[build_persona_embeddings] wrote {path}  shape={mat.shape}")

    # Quick diagnostics: pairwise cosine distance to make sure the three
    # representations actually live in different geometry.
    def cos_mean(mat: np.ndarray) -> float:
        m = mat / (np.linalg.norm(mat, axis=1, keepdims=True) + 1e-8)
        K = m.shape[0]
        sim = m @ m.T
        iu = np.triu_indices(K, k=1)
        return float(sim[iu].mean())

    diag = {name: {"mean_pairwise_cos": cos_mean(mat)} for name, mat in artifacts.items()}
    (out_dir / "persona_emb_manifest.json").write_text(
        json.dumps({"manifest": manifest, "diagnostics": diag}, indent=2)
    )
    print("[build_persona_embeddings] mean pairwise cos:", diag)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
