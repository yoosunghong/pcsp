# CLAUDE.md - co-spec Project Context

## Project Overview

This is a **PCSP (Persona-Conditioned Shared Policy)** research project.
The goal is to train a single shared RL policy conditioned on natural-language persona text, enabling thousands of NPCs to behave according to distinct personalities.
The current primary paper direction is the IEEE CoG 2026 Vision Paper in `paper/cog2026_vision/main.tex`.

**Active execution plan:** `PLAN.md`

Older proposal documents such as `persona-proposal.md` and `full-proposal.md` are reference material only; they are not the active direction. Stale plans and proposals should be preserved under `archive/`.

---

## Working Rules

All agents and automation should work from the root `PLAN.md`.

1. **Before starting work**
   - Read `PLAN.md` first and check the current active paper direction, immediate problem, and active checklist.
   - Treat `paper/cog2026_vision/main.tex` as the source of truth for paper framing.
   - Do not mistake the speculative sLM/RL co-adaptation direction in `full-proposal.md` for the current PCSP paper direction.

2. **During work**
   - Connect every new code, experiment, or documentation change to one of the checklist items in `PLAN.md`.
   - Any change that breaks compatibility with existing v1/v2 results, such as action space, observation dimension, or model head changes, must record the retraining requirement in `PLAN.md`.
   - Do not delete existing documents. If a document's direction has changed, preserve it under `archive/YYYY-MM-DD` or `archive/docs_YYYY-MM-DD`.

3. **After finishing work**
   - If you completed non-trivial work, update `PLAN.md` in the same turn.
   - Mark completed items with `[x]`, and add newly discovered TODOs to the appropriate phase.
   - Record important decisions, result file paths, failed experiments, and retraining requirements in the Decision Log or the relevant phase of `PLAN.md`.

4. **Current priorities**
   - Strengthen persona-conditioned behavior that is observable to humans.
   - Expand human evaluation from coarse action labels to rich trajectory traces.
   - In the short term, keep the existing 12-action policy and enrich rollout/event rendering.
   - In the medium term, design the Mini-Inzoi v3 action ontology and environment redesign.

---

## Development Environment

```bash
# Always use the paper conda environment
conda activate paper

# Or, for one-off commands
conda run -n paper python <script>
```

| Item | Value |
|:-----|:------|
| Python | 3.10 (paper env) |
| PyTorch | 2.5.1 + CUDA 12.8 |
| GPU | NVIDIA RTX 6000 Ada (49GB VRAM) |
| PettingZoo | 1.24.1 |
| Transformers | 5.6.2 |
| PEFT | 0.19.1 |
| NumPy | 1.24.3 |

---

## Directory Structure

```
co-spec/
├── CLAUDE.md                        ← this file
├── AGENTS.md                        ← shared agent instructions
├── PLAN.md                          ← active research execution plan; update before/after work
├── paper/cog2026_vision/main.tex    ← current primary paper
├── archive/                         ← archived plans and proposals
├── persona-proposal.md              ← older proposal / reference
├── full-proposal.md                 ← separate co-adaptation proposal / reference
│
├── src/
│   ├── env/
│   │   ├── mini_inzoi.py            ← PettingZoo AEC environment v1 (6×6, 4 agents, 8 needs, 12 actions)
│   │   ├── mini_inzoi_v2.py         ← scale-up environment v2 (12×12, 16 agents)
│   │   └── action_semantics.py      ← separates action IDs from human-readable event semantics
│   ├── models/
│   │   └── film.py                  ← FiLM conditioning: PersonaProjection, Policy, Value
│   ├── data/
│   │   └── persona_generator.py     ← defines the 30-persona dataset (Big Five × occupation)
│   ├── training/                    ← PPO/PCSP training loops and baselines
│   └── eval/                        ← consistency/diversity/zeroshot/human-eval metrics
│
├── scripts/
│   ├── smoke_test_qwen3_embed.py    ← Qwen3-Embedding speed benchmark
│   ├── visualize_persona_tsne.py    ← t-SNE visualization for 30 personas
│   ├── test_env.py                  ← Mini-Inzoi PettingZoo API test
│   └── test_film.py                 ← FiLM module sanity check
│
├── data/
│   └── personas/
│       ├── personas_300.json        ← v1 persona set
│       ├── train_240.json           ← v1 train split
│       ├── test_60.json             ← v1 zero-shot split
│       ├── train_400.json           ← v2 train split
│       └── test_100.json            ← v2 zero-shot split
│
├── results/
│   ├── smoke_test_result.json       ← embedding speed benchmark result
│   ├── embeddings/
│   │   └── persona_embeddings_30.npy ← Qwen3-Embed embedding vectors (30, 1024)
│   └── figures/
│       ├── persona_tsne.png         ← t-SNE visualization
│       └── persona_sim_matrix.npy   ← cosine similarity matrix
│
└── notebooks/
    └── related_work_survey.md       ← four-axis related work comparison table
```

---

## Core Module Usage

### Environment (`src/env/mini_inzoi.py`)

```python
from src.env.mini_inzoi import MiniInzoiEnv, PersonaConfig, DEFAULT_PERSONAS

env = MiniInzoiEnv(personas=DEFAULT_PERSONAS, max_steps=200)
env.reset(seed=42)

for agent in env.agent_iter():
    obs, rew, term, trunc, info = env.last()
    if term or trunc:
        env.step(None)
    else:
        action = env.action_space(agent).sample()
        env.step(action)
```

- Observation dimension: `(20,)` - position (2) + time (1) + needs (8) + other agents (9)
- Action space: `Discrete(12)` - 8 activities + 4 movement directions
- Each persona has different need-decay rates and preferred actions with a `+0.5` bonus.

### FiLM Policy (`src/models/film.py`)

```python
from src.models.film import PersonaConditionedPolicy, PersonaConditionedValue

policy = PersonaConditionedPolicy(obs_dim=20, n_actions=12, persona_dim=64, llm_dim=1024)
value  = PersonaConditionedValue(obs_dim=20, persona_dim=64, llm_dim=1024)

# e_llm: Qwen3-Embed output, precomputed and frozen
logits = policy(obs, e_llm)       # (B, 12)
v      = value(obs, e_llm)        # (B,)
action, log_prob = policy.act(obs, e_llm)
```

- `PersonaProjection`: LLM embedding (1024) -> trainable persona embedding (64), LoRA rank 16
- `FiLMLayer`: conditions each hidden layer with `gamma(e_p) * h + beta(e_p)`
- Total parameters: approximately 207K

### Persona Embeddings (Qwen3-Embedding-0.6B)

```python
from transformers import AutoTokenizer, AutoModel
import torch

tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen3-Embedding-0.6B", trust_remote_code=True)
model = AutoModel.from_pretrained("Qwen/Qwen3-Embedding-0.6B", dtype=torch.float16).cuda()
model.eval()

# Encode the persona once when the NPC is created: 14.6 ms each, 43.9 ms for batch size 100
enc = tokenizer([persona_text], return_tensors="pt", truncation=True, max_length=128).to("cuda")
with torch.no_grad():
    out = model(**enc)

# Last-token pooling + L2 normalization
e_llm = out.last_hidden_state[:, -1]
e_llm = torch.nn.functional.normalize(e_llm, dim=-1)  # (1, 1024)
```

---

## Common Commands

```bash
# Environment test
conda run -n paper python scripts/test_env.py

# FiLM module test
conda run -n paper python scripts/test_film.py

# Re-run embedding speed benchmark
conda run -n paper python scripts/smoke_test_qwen3_embed.py

# Regenerate t-SNE visualization
conda run -n paper python scripts/visualize_persona_tsne.py
```

---

## Key Design Decisions and Rationale

| Decision | Rationale |
|:---------|:----------|
| Frozen LLM encoder (Qwen3-0.6B-Embed) | Called only once at inference, uses 1.1 GB VRAM, supports multilingual text |
| FiLM conditioning (vs. concat) | Injects persona information into every hidden layer and helps prevent mode collapse |
| LoRA projection (rank 16) | The LLM embedding space captures occupation more strongly than personality, so fine-tuning is needed |
| PettingZoo AEC (vs. parallel env) | Sequential action simulation is closer to turn-based NPC structures in real games |
| Contrastive consistency loss | Persona should be recoverable from trajectories to prevent mode collapse |

---

## Known Issues and Cautions

- **Occupation vs. personality embeddings:** Qwen3-Embed captures occupational similarity more strongly than personality traits, e.g. salesperson-executive: 0.61 vs. trainer-blogger: 0.33. The LoRA projection should learn to amplify personality axes.
- **PettingZoo AEC pattern:** At the start of `step()`, `_cumulative_rewards[agent] = 0` must come before `_clear_rewards()`. Changing the order breaks the API test.
- **`sys.path`:** Scripts under `scripts/` need `sys.path.insert(0, "/home/swim/Documents/Projects/co-spec")`.
- **Korean fonts:** When using matplotlib, manually register `NanumGothic` or `NotoSansCJK`; see `visualize_persona_tsne.py`.
