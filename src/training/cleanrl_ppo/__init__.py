"""In-house CleanRL-style PPO for Melting Pot.

Single-file-per-concern decomposition (per MELTINGPOT_PLAN.md Phase 1):

- ``config.py``  : dataclass-typed run config.
- ``networks.py``: IMPALA-CNN encoder + actor/critic heads (+ optional LSTM).
- ``rollout_buffer.py``: on-policy buffer with GAE.
- ``trainer.py`` : top-level training loop.
- ``launch.py``  : CLI entry point.
"""
