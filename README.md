# pcsp Workspace

This repository is now split for game-engine integration:

- `research/` contains the existing PCSP research artifact, including source code, data, results, paper files, and plans.
- `ue/` is reserved for the Unreal Engine project.

For research work, start in `research/`:

```bash
cd research
conda run -n paper python scripts/test_env.py
conda run -n paper python scripts/test_env_v3.py
```

See `research/README.md` and `research/PLAN.md` for the PCSP research workflow.
