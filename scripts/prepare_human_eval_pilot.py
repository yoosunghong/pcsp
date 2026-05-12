"""
Prepare counterbalanced pilot packets for the v3 rich-vs-coarse human eval.

Each pilot participant sees every trajectory item once, but only in one
condition (rich or coarse). Across participants, item conditions are balanced:
with 10 participants and 30 items, each item appears 5 times rich and 5 times
coarse. The script emits participant-facing Markdown packets plus CSV templates
that can be filled after collection.

Usage:
    conda run -n paper python scripts/prepare_human_eval_pilot.py
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _load_json(path: Path) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _item_uid(condition: str, item_id: str) -> str:
    return f"{condition}:{item_id}"


def _participant_id(idx: int) -> str:
    return f"pilot_{idx:02d}"


def _condition_for(participant_idx: int, item_idx: int) -> str:
    # Alternating parity gives exact balance when n_participants is even.
    return "rich" if (participant_idx + item_idx) % 2 == 0 else "coarse"


def _packet_markdown(participant_id: str, rows: list[dict[str, Any]]) -> str:
    lines = [
        "# NPC 페르소나 식별 평가 파일럿",
        "",
        f"참가자 ID: `{participant_id}`",
        "",
        "각 문항에서 후보 A 또는 후보 B를 고르고, 확신도를 1-5로 기록해 주세요.",
        "응답 시간은 가능하면 초 단위로 함께 기록합니다.",
        "",
    ]
    for idx, row in enumerate(rows, start=1):
        lines.extend([
            f"## 문항 {idx:02d} ({row['item_uid']})",
            "",
            "```text",
            row["display_text"],
            "```",
            "",
            "응답: ",
            "확신도: ",
            "응답 시간(초): ",
            "",
        ])
    return "\n".join(lines)


def prepare_pilot(
    rich_survey_path: Path,
    coarse_survey_path: Path,
    output_dir: Path,
    n_participants: int,
    seed: int,
) -> dict[str, Any]:
    if n_participants < 2 or n_participants % 2 != 0:
        raise ValueError("n_participants must be an even integer >= 2 for balanced conditions.")

    rich = _load_json(rich_survey_path)
    coarse = _load_json(coarse_survey_path)
    rich_items = {item["item_id"]: item for item in rich["items"]}
    coarse_items = {item["item_id"]: item for item in coarse["items"]}
    item_ids = sorted(rich_items)
    if item_ids != sorted(coarse_items):
        raise ValueError("Rich and coarse surveys must contain the same item_ids.")

    output_dir.mkdir(parents=True, exist_ok=True)
    packets_dir = output_dir / "participant_packets"
    packets_dir.mkdir(parents=True, exist_ok=True)

    response_rows: list[dict[str, Any]] = []
    answer_rows: list[dict[str, Any]] = []
    assignment_rows: list[dict[str, Any]] = []
    rng = random.Random(seed)

    for p_idx in range(n_participants):
        participant_id = _participant_id(p_idx + 1)
        packet_rows: list[dict[str, Any]] = []

        for item_idx, item_id in enumerate(item_ids):
            condition = _condition_for(p_idx, item_idx)
            source_item = rich_items[item_id] if condition == "rich" else coarse_items[item_id]
            uid = _item_uid(condition, item_id)
            row = {
                "participant_id": participant_id,
                "item_uid": uid,
                "condition": condition,
                "item_id": item_id,
                "trajectory_id": source_item["trajectory_id"],
                "model": source_item.get("model", "unknown"),
                "split": source_item.get("split", "unknown"),
                "target_persona_id": source_item["target_persona_id"],
                "correct_option": source_item["correct_option"],
                "display_text": source_item["display_text"],
            }
            packet_rows.append(row)
            response_rows.append({
                "participant_id": participant_id,
                "item_uid": uid,
                "condition": condition,
                "item_id": item_id,
                "response": "",
                "confidence": "",
                "response_time_sec": "",
            })
            assignment_rows.append({
                "participant_id": participant_id,
                "item_uid": uid,
                "condition": condition,
                "item_id": item_id,
                "trajectory_id": source_item["trajectory_id"],
                "target_persona_id": source_item["target_persona_id"],
            })

        rng.shuffle(packet_rows)
        packet_path = packets_dir / f"{participant_id}.md"
        packet_path.write_text(_packet_markdown(participant_id, packet_rows), encoding="utf-8")

    for condition, items in (("rich", rich_items), ("coarse", coarse_items)):
        for item_id, item in sorted(items.items()):
            answer_rows.append({
                "item_uid": _item_uid(condition, item_id),
                "condition": condition,
                "item_id": item_id,
                "trajectory_id": item["trajectory_id"],
                "model": item.get("model", "unknown"),
                "split": item.get("split", "unknown"),
                "target_persona_id": item["target_persona_id"],
                "correct_option": item["correct_option"],
            })

    response_template_path = output_dir / "pilot_response_template.csv"
    answer_key_path = output_dir / "pilot_answer_key.csv"
    assignment_path = output_dir / "pilot_assignment_manifest.csv"
    manifest_path = output_dir / "pilot_manifest.json"
    readme_path = output_dir / "README.md"

    with open(response_template_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "participant_id", "item_uid", "condition", "item_id",
                "response", "confidence", "response_time_sec",
            ],
        )
        writer.writeheader()
        writer.writerows(response_rows)

    with open(answer_key_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(answer_rows[0].keys()))
        writer.writeheader()
        writer.writerows(answer_rows)

    with open(assignment_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(assignment_rows[0].keys()))
        writer.writeheader()
        writer.writerows(assignment_rows)

    condition_counts: dict[str, int] = {"rich": 0, "coarse": 0}
    for row in assignment_rows:
        condition_counts[row["condition"]] += 1

    manifest = {
        "study": "pcsp_v3_rich_vs_coarse_pilot",
        "rich_survey": str(rich_survey_path),
        "coarse_survey": str(coarse_survey_path),
        "n_participants": n_participants,
        "n_items_per_participant": len(item_ids),
        "total_planned_responses": len(response_rows),
        "condition_counts": condition_counts,
        "response_template": str(response_template_path),
        "answer_key": str(answer_key_path),
        "assignment_manifest": str(assignment_path),
        "participant_packets_dir": str(packets_dir),
        "analysis_command": (
            "conda run -n paper python src/eval/human_eval.py "
            f"--csv {response_template_path.relative_to(ROOT)} "
            f"--answer_key {answer_key_path.relative_to(ROOT)} "
            "--output results/eval/human_eval_pilot_summary.json"
        ),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    readme_path.write_text(
        "\n".join([
            "# Human-Eval Pilot Package",
            "",
            "Use `participant_packets/pilot_XX.md` for pilot collection.",
            "Fill `pilot_response_template.csv` with each participant's A/B response, confidence, and response time.",
            "Score filled responses with:",
            "",
            "```bash",
            manifest["analysis_command"],
            "```",
            "",
            "Design: each participant sees all 30 trajectory items once, split 15 rich / 15 coarse.",
            "Across 10 participants, each item is assigned to rich 5 times and coarse 5 times.",
            "",
        ]),
        encoding="utf-8",
    )

    return manifest


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--rich_survey", default="data/human_eval/persona_identification_survey_ko.json")
    p.add_argument("--coarse_survey", default="data/human_eval/persona_identification_survey_ko_coarse.json")
    p.add_argument("--output_dir", default="data/human_eval/pilot_v3")
    p.add_argument("--n_participants", type=int, default=10)
    p.add_argument("--seed", type=int, default=20260512)
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    manifest = prepare_pilot(
        rich_survey_path=ROOT / args.rich_survey,
        coarse_survey_path=ROOT / args.coarse_survey,
        output_dir=ROOT / args.output_dir,
        n_participants=args.n_participants,
        seed=args.seed,
    )
    print(json.dumps(manifest, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
