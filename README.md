# PCSP

PCSP is a research project on scalable, persona-conditioned game agents for
life-simulation NPCs. The core idea is to encode a natural-language persona once
per NPC with a frozen language-model embedding, then condition a single shared
reinforcement-learning policy on that persona vector at every decision step.
This targets a practical gap in game AI: giving hundreds or thousands of NPCs
distinct, consistent, designer-controllable behavior without hand-authoring a
behavior tree or training a separate policy for each character.

The project evaluates Persona-Conditioned Shared Policies (PCSP) across three
validation layers:

- A controlled Mini-Inzoi / PCSP-D benchmark for testing whether trajectories
  remain traceable to the intended persona.
- External multi-agent social-dilemma substrates based on Melting Pot.
- A UE5 deployment that runs the trained policy inside a real-time Behavior
  Tree / Blackboard stack.

The main empirical finding is that trajectory-level persona consistency is not
just a side effect of reward learning. The InfoNCE consistency objective is
load-bearing: removing it can preserve or improve task reward while collapsing
zero-shot trajectory-to-persona identification toward chance.

## Repository Layout

- `research/` contains the PCSP research code, environments, persona data,
  training scripts, evaluation scripts, and generated experiment artifacts.
- `ue/` contains the Unreal Engine integration work for running PCSP policies in
  an engine-side NPC stack.

## Quick Start

Research commands should be run from `research/`:

```bash
cd research
conda run -n paper python scripts/test_env.py
conda run -n paper python scripts/test_env_v3.py
```

The research environment uses the `paper` conda environment.
