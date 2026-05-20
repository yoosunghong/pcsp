# AGENTS.md - pcsp Workspace Context

## Repository Layout

This workspace has two active top-level project areas:

- `research/` - the existing PCSP research code, data artifacts, paper source, plans, and historical docs.
- `ue/` - Unreal Engine work. The current UE5 project lives under `ue/cnzoi/`.

The PCSP research project is a self-contained subtree. Research commands should normally be run from `D:\Github\pcsp\research`, so existing relative paths such as `scripts/test_env.py`, `data/personas/...`, `results/...`, and `paper/cog2026_main/main.tex` continue to work.

UE5 commands and file edits should normally target `D:\Github\pcsp\ue\cnzoi`.

## Work Routing

- For research scripts, training, evaluation, plotting, paper text, and Python environment work, use `research/`.
- For Unreal Engine source, assets, configs, Behavior Tree integration, PCSP runtime bridge work, and UE5-specific planning, use `ue/cnzoi/`.
- For repository-level documentation, ignore rules, or coordination between research and UE5, work from the repository root.

## Research Working Rules

For research work:

1. Read `research/PLAN.md` before changing code, experiments, evaluation, or paper text.
2. Treat `research/paper/cog2026_main/main.tex` as the source of truth for the active paper framing. This is the **COG 2026 Main Track** manuscript; it is not a workshop, vision, or position paper. Do not reintroduce workshop/vision framing in the abstract, contributions, conclusion, or context docs. The previous directory name `cog2026_vision/` has been renamed to `cog2026_main/`; any reference to the old path is stale.
3. Do not treat older proposals such as `research/persona-proposal.md` or archived documents as the active direction.
4. Connect non-trivial research changes to `research/PLAN.md`.
5. Record important decisions, result paths, failed experiments, and retraining requirements in `research/PLAN.md` or `research/DONE.md`.
6. Preserve old documents under `research/archive/`; do not delete them.

## UE5 Working Rules

For Unreal Engine work:

1. Read `ue/cnzoi/PLAN.md` before changing UE5 code, assets, AI behavior, inference integration, or UE-specific docs.
2. Treat `ue/cnzoi/PROPOSAL.md` as the high-level UE5 rationale and scope document.
3. Treat `ue/cnzoi/PCSP_UE5_Implementation_Plan.md` as the original detailed implementation plan.
4. Record important UE5 decisions, result paths, failed attempts, and follow-up requirements in `ue/cnzoi/DONE.md`.
5. Keep Unreal-generated build/cache directories out of Git unless explicitly needed.
6. If Unreal integration changes the research API contract, observation schema, action ontology, training export format, or evaluation protocol, also update `research/PLAN.md`.

## Development Environment

Research commands use the `paper` conda environment:

```bash
conda activate paper
```

or, for one-off commands from `research/`:

```bash
conda run -n paper python scripts/test_env.py
conda run -n paper python scripts/test_env_v3.py
conda run -n paper python scripts/test_film.py
```

UE5 work should be performed inside `ue/cnzoi/`. Do not add generated directories such as `Binaries/`, `Intermediate/`, `Saved/`, `DerivedDataCache/`, or `.vs/` to version control unless the user explicitly asks for it.

## Key Research Paths

- `research/src/` - Mini-Inzoi environments, models, training, and eval code.
- `research/scripts/` - training, evaluation, plotting, and artifact scripts.
- `research/data/` - persona datasets and human-eval artifacts.
- `research/results/` - generated metrics, figures, checkpoints, and reports.
- `research/paper/cog2026_main/` - current manuscript source.
- `research/docs/` - design notes such as Mini-Inzoi v3.

## Key UE5 Paths

- `ue/cnzoi/Source/` - Unreal C++ source.
- `ue/cnzoi/Config/` - Unreal project configuration.
- `ue/cnzoi/Content/` - Unreal assets, maps, Behavior Trees, and related content.
- `ue/cnzoi/PLAN.md` - active UE5 implementation plan.
- `ue/cnzoi/DONE.md` - UE5 progress and decision log.
- `ue/cnzoi/PROPOSAL.md` - UE5 project proposal and rationale.
- `ue/cnzoi/PCSP_UE5_Implementation_Plan.md` - original detailed UE5 implementation plan.

## Current Research Priorities

- Strengthen persona-conditioned behavior that is observable to humans.
- Expand human evaluation from coarse action labels to rich trajectory traces.
- Keep existing v1/v2/v3 research results reproducible from within `research/`.
- Design the Mini-Inzoi v3 / Unreal integration boundary carefully before changing observation or action contracts.

## Current UE5 Priorities

- Define the affordance taxonomy and BT-Blackboard-Policy contract.
- Build a 16-agent continuous-space prototype.
- Integrate PCSP as a Behavior Tree decision service or task.
- Preserve persona-conditioned high-level actions while delegating movement and interaction execution to UE5 systems.
