"""Fresh-process evaluation matrix. No live mode switching or automatic speedup claims."""
import argparse
import json
from pathlib import Path
import subprocess
import uuid


def matrix(axes, seeds, counts=None):
    for axis in axes:
        for count in counts or ([64] if axis == 1 else [1024]):
            if not 1 <= count <= (128 if axis == 1 else 4096):
                raise ValueError(f"Unsupported NPC count {count} for axis {axis}")
            for repetition, seed in enumerate(seeds):
                variants = list(range(3 if axis == 0 else 2))
                offset = repetition % len(variants)
                for variant in variants[offset:] + variants[:offset]:
                    yield axis, variant, count, seed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--axis", choices=["all", "persona", "execution", "inference"], default="all")
    parser.add_argument("--counts", type=int, nargs="+")
    parser.add_argument("--seeds", type=int, nargs="+", default=[17, 18, 19])
    parser.add_argument("--seconds", type=float, default=30)
    parser.add_argument("--warmup", type=float, default=5)
    parser.add_argument("--resolution", default="1280x720")
    parser.add_argument("--map", default="/Game/PCSP/Maps/Map_PCSPDistrict_Portfolio_Visual")
    parser.add_argument("--engine", type=Path, default=Path("C:/Program Files/Epic Games/UE_5.8/Engine/Binaries/Win64/UnrealEditor.exe"))
    parser.add_argument("--timeout", type=float, default=240)
    parser.add_argument("--offscreen", action="store_true")
    parser.add_argument("--null-rhi", action="store_true", help="Functional smoke only, never performance evidence")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if not 2 <= args.seconds <= 600 or not 1 <= args.warmup <= 120:
        parser.error("seconds must be 2..600 and warmup 1..120")
    width, height = map(int, args.resolution.split("x"))
    if min(width, height) < 320:
        parser.error("Resolution must be at least 320 pixels per dimension")
    project = Path(__file__).resolve().parents[1]
    axes = [0, 1, 2] if args.axis == "all" else [["persona", "execution", "inference"].index(args.axis)]
    cases = list(matrix(axes, args.seeds, args.counts))
    suite = project / "Saved/PCSP/Evaluation" / ("suite_" + uuid.uuid4().hex)
    manifest = []
    if not args.dry_run:
        suite.mkdir(parents=True)
    for index, (axis, variant, count, seed) in enumerate(cases):
        series = uuid.uuid4().hex
        command = [str(args.engine), str(project / "cnzoi.uproject"), args.map, "-game", "-unattended", "-nosound",
                   "-windowed", f"-ResX={width}", f"-ResY={height}", f"-PCSP_EvalAxis={axis}",
                   f"-PCSP_EvalVariant={variant}", f"-PCSP_EvalCount={count}", f"-PCSP_EvalSeed={seed}",
                   f"-PCSP_EvalSeconds={args.seconds}", f"-PCSP_EvalWarmup={args.warmup}",
                   f"-PCSP_EvalSeries={series}", "-PCSP_EvalAutoQuit", "-ExecCmds=r.VSync 0,t.MaxFPS 0",
                   f"-abslog={suite / (str(index) + '.log')}"]
        if args.offscreen:
            command.append("-RenderOffscreen")
        if args.null_rhi:
            command.append("-nullrhi")
        if axis == 2 and variant == 0:
            command.append("-PCSP_EvalReplay")
        entry = dict(axis=axis, variant=variant, count=count, seed=seed, command=command,
                     functional_only=args.null_rhi, series=series)
        print(json.dumps(entry), flush=True)
        if args.dry_run:
            continue
        try:
            completed = subprocess.run(command, cwd=project, timeout=args.timeout, check=False)
            entry["exit_code"] = completed.returncode
            results = list((project / "Saved/PCSP/Evaluation" / series).glob("run_*.json"))
            entry["results"] = [str(p) for p in results]
            entry["passed"] = completed.returncode == 0 and len(results) == 1 and json.loads(results[0].read_text(encoding="utf-8-sig"))["complete"]
        except subprocess.TimeoutExpired:
            entry.update(passed=False, error="Timed out; spawned game process terminated")
        manifest.append(entry)
        (suite / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        if not entry["passed"]:
            raise SystemExit(f"Evaluation failed; inspect {suite / 'manifest.json'}")
    if not args.dry_run:
        print(f"Completed {len(manifest)} runs. Manifest: {suite / 'manifest.json'}")


if __name__ == "__main__":
    main()
