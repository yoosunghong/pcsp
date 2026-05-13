# CLAUDE.md - pcsp Workspace Context

Use the same working rules as `AGENTS.md`.

Top-level layout:

- `research/` contains the existing PCSP research project.
- `ue/cnzoi/` contains the current Unreal Engine 5 project.

Route work by target:

- For research scripts, experiments, evaluation, plotting, or paper text, read `research/PLAN.md` and work from `research/`.
- For UE5 code, assets, Behavior Trees, AI integration, inference bridge work, or UE5-specific docs, read `ue/cnzoi/PLAN.md` and work from `ue/cnzoi/`.
- For repository-level coordination, docs, or ignore rules, work from the repository root and keep both project areas in sync.

If UE5 integration changes the research API contract, observation schema, action ontology, training export format, or evaluation protocol, update `research/PLAN.md` as well as the relevant UE5 docs.
