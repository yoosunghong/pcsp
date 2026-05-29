"""
Intra-session persona-distance vs action-KL Spearman.

Tests the paper's headline ρ≈0.73 claim — that personas with similar
embedding vectors produce similar action distributions — against the
UE5 PIE runs. Operates on the per-persona aggregates already written by
`analyze_ue_session.py` plus the `persona_embeddings.json` snapshot that
was active for the session.

Pipeline:
  1. Load `summary.json` produced by `analyze_ue_session.py`.
     Use `policy_probs` (mean softmax(logits)) when present; otherwise
     fall back to the 20-bin action-execution histogram.
  2. Load the persona_embeddings.json that was in `Content/PCSP/Data/`
     at the time of the session. Embedding row i corresponds to UE
     slot persona_id = i + 1.
  3. For every pair (i, j) of personas observed in the session compute
        - persona_distance: 1 - cosine_similarity(emb_i, emb_j)
        - action_distance:  symmetric KL of action distributions
     and report Spearman ρ between the two pair-wise vectors.

Outputs `persona_distance_vs_kl.json` with:
  - n_pairs, spearman_rho, pearson_r
  - per-pair scatter rows (so a follow-up plot is trivial)

Usage:
  python research/scripts/analyze_persona_distance_vs_kl.py \\
      --summary research/results/ue_sessions/<stamp>/summary.json \\
      --embeddings ue/cnzoi/Content/PCSP/Data/persona_embeddings.json \\
      --out research/results/ue_sessions/<stamp>/persona_distance_vs_kl.json

Optional: pass `--manifest <slot_to_real_id.json>` for held-out sessions
where UE slot i held real persona ID m[i]; the script then looks up
embeddings by the real ID rather than slot index.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from statistics import mean, median


def _cosine_distance(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        return float("nan")
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return float("nan")
    return 1.0 - dot / (na * nb)


def _symmetric_kl(p: list[float], q: list[float], eps: float = 1e-8) -> float:
    if len(p) != len(q) or not p:
        return float("nan")

    def one_way(a, b):
        s = 0.0
        for ai, bi in zip(a, b):
            if ai <= 0.0:
                continue
            s += ai * math.log((ai + eps) / (bi + eps))
        return s

    return 0.5 * (one_way(p, q) + one_way(q, p))


def _spearman(xs: list[float], ys: list[float]) -> float:
    if len(xs) != len(ys) or len(xs) < 2:
        return float("nan")

    def rank(vs):
        order = sorted(range(len(vs)), key=lambda i: vs[i])
        r = [0.0] * len(vs)
        i = 0
        while i < len(vs):
            j = i
            while j + 1 < len(vs) and vs[order[j + 1]] == vs[order[i]]:
                j += 1
            avg = (i + j) / 2 + 1
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r

    rx, ry = rank(xs), rank(ys)
    n = len(xs)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((rx[i] - mx) * (ry[i] - my) for i in range(n))
    dx = math.sqrt(sum((rx[i] - mx) ** 2 for i in range(n)))
    dy = math.sqrt(sum((ry[i] - my) ** 2 for i in range(n)))
    return num / (dx * dy) if dx > 0 and dy > 0 else float("nan")


def _pearson(xs: list[float], ys: list[float]) -> float:
    if len(xs) != len(ys) or len(xs) < 2:
        return float("nan")
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    num = sum((xs[i] - mx) * (ys[i] - my) for i in range(len(xs)))
    dx = math.sqrt(sum((xs[i] - mx) ** 2 for i in range(len(xs))))
    dy = math.sqrt(sum((ys[i] - my) ** 2 for i in range(len(xs))))
    return num / (dx * dy) if dx > 0 and dy > 0 else float("nan")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--summary", required=True, type=Path,
                    help="summary.json from analyze_ue_session.py")
    ap.add_argument("--embeddings", required=True, type=Path,
                    help="persona_embeddings.json active for the session")
    ap.add_argument("--manifest", type=Path, default=None,
                    help="Optional slot->real_id mapping (held-out runs)")
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--action-source", choices=("auto", "logits", "hist"),
                    default="auto",
                    help="auto: prefer policy_probs, fallback to action_distribution")
    args = ap.parse_args()

    summary = json.loads(args.summary.read_text())
    emb_blob = json.loads(args.embeddings.read_text())
    embeddings: list[list[float]] = emb_blob["embeddings"]

    manifest = None
    if args.manifest:
        raw = json.loads(args.manifest.read_text())
        # Accept either {"1": 241, ...} or [241, 242, ...]
        if isinstance(raw, dict):
            manifest = {int(k): int(v) for k, v in raw.items()}
        else:
            manifest = {i + 1: int(v) for i, v in enumerate(raw)}

    use_logits = args.action_source != "hist"
    rows = []
    skipped_no_dist = 0
    skipped_no_emb = 0
    for r in summary["per_persona"]:
        pid = r["persona_id"]
        real_id = manifest[pid] if manifest and pid in manifest else pid
        emb_idx = real_id - 1
        if not (0 <= emb_idx < len(embeddings)):
            skipped_no_emb += 1
            continue
        dist = None
        if use_logits and r.get("policy_probs"):
            dist = r["policy_probs"]
        if dist is None and args.action_source != "logits":
            dist = r.get("action_distribution")
        if not dist or sum(dist) <= 0.0:
            skipped_no_dist += 1
            continue
        rows.append({
            "persona_id": pid,
            "real_id": real_id,
            "embedding": embeddings[emb_idx],
            "action_dist": dist,
            "n_decisions": r.get("n_decisions", 0),
            "source": "logits" if (use_logits and r.get("policy_probs")) else "hist",
        })

    if len(rows) < 2:
        raise SystemExit(
            f"Need >=2 personas with embeddings + action data; got {len(rows)} "
            f"(skipped no_emb={skipped_no_emb}, no_dist={skipped_no_dist})"
        )

    pair_rows = []
    persona_dists: list[float] = []
    action_dists: list[float] = []
    for i in range(len(rows)):
        for j in range(i + 1, len(rows)):
            pd = _cosine_distance(rows[i]["embedding"], rows[j]["embedding"])
            ad = _symmetric_kl(rows[i]["action_dist"], rows[j]["action_dist"])
            if math.isnan(pd) or math.isnan(ad):
                continue
            persona_dists.append(pd)
            action_dists.append(ad)
            pair_rows.append({
                "pid_a": rows[i]["persona_id"],
                "pid_b": rows[j]["persona_id"],
                "real_a": rows[i]["real_id"],
                "real_b": rows[j]["real_id"],
                "persona_cosine_distance": pd,
                "action_symmetric_kl": ad,
            })

    rho = _spearman(persona_dists, action_dists)
    r_pearson = _pearson(persona_dists, action_dists)
    source_mix = {}
    for r in rows:
        source_mix[r["source"]] = source_mix.get(r["source"], 0) + 1

    out = {
        "summary_path": str(args.summary),
        "embeddings_path": str(args.embeddings),
        "manifest_path": str(args.manifest) if args.manifest else None,
        "session_policy_mode": summary.get("policy_mode"),
        "session_active_ablation": summary.get("active_ablation"),
        "n_personas": len(rows),
        "n_pairs": len(pair_rows),
        "action_source_mix": source_mix,
        "spearman_rho": rho,
        "pearson_r": r_pearson,
        "persona_distance": {
            "mean": float(mean(persona_dists)) if persona_dists else None,
            "median": float(median(persona_dists)) if persona_dists else None,
        },
        "action_kl": {
            "mean": float(mean(action_dists)) if action_dists else None,
            "median": float(median(action_dists)) if action_dists else None,
        },
        "skipped": {"no_embedding": skipped_no_emb, "no_distribution": skipped_no_dist},
        "pairs": pair_rows,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2))
    print(f"[ok] wrote {args.out}")
    abl_s = summary.get("active_ablation") or "-"
    print(f"     personas={len(rows)} pairs={len(pair_rows)} "
          f"source={source_mix} mode={summary.get('policy_mode')} ablation={abl_s}")
    print(f"     spearman_rho={rho:.4f}  pearson_r={r_pearson:.4f}")
    print(f"     persona_cos_dist mean={out['persona_distance']['mean']:.4f}  "
          f"action_kl mean={out['action_kl']['mean']:.4f}")


if __name__ == "__main__":
    main()
