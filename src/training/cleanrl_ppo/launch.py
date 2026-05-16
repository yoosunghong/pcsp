"""CLI entry point for the CleanRL-style PPO trainer.

Usage:
    python -m src.training.cleanrl_ppo.launch \\
        --substrate commons_harvest__open --num-envs 8 --total-env-steps 1000000
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import fields
from pathlib import Path

from .config import PPOConfig
from .trainer import PPOTrainer, seed_everything


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="CleanRL-style PPO on Melting Pot.")
    for f in fields(PPOConfig):
        flag = "--" + f.name.replace("_", "-")
        kw: dict = {"default": None, "dest": f.name}
        if f.type is bool or f.default is True or f.default is False:
            p.add_argument(flag, type=lambda x: x.lower() in ("1", "true", "yes"), **kw)
        elif f.type in (int, "int") or isinstance(f.default, int):
            p.add_argument(flag, type=int, **kw)
        elif f.type in (float, "float") or isinstance(f.default, float):
            p.add_argument(flag, type=float, **kw)
        elif f.name == "num_players":
            p.add_argument(flag, type=int, **kw)
        elif f.name == "target_kl":
            p.add_argument(flag, type=float, **kw)
        elif f.name == "persona_population_kind":
            p.add_argument(flag, type=str, **kw)
        elif f.name == "extra":
            continue
        else:
            p.add_argument(flag, type=str, **kw)
    p.add_argument("--resume-from", type=str, default=None, help="Path to checkpoint to resume from.")
    p.add_argument("--no-async", action="store_true", help="Use SyncVectorMeltingPot (debug).")
    return p


def merge_cfg(args: argparse.Namespace) -> PPOConfig:
    cfg = PPOConfig()
    for f in fields(PPOConfig):
        v = getattr(args, f.name, None)
        if v is not None:
            setattr(cfg, f.name, v)
    if args.no_async:
        cfg.async_envs = False
    if cfg.run_name is None:
        cfg.run_name = f"{cfg.substrate}-seed{cfg.seed}-{int(time.time())}"
    return cfg


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    cfg = merge_cfg(args)
    seed_everything(cfg.seed)

    # Lazy import so help/argparse doesn't load TF.
    from src.env.meltingpot import AsyncVectorMeltingPot, SyncVectorMeltingPot

    EnvCls = AsyncVectorMeltingPot if cfg.async_envs else SyncVectorMeltingPot
    env = EnvCls(
        cfg.substrate,
        num_envs=cfg.num_envs,
        num_players=cfg.num_players,
        base_seed=cfg.seed,
    )

    writer = None
    if cfg.tb_logging:
        try:
            from torch.utils.tensorboard import SummaryWriter  # type: ignore
            tb_dir = Path(cfg.run_dir) / cfg.run_name / "tb"
            tb_dir.mkdir(parents=True, exist_ok=True)
            writer = SummaryWriter(str(tb_dir))
        except Exception as e:  # pragma: no cover
            print(f"[ppo] TB disabled: {e}", file=sys.stderr)

    # Dump effective config.
    cfg_dir = Path(cfg.run_dir) / cfg.run_name
    cfg_dir.mkdir(parents=True, exist_ok=True)
    (cfg_dir / "config.json").write_text(json.dumps(cfg.to_dict(), indent=2, default=str))

    trainer = PPOTrainer(cfg, env, writer=writer)
    if args.resume_from:
        trainer.load_checkpoint(args.resume_from)

    try:
        trainer.train()
    finally:
        env.close()
        if writer is not None:
            writer.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
