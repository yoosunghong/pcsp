"""Validate real mode recordings without treating them as a controlled benchmark."""
import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("csv", type=Path)
args = parser.parse_args()
runs = defaultdict(list)
with args.csv.open(encoding="utf-8") as stream:
    for row in csv.DictReader(stream):
        runs[int(row["run"])].append(row)
assert runs, "No samples were recorded"
latest = {}
for run_id, rows in sorted(runs.items()):
    modes = {row["mode"] for row in rows}
    assert len(modes) == 1, "Modes mixed inside a run"
    elapsed = 0.0
    for row in rows:
        seconds = float(row["window_s"])
        frames = int(row["frames"])
        assert seconds > 0 and frames > 0
        assert float(row["elapsed_s"]) > elapsed
        elapsed = float(row["elapsed_s"])
        cpu = float(row["process_cpu_pct"])
        assert cpu == -1 or 0 <= cpu <= 100
        # CSV times have 1 ms precision; include that rounding in tolerance.
        assert abs(float(row["fps"]) - frames / seconds) < max(0.1, frames * 0.001 / seconds**2)
        assert abs(float(row["mean_frame_ms"]) - seconds * 1000 / frames) < max(0.1, 0.5 / frames + 0.001)
    total_time = sum(float(row["window_s"]) for row in rows)
    latest[next(iter(modes))] = {
        "run": run_id, "samples": len(rows), "seconds": total_time,
        "fps": sum(int(row["frames"]) for row in rows) / total_time,
    }
assert set(latest) == {"HybridPCSP", "BTOnly", "HybridNoPersona"}, latest
assert all(run["samples"] >= 2 for run in latest.values()), latest
print(json.dumps({"result": "PASS", "latest_runs": latest}, indent=2))
