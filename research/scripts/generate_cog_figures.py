"""
Generate updated Fig 2 (learning curves) and Fig 3 (KL scatter)
for the CoG 2026 Vision Paper, showing v1 and v2 results side by side.

Outputs:
  paper/figures/fig2_learning_v1v2.png/pdf
  paper/figures/fig3_kl_v1v2.png/pdf
"""
import sys, json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path
import torch
import torch.nn.functional as F

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT  = ROOT / "paper" / "figures"
EVAL_OUT = ROOT / "results" / "eval"

# ── colour palette ────────────────────────────────────────────────────────────
C_FULL      = "#2271B3"
C_NOCONSIST = "#F0A500"
C_NODIVERSE = "#D43A2F"
C_CONCAT    = "#5BA85E"

plt.rcParams.update({
    "font.family": "serif",
    "font.size": 9,
    "axes.labelsize": 9,
    "axes.titlesize": 9,
    "legend.fontsize": 7.5,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "figure.dpi": 150,
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
})


def smooth(arr, w=12):
    if len(arr) < w:
        return np.array(arr, dtype=float)
    return np.convolve(arr, np.ones(w) / w, mode="valid")


def load_metrics(path):
    d = json.loads(Path(path).read_text())
    metrics = d["metrics"]
    iters   = np.array([m["iteration"]       for m in metrics])
    reward  = np.array([m["mean_ep_reward"]  for m in metrics])
    consist = np.array([m.get("consistency_loss", np.nan) for m in metrics])
    return iters, reward, consist


# ─────────────────────────────────────────────────────────────────────────────
# Fig 2  Learning Curves  (v1 left | v2 right)
# ─────────────────────────────────────────────────────────────────────────────
def fig2_learning_curves():
    modes = [
        ("full",       C_FULL,      "PCSP (full)",   2.0),
        ("no_consist", C_NOCONSIST, r"no\_consist",  1.3),
        ("no_diverse", C_NODIVERSE, r"no\_diverse",  1.3),
    ]

    fig, axes = plt.subplots(1, 2, figsize=(7, 2.8), sharey=False)

    for ax, (ver, pcsp_dir, title, xlim) in zip(axes, [
        ("v1", ROOT / "results" / "pcsp",    "(a) v1: 6×6, 4 agents, 300 iters", 299),
        ("v2", ROOT / "results" / "v2" / "pcsp", "(b) v2: 12×12, 16 agents, 200 iters", 199),
    ]):
        for mode, color, label, lw in modes:
            path = pcsp_dir / mode / "metrics.json"
            if not path.exists():
                continue
            iters, reward, _ = load_metrics(path)
            sm = smooth(reward, w=12)
            x  = iters[len(iters) - len(sm):]
            ax.plot(x, sm, color=color, lw=lw, label=label)

        ax.set_xlabel("PPO Iteration")
        ax.set_ylabel("Episode Reward")
        ax.set_title(title, fontsize=8.5)
        ax.legend(loc="lower right")
        ax.grid(True, alpha=0.3, lw=0.5)
        ax.set_xlim(0, xlim)

    fig.tight_layout(pad=0.8)
    for ext in ("pdf", "png"):
        fig.savefig(OUT / f"fig2_learning_v1v2.{ext}",
                    bbox_inches="tight", dpi=200 if ext == "png" else None)
    plt.close(fig)
    print("Fig 2 (v1v2) saved.")


# ─────────────────────────────────────────────────────────────────────────────
# Fig 3  KL Scatter  (v1 left | v2 right)
# ─────────────────────────────────────────────────────────────────────────────
def fig3_kl_scatter():
    from scipy.stats import spearmanr
    from src.eval.diversity import _sample_random_states
    from src.training.pcsp_trainer import PCSPActorCritic
    from scripts.run_eval_v2 import _sample_states_v2
    from scripts.run_pcsp_v2 import PCSPActorCriticV2

    def _load_json(path):
        return json.loads((ROOT / path).read_text())

    def empirical_pairs(
        *,
        label,
        policy,
        policy_path,
        embeddings_path,
        personas_path,
        states_np,
        n_pairs,
        seed,
        device,
    ):
        policy.load_state_dict(torch.load(ROOT / policy_path, map_location="cpu", weights_only=True))
        policy.to(device).eval()
        all_emb = np.load(ROOT / embeddings_path)
        personas = _load_json(personas_path)

        rng = np.random.default_rng(seed)
        pairs = []
        while len(pairs) < min(n_pairs, len(personas) * (len(personas) - 1) // 2):
            i, j = rng.choice(len(personas), size=2, replace=False)
            pair = (int(i), int(j))
            if pair not in pairs and (pair[1], pair[0]) not in pairs:
                pairs.append(pair)

        states = torch.FloatTensor(states_np).to(device)
        kl_values, dist_values = [], []
        rows = []
        for i, j in pairs:
            p_i, p_j = personas[i], personas[j]
            e_i = torch.FloatTensor(all_emb[p_i["id"] - 1].astype(np.float32)).unsqueeze(0).to(device)
            e_j = torch.FloatTensor(all_emb[p_j["id"] - 1].astype(np.float32)).unsqueeze(0).to(device)

            with torch.no_grad():
                logits_i = policy.action_logits(states, e_i.expand(len(states_np), -1))
                logits_j = policy.action_logits(states, e_j.expand(len(states_np), -1))
                pe_i = policy.persona_proj(e_i)
                pe_j = policy.persona_proj(e_j)

            log_p_i = F.log_softmax(logits_i, dim=-1)
            log_p_j = F.log_softmax(logits_j, dim=-1)
            sym_kl = (
                F.kl_div(log_p_j, log_p_i.exp(), reduction="batchmean").item()
                + F.kl_div(log_p_i, log_p_j.exp(), reduction="batchmean").item()
            ) / 2.0
            dist = float(torch.norm(pe_i - pe_j, dim=-1).item())

            kl_values.append(sym_kl)
            dist_values.append(dist)
            rows.append({
                "persona_i": int(p_i["id"]),
                "persona_j": int(p_j["id"]),
                "projected_l2_distance": dist,
                "symmetric_policy_kl": sym_kl,
            })

        kl_arr = np.array(kl_values, dtype=float)
        dist_arr = np.array(dist_values, dtype=float)
        rho, p_val = spearmanr(kl_arr, dist_arr)
        return {
            "label": label,
            "n_pairs": len(rows),
            "n_states": int(len(states_np)),
            "spearman_rho": float(rho),
            "spearman_p": float(p_val),
            "mean_kl": float(kl_arr.mean()),
            "std_kl": float(kl_arr.std()),
            "points": rows,
        }

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    data = [
        empirical_pairs(
            label="v1: 6×6 / 300 personas",
            policy=PCSPActorCritic(),
            policy_path="results/pcsp/full/policy.pt",
            embeddings_path="results/embeddings/persona_embeddings_300.npy",
            personas_path="data/personas/train_240.json",
            states_np=_sample_random_states(200, seed=0),
            n_pairs=100,
            seed=0,
            device=device,
        ),
        empirical_pairs(
            label="v2: 12×12 / 500 personas",
            policy=PCSPActorCriticV2(),
            policy_path="results/v2/pcsp/full/policy.pt",
            embeddings_path="results/embeddings/persona_embeddings_500.npy",
            personas_path="data/personas/train_400.json",
            states_np=_sample_states_v2(100, seed=0),
            n_pairs=60,
            seed=0,
            device=device,
        ),
    ]
    EVAL_OUT.mkdir(parents=True, exist_ok=True)
    (EVAL_OUT / "fig3_kl_v1v2_points.json").write_text(
        json.dumps({"source": "empirical_policy_kl", "panels": data}, indent=2)
    )

    fig, axes = plt.subplots(1, 2, figsize=(6.5, 2.8))

    for ax, panel in zip(axes, data):
        dist_vals = np.array([p["projected_l2_distance"] for p in panel["points"]])
        kl_vals = np.array([p["symmetric_policy_kl"] for p in panel["points"]])

        ax.scatter(dist_vals, kl_vals, s=14, alpha=0.5,
                   color=C_FULL, lw=0)
        z    = np.polyfit(dist_vals, kl_vals, 1)
        xfit = np.linspace(dist_vals.min(), dist_vals.max(), 80)
        ax.plot(xfit, np.polyval(z, xfit), color=C_FULL, lw=2.0, alpha=0.9)

        ax.set_title(panel["label"], fontsize=8.5)
        ax.set_xlabel("Projected Persona Distance", fontsize=8)
        if ax is axes[0]:
            ax.set_ylabel("Behavioral KL Divergence", fontsize=8)
        ax.text(0.97, 0.05, f"ρ = {panel['spearman_rho']:.3f}",
                transform=ax.transAxes, ha="right", va="bottom", fontsize=9,
                bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="#BBBBBB"))
        ax.grid(True, alpha=0.25, lw=0.5)

    fig.suptitle("Empirical Persona Distance vs. Behavioral KL — scale comparison",
                 fontsize=9, y=1.01)
    fig.tight_layout(pad=0.8)
    for ext in ("pdf", "png"):
        fig.savefig(OUT / f"fig3_kl_v1v2.{ext}",
                    bbox_inches="tight", dpi=200 if ext == "png" else None)
    plt.close(fig)
    print("Fig 3 (v1v2) saved.")


if __name__ == "__main__":
    print("Generating CoG 2026 figures (v1+v2)...")
    fig2_learning_curves()
    fig3_kl_scatter()
    print(f"Done → {OUT}/")
