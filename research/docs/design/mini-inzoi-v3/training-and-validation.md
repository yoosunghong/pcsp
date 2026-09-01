# Mini-Inzoi v3: Training and Validation Contract

## Reward

`r_total = r_need + r_persona_action + r_persona_style + r_social`.

- `r_need` and `r_social` retain the prior meanings.
- `r_persona_action` grants `+0.5` for an action in the persona's v3 preferred set.
- `r_persona_style` grants `+0.3 * cos(persona.bf_vec, ACTION_STYLE_PROFILE[a])`.

The style term distinguishes actions that satisfy the same need. Keep coefficients synchronized with the environment implementation; evaluation scripts must not duplicate them.

## Compatibility and retraining

v1/v2 remain reproducible. v3 changes observations (20→33 base, 56→69 large) and actions (12→20), so old checkpoints are incompatible. Trainers and evaluators receive `obs_dim`, `n_actions`, `env_factory`, and `personas_path`; do not fork parallel `*_v3.py` implementations.

Any action or observation change updates policy heads, trajectory-action one-hot dimensions, trainers/evaluators, export metadata, UE mapping, and this contract. Record checkpoint impact in `research/DONE.md`.

## Deterministic persona conversion

`scripts/build_personas_v3.py` deterministically creates `personas_300_v3.json` from `personas_300.json`. It expands old actions by the relevant Big-Five trait: work/sleep use C, social/rest/exercise use E, and read uses O. High openness additionally receives `explore` (15). Regenerate instead of hand-editing the output.

## Acceptance gates

Implementation requires a passing PettingZoo test, reachable actions, all eight needs restored, distinct activity style rows, snapshotted action order, and useful repeat-heavy routine range. Training smoke needs reward improvement, distinct persona encodings, and the pinned InfoNCE sanity threshold. Paper-ready claims additionally require the relevant held-out and human-trace evidence in `research/PLAN.md`.
