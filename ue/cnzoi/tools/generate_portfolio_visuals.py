#!/usr/bin/env python3
"""Generate data-grounded visuals for the PCSP engineering portfolio.

The figures intentionally separate the measured Actor/BT benchmark from the
offscreen 1,024-NPC compatibility smoke. The latter proves that the hybrid
runtime path executes, but its throttled frame timings are not performance
evidence.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT = REPO_ROOT / "ue" / "cnzoi" / "docs" / "portfolio" / "assets"

SCALING_SOURCE = (
    REPO_ROOT
    / "research"
    / "results"
    / "ue_sessions"
    / "scaling_20260520"
    / "scaling_curve.json"
)
ABLATION_SOURCE = (
    REPO_ROOT
    / "research"
    / "results"
    / "ue_sessions"
    / "ablation_20260518_154827"
    / "ablation.json"
)
MASS_SOURCE = (
    REPO_ROOT
    / "research"
    / "results"
    / "ue_sessions"
    / "mass_smoke_20260831"
    / "per_session.json"
)
MASS_SCALING_SOURCE = (
    REPO_ROOT
    / "research"
    / "results"
    / "ue_sessions"
    / "mass_scaling_20260901"
    / "scaling_curve.json"
)

COLORS = {
    "background": "#07131f",
    "panel": "#0d2030",
    "text": "#edf6ff",
    "muted": "#a4b7c8",
    "grid": "#29465d",
    "cyan": "#4cc9f0",
    "blue": "#4895ef",
    "green": "#62d394",
    "orange": "#ffb454",
    "red": "#ff6b6b",
}


def _load_json(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _apply_theme(fig, axes) -> None:
    fig.patch.set_facecolor(COLORS["background"])
    for ax in axes:
        ax.set_facecolor(COLORS["panel"])
        ax.tick_params(colors=COLORS["muted"], labelsize=10)
        for spine in ax.spines.values():
            spine.set_color(COLORS["grid"])
        ax.grid(axis="y", color=COLORS["grid"], linewidth=0.8, alpha=0.65)
        ax.set_axisbelow(True)
        ax.xaxis.label.set_color(COLORS["muted"])
        ax.yaxis.label.set_color(COLORS["muted"])
        ax.title.set_color(COLORS["text"])


def _save(fig, output_dir: Path, stem: str) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(
        output_dir / f"{stem}.png",
        dpi=180,
        facecolor=fig.get_facecolor(),
        bbox_inches="tight",
    )
    fig.savefig(
        output_dir / f"{stem}.svg",
        facecolor=fig.get_facecolor(),
        bbox_inches="tight",
    )
    plt.close(fig)


def generate_actor_scaling(output_dir: Path) -> None:
    rows = _load_json(SCALING_SOURCE)
    agents = [row["n_agents"] for row in rows]
    frame = [row["frame_ms_p95"]["mean"] for row in rows]
    frame_std = [row["frame_ms_p95"]["std"] for row in rows]
    failure = [100.0 * row["fail_rate"]["mean"] for row in rows]
    failure_std = [100.0 * row["fail_rate"]["std"] for row in rows]

    fig, (ax_frame, ax_failure) = plt.subplots(1, 2, figsize=(14.4, 6.4))
    _apply_theme(fig, (ax_frame, ax_failure))
    fig.subplots_adjust(left=0.07, right=0.98, top=0.76, bottom=0.20, wspace=0.24)

    fig.suptitle(
        "Where the Actor / Behavior Tree stack stops scaling",
        color=COLORS["text"],
        fontsize=21,
        fontweight="bold",
        y=0.95,
    )
    fig.text(
        0.5,
        0.885,
        "Visible UE baseline  |  3 seeds per point  |  about 10.5 minutes per run",
        ha="center",
        color=COLORS["muted"],
        fontsize=11,
    )

    ax_frame.errorbar(
        agents,
        frame,
        yerr=frame_std,
        color=COLORS["cyan"],
        marker="o",
        markersize=7,
        linewidth=2.5,
        elinewidth=1.3,
        capsize=4,
        zorder=3,
    )
    ax_frame.axhline(16.67, color=COLORS["orange"], linewidth=1.7, linestyle="--")
    ax_frame.text(
        10,
        17.05,
        "16.67 ms / 60 FPS budget",
        color=COLORS["orange"],
        fontsize=10,
        va="bottom",
    )
    ax_frame.scatter([64], [frame[agents.index(64)]], color=COLORS["green"], s=95, zorder=4)
    ax_frame.annotate(
        "64 NPCs\n13.38 ms p95",
        xy=(64, frame[agents.index(64)]),
        xytext=(49, 10.0),
        color=COLORS["text"],
        fontsize=10,
        arrowprops={"arrowstyle": "-", "color": COLORS["green"], "lw": 1.5},
    )
    ax_frame.scatter([128], [frame[-1]], color=COLORS["red"], s=95, zorder=4)
    ax_frame.annotate(
        "128 NPCs\n17.05 ms p95",
        xy=(128, frame[-1]),
        xytext=(102, 14.0),
        color=COLORS["text"],
        fontsize=10,
        arrowprops={"arrowstyle": "-", "color": COLORS["red"], "lw": 1.5},
    )
    ax_frame.set_title(
        "Frame-time pressure", loc="left", fontsize=14, pad=14, color=COLORS["text"]
    )
    ax_frame.set_xlabel("Concurrent Actor / BT NPCs")
    ax_frame.set_ylabel("Frame p95 (ms)")
    ax_frame.set_xticks(agents)
    ax_frame.set_ylim(0, 22.5)

    bar_colors = [
        COLORS["cyan"],
        COLORS["cyan"],
        COLORS["cyan"],
        COLORS["green"],
        COLORS["orange"],
        COLORS["red"],
    ]
    bars = ax_failure.bar(
        agents,
        failure,
        width=11,
        color=bar_colors,
        yerr=failure_std,
        error_kw={"ecolor": COLORS["muted"], "elinewidth": 1.2, "capsize": 3},
    )
    for n_agents, bar, value in zip(agents, bars, failure):
        if n_agents < 64:
            continue
        label = f"{value:.1f}%" if value >= 0.1 else f"{value:.2f}%"
        ax_failure.text(
            bar.get_x() + bar.get_width() / 2,
            max(value, 0) + 1.2,
            label,
            color=COLORS["text"],
            fontsize=9.5,
            ha="center",
            va="bottom",
        )
    ax_failure.text(
        20,
        1.6,
        "8-32 NPCs: at most 0.1%",
        color=COLORS["muted"],
        fontsize=9.5,
        ha="center",
    )
    ax_failure.set_title(
        "Navigation failure cliff", loc="left", fontsize=14, pad=14, color=COLORS["text"]
    )
    ax_failure.set_xlabel("Concurrent Actor / BT NPCs")
    ax_failure.set_ylabel("Movement failure rate (%)")
    ax_failure.set_xticks(agents)
    ax_failure.set_ylim(0, 51)

    fig.text(
        0.5,
        0.075,
        "ONNX mean latency remains 0.13-0.20 ms/call. The first hard ceiling is bursty navigation and affordance contention.",
        ha="center",
        color=COLORS["text"],
        fontsize=10.5,
    )
    fig.text(
        0.5,
        0.035,
        "Source: research/results/ue_sessions/scaling_20260520/scaling_curve.json",
        ha="center",
        color=COLORS["muted"],
        fontsize=8.5,
    )
    _save(fig, output_dir, "actor-scaling-evidence")


def generate_ablation(output_dir: Path) -> None:
    payload = _load_json(ABLATION_SOURCE)
    by_mode = {row["policy_mode"]: row for row in payload["modes"]}
    modes = ["HybridPCSP", "HybridNoPersona", "BTOnly"]
    labels = ["PCSP + persona", "PCSP, no persona", "Behavior Tree only"]
    colors = [COLORS["cyan"], COLORS["orange"], COLORS["muted"]]

    metrics = [
        (
            "Movement failure",
            [100.0 * by_mode[mode]["failure_rate"] for mode in modes],
            "%",
            "Lower is better",
        ),
        (
            "Completed interactions / NPC",
            [by_mode[mode]["interactions_per_agent"] for mode in modes],
            "",
            "Higher is better",
        ),
        (
            "Action correlation between personas",
            [by_mode[mode]["inter_persona_rho_mean"] for mode in modes],
            " rho",
            "Lower means more distinct behavior",
        ),
    ]

    fig, axes = plt.subplots(1, 3, figsize=(15.5, 6.5))
    _apply_theme(fig, axes)
    fig.subplots_adjust(left=0.055, right=0.985, top=0.75, bottom=0.27, wspace=0.26)
    fig.suptitle(
        "Persona conditioning changes behavior, not just reward",
        color=COLORS["text"],
        fontsize=21,
        fontweight="bold",
        y=0.95,
    )
    fig.text(
        0.5,
        0.885,
        "UE execution ablation  |  64 personas per mode",
        ha="center",
        color=COLORS["muted"],
        fontsize=11,
    )

    for ax, (title, values, suffix, note) in zip(axes, metrics):
        bars = ax.bar(range(3), values, color=colors, width=0.66)
        ax.set_title(title, loc="left", fontsize=13, pad=12, color=COLORS["text"])
        ax.set_xticks(range(3), labels, rotation=13, ha="right")
        max_value = max(values)
        ax.set_ylim(0, max_value * 1.24 if max_value else 1)
        ax.text(
            0.02,
            0.96,
            note,
            transform=ax.transAxes,
            color=COLORS["muted"],
            fontsize=9,
            va="top",
        )
        for bar, value in zip(bars, values):
            if suffix == "%":
                label = f"{value:.2f}%" if value < 1 else f"{value:.1f}%"
            elif suffix == " rho":
                label = f"{value:.3f}"
            else:
                label = f"{value:.1f}"
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                value + max_value * 0.035,
                label,
                color=COLORS["text"],
                fontsize=10,
                ha="center",
                va="bottom",
            )

    fig.text(
        0.5,
        0.075,
        "Removing persona input makes agents nearly behaviorally identical (rho about 0.99) and raises execution failures to 13.3%.",
        ha="center",
        color=COLORS["text"],
        fontsize=10.5,
    )
    fig.text(
        0.5,
        0.035,
        "Source: research/results/ue_sessions/ablation_20260518_154827/ablation.json",
        ha="center",
        color=COLORS["muted"],
        fontsize=8.5,
    )
    _save(fig, output_dir, "persona-ablation-evidence")


def _node(ax, xy, width, height, title, body, color) -> None:
    x, y = xy
    patch = FancyBboxPatch(
        (x, y),
        width,
        height,
        boxstyle="round,pad=0.012,rounding_size=0.018",
        linewidth=1.4,
        edgecolor=color,
        facecolor=COLORS["panel"],
    )
    ax.add_patch(patch)
    ax.text(x + 0.025, y + height - 0.07, title, color=COLORS["text"], fontsize=13, fontweight="bold", va="top")
    ax.text(x + 0.025, y + height - 0.14, body, color=COLORS["muted"], fontsize=10.3, va="top", linespacing=1.5)


def generate_mass_runtime_proof(output_dir: Path) -> None:
    rows = _load_json(MASS_SOURCE)
    if len(rows) != 1:
        raise ValueError(f"Expected one Mass smoke row, found {len(rows)}")
    row = rows[0]

    fig, ax = plt.subplots(figsize=(15.5, 7.2))
    fig.patch.set_facecolor(COLORS["background"])
    ax.set_facecolor(COLORS["background"])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    ax.text(
        0.5,
        0.94,
        "Hybrid runtime path verified at 1,024 NPCs",
        color=COLORS["text"],
        fontsize=23,
        fontweight="bold",
        ha="center",
    )
    ax.text(
        0.5,
        0.885,
        f"Compatibility smoke  |  {row['hero_agents']} Hero Actors + {row['mass_entities']:,} Mass entities  |  {row['duration_s']:.1f} seconds",
        color=COLORS["muted"],
        fontsize=11,
        ha="center",
    )

    _node(ax, (0.055, 0.50), 0.21, 0.24, "Shared PCSP intent", "Persona + needs\n33-d observation\n20 semantic actions", COLORS["cyan"])
    _node(ax, (0.385, 0.57), 0.245, 0.20, "Hero tier: 4", "Actor + AIController + BT\nNavMesh + reservations", COLORS["green"])
    _node(ax, (0.385, 0.34), 0.245, 0.20, "Background tier: 1,020", "Mass fragments + 32 cohorts\nHISM + simulation-LOD motion", COLORS["orange"])
    _node(ax, (0.755, 0.50), 0.19, 0.24, "Unified evidence", "Agent JSONL\nPath scheduler JSONL\nMass statistics JSONL", COLORS["blue"])

    arrow = {"arrowstyle": "-|>", "lw": 1.8, "color": COLORS["grid"], "mutation_scale": 14}
    ax.annotate("", xy=(0.385, 0.67), xytext=(0.265, 0.62), arrowprops=arrow)
    ax.annotate("", xy=(0.385, 0.44), xytext=(0.265, 0.62), arrowprops=arrow)
    ax.annotate("", xy=(0.755, 0.64), xytext=(0.63, 0.67), arrowprops=arrow)
    ax.annotate("", xy=(0.755, 0.57), xytext=(0.63, 0.44), arrowprops=arrow)

    metrics = [
        (f"{row['mass']['decisions']:,}", "Mass decisions"),
        (f"{row['mass']['arrivals']:,}", "Mass arrivals"),
        (f"{row['n_move_failed']}", "Hero move failures"),
        (f"{row['mass']['policy_us_mean']:.0f} us", "Mean Mass policy call"),
        (f"{row['path_scheduler']['wait_ms_p95_mean']:.1f} ms", "Scheduler p95 wait"),
    ]
    xs = [0.10, 0.30, 0.50, 0.70, 0.90]
    for x, (value, label) in zip(xs, metrics):
        ax.text(x, 0.205, value, color=COLORS["text"], fontsize=18, fontweight="bold", ha="center")
        ax.text(x, 0.16, label, color=COLORS["muted"], fontsize=9.5, ha="center")

    ax.text(
        0.5,
        0.075,
        "Runtime integration proof only - offscreen frame timing is excluded from performance claims.",
        color=COLORS["orange"],
        fontsize=10.5,
        ha="center",
    )
    ax.text(
        0.5,
        0.035,
        "Source: research/results/ue_sessions/mass_smoke_20260831/per_session.json",
        color=COLORS["muted"],
        fontsize=8.5,
        ha="center",
    )
    _save(fig, output_dir, "mass-hybrid-runtime-proof")


def generate_mass_scaling(output_dir: Path) -> None:
    rows = _load_json(MASS_SCALING_SOURCE)
    totals = [row["n_agents"] for row in rows]
    frame = [row["frame_ms_p95"]["mean"] for row in rows]
    frame_std = [row["frame_ms_p95"]["std"] for row in rows]
    failures = [100.0 * row["fail_rate"]["mean"] for row in rows]
    failure_std = [100.0 * row["fail_rate"]["std"] for row in rows]
    throughput = [row["intents_per_agent_per_min"]["mean"] for row in rows]
    throughput_std = [row["intents_per_agent_per_min"]["std"] for row in rows]

    fig, axes = plt.subplots(1, 3, figsize=(16.2, 6.6))
    _apply_theme(fig, axes)
    fig.subplots_adjust(left=0.055, right=0.985, top=0.75, bottom=0.25, wspace=0.27)
    fig.suptitle(
        "Mass simulation LOD keeps incremental cost bounded through 1,024 NPCs",
        color=COLORS["text"],
        fontsize=20,
        fontweight="bold",
        y=0.95,
    )
    fig.text(
        0.5,
        0.885,
        "Visible UE 5.8 standalone  |  16 Hero Actors + Mass background  |  3 seeds x 300 seconds",
        ha="center",
        color=COLORS["muted"],
        fontsize=11,
    )

    ax_frame, ax_failure, ax_throughput = axes
    ax_frame.errorbar(
        totals,
        frame,
        yerr=frame_std,
        color=COLORS["cyan"],
        marker="o",
        markersize=7,
        linewidth=2.5,
        capsize=4,
    )
    ax_frame.axhline(16.67, color=COLORS["orange"], linewidth=1.6, linestyle="--")
    ax_frame.set_title(
        "Frame p95", loc="left", fontsize=13, pad=12, color=COLORS["text"]
    )
    ax_frame.set_xlabel("Total simulated NPCs")
    ax_frame.set_ylabel("Milliseconds")
    ax_frame.set_xticks(totals)
    ax_frame.set_ylim(0, max(frame) * 1.28)
    ax_frame.text(
        0.04,
        0.94,
        f"128 -> 1,024: {frame[0]:.2f} -> {frame[-1]:.2f} ms",
        transform=ax_frame.transAxes,
        color=COLORS["text"],
        fontsize=9.5,
        va="top",
    )

    bars = ax_failure.bar(
        totals,
        failures,
        width=90,
        color=[COLORS["green"], COLORS["green"], COLORS["orange"], COLORS["green"]],
        yerr=failure_std,
        error_kw={"ecolor": COLORS["muted"], "elinewidth": 1.2, "capsize": 3},
    )
    for bar, value in zip(bars, failures):
        ax_failure.text(
            bar.get_x() + bar.get_width() / 2,
            value + 0.12,
            f"{value:.1f}%",
            ha="center",
            color=COLORS["text"],
            fontsize=9.5,
        )
    ax_failure.set_title(
        "Hero movement failure",
        loc="left",
        fontsize=13,
        pad=12,
        color=COLORS["text"],
    )
    ax_failure.set_xlabel("Total simulated NPCs")
    ax_failure.set_ylabel("Failure rate (%)")
    ax_failure.set_xticks(totals)
    ax_failure.set_ylim(0, max(2.0, max(failures) + max(failure_std) + 0.8))

    ax_throughput.errorbar(
        totals,
        throughput,
        yerr=throughput_std,
        color=COLORS["blue"],
        marker="o",
        markersize=7,
        linewidth=2.5,
        capsize=4,
    )
    ax_throughput.set_title(
        "Completed intents",
        loc="left",
        fontsize=13,
        pad=12,
        color=COLORS["text"],
    )
    ax_throughput.set_xlabel("Total simulated NPCs")
    ax_throughput.set_ylabel("Per NPC per minute")
    ax_throughput.set_xticks(totals)
    ax_throughput.set_ylim(0, max(throughput) * 1.25)
    ax_throughput.text(
        0.04,
        0.94,
        f"1,024 NPCs: {throughput[-1]:.2f} intents/min",
        transform=ax_throughput.transAxes,
        color=COLORS["text"],
        fontsize=9.5,
        va="top",
    )

    fig.text(
        0.5,
        0.075,
        "Scaling overhead is flat, but the absolute frame time is about 25 ms mean / 30 ms p95; this is not a 60 FPS claim.",
        ha="center",
        color=COLORS["orange"],
        fontsize=10.5,
    )
    fig.text(
        0.5,
        0.035,
        "Source: research/results/ue_sessions/mass_scaling_20260901/scaling_curve.json",
        ha="center",
        color=COLORS["muted"],
        fontsize=8.5,
    )
    _save(fig, output_dir, "mass-scaling-evidence")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output directory (default: {DEFAULT_OUTPUT})",
    )
    args = parser.parse_args()

    generate_actor_scaling(args.out)
    generate_ablation(args.out)
    generate_mass_runtime_proof(args.out)
    generate_mass_scaling(args.out)
    print(f"Wrote portfolio visuals to {args.out}")


if __name__ == "__main__":
    main()
