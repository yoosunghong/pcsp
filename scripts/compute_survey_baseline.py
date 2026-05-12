"""
Automated trajectory-to-persona 2AFC baseline for the Korean human-eval survey.

For each survey item we replay the policy's saved trajectory through the
trained PCSP trajectory encoder and the LoRA persona projection, then pick
the candidate persona whose projected embedding has higher cosine similarity
with the trajectory embedding.

This mirrors the InfoNCE retrieval objective the policy was trained on, and
gives an automated upper-floor baseline against which human accuracy can be
compared. Items are also bucketed into easy/medium/hard tertiles by the
heuristic `distractor_score` recorded at survey-generation time so the same
buckets can be applied to human responses later.

Outputs:
  results/human_eval/automated_baseline.json
  results/human_eval/automated_baseline_per_item.csv

Usage:
    conda run -n paper python scripts/compute_survey_baseline.py
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import torch
import torch.nn.functional as F

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.env.mini_inzoi import ACTION_NAMES
from src.env.v3_constants import ACTION_NAMES_V3, OBS_DIM_V3_BASE
from src.eval.human_eval import wilson_ci
from src.models.trajectory_encoder import TrajectoryEncoder
from src.training.pcsp_trainer import PCSPActorCritic, ConcatActorCritic

ENV_SPECS = {
    "v1": {"obs_dim": 20, "n_actions": len(ACTION_NAMES)},
    "v3": {"obs_dim": OBS_DIM_V3_BASE, "n_actions": len(ACTION_NAMES_V3)},
}


def _load_json(path: Path) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _load_policy(
    policy_path: Path,
    model_type: str,
    obs_dim: int,
    n_actions: int,
    device: torch.device,
) -> torch.nn.Module:
    cls = ConcatActorCritic if model_type == "concat" else PCSPActorCritic
    policy = cls(obs_dim, n_actions)
    policy.load_state_dict(torch.load(policy_path, map_location="cpu", weights_only=True))
    return policy.to(device).eval()


def _load_traj_encoder(path: Path, obs_dim: int, n_actions: int, device: torch.device) -> TrajectoryEncoder:
    enc = TrajectoryEncoder(obs_dim=obs_dim, n_actions=n_actions)
    enc.load_state_dict(torch.load(path, map_location="cpu", weights_only=True))
    return enc.to(device).eval()


def _rank_buckets(scores: list[float]) -> tuple[list[str], float, float]:
    # Higher distractor_score = the distractor is more similar to the target,
    # which makes the 2AFC item harder. We rank items by score and split into
    # equal-size tertiles (rank-based, not value-based) so that score ties at
    # quantile boundaries do not produce wildly uneven buckets.
    n = len(scores)
    if n == 0:
        return ([], 0.0, 1.0)
    order = sorted(range(n), key=lambda i: (scores[i], i))
    third = n // 3
    rest = n - 2 * third
    labels_in_rank = ["easy"] * third + ["medium"] * rest + ["hard"] * (n - third - rest)
    bucket_by_index: list[str] = [""] * n
    for rank, idx in enumerate(order):
        bucket_by_index[idx] = labels_in_rank[rank]
    easy_max = scores[order[third - 1]] if third > 0 else float("-inf")
    hard_min = scores[order[third + rest]] if (third + rest) < n else float("inf")
    return (bucket_by_index, float(easy_max), float(hard_min))


def _encode_trajectory(
    encoder: TrajectoryEncoder,
    actions: list[dict[str, Any]],
    device: torch.device,
) -> torch.Tensor:
    obs_seq = torch.tensor(
        [step["obs"] for step in actions], dtype=torch.float32, device=device
    ).unsqueeze(0)  # (1, T, obs_dim)
    act_seq = torch.tensor(
        [int(step["action_id"]) for step in actions], dtype=torch.long, device=device
    ).unsqueeze(0)  # (1, T)
    with torch.no_grad():
        return encoder(obs_seq, act_seq).squeeze(0)  # (output_dim,)


def _project_persona(
    policy: torch.nn.Module,
    embeddings: np.ndarray,
    persona_id: int,
    device: torch.device,
) -> torch.Tensor:
    idx = persona_id - 1
    e_llm = torch.tensor(embeddings[idx], dtype=torch.float32, device=device).unsqueeze(0)
    with torch.no_grad():
        e_p = policy.persona_proj(e_llm).squeeze(0)
    return F.normalize(e_p, dim=-1)


def _aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(rows)
    k = sum(1 for r in rows if r["is_correct"])
    lo, hi = wilson_ci(k, n)
    margins = [r["margin"] for r in rows]
    return {
        "n": n,
        "correct": k,
        "accuracy": k / n if n else 0.0,
        "wilson_ci_95": [lo, hi],
        "mean_margin": float(np.mean(margins)) if margins else 0.0,
    }


def run_baseline(
    survey_path: Path,
    rollouts_path: Path,
    policy_path: Path,
    traj_encoder_path: Path,
    embeddings_path: Path,
    output_dir: Path,
    model_type: str,
    env_variant: str,
    device_name: str,
) -> dict[str, Any]:
    survey = _load_json(survey_path)
    rollouts_payload = _load_json(rollouts_path)
    rollouts = {r["trajectory_id"]: r for r in rollouts_payload["rollouts"]}
    embeddings = np.load(embeddings_path)
    inferred_env = str(rollouts_payload.get("env_variant", env_variant))
    if env_variant == "auto":
        env_variant = inferred_env
    if env_variant not in ENV_SPECS:
        raise ValueError(f"Unknown env_variant={env_variant!r}; expected one of {sorted(ENV_SPECS)} or 'auto'.")
    obs_dim = int(rollouts_payload.get("obs_dim") or ENV_SPECS[env_variant]["obs_dim"])
    n_actions = int(rollouts_payload.get("n_actions") or ENV_SPECS[env_variant]["n_actions"])

    device = torch.device(device_name if device_name == "cuda" and torch.cuda.is_available() else "cpu")
    policy = _load_policy(policy_path, model_type, obs_dim, n_actions, device)
    encoder = _load_traj_encoder(traj_encoder_path, obs_dim, n_actions, device)

    items = survey["items"]
    scores = [float(item["distractor_score"]) for item in items]
    bucket_by_index, easy_max, hard_min = _rank_buckets(scores)

    per_item: list[dict[str, Any]] = []
    for item_idx, item in enumerate(items):
        traj_id = item["trajectory_id"]
        if traj_id not in rollouts:
            raise KeyError(f"Trajectory {traj_id} missing from rollouts file.")
        rollout = rollouts[traj_id]
        actions = rollout.get("actions", [])
        if not actions or "obs" not in actions[0]:
            raise ValueError(
                f"Rollout {traj_id} has no obs field. Re-run "
                "scripts/export_persona_identification_rollouts.py."
            )

        traj_emb = _encode_trajectory(encoder, actions, device)
        candidate_a = _project_persona(policy, embeddings, int(item["candidate_a_id"]), device)
        candidate_b = _project_persona(policy, embeddings, int(item["candidate_b_id"]), device)

        sim_a = float(torch.dot(traj_emb, candidate_a).item())
        sim_b = float(torch.dot(traj_emb, candidate_b).item())
        prediction = "A" if sim_a >= sim_b else "B"
        is_correct = prediction == item["correct_option"]
        margin = abs(sim_a - sim_b)
        bucket = bucket_by_index[item_idx]

        per_item.append({
            "item_id": item["item_id"],
            "trajectory_id": traj_id,
            "model": item.get("model", "unknown"),
            "split": item.get("split", "unknown"),
            "target_persona_id": int(item["target_persona_id"]),
            "distractor_persona_id": int(item["distractor_persona_id"]),
            "distractor_score": float(item["distractor_score"]),
            "difficulty_bucket": bucket,
            "candidate_a_id": int(item["candidate_a_id"]),
            "candidate_b_id": int(item["candidate_b_id"]),
            "sim_a": sim_a,
            "sim_b": sim_b,
            "margin": margin,
            "prediction": prediction,
            "correct_option": item["correct_option"],
            "is_correct": is_correct,
        })

    overall = _aggregate(per_item)
    by_bucket = {
        b: _aggregate([r for r in per_item if r["difficulty_bucket"] == b])
        for b in ("easy", "medium", "hard")
    }

    summary = {
        "task": "automated_2afc_persona_identification",
        "source_survey": str(survey_path),
        "source_rollouts": str(rollouts_path),
        "policy": str(policy_path),
        "traj_encoder": str(traj_encoder_path),
        "embeddings": str(embeddings_path),
        "env_variant": env_variant,
        "obs_dim": obs_dim,
        "n_actions": n_actions,
        "device": str(device),
        "n_items": len(per_item),
        "difficulty_thresholds": {
            "easy_max_score": easy_max,
            "hard_min_score": hard_min,
            "rule": "Items ranked by distractor_score; equal-size tertiles → easy / medium / hard.",
        },
        "overall": overall,
        "by_difficulty": by_bucket,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "automated_baseline.json"
    csv_path = output_dir / "automated_baseline_per_item.csv"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "per_item": per_item}, f, indent=2, ensure_ascii=False)
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(per_item[0].keys()))
        writer.writeheader()
        writer.writerows(per_item)

    return summary


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--survey", default="data/human_eval/persona_identification_survey_ko.json")
    p.add_argument("--rollouts", default="results/human_eval/pcsp_v3_full_zero_shot_rollouts.json")
    p.add_argument("--policy", default="results/pcsp_v3/full/policy.pt")
    p.add_argument("--traj_encoder", default="results/pcsp_v3/full/traj_encoder.pt")
    p.add_argument("--embeddings", default="results/embeddings/persona_embeddings_300.npy")
    p.add_argument("--output_dir", default="results/human_eval")
    p.add_argument("--model_type", choices=["pcsp", "concat"], default="pcsp")
    p.add_argument("--env_variant", choices=["auto", *sorted(ENV_SPECS.keys())], default="auto")
    p.add_argument("--device", default="cuda")
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    summary = run_baseline(
        survey_path=ROOT / args.survey,
        rollouts_path=ROOT / args.rollouts,
        policy_path=ROOT / args.policy,
        traj_encoder_path=ROOT / args.traj_encoder,
        embeddings_path=ROOT / args.embeddings,
        output_dir=ROOT / args.output_dir,
        model_type=args.model_type,
        env_variant=args.env_variant,
        device_name=args.device,
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
