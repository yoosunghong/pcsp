"""Summarize -PCSP_CityRouteAudit output; no third-party Python packages required."""
import argparse
import json
import math
from collections import defaultdict
from pathlib import Path


def analyze(session):
    config = json.loads((session / "mass_run_config.json").read_text(encoding="utf-8"))
    first, last, moved = {}, {}, set()
    frames = defaultdict(list)
    for line in (session / "mass_routes.jsonl").read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        ident = row["id"]
        first.setdefault(ident, row)
        last[ident] = row
        frames[row["t"]].append(row)
        if math.dist(first[ident]["pos"], row["pos"]) > 100:
            moved.add(ident)
    diameter = config["agent_radius"] * 2
    overlaps = 0
    minimum = math.inf
    for rows in frames.values():
        cells = defaultdict(list)
        for row in rows:
            x, y, z = row["pos"]
            cell = (math.floor(x / diameter), math.floor(y / diameter))
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for ox, oy, oz in cells[(cell[0] + dx, cell[1] + dy)]:
                        if abs(z - oz) >= diameter:
                            continue
                        distance = math.hypot(x - ox, y - oy)
                        minimum = min(minimum, distance)
                        if distance < diameter - 1:  # centimetre tolerance for rounded logs
                            overlaps += 1
            cells[cell].append((x, y, z))
    stats = [json.loads(line) for line in (session / "mass_stats.jsonl").read_text(encoding="utf-8").splitlines()]
    return {
        "session": str(session), "scale": config["representation_scale"],
        "entities": len(first), "sampled_frames": len(frames),
        "first_t": min(frames), "last_t": max(frames),
        "moved_over_100cm": len(moved), "never_moved_ids": sorted(first.keys() - moved),
        "moving_last_frame": sum(row["moving"] for row in last.values()),
        "arrivals": sum(row["arrivals"] for row in stats),
        "failed_route_attempts": sum(row["route_blocked"] for row in stats),
        "overlapping_pair_samples": overlaps,
        "minimum_sampled_neighbor_distance_cm": None if math.isinf(minimum) else minimum,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("session", type=Path)
    args = parser.parse_args()
    print(json.dumps(analyze(args.session), indent=2))
