# Research Proposal: Persona-Conditioned NPC Policy

**"One Policy, Infinite NPCs: LLM-Persona Conditioned RL for Life Simulation Game NPCs"**

*April 2026 — NeurIPS 2026 Workshop Target*

***

## 1. Motivation & Problem Statement

Life simulation 게임(The Sims, Krafton의 *Inzoi* 등)과 오픈월드 RPG는 **수백~수천 명의 NPC가 각각 일관된 개성을 가지고 행동해야 한다**는 본질적 요구를 가진다. 현재 산업/학계의 접근은 모두 한계를 가진다:

- **Hand-crafted Behavior Tree**: 다양성 한계, NPC당 작성 비용 폭증
- **One-policy-per-NPC RL**: 학습 비용이 NPC 수에 비례, 메모리 비현실적
- **단일 stochastic policy + 샘플링**: persona 일관성 없음, "성격"이 trajectory에 걸쳐 유지되지 않음
- **LLM-as-policy** (SayCan, Voyager 계열): persona는 잘 표현되지만 추론 latency가 게임 실시간성과 충돌

본 연구는 이 gap을 다음 질문으로 정의한다:

> *"단일 RL policy가 자연어 persona 텍스트를 조건으로 받아, persona-consistent하면서도 행동적으로 다양한 정책을 zero-shot으로 생성할 수 있는가? 그리고 unseen persona 텍스트에 대해 일반화하는가?"*

***

## 2. 핵심 아이디어: Persona-Conditioned Shared Policy (PCSP)

### 시스템 구조

```
┌──────────────────────────────────────────────────────────┐
│            Persona-Conditioned Shared Policy             │
│                                                          │
│  Persona Text ──► [Frozen LLM Encoder]                   │
│  "내성적이고 책       Qwen3-0.6B-Embed                   │
│   읽기 좋아하는       ↓ persona embedding e_p ∈ ℝ^d      │
│   30대 회사원"        (LoRA-adapted projection)          │
│                       ↓                                  │
│  Game State ──► [Shared Policy Net π_θ(a | s, e_p)]      │
│  (s_t)            MLP/Transformer + FiLM conditioning    │
│                       ↓                                  │
│                   Action a_t                             │
│                       ↓                                  │
│                   Environment                            │
│                       ↓                                  │
│            ┌──────────┴──────────┐                       │
│            ↓                     ↓                       │
│    Game Reward r_t         Persona Consistency           │
│            ↓                     ↓                       │
│       PPO update          Aux. classifier loss           │
└──────────────────────────────────────────────────────────┘
```

### 핵심 인사이트

1. **언어가 persona의 가장 풍부한 표현 공간**: "내성적이지만 가까운 친구에겐 수다스러운 30대"는 수치 벡터로 표현 불가능
2. **단일 policy + persona 조건부 = O(1) 메모리**: NPC 수에 무관한 추론 비용
3. **Zero-shot 일반화**: LLM 임베딩 공간의 매끄러움 덕에 학습에 등장하지 않은 persona 텍스트에도 그럴듯한 행동 생성 가능
4. **FiLM(Feature-wise Linear Modulation)** 으로 조건부 주입: persona 정보가 모든 layer에 영향을 미치도록 보장

### 모델 선택

| 컴포넌트 | 모델 | 이유 |
| :-- | :-- | :-- |
| Persona Encoder | `Qwen3-0.6B-Embed` (frozen) + LoRA projection | 600M로 임베딩 1회 호출 비용 무시 가능, multilingual |
| Shared Policy | 4-layer Transformer (~10M params) + FiLM | 빠른 추론, persona 조건부 주입에 FiLM이 효과적 |
| Critic (PPO) | persona-conditioned value net (별도) | actor-critic 표준 구조 |

***

## 3. 핵심 수식화

### 3.1 Persona-Conditioned Policy

$$
\pi_\theta(a \mid s, e_p), \quad e_p = W_{\text{proj}} \cdot f_{\text{LLM}}(\text{persona text})
$$

여기서 $f_{\text{LLM}}$ 은 frozen LLM encoder, $W_{\text{proj}}$ 는 학습 가능한 projection (LoRA)이다.

### 3.2 Co-Training Objective

세 손실의 가중합으로 학습한다:

$$
\mathcal{L}_{\text{total}} = \mathcal{L}_{\text{PPO}} + \lambda_1 \mathcal{L}_{\text{consistency}} + \lambda_2 \mathcal{L}_{\text{diversity}}
$$

**(a) PPO loss** (표준 RL):

$$
\mathcal{L}_{\text{PPO}} = \mathbb{E}\left[\min\left(r_t(\theta) \hat{A}_t,\ \text{clip}(r_t(\theta), 1-\epsilon, 1+\epsilon)\hat{A}_t\right)\right]
$$

**(b) Persona Consistency loss** — trajectory로부터 persona를 역추론할 수 있어야 함 (mode collapse 방지):

$$
\mathcal{L}_{\text{consistency}} = -\log \frac{\exp(\text{sim}(g_\phi(\tau), e_p)/T)}{\sum_{p' \in \mathcal{P}_{\text{batch}}} \exp(\text{sim}(g_\phi(\tau), e_{p'})/T)}
$$

여기서 $g_\phi$ 는 trajectory encoder, $\text{sim}$ 은 cosine similarity, $T$ 는 temperature. 같은 persona의 trajectory가 그 persona embedding과 가장 가깝도록 contrastive하게 학습.

**(c) Behavioral Diversity loss** — 다른 persona는 다른 행동 분포를 가져야 함:

$$
\mathcal{L}_{\text{diversity}} = -\mathbb{E}_{s, p \neq p'}\left[ D_{\text{KL}}(\pi_\theta(\cdot \mid s, e_p) \,\|\, \pi_\theta(\cdot \mid s, e_{p'})) \right]
$$

### 3.3 핵심 차별화 (vs. 기존 연구)

| 기존 접근 | 본 연구의 차별점 |
| :-- | :-- |
| Goal-conditioned RL (UVFA) | Goal이 아닌 persona, 그리고 condition이 자연어 |
| Language-conditioned RL (BabyAI 계열) | 즉시적 instruction이 아닌 *지속적 성격 특성* |
| Skill embedding (DIAYN) | unsupervised latent이 아닌 *human-interpretable* 자연어 grounding |
| LLM-as-policy (SayCan/Voyager) | LLM은 매 step 호출 안 함 (1회 임베딩 후 빠른 policy net) |

***

## 4. 실험 설계

### Phase 1: 환경 및 Persona 데이터셋 구축 (5월)

**환경**: 자체 제작 *Mini-Inzoi* — 6×6 그리드 사회 시뮬레이션

- **Agents**: 4명 (각 다른 persona)
- **상태**: 위치, 8개 needs(허기·수면·사교·여가·청결·운동·일·학습), 다른 agent 위치/상태, 시간(0-24)
- **행동 공간** (10개 이산):
  - 활동: {일하기, 먹기, 자기, 사교(타 agent와), 운동, 독서, 청소, 휴식}
  - 이동: {위/아래/좌/우}
- **보상**: needs 충족(+) + persona-aligned 행동(+, 별도 reward shaping) + 사회적 상호작용(+/-)

**Persona 데이터셋**: Big Five 성격 5축 × 직업/연령 조합으로 **300개 persona 텍스트** 생성

```python
# 예시
"외향적이고 새로운 경험을 즐기는 25세 마케터, 운동을 좋아함"
"내성적이고 신중한 35세 연구원, 독서와 혼자만의 시간 선호"
"성실하고 가족 중심적인 42세 부모, 정해진 루틴을 중시"
```

- 학습용 240개 / 테스트용 60개 (zero-shot 평가)
- LLM(GPT-4) + 인간 검토로 생성

### Phase 2: Baseline 5종 구현 (6월)

| # | Baseline | 설명 |
| :-- | :-- | :-- |
| 1 | **No-Persona PPO** | persona 무시, 단일 generic policy |
| 2 | **One-Policy-per-Persona** | persona마다 독립 학습 (oracle, 비현실적이지만 상한선) |
| 3 | **Sentence-BERT + frozen embed** | LLM 대신 SBERT로 persona 인코딩, projection만 학습 |
| 4 | **Random latent skill (DIAYN)** | unsupervised skill embedding |
| 5 | **LLM-as-policy (Qwen3-1.7B prompted)** | 매 step LLM에 persona+state 주고 행동 출력 (latency baseline) |

### Phase 3: PCSP 구현 + Ablation (7월)

```python
# 핵심 학습 루프
for episode in range(N):
    persona = sample_persona()                    # 학습 풀에서 1개
    e_p = llm_encoder(persona).detach()           # frozen LLM, 1회
    e_p = persona_proj(e_p)                       # LoRA projection (학습)

    obs = env.reset(); done = False
    trajectory = []
    while not done:
        action = policy(obs, e_p)                 # FiLM conditioning
        obs_next, reward, done = env.step(action)
        trajectory.append((obs, action, reward))
        obs = obs_next

    # PPO update on trajectory
    ppo_update(policy, value_net, trajectory)

    # Consistency: trajectory ↔ persona contrastive
    L_cons = contrastive_loss(traj_encoder(trajectory), e_p, batch_personas)

    # Diversity: KL divergence across personas at sampled states
    L_div = -kl_divergence_across_personas(policy, sampled_states)

    backward(L_cons + L_div)
```

### 4.1 평가 지표

| 카테고리 | 지표 | 목적 |
| :-- | :-- | :-- |
| **Persona 일관성** | Persona classification accuracy from trajectory | 학습된 trajectory encoder가 persona를 맞히는지 |
| **행동 다양성** | Behavioral KL between personas (avg pairwise) | 서로 다른 persona가 정말 다른 행동을 하는지 |
| **Task 성능** | Episode reward (needs 충족도) | 게임으로서 성립하는지 |
| **샘플 효율** | Reward per env step (vs. one-policy-per-persona) | 단일 모델이 oracle 대비 얼마나 효율적인지 |
| **Zero-shot 일반화** | 60개 unseen persona의 일관성/다양성 | LLM 임베딩 일반화가 정말 작동하는지 (★ 핵심 결과) |
| **추론 latency** | ms/step (persona 1회 인코딩 후) | 실시간 게임 적합성 |
| **Human eval** | "두 NPC가 다른 사람처럼 보이는가?" (n=30 평가자) | 정성 평가 |

***

## 5. 기대 결과 & Novelty 요약

### 핵심 기대 결과

1. **Zero-shot persona 일반화 성공**: unseen persona 60개에 대해 학습 persona 대비 90% 이상의 consistency 유지 → LLM 임베딩 공간의 매끄러움이 RL policy에도 전파됨을 입증
2. **One-policy-per-persona 대비 95% 성능 + 단일 모델 메모리**: 즉, 거의 손실 없이 NPC 수와 무관한 시스템 구축 가능
3. **LLM-as-policy 대비 100배 이상 빠른 추론** (<5ms vs ~500ms), 동등한 persona 일관성
4. **Behavioral KL이 persona 거리(임베딩 cosine)와 단조 증가** → "비슷한 persona = 비슷한 행동, 다른 persona = 다른 행동" 정량적 입증

### Novelty 포지셔닝 (워크샵 1문장)

> "We present the first end-to-end framework that grounds free-form natural language persona descriptions into a single shared RL policy via LLM embeddings, enabling zero-shot generation of behaviorally distinct yet persona-consistent NPCs at constant inference cost."

### 산업 임팩트 (Krafton 핏)

- **Inzoi**: 수만 NPC 각각의 persona를 텍스트로만 정의 → 자동 행동 생성. 게임 디자이너 워크플로우 혁신
- **PUBG / 배틀그라운드**: 봇의 "공격적/소극적/협동적" 등 플레이 스타일을 자연어로 제어
- **모바일 환경**: 단일 small policy net이므로 on-device 추론 가능

***

## 6. 제출 전략 및 타임라인

```
2026년
 4월 말 ~ 5월 1주  │ Mini-Inzoi 환경 prototype + Qwen3-Embed smoke test
 5월 2주 ~ 5월 말  │ Persona 데이터셋 300개 생성 + 환경 완성
 6월               │ Baseline 5종 구현 (no-persona PPO, SBERT, DIAYN, LLM-as-policy 등)
 7월 1~3주         │ PCSP 본 구현 + ablation (FiLM vs concat, λ 튜닝)
 7월 4주 ~ 8월 1주 │ Zero-shot 평가 + Human eval (Prolific n=30)
 8월 2~3주         │ 논문 draft (4~6p 워크샵 포맷) + figure 정리
 8월 29일          │ ★ NeurIPS 2026 Workshop 제출
                    (예상 타깃: Generative AI for Games / ALOE / FMDM)
 9월 29일          │ 결과 통보

2027년
 1월 ~ 2월         │ 메인 트랙 확장: 환경 복잡도 증가 (Melting Pot 시나리오 통합)
                    persona 동적 변화(시간에 따른 mood) 추가
 3월               │ ICLR 2027 workshop 또는 AAAI 2027 메인트랙 / CHI 2027 (HCI 측면)
```

### 타깃 워크샵 후보 (우선순위)

1. **NeurIPS Workshop on Generative AI for Games** — 가장 직접적 핏
2. **NeurIPS Workshop on Foundation Models for Decision Making (FMDM)** — LLM+RL 측면
3. **NeurIPS Workshop on Agent Learning in Open-Endedness (ALOE)** — open-ended persona generation 측면

***

## 7. 이번 주 즉시 실행 항목

1. **Smoke test**: `Qwen/Qwen3-0.6B-Embedding` 로드 → persona 텍스트 100개 임베딩 시간 측정 (목표: 배치 100 < 500ms on RTX 3090)
2. **환경 prototype**: PettingZoo 기반 6×6 Mini-Inzoi 1차 구현 (4 agent, 8 needs, 10 actions)
3. **Persona 데이터 30개 시범 생성**: GPT-4로 Big Five × 직업 조합 → 임베딩 분포 t-SNE 시각화로 클러스터링 확인
4. **FiLM conditioning 모듈** PyTorch 구현 (작은 MLP로 sanity check)
5. **Related work 1차 문헌 정리**: goal-conditioned RL / language-conditioned RL / skill embedding / LLM-as-policy 4축으로 survey table 작성

***

## 8. 위험 요소 및 완화 전략

| 위험 | 완화 |
| :-- | :-- |
| Persona가 정책에 영향을 못 미침 (mode collapse to mean policy) | Consistency loss + FiLM (concat 대신) + λ 스케줄링 |
| Diversity loss가 task reward를 해침 | λ_2 작게 시작, curriculum (PPO 우선 → diversity 점진 증가) |
| 6×6 환경이 너무 단순해서 persona가 의미 없음 | needs/사회적 상호작용 충분히 풍부하게 설계, 필요시 환경 확장 |
| Human eval 모집 비용 | Prolific 또는 학내 평가자 활용, n=30로 최소 |
| Zero-shot 일반화 실패 | 학습 persona 다양성을 Big Five 전 영역 커버하도록 균형 샘플링 |

***

## 부록: 환경 설계 상세 (Mini-Inzoi v0.1)

### 상태 표현
```
state = {
    "agent_pos": (x, y),
    "time_of_day": int,  # 0-23
    "needs": {           # 0-100, 시간당 자연 감소
        "hunger": int, "sleep": int, "social": int,
        "leisure": int, "hygiene": int, "fitness": int,
        "work_progress": int, "learning": int
    },
    "other_agents": [(pos, current_action), ...],
    "world_objects": {"bed": pos, "kitchen": pos, "gym": pos, ...}
}
```

### Persona 영향 메커니즘
- **Need 감소율**: 외향적 → social 빠르게 감소, 내성적 → 천천히 감소
- **선호 보상 가중치**: persona-aligned 활동 시 +0.5 보너스
- **사회적 반응**: 같은 persona 유사도가 높은 agent와 상호작용 시 + reward

### 학습 hyperparameter (초안)
- PPO: lr=3e-4, clip=0.2, batch=2048
- LoRA projection: r=16, lr=1e-4
- λ_1 (consistency) = 0.5, λ_2 (diversity) = 0.1
- Trajectory encoder: 2-layer GRU, hidden=128
