# PCSP: Persona-Conditioned Shared Policy

This repository contains the code, data artifacts, and manuscript source for
**One Policy, Infinite NPCs: A Vision for Scalable Persona-Conditioned NPC
Control in Life Simulation Games**.

PCSP trains a single shared reinforcement-learning policy conditioned on frozen
LLM embeddings of natural-language persona descriptions. The goal is to support
many life-simulation NPCs with distinct, designer-controllable behavior without
training one policy per character.

Paper source: `paper/cog2026_vision/main.tex`  
Current PDF: `paper/cog2026_vision/main.pdf`  
Repository: https://github.com/yoosunghong/pcsp

This repository is maintained as the public research artifact for the manuscript.
It now lives under the repository's `research/` subtree so the top-level
workspace can also host an Unreal Engine project in `ue/`.

## Highlights

- Mini-Inzoi v1/v2/v3 PettingZoo life-simulation environments.
- Persona-conditioned actor-critic policy with learned LoRA projection from
  Qwen3-Embedding-0.6B persona embeddings.
- PPO training with trajectory-persona InfoNCE consistency and KL diversity
  objectives.
- v3 action ontology with richer activity styles such as `focused_work`,
  `planning_work`, `rest_alone`, `rest_with_others`, `eat_quick`, and
  `eat_slow`.
- Designer-authored qualitative case study using Sims 3 trait combinations and
  Animal Crossing villager personality archetypes.

## Setup

The project assumes the `paper` conda environment used during development.
Run commands from this `research/` directory.

```bash
conda activate paper
```

Core smoke tests:

```bash
conda run -n paper python scripts/test_env.py
conda run -n paper python scripts/test_env_v3.py
conda run -n paper python scripts/test_film.py
```

## Common Commands

Run PCSP v3 training:

```bash
conda run -n paper python scripts/run_pcsp_v3.py --mode full
```

Run v3 zero-shot evaluation:

```bash
conda run -n paper python scripts/run_eval_v3_zeroshot.py
```

Run the designer-authored qualitative case study:

```bash
conda run -n paper python scripts/run_designer_persona_case_study.py
```

Recompile the paper:

```bash
cd paper/cog2026_vision
pdflatex -interaction=nonstopmode main.tex
bibtex main
pdflatex -interaction=nonstopmode main.tex
pdflatex -interaction=nonstopmode main.tex
```

## Repository Layout

- `src/env/`: Mini-Inzoi environments and action semantics.
- `src/models/`: FiLM conditioning and trajectory encoder modules.
- `src/training/`: PPO and PCSP training code.
- `src/eval/`: automated evaluation metrics.
- `scripts/`: training, evaluation, plotting, and qualitative-study runners.
- `data/personas/`: persona datasets and train/test splits.
- `results/`: generated checkpoints, metrics, figures, and case-study outputs.
- `paper/cog2026_vision/`: LaTeX manuscript source.

## License

Source code and scripts are released under the MIT License. See `LICENSE`.

The manuscript text, paper figures, and generated result artifacts are provided
for research transparency and citation.
