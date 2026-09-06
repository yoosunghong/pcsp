"""Summarize one explicit evaluation suite, excluding incomplete or mismatched runs."""
import argparse
import json
from collections import defaultdict
from pathlib import Path
from statistics import mean, stdev


def summarize(manifest):
    groups = defaultdict(list)
    for entry in manifest:
        if not entry.get("passed") or entry.get("functional_only"):
            continue
        for path in entry["results"]:
            row = json.loads(Path(path).read_text(encoding="utf-8-sig"))
            if not row["complete"] or row["invalid_reason"] or row.get("inference_failures", 0) > 0:
                continue
            # Seeds are repetitions, not different workloads; all other context stays explicit.
            key = tuple(row[k] for k in ("axis", "variant", "npc_count", "map", "world_type", "width", "height", "vsync", "fps_cap"))
            groups[key].append(row)
    output = []
    for key, rows in groups.items():
        result = dict(zip(("axis", "variant", "npc_count", "map", "world_type", "width", "height", "vsync", "fps_cap"), key))
        result["seeds"] = [r["seed"] for r in rows]
        result["n"] = len(rows)
        result["scope"] = rows[0]["comparison_scope"]
        for metric in ("fps", "cpu_pct", "p95_frame_ms", "action_entropy_bits"):
            values = [r[metric] for r in rows if r[metric] >= 0]
            result[metric] = {"mean": mean(values), "stdev": stdev(values) if len(values) > 1 else None} if values else None
        output.append(result)
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    result = summarize(json.loads(args.manifest.read_text(encoding="utf-8")))
    destination = args.manifest.with_name("summary.json")
    destination.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(destination)
