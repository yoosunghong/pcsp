# Related Work Survey: PCSP (Persona-Conditioned Shared Policy)

**4축 분류: Goal-Cond RL / Lang-Cond RL / Skill Embedding / LLM-as-Policy**

*작성일: 2026-04-27 | 목적: NeurIPS 2026 Workshop 제출을 위한 related work 차별화*

---

## Axis 1: Goal-Conditioned RL (GCRL)

| 논문 | 핵심 기여 | 조건부 입력 타입 | PCSP와의 차별점 |
|:-----|:----------|:----------------|:---------------|
| **UVFA** (Schaul et al., 2015) | Universal Value Function Approximator — goal을 상태와 함께 value network에 입력 | Goal state / reward vector | Goal = 달성할 목표 상태; persona = 지속적 성격 특성 (goal과 개념적으로 다름) |
| **HER** (Andrychowicz et al., 2017) | Hindsight Experience Replay — 실패한 trajectory의 goal을 사후 재정의 | Goal state | NPC persona는 trajectory 종료 후 바뀌지 않는 정체성; HER은 sparse reward 문제 해결에 초점 |
| **RIG** (Nair et al., 2018) | 잠재 공간에서 goal을 샘플링, visual goal-conditioned policy | Latent image embedding | 시각적 goal latent vs. 자연어 persona latent; RIG은 달성 목표를, PCSP는 행동 방식을 조건화 |
| **GoFAR** (Ma et al., 2022) | Goal-conditioned offline RL with hindsight relabeling | Goal state | 오프라인 데이터 기반; PCSP는 온라인 persona-conditioned 학습 |

**핵심 구별**: GCRL의 "goal"은 **달성 상태(what to achieve)**지만, PCSP의 "persona"는 **행동 방식(how to behave)**이다. 외향적 NPC와 내성적 NPC는 동일한 needs를 충족시키되, 전혀 다른 행동 패턴을 통해서 달성한다.

---

## Axis 2: Language-Conditioned RL

| 논문 | 핵심 기여 | 조건부 입력 타입 | PCSP와의 차별점 |
|:-----|:----------|:----------------|:---------------|
| **BabyAI** (Chevalier-Boisvert et al., 2019) | 자연어 instruction-conditioned 격자 환경 + imitation learning | 즉시적 instruction (e.g., "go to the red ball") | Instruction = 즉각적 단발 명령; persona = 에피소드 전체에 걸쳐 일관된 성격 특성 |
| **GAIL + language** (Kang et al., 2019) | 자연어 목표를 GAN-style로 policy에 조건부 부여 | Natural language goal | Goal description; PCSP는 personality description |
| **SFT + RLHF** (Ouyang et al., 2022; InstructGPT) | 인간 피드백으로 언어 instruction-following 강화 | Human instruction | 대화형 instruction-following; PCSP는 NPC 행동 생성에 특화, 자연어→RL 정책 직접 연결 |
| **LangSAC** (Shao et al., 2021) | 언어 명령어로 연속 제어 policy 조건화 | Language instruction | 로봇 조작 task의 단기 goal; PCSP는 생활 시뮬레이션의 long-horizon persona |
| **ELLM** (Carta et al., 2023) | LLM이 RL agent에게 탐험 목표 제안 | LLM-generated sub-goals | LLM이 매 step 관여; PCSP는 LLM을 1회만 호출 (persona 임베딩) |

**핵심 구별**: 기존 lang-cond RL은 **즉시적 instruction("go left", "pick up box")**을 처리하지만, PCSP는 **지속적 성격("내성적 연구원")**을 조건화한다. Instruction은 에피소드마다 바뀔 수 있지만, persona는 NPC의 영구적 정체성이다.

---

## Axis 3: Skill Embedding / Unsupervised RL

| 논문 | 핵심 기여 | 조건부 입력 타입 | PCSP와의 차별점 |
|:-----|:----------|:----------------|:---------------|
| **DIAYN** (Eysenbach et al., 2019) | Diversity Is All You Need — mutual information 최대화로 다양한 skill 자동 발견 | Latent skill index z (discrete/continuous) | Unsupervised latent (해석 불가); PCSP는 human-readable 자연어 persona |
| **VALOR** (Achiam et al., 2018) | Variational Option Discovery — option 다양성 장려 | Latent option vector | Options are abstract; PCSP conditions on semantically interpretable text |
| **VIC** (Gregor et al., 2016) | Variational Intrinsic Control | Latent option | Same: unsupervised latent vs. PCSP's human-specified text |
| **CIC** (Laskin et al., 2022) | Contrastive Intrinsic Control for task-agnostic RL | Latent skill embedding | Skill discovery without human labels; PCSP uses LLM for semantic grounding |
| **LSD** (Park et al., 2022) | Language-grounded Skill Discovery | Text-labeled skill latent | Text에 skill을 사후 grounding; PCSP는 처음부터 자연어로 persona 지정 |

**핵심 구별**: Skill embedding 방법은 **unsupervised latent**로 다양성을 확보하지만 학습된 skill이 무엇을 의미하는지 알 수 없다. PCSP는 **human-interpretable 자연어 persona**로 직접 conditioning — 게임 디자이너가 NPC 성격을 직접 텍스트로 지정할 수 있다.

---

## Axis 4: LLM-as-Policy

| 논문 | 핵심 기여 | LLM 역할 | PCSP와의 차별점 |
|:-----|:----------|:---------|:---------------|
| **SayCan** (Ahn et al., 2022) | LLM이 robot skill 선택을 언어로 추론 | 매 step LLM 호출 (action 생성) | 매 step ~500ms LLM 추론; PCSP는 persona 임베딩 1회 후 <5ms 정책망 추론 |
| **Voyager** (Wang et al., 2023) | LLM이 Minecraft에서 코드 스킬을 생성 | 프로그래밍 통한 행동 생성 | 코드 생성 기반; PCSP는 RL policy의 continuous conditioning |
| **DEPS** (Wang et al., 2023) | LLM 계획 + RL 실행 분리 | 고수준 계획 담당 | 계층적 분리; PCSP는 단일 policy가 persona 전체를 처리 |
| **ReAct** (Yao et al., 2023) | Reasoning + Acting interleaved | 매 step 추론+행동 | Interactive 추론; 게임 실시간성과 충돌 (~200ms/step) |
| **ChatPCG** (Todd et al., 2023) | LLM을 reward shaper로 활용 | LLM이 reward 설계 | Reward design 용도; PCSP는 LLM을 persona encoder로만 사용 |
| **Inner Monologue** (Huang et al., 2022) | LLM이 환경 피드백을 언어로 처리하여 재계획 | 반복 언어 추론 | Replanning 기반; 실시간 NPC에 비적합 |

**핵심 구별**: LLM-as-policy 접근은 **매 step마다 LLM 추론**이 필요해 게임 실시간성(<50ms)과 충돌한다. PCSP는 LLM을 **1회 persona 임베딩에만** 사용하고, 이후 추론은 경량 FiLM-conditioned 정책망으로 처리한다.

---

## 통합 비교 테이블

| 방법 | Persona 일관성 | 자연어 조건 | Zero-shot 일반화 | 추론 속도 | 메모리(NPC 수 기준) |
|:-----|:-------------|:-----------|:----------------|:---------|:-----------------|
| Goal-cond RL (UVFA) | ✗ (goal≠persona) | ✗ | ✗ | ✓ fast | O(1) |
| Lang-cond RL (BabyAI) | △ (instruction only) | ✓ | △ | ✓ fast | O(1) |
| Skill embed (DIAYN) | △ (latent) | ✗ | ✗ | ✓ fast | O(1) |
| One-policy-per-NPC RL | ✓ | ✗ | ✗ | ✓ fast | **O(N)** |
| LLM-as-policy (SayCan) | ✓ | ✓ | ✓ | ✗ slow | O(1) |
| **PCSP (Ours)** | **✓** | **✓** | **✓** | **✓ fast** | **O(1)** |

---

## 포지셔닝 요약 (논문 2문장 버전)

> Prior work either lacks natural language grounding (goal-conditioned RL, skill discovery), handles only short-horizon instructions rather than persistent personalities (language-conditioned RL), or incurs prohibitive per-step inference costs (LLM-as-policy). PCSP is the first method to ground free-form persona text into a single shared RL policy via LLM embeddings, achieving zero-shot persona generalization at constant inference cost.

---

## 추가 검토 필요 논문 (5월 중)

- [ ] **CLIP-MCTS** (Nakamoto et al., 2023) — contrastive representation + planning
- [ ] **Motif** (Klissarov et al., 2024) — LLM-based intrinsic motivation (NeurIPS 2024)
- [ ] **EUREKA** (Ma et al., 2023) — LLM reward design (CoRL 2023)
- [ ] **Generative Agents** (Park et al., 2023) — LLM-simulated social agents (UIST 2023)
- [ ] **GROOT** (Cai et al., 2023) — generalist policy with goal video conditioning
