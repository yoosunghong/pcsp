# AGENTS.md — co-spec 프로젝트 컨텍스트

## 프로젝트 개요

**PCSP (Persona-Conditioned Shared Policy)** 연구 프로젝트.
자연어 persona 텍스트를 조건으로 받는 단일 공유 RL policy를 학습해, 수천 명의 NPC가 각자 다른 성격으로 행동하는 시스템 구현.
NeurIPS 2026 Workshop 제출 목표 (마감: 2026-08-29).

제안서: `persona-proposal.md` (주 연구), `full-proposal.md` (co-adaptation 연구 참고)

---

## 개발 환경

```bash
# 항상 paper conda 환경 사용
conda activate paper
# 또는 명령 단위 실행 시
conda run -n paper python <script>
```

| 항목 | 값 |
|:-----|:---|
| Python | 3.10 (paper env) |
| PyTorch | 2.5.1 + CUDA 12.8 |
| GPU | NVIDIA RTX 6000 Ada (49GB VRAM) |
| PettingZoo | 1.24.1 |
| Transformers | 5.6.2 |
| PEFT | 0.19.1 |
| NumPy | 1.24.3 |

---

## 디렉토리 구조

```
co-spec/
├── AGENTS.md                        ← 이 파일
├── PLAN.md                          ← 연구 실행 계획 (단계별 TODO)
├── persona-proposal.md              ← 주 연구 제안서
├── full-proposal.md                 ← co-adaptation 연구 제안서 (참고)
│
├── src/
│   ├── env/
│   │   └── mini_inzoi.py            ← PettingZoo AEC 환경 (6×6, 4 agents, 8 needs, 10 actions)
│   ├── models/
│   │   └── film.py                  ← FiLM conditioning: PersonaProjection, Policy, Value
│   ├── data/
│   │   └── persona_generator.py     ← 30개 persona 데이터셋 정의 (Big Five × 직업)
│   ├── training/                    ← PPO 학습 루프 (미구현, 6월 예정)
│   └── eval/                        ← 평가 지표 (미구현, 7월 예정)
│
├── scripts/
│   ├── smoke_test_qwen3_embed.py    ← Qwen3-Embedding 속도 벤치마크
│   ├── visualize_persona_tsne.py    ← 30개 persona t-SNE 시각화
│   ├── test_env.py                  ← Mini-Inzoi PettingZoo API 테스트
│   └── test_film.py                 ← FiLM 모듈 sanity check
│
├── data/
│   └── personas/
│       ├── personas_30.json         ← 전체 30개 (seed dataset)
│       ├── train.json               ← 24개 학습용
│       └── test.json                ← 6개 zero-shot 평가용
│
├── results/
│   ├── smoke_test_result.json       ← 임베딩 속도 벤치마크 결과
│   ├── embeddings/
│   │   └── persona_embeddings_30.npy ← Qwen3-Embed 임베딩 벡터 (30, 1024)
│   └── figures/
│       ├── persona_tsne.png         ← t-SNE 시각화
│       └── persona_sim_matrix.npy   ← 코사인 유사도 행렬
│
└── notebooks/
    └── related_work_survey.md       ← 4축 related work 비교 테이블
```

---

## 핵심 모듈 사용법

### 환경 (`src/env/mini_inzoi.py`)

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

- 관측 차원: `(20,)` — 위치(2) + 시간(1) + needs(8) + 타 에이전트(9)
- 행동 공간: `Discrete(10)`
- Persona별 needs decay 속도와 선호 행동(+0.5 보너스)이 다름

### FiLM 정책 (`src/models/film.py`)

```python
from src.models.film import PersonaConditionedPolicy, PersonaConditionedValue

policy = PersonaConditionedPolicy(obs_dim=20, n_actions=10, persona_dim=64, llm_dim=1024)
value  = PersonaConditionedValue(obs_dim=20, persona_dim=64, llm_dim=1024)

# e_llm: Qwen3-Embed 출력 (사전 계산, frozen)
logits = policy(obs, e_llm)       # (B, 10)
v      = value(obs, e_llm)        # (B,)
action, log_prob = policy.act(obs, e_llm)
```

- `PersonaProjection`: LLM 임베딩(1024) → 학습 가능한 persona embedding(64), LoRA rank-16
- `FiLMLayer`: `γ(e_p) ⊙ h + β(e_p)` 로 매 hidden layer 조건화
- 총 파라미터: ~207K

### Persona 임베딩 (Qwen3-Embedding-0.6B)

```python
from transformers import AutoTokenizer, AutoModel
import torch

tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen3-Embedding-0.6B", trust_remote_code=True)
model = AutoModel.from_pretrained("Qwen/Qwen3-Embedding-0.6B", dtype=torch.float16).cuda()
model.eval()

# Persona는 NPC 생성 시 1회만 인코딩 (14.6ms/ea, 배치 100 기준 43.9ms)
enc = tokenizer([persona_text], return_tensors="pt", truncation=True, max_length=128).to("cuda")
with torch.no_grad():
    out = model(**enc)
# last-token pooling + L2 normalize
e_llm = out.last_hidden_state[:, -1]
e_llm = torch.nn.functional.normalize(e_llm, dim=-1)  # (1, 1024)
```

---

## 자주 쓰는 명령

```bash
# 환경 테스트
conda run -n paper python scripts/test_env.py

# FiLM 모듈 테스트
conda run -n paper python scripts/test_film.py

# 임베딩 속도 벤치마크 (재실행)
conda run -n paper python scripts/smoke_test_qwen3_embed.py

# t-SNE 시각화 재생성
conda run -n paper python scripts/visualize_persona_tsne.py
```

---

## 핵심 설계 결정 및 근거

| 결정 | 이유 |
|:-----|:-----|
| Frozen LLM encoder (Qwen3-0.6B-Embed) | 추론 시 1회만 호출, 1.1GB VRAM, 다국어 지원 |
| FiLM conditioning (vs. concat) | 모든 hidden layer에 persona 정보 전달, mode collapse 방지 |
| LoRA projection (rank-16) | LLM 임베딩 공간이 성격보다 직업을 더 강하게 포착 → fine-tuning 필요 |
| PettingZoo AEC (vs. parallel env) | 순차 행동 시뮬레이션이 실제 게임 NPC 턴제 구조에 더 가까움 |
| Contrastive consistency loss | trajectory로 persona 역추론 가능해야 mode collapse 방지 |

---

## 알려진 이슈 및 주의사항

- **직업 vs. 성격 임베딩**: Qwen3-Embed가 직업 유사도를 성격 특성보다 강하게 포착함 (영업사원↔임원: 0.61 vs 트레이너↔블로거: 0.33). LoRA projection이 성격 축을 증폭하도록 학습해야 함.
- **PettingZoo AEC 패턴**: `step()` 시작 시 `_cumulative_rewards[agent] = 0` 후 `_clear_rewards()` 순서 필수. 순서 바뀌면 API 테스트 실패.
- **sys.path**: `scripts/` 내 스크립트는 `sys.path.insert(0, "/home/swim/Documents/Projects/co-spec")` 필요.
- **한국어 폰트**: matplotlib 사용 시 `NanumGothic` 또는 `NotoSansCJK` 폰트 수동 등록 필요 (`visualize_persona_tsne.py` 참고).
