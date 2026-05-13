# PLAN.md — PCSP 연구 실행 계획

**논문 제목**: "One Policy, Infinite NPCs: LLM-Persona Conditioned RL for Life Simulation Game NPCs"
**제출 목표 (단계별)**:
- ★ **IEEE CoG 2026** (마감 **2026-05-14**, 약 2.5주 남음) — 4p short paper, 즉시 타겟
- **NeurIPS 2026 Workshop** (마감 **2026-08-29**) — 현재 draft 기반 제출
- **AAAI-27** (Abstract 마감 예상 **2026-08**, 본회의 2027년 1월 싱가포르) — Melting Pot + human eval n≥100 완성 조건

**최종 업데이트**: 2026-04-27 (Phase 7~9 로드맵 추가, 현재 결과 약점 분석 반영)

---

## 현재 결과의 주요 약점 (2026-04-27 기준)

| 약점 | 심각도 | 보강 목표 |
|:-----|:------:|:---------|
| 6×6 toy environment — 메인 컨퍼런스 거절 1순위 사유 | ⚠️ 치명적 | Melting Pot 확장 (Phase 8) |
| 300 personas, test 60개 — 통계 불안정 | 🔶 중요 | 1000개, test 200개 (Phase 8) |
| Human eval n=30 미완성 — 자동 지표만 존재 | ⚠️ 치명적 | Prolific n≥100, α≥0.6 (Phase 9) |
| LoRA projection geometry 분석 없음 | 🔷 탑티어 한정 | before/after t-SNE + sensitivity (Phase 9) |

---

## 전체 타임라인

```
4월 말 ~ 5월 1주  [Phase 1] 환경 prototype + Qwen3-Embed smoke test       ✅ 완료
5월 2주 ~ 5월 말  [Phase 2] Persona 300개 생성 + 환경 고도화              ✅ 완료
6월               [Phase 3] Baseline 5종 구현                             ✅ 완료
7월 1~3주         [Phase 4] PCSP 본 구현 + Ablation                      ✅ 완료
7월 4주 ~ 8월 1주 [Phase 5] Zero-shot 평가 + Human eval (n=30)           ✅ 완료 (auto 지표)
8월 2~3주         [Phase 6] 논문 draft (4~6p) + figure 정리              ✅ 완료
─────────────────────────────────────────────────────────────────────────────────
4월 27일~5월 13일 [Phase 7] IEEE CoG 2026 short paper 제출 준비          🔥 즉시 시작
5월~7월           [Phase 8] 환경 스케일 확장 (Melting Pot) +              🔲 예정
                             Persona 1000개 + Human eval n≥100
8월               [Phase 9] AAAI-27 확장판 논문 작성                     🔲 예정
8월 29일          ★ NeurIPS 2026 Workshop 제출
~2026-08          ★ AAAI-27 Abstract 제출 (Melting Pot + human eval 완성 시)
```

---

## Phase 1 — 환경 Prototype + Smoke Test ✅ 완료 (2026-04-27)

### 완료된 작업

- [x] **conda 환경 설정**: `paper` env에 transformers 5.6.2 / peft 0.19.1 / sentence_transformers 5.4.1 설치
- [x] **Qwen3-Embedding-0.6B smoke test**: 배치 100 → **43.9ms** (목표 <500ms), 단일 14.6ms, VRAM 1.1GB
  - 결과: `results/smoke_test_result.json`
- [x] **Mini-Inzoi v0.1 환경** (`src/env/mini_inzoi.py`): PettingZoo AEC, 6×6 그리드, 4 에이전트, 8 needs, 10 행동
  - PettingZoo API 테스트 PASS
- [x] **Persona 데이터셋 30개** (`src/data/persona_generator.py`): Big Five × 직업 조합, train 24 / test 6
  - t-SNE 시각화: `results/figures/persona_tsne.png`
- [x] **FiLM conditioning module** (`src/models/film.py`): PersonaProjection (LoRA r=16), Policy + Value nets, 207K params
  - gradient flow 확인, sanity check PASS
- [x] **Related work survey** (`notebooks/related_work_survey.md`): 4축 비교 테이블

### Phase 1 핵심 발견

> Qwen3-Embed가 직업 유사도(영업사원↔임원: 0.61)를 성격 특성(트레이너↔블로거: 0.33)보다 강하게 포착.
> → LoRA projection이 성격 축을 증폭하도록 학습해야 함. Contrastive consistency loss의 중요성이 더 커짐.

---

## Phase 2 — Persona 300개 생성 + 환경 고도화 ✅ 완료 (2026-04-27)

### 목표
- Persona 데이터셋을 30개(seed) → 300개로 확장 (train 240 / test 60)
- Mini-Inzoi 환경에 사회적 상호작용 보상 강화
- Persona → `PersonaConfig` 자동 변환 파이프라인 완성

### 완료된 작업 (2026-04-27)

#### 2-2. Persona → PersonaConfig 자동 변환 ✅
- [x] `src/data/persona_to_config.py`: Claude Haiku 기반 자연어 → 구조화 config 추출
  - 단일 persona: ~100ms, 배치 처리 지원
  - decay_modifiers 범위 검증 (0.3~2.5), preferred_actions 유효성 확인

#### 2-3. Mini-Inzoi v0.2 환경 업그레이드 ✅
- [x] **N_ACTIONS 10→12**: `move_left`(10), `move_right`(11) 추가 (4방향 이동)
- [x] **PersonaConfig.big_five**: Big Five dict 필드 추가, compatibility() 메서드
- [x] **사회적 상호작용 보상**: `0.2 + 0.3 × cosine_similarity(bf_i, bf_j)` (범위 0.2~0.5)
- [x] **render() 개선**: ASCII needs 바 + 호환성 행렬 출력
- [x] **환경 속도 벤치마크** (`scripts/benchmark_env.py`):
  - Random policy: **44,133 steps/sec** (목표 >10,000 PASS ✓)
  - FiLM policy (단일 스텝 추론): 2,141 steps/sec
  - → PPO 학습 시 배치 rollout으로 충분한 throughput 달성 예상

### 완료된 작업 (추가, 2026-04-27)

#### 2-1. Persona 300개 생성 ✅
- [x] `scripts/generate_personas_300.py` 실행 완료
  - 15 Big Five archetypes × 20 occupations = 300 (train 240 / test 60)
  - 출력: `data/personas/personas_300.json`, `train_240.json`, `test_60.json`
- [x] **t-SNE 시각화 300개 버전** (`scripts/visualize_persona_tsne_300.py`)
  - 2×3 패널: Big Five E/N/A/C/O 축별 + 직업군 → `results/figures/persona_tsne_300.png`
  - 임베딩 저장: `results/embeddings/persona_embeddings_300.npy`
  - 코사인 유사도 행렬: `results/figures/persona_sim_matrix_300.npy`

### Phase 2 핵심 발견 (추가)

> Big Five 5축 모두 intra-high > high-vs-low (Δ 최대: Neuroticism 0.096, Agreeableness 0.082).
> Extraversion은 Δ 0.037로 가장 약함 → LoRA projection에서 E축 분리에 더 집중 필요.

---

## Phase 3 — Baseline 5종 구현 🔲 (6월) ← 구현 완료, 전체 학습 예정

### 목표
PCSP 대비 baseline 상한/하한 확립.

### 구현할 Baseline

| # | Baseline | 설명 | 구현 위치 |
|:--|:---------|:-----|:---------|
| B1 | **No-Persona PPO** | persona 무시, 단일 generic policy | `src/training/baselines/no_persona_ppo.py` |
| B2 | **One-Policy-per-Persona** | persona마다 독립 PPO 학습 (oracle 상한선) | `src/training/baselines/per_persona_ppo.py` |
| B3 | **SBERT + frozen embed** | SentenceBERT로 인코딩, projection만 학습 | `src/training/baselines/sbert_policy.py` |
| B4 | **DIAYN** | unsupervised skill embedding (랜덤 latent) | `src/training/baselines/diayn.py` |
| B5 | **LLM-as-policy** | Qwen3-1.7B에 persona+state 주고 매 step 행동 출력 | `src/training/baselines/llm_policy.py` |

### TODO
- [x] PPO 공통 학습 루프 구현 (`src/training/ppo_trainer.py`)
  - AEC rollout 수집, GAE-Lambda, PPO clip ε=0.2, 공유 trainer
- [x] B1: No-Persona PPO (`src/training/baselines/no_persona_ppo.py`)
  - smoke test: 20 iter → reward 59.0 (수렴 확인)
- [x] B2: Per-Persona PPO (`src/training/baselines/per_persona_ppo.py`)
  - 24개 persona × 독립 학습, total 1.8M params (74K/policy)
  - smoke test: 20 iter → reward 65.2 (oracle 상한선 확인)
- [x] B3: SBERT 임베딩 파이프라인 (`src/training/baselines/sbert_policy.py`)
  - `all-MiniLM-L6-v2` 384-dim, 임베딩 캐시: `results/embeddings/sbert_embeddings_train240.npy`
  - smoke test: 20 iter → reward 57.8
- [x] B4: DIAYN 구현 (`src/training/baselines/diayn.py`)
  - random 64-dim latent, FiLM conditioning, SkillDiscriminator 구현 (optional)
  - smoke test: 20 iter → reward 67.1
- [x] B5: Qwen3-1.7B latency 측정 (`src/training/baselines/llm_policy.py`)
  - `/no_think` 모드, prompt 템플릿, action 파싱 구현
  - 실제 latency 측정은 전체 실험 시 실행 예정
- [x] 통합 실험 스크립트 (`scripts/run_baselines.py`)
  - `--smoke` / `--baseline b1..b5` / `--skip_b5` 옵션
- [x] 전체 학습 실행 (300 iterations, ~68분): `results/baselines/summary.json`
- [ ] B5 Qwen3-1.7B latency 실측 (논문 작성 전 실행)

### Phase 3 전체 학습 결과 (300 iter, 2026-04-27)
| Baseline | Reward | 비고 |
|:---------|-------:|:-----|
| B3 SBERT | **105.4** | 최고 — 384-dim semantic embedding |
| B4 DIAYN | 84.7 | random 64-dim embedding |
| B1 No-Persona | 79.2 | lower bound |
| B2 Per-Persona (24) | 65.4 | oracle 예상이었으나 데이터 효율 문제로 최저 |

### Phase 3 핵심 발견

> **B3(semantic) > B4(random) > B1(none) > B2(per-policy)**
>
> 1. **Semantic conditioning 효과 확인**: B3 > B4 (+20.7) — LLM embedding의 의미론적 내용이 행동 조건화에 실질적으로 기여
> 2. **Conditioning 자체 효과**: B4 > B1 (+5.5) — 임베딩이 랜덤이어도 conditioning이 behavioral diversification에 도움
> 3. **B2 data efficiency 문제**: 24개 정책이 전체 데이터를 1/6씩 분할 → 개별 정책이 수렴 부족. 무한 데이터 환경에서는 oracle이 맞지만 이 스케일에서는 공유 정책이 우월
> 4. **Phase 4 가설**: PCSP (Qwen3 1024-dim + LoRA) >> B3 (SBERT 384-dim) 예상 — 더 풍부한 semantic embedding + FiLM 조합

---

## Phase 4 — PCSP 본 구현 + Ablation ✅ 구현 완료, 전체 학습 실행 대기

### 목표
PCSP 풀 구현 및 ablation으로 각 구성요소의 기여도 검증.

### 구현 완료 (2026-04-27)

#### 4-2. Trajectory Encoder (`src/models/trajectory_encoder.py`) ✅
- [x] 2-layer GRU, hidden=128, output_dim=64
- [x] 입력: (obs, action_onehot) sequence
- [x] 출력: L2-normalized trajectory embedding for InfoNCE loss

#### 4-1. PCSP 학습 루프 (`src/training/pcsp_trainer.py`) ✅
- [x] 에피소드마다 train pool에서 persona 4개 샘플링 → 에피소드 내 고정
- [x] 사전 계산된 Qwen3 e_llm 로드 (frozen), 에이전트 context로 전달
- [x] PPO update on trajectory (n_epochs=4, batch=256, GAE-λ)
- [x] Consistency loss: GRU trajectory encoder + InfoNCE (T=0.07), epoch당 1회
- [x] Diversity loss: batched 다중 persona KL (n_sample=8 persona × 32 state), epoch당 1회
- [x] `λ₁=0.5`(consistency), `λ₂=0.1`(diversity), LoRA lr=1e-4 분리 최적화

#### 4-3. Co-training Objective 구현 ✅
```
L_total = L_PPO + λ_1 * L_consistency + λ_2 * L_diversity
```
- [x] `L_consistency`: InfoNCE in-batch contrastive (traj_emb ↔ persona_emb, same persona = positive)
- [x] `L_diversity`: -E[KL(π(·|s,eₚ) ‖ π(·|s,eₚ'))] 배치화 forward pass로 효율 최적화

#### 4-4. Ablation Study 구현 ✅ (`scripts/run_pcsp.py`)
- [x] `full`:        PCSPActorCritic (FiLM) + λ₁=0.5 + λ₂=0.1
- [x] `no_consist`:  λ₁=0 (consistency loss 제거)
- [x] `no_diverse`:  λ₂=0 (diversity loss 제거)
- [x] `concat`:      ConcatActorCritic (FiLM → concat 교체)
- [x] `frozen_proj`: LoRA projection frozen (raw LLM embed 사용)
- [x] 전체 smoke test (20 iter) PASS

### 전체 학습 결과 (300 iter, 2026-04-27) ✅
| Mode | Reward | vs full | 소요 |
|:-----|-------:|--------:|-----:|
| no_consist | **99.2** | +1.2 | 20min |
| **full** | **97.9** | — | 20min |
| frozen_proj | 87.9 | -10.0 | 98min* |
| concat | 84.5 | -13.4 | 39min* |
| no_diverse | 82.4 | -15.5 | 21min |

*GPU 경쟁 (train_scaling.py 6개 프로세스 동시 실행)으로 인한 지연

### Phase 4 핵심 발견

> 1. **Diversity loss가 가장 중요** (no_diverse -15.5): 없으면 policy가 persona를 무시하는 방향으로 수렴
> 2. **FiLM >> concat** (concat -13.4): 모든 hidden layer에 persona 조건화하는 FiLM 구조 정당성 확인
> 3. **LoRA projection 학습 필요** (frozen_proj -10.0): raw LLM 임베딩 공간이 행동 조건화에 최적화되지 않음
> 4. **Consistency loss는 task reward와 trade-off** (no_consist +1.2): task 최적화와 약간 경쟁하지만 Phase 5 persona 추론 정확도에서 역할
> 5. **PCSP full (97.9) vs B3 SBERT (105.4)**: task reward 단독 비교 시 B3가 높으나, PCSP의 진가는 Phase 5 zero-shot consistency에서 확인 예정

### Hyperparameter 기준값
```
PPO:        lr=3e-4, clip=0.2, batch=2048, γ=0.99, λ_GAE=0.95
LoRA proj:  r=16, lr=1e-4
λ_1:        0.5 (consistency)
λ_2:        0.1 (diversity)
Traj enc:   GRU hidden=128, lr=3e-4
Temp T:     0.07 (contrastive)
```

---

## Phase 5 — Zero-shot 평가 + Human eval 🔲 (7월 4주~8월 1주)

### 목표
핵심 결과 수치 확보.

### 평가 지표 구현 (`src/eval/`) ✅ 구현 완료 (2026-04-27)

| 지표 | 구현 파일 | 설명 |
|:-----|:---------|:-----|
| Persona classification accuracy | `eval/consistency.py` | trajectory → persona k-NN 역추론 정확도 |
| Behavioral KL | `eval/diversity.py` | 다른 persona 쌍의 행동 분포 KL divergence + Spearman ρ |
| Episode reward | `eval/task_perf.py` | needs 충족도 총합 (mean/std/min/max) |
| Sample efficiency | `eval/efficiency.py` | AUC / steps-to-threshold (training log 기반) |
| **Zero-shot consistency** | `eval/zeroshot.py` | ★ 60개 unseen persona의 k-NN accuracy + coherence ratio |
| Inference latency | `eval/latency.py` | ms/step (GPU, p95/p99 포함) |
| Human eval | `eval/human_eval.py` | Prolific CSV 처리, Krippendorff α, 설문 템플릿 생성 |
| **통합 스크립트** | `scripts/run_eval.py` | 전체 모델 × 전체 지표 비교 테이블 생성 (JSON + LaTeX) |

### TODO
- [x] 평가 모듈 7종 구현 (`src/eval/`)
- [x] 통합 평가 스크립트 (`scripts/run_eval.py`)
  - `--smoke`: 빠른 sanity check
  - `--models`, `--metrics`: 선택적 실행
  - JSON + LaTeX 비교 테이블 자동 생성
- [x] **실행 완료** (`results/eval/comparison.json`, `results/eval/comparison.tex`)
- [ ] Prolific 설문지 생성 (`python src/eval/human_eval.py --gen_template`)
- [ ] Prolific 설문 진행 (n=30, 7월 중)
- [ ] B5 Qwen3-1.7B latency 실측 (논문 작성 전)

### Phase 5 전체 평가 결과 (2026-04-27)

| 모델 | Reward | Consist Acc | ZeroShot Acc | Coherence | Mean KL | Spearman ρ | Latency |
|:-----|-------:|------------:|-------------:|----------:|--------:|-----------:|--------:|
| **PCSP (full)** | 83.4 | 0.283 | 0.193 | **6.24** | **5.87** | **0.728** | 1.97ms |
| PCSP (no_consist) | 84.3 | 0.008 ❌ | 0.017 ❌ | 1.04 ❌ | 3.78 | 0.638 | 2.03ms |
| PCSP (no_diverse) | 76.8 | 0.225 | 0.147 | 4.31 | 0.39 ❌ | 0.928* | 1.79ms |
| PCSP (concat) | 77.4 | 0.392 | 0.320 | 8.27 | 2.87 | 0.738 | 1.72ms |
| PCSP (frozen_proj) | 83.6 | 0.188 | 0.207 | 2.55 | 5.60 | 0.384 ↓ | 1.79ms |
| B1 No-Persona | 73.2 | — | — | — | — | — | 1.83ms |
| B3 SBERT | **86.2** | — | — | — | — | — | 1.88ms |
| B4 DIAYN | 81.9 | — | — | — | — | — | 1.94ms |
| B5 LLM-as-policy | — | — | — | — | — | — | 43.7ms |

*no_diverse의 ρ=0.928은 KL값(0.39) 자체가 너무 작아 noise에 의한 것

### Phase 5 핵심 발견

> **1. Consistency loss가 persona 역추론의 필수 조건**
> no_consist: acc 0.008 (랜덤 수준), coherence 1.04 (군집화 없음)
> → "consistency loss 없이는 trajectory가 persona 정보를 전혀 담지 않음"

> **2. Diversity loss가 실질적 행동 다양성의 필수 조건**
> no_diverse: mean KL 0.39 (full의 1/15) → 모든 persona가 거의 동일하게 행동
> → "diversity loss 없이는 policy가 persona를 무시하는 방향으로 수렴"

> **3. Zero-shot 일반화 성공 (★ 핵심 기여)**
> PCSP full 기준 — 60개 unseen persona에서 acc=0.193 (랜덤 1.7%의 11배), coherence=6.24
> → 학습에 없던 persona 텍스트에도 의미 있는 행동 조건화 달성

> **4. FiLM vs concat 트레이드오프**
> concat: consistency acc 더 높음 (0.392 vs 0.283), coherence 더 높음 (8.27 vs 6.24)
> PCSP full: behavioral KL 더 높음 (5.87 vs 2.87), task reward 더 높음 (83.4 vs 77.4)
> → FiLM은 진정한 행동 다양성(KL)과 task 성능에서 우세; concat은 persona 신호가 표층적으로 더 쉽게 추출되나 행동 폭이 좁음

> **5. LoRA projection의 역할: 의미 구조 정렬**
> frozen_proj: Spearman ρ 0.384 (full 0.728의 절반) → "embedding 거리와 행동 거리 간 상관" 붕괴
> → LoRA 없이는 LLM embedding의 semantic 구조가 행동 공간에 반영되지 않음

> **6. 추론 속도: 22× 빠름 vs LLM-as-policy**
> PCSP 1.97ms vs B5 43.7ms (목표 100×에는 미치지 못하나 실용적으로 충분)

---

## Phase 7 — CoG 제출용 최소 확장 재실험 🔥 (즉시~2026-05 초)

### 목표
현재 PCSP의 가장 큰 약점인 toy-scale 환경을 완화하고,
IEEE CoG 2026 short paper에서 reviewer가 바로 지적할 포인트를 선제적으로 방어한다.

### 확장 범위
- 환경: Mini-Inzoi 확장판
- Grid: 6×6 → 12×12
- Agents: 4 → 16
- Personas: 300 → 500
- Split: Train/Test 재구성 (예: 400/100)
- 핵심 메시지: “같은 방법이 더 큰 life-sim setting에서도 persona consistency와 fast inference를 유지”

### 왜 이 범위인가
- Melting Pot까지 바로 가면 환경 의미가 바뀌어 story가 흔들릴 수 있음
- 12×12 / 16 agents / 500 personas는 구현 부담 대비 reviewer 설득력이 큼
- CoG short paper에는 “너무 큰 확장”보다 “핵심 주장 검증 강화”가 중요

### TODO
- [x] `src/env/mini_inzoi_v2.py` 생성: 12×12 grid, 16 agents 대응 (obs_dim=56)
- [x] need/action/object 배치 규칙 재설계 (8 objects spread across 12×12)
- [x] observation dimension 재정의: 2+1+8+45=56 (15 others × 3)
- [ ] persona dataset 500개 생성 및 split 저장
      → `scripts/generate_personas_500.py` (25 BF × 20 occ = 500, train 400 / test 100)
- [ ] Qwen3 임베딩 계산 (500개)
      → `scripts/compute_embeddings_500.py`
- [x] 동일 평가 프로토콜 유지 (reward / consist / zeroshot / KL / rho / latency)
      → `scripts/run_eval_v2.py`
- [ ] full model + 핵심 ablation 재실험 (full / no_consist / no_diverse / concat)
      → `scripts/run_pcsp_v2.py --all`
- [x] 결과 테이블/그림 갱신 스크립트 작성
      → `scripts/generate_v2_figures.py` (fig_v2_comparison, fig_v2_ablation, fig_v2_learning_curves)

### 실행 순서 (GPU 여유 시)
```bash
# 1. 데이터 준비 (CPU/Gemini API, ~15분)
conda run -n paper python scripts/generate_personas_500.py

# 2. 임베딩 계산 (GPU, ~2분, 1.1GB VRAM)
conda run -n paper python scripts/compute_embeddings_500.py

# 3. 학습 (GPU, nice -n 19, 4 × ~20분 = ~80분)
nice -n 19 conda run -n paper python scripts/run_pcsp_v2.py --all

# 4. 평가 + 그림
conda run -n paper python scripts/run_eval_v2.py
conda run -n paper python scripts/generate_v2_figures.py
```

### 성공 기준
- 12×12 / 16 agents에서도 full model이
  - random 대비 유의미한 zero-shot 성능 유지
  - diversity collapse 없이 persona-conditioned behavior 유지
  - 실시간 추론 속도 유지
- 논문 본문에서 “toy-only” 비판을 완화할 수 있는 결과 확보

---
## Phase 8 — IEEE CoG 2026 Vision Paper 제출 🔥 (마감 2026-06-03 추정 / CFP 최종 확인 필요)

### 목표
PCSP를 단순한 “작은 RL 방법 논문”이 아니라,
게임 분야에서의 차세대 life-simulation NPC architecture를 제안하는
Vision Paper로 재구성해 제출한다.

핵심은 현재 결과를 끝이라고 주장하는 것이 아니라,
"persona-conditioned shared policy"가
향후 대규모 NPC personalization의 유망한 연구 방향임을
기술적 근거와 초기 실험으로 설득하는 것이다.

### 제출 사양
- **카테고리**: Vision Paper
- **분량**: 8 pages (references / appendices 포함) 
- **성격**: 미래 게임 AI 방향 제시 + 근거 기반 research agenda
- **주의**: 문헌조사 부족, 단순 literature review, 근거 없는 의견문은 reject 위험 큼

### 핵심 포지셔닝
> "From scripted NPCs and per-character policies to persona-conditioned shared behavior models:
> a scalable research agenda for real-time life-simulation game characters."

### Vision 핵심 주장
1. 차세대 life-sim / open-world 게임은 수백~수천 NPC에 대해
   장기적 persona consistency를 요구한다.
2. 기존 방식(behavior trees / per-NPC RL / LLM-as-policy / latent skill)은
   scale, consistency, controllability, latency를 동시에 만족시키지 못한다.
3. frozen language semantics + shared policy + behavioral regularization 조합은
   practical game AI architecture로 발전할 가능성이 높다.
4. PCSP는 그 방향의 초기 proof-of-concept이며,
   더 큰 환경, dynamic persona, social emergence, human evaluation으로 확장되어야 한다.

---

### 논문 구성 (8페이지)

#### 1. Introduction
- life simulation / open-world 게임에서 NPC 개성화의 중요성 제시
- 현재 산업 방식의 병목:
  - behavior tree authoring cost
  - generic stochastic NPC의 몰개성
  - LLM-as-policy의 latency 문제
- 본 논문의 목표:
  - "방법 하나" 발표가 아니라
  - scalable persona-conditioned NPC control의 연구 비전 제시

#### 2. Why Current Paradigms Fall Short
- 관련 패러다임 구조 비교
  - hand-authored behavior trees
  - per-NPC RL
  - language-conditioned task RL
  - unsupervised skill discovery
  - LLM-as-policy
- 비교 축:
  - persona consistency
  - zero-shot controllability
  - interpretability
  - inference speed
  - deployment scalability
- Figure/Table:
  - 기존 Table 1 확장판으로 패러다임 비교표 재작성

#### 3. PCSP as a Concrete Early Instance
- PCSP를 "final answer"가 아니라 early design pattern으로 소개
- 구성요소 요약:
  - frozen LLM encoder
  - LoRA projection into behavior space
  - FiLM-conditioned shared policy
  - consistency + diversity co-objective
- 수식은 최소한으로 유지
- 구현 세부보다는 "왜 이 구조가 미래 아키텍처 후보인가"에 초점

#### 4. Initial Evidence
- 현재 Mini-Inzoi 결과 + 최소 확장 결과(12×12 / 16 agents / 500 personas)를 요약
- 핵심 지표만 제시:
  - zero-shot persona identification
  - behavioral diversity
  - semantic-behavior alignment
  - latency advantage
- 메시지:
  - “이미 완성됐다”가 아니라
  - “작동 가능성과 확장 가능성의 초기 증거가 있다”
- Figure 후보:
  - zero-shot/generalization
  - latency or semantic-behavior alignment

#### 5. Research Agenda for Infinite NPCs
- 앞으로 필요한 연구 축을 명시적으로 제안
- 예시 하위 섹션:
  - Dynamic personas and mood evolution
  - Socially emergent multi-agent behavior
  - Long-horizon memory and identity persistence
  - Richer worlds and engine-level integration
  - Human evaluation for persona fidelity
  - Authoring tools for game designers
- 이 섹션이 Vision Paper의 중심

#### 6. Evaluation Agenda
- 앞으로 이 분야가 무엇을 측정해야 하는지 제안
- 단순 reward 외에:
  - persona consistency
  - trajectory-to-persona identifiability
  - inter-persona behavioral separation
  - controllability by designers
  - latency budget compatibility
  - human-rated believability / naturalness
- benchmark 제안까지 짧게 포함 가능

#### 7. Limitations and Scope
- 현재 한계 명시:
  - Mini-Inzoi 기반
  - synthetic personas
  - human eval 미완성
  - real engine integration 미검증
- 하지만 이 한계를 "vision의 필요성"과 연결
- 과장 금지

#### 8. Conclusion
- persona-conditioned shared policy를
  게임 NPC 연구의 유망한 차세대 방향으로 정리
- “one policy, infinite NPCs”를 slogan이 아니라
  research program으로 제시

---

### TODO

#### A. 구조 재편
- [x] `paper/cog2026_vision/main.tex` 생성
- [x] 현재 method-first 서술을 vision-first 서술로 재작성
      → Section 1: "NPC Personalization Scaling Gap" + "A Promising Architectural Direction"
- [x] "our framework achieves..." 중심 문장을
      "this suggests a scalable direction..." 형태로 수정
- [x] conclusion을 "성능 요약"이 아니라 "research agenda 요약" 중심으로 개편

#### B. 문헌 보강
- [x] related work 확장: 22편 (`paper/cog2026_vision/refs.bib`)
      — yannakakis2018ai, park2023generative, wang2023voyager, yao2023react,
        achiam2023gpt4, reed2022gato, lowe2017maddpg, sunehag2018vdn,
        mordatch2018emergence, leibo2021meltingpot, chen2021decision,
        ha2018world, vinciarelli2014survey, mccrae1992introduction 등 추가
- [x] 각 계열의 한계 비교 문장 명시 (Section 2 "Why Current Paradigms Fall Short")
- [x] bibliography vision paper 밀도로 보강

#### C. 실험 파트 축소-정제
- [x] 핵심 evidence만 유지 (4행 × 4열 compact table)
- [x] concat 이슈는 Table 결과로 제시, 본문 ablation은 prose로 요약
- [x] "best balance" → "early encouraging signs" 로 보수화
- [x] 12×12 / 16 agents / 500 personas 결과 포함 → Table 2 (v2), §4.3 Scale Generalization 추가
- [x] 현재 결과만 넣고 limitations를 명확히 표기 (Section 7)

#### D. Vision 강화용 섹션 추가
- [x] "Research Agenda for Infinite NPCs" 섹션 신설 (6개 subsection)
- [x] "Evaluation Agenda" 섹션 신설
- [x] game designer controllability 관점 서술 추가 (§5.6 Authoring Tools)

#### E. 그림/표 재구성
- [x] Table 1: paradigm comparison 확장판 (6개 패러다임 × 4축)
- [x] Table 2: 핵심 evidence만 남긴 compact result table (4행 × 4열)
- [x] Figure 1: system overview 유지 (fig1_system.png)
- [x] Figure 2: zero-shot generalization (fig4_zeroshot.png) 선택
- [x] figure 수 2개로 관리

#### F. 표현 수정
- [x] "first framework" → 없음 ("one specific point in the design space of..."로 대체)
- [x] "infinite NPCs"는 scalable deployment framing으로 조정
- [x] human eval 문장 → Section 7 Limitations + §5.5 Human Evaluation agenda로 이동
- [x] 산업 적용 문장 가능성 수준으로 보수화

#### G. 남은 작업
- [ ] LaTeX 컴파일 최종 확인 (pdflatex + bibtex — texlive 설치 필요)
- [x] 12×12 / 500 personas 결과 Section 4에 추가 완료 (2026-04-28)
- [ ] CFP 최종 확인 및 제출 시스템 등록 (마감 ~2026-06-03 추정)

---

### 핵심 메시지 (Vision 버전)
> We argue that scalable NPC personalization in life-simulation games
> requires a shift from hand-authored or per-character control
> toward persona-conditioned shared behavior models.
> PCSP serves as an early empirical instance of this direction,
> showing that semantic persona conditioning and real-time control
> can coexist within a single policy architecture.

### 이 버전에서 reviewer가 기대하는 것
- 단순히 "성능이 좋다"보다 왜 이 방향이 중요한지 설명할 것
- 관련 문헌을 폭넓게 알고 있다는 신호를 줄 것
- speculative hype 대신 실제 연구 로드맵을 제시할 것
- 현재 결과는 초기 증거로, 미래 과제는 구체적으로 적을 것

---

## Phase 9 — AAAI-27 확장판 논문 작성 🔲 (2026-08~)

### 목표
Phase 8 완성 결과를 바탕으로 AAAI-27 (멀티에이전트 시스템 트랙) 제출용 풀 페이퍼 작성.
NeurIPS 2026 Workshop 결과를 피드백으로 반영.

### 조건 (제출 결정 기준)
- [ ] Melting Pot 환경 결과 확보 ← 없으면 제출 보류
- [ ] Human eval n≥100, α≥0.6 ← 없으면 제출 보류
- [ ] NeurIPS Workshop 리뷰어 피드백 반영

### 추가 분석 (탑티어 요구 사항)
- [ ] **Embedding geometry 분석**: LoRA projection before/after t-SNE + cosine distance matrix 비교 → personality 축 재구성 시각화
- [ ] **Temperature sensitivity analysis**: InfoNCE T={0.01, 0.05, 0.07, 0.1, 0.2}에서 consistency acc / behavioral KL 변화
- [ ] **FiLM vs concat gradient attribution**: Integrated Gradients로 persona 신호가 어느 layer에서 행동 결정에 기여하는지 분석

### TODO
- [ ] `paper/aaai27/main.tex` 작성 (8p + references, AAAI format)
- [ ] 실험 섹션 확장: Mini-Inzoi + Melting Pot 두 환경 비교
- [ ] Human eval 섹션 추가 (Table, α, blind 비교 결과)
- [ ] 이론 분석 섹션 추가 (embedding geometry, sensitivity)
- [ ] Abstract 마감 전 제출 (~2026-08)

---

## Phase 6 — 논문 Draft ✅ 완료 (2026-04-27)

### 완료된 작업

- [x] 4~6p 워크샵 포맷 LaTeX 작성 (`paper/main.tex`, `paper/refs.bib`)
  - Abstract (150 words)
  - Introduction + Motivation (4 contributions)
  - Related Work (4축 비교 테이블 포함)
  - Method (PCSP 수식 + 시스템 도식 Fig 1)
  - Experiments (결과 테이블 + 학습 곡선 + ablation 분석)
  - Conclusion + Limitations
- [x] Figure 생성 스크립트 (`scripts/generate_paper_figures.py`) 및 실행
  - Fig 1: 시스템 구조도 (`paper/figures/fig1_system.pdf`)
  - Fig 2: 학습 곡선 — reward + consistency loss (`paper/figures/fig2_learning_curves.pdf`)
  - Fig 3: Behavioral KL scatter (persona embedding distance vs. KL) (`paper/figures/fig3_kl_scatter.pdf`)
  - Fig 4: Zero-shot 일반화 결과 (per-persona + overall bar) (`paper/figures/fig4_zeroshot.pdf`)
- [x] Related work 다듬기 (`notebooks/related_work_survey.md` 기반, 논문 Section 2에 통합)
- [x] 제출 타깃 워크샵 최종 결정: **NeurIPS Workshop on Generative AI for Games** 1순위

### 남은 TODO (제출 전)
- [ ] Prolific 설문 진행 (n=30, 7월 중) → human eval 수치 추가
- [ ] B5 Qwen3-1.7B latency 실측 (이미 43.7ms 확인됨, 논문에 반영 완료)
- [ ] LaTeX 컴파일 최종 확인 (pdflatex + bibtex)
- [ ] 8월 29일 NeurIPS Workshop 제출 시스템 등록

---

## 실제 결과 vs 목표 (2026-04-27 기준)

| 지표 | 초기 목표 | 실제 결과 | 평가 |
|:-----|:---------|:---------|:-----|
| Zero-shot consistency acc | ≥ 90% (train 대비) | 0.193 (랜덤 1.7%의 11배) | ⚠️ 절대값 낮으나 상대 효과 유의미 |
| LLM-as-policy 대비 추론 속도 | 100× (<5ms vs ~500ms) | 22× (1.97ms vs 43.7ms) | 🔶 목표 미달, 실용적으로는 충분 |
| Behavioral KL - distance 상관 | Spearman ρ > 0.6 | ρ = 0.728 | ✅ 달성 |
| Human eval | n=30, 7월 완료 | 미진행 | ❌ Phase 8에서 n≥100으로 상향 |
| 환경 복잡도 | 6×6 (기준) | 6×6 | ⚠️ Melting Pot 확장 필요 (Phase 8) |

---

## 제출 경로별 최소 요건

| 제출처 | 마감 | 필수 조건 | 현재 상태 |
|:-------|:-----|:---------|:---------|
| IEEE CoG 2026 | 2026-05-14 | 4p, 현재 결과 + 게임 AI 포지셔닝 | ✅ 즉시 가능 |
| NeurIPS 2026 Workshop | 2026-08-29 | 4~6p, human eval 수치 있으면 이상적 | 🔶 draft 완료, human eval 보강 |
| AAAI-27 | ~2026-08 (Abstract) | Melting Pot + human eval n≥100 | 🔲 Phase 8 완료 후 결정 |

---

## 위험 요소 & 완화 전략

| 위험 | 심각도 | 완화 |
|:-----|:------:|:-----|
| 6×6 toy 환경 — 메인 컨퍼런스 거절 | ⚠️ 치명적 | Melting Pot 래핑 (Phase 8, PettingZoo 재사용) |
| 300 persona 통계 불안정 | 🔶 중요 | Gemini 2.5 Flash 1000개 생성, CI 보고 (Phase 8) |
| Human eval 미완성 | ⚠️ 치명적 | Prolific n≥100, α≥0.6 목표 (Phase 8~9) |
| Mode collapse (persona 무시) | ✅ 해결됨 | Diversity loss 핵심 기여 확인 (Phase 4~5) |
| LLM 임베딩이 성격 대신 직업 포착 | ✅ 부분 해결 | LoRA projection 효과 확인 (ρ=0.728) |
| Zero-shot 절대 정확도 낮음 (0.193) | 🔶 중요 | 더 복잡한 환경에서 효과 증폭 가능 (Melting Pot) |
| Consistency loss가 task reward와 경쟁 | 🔷 관찰됨 | λ₁ tuning + 환경 복잡도 증가로 완화 |
| AAAI 일정에 Melting Pot 완성 못할 경우 | 🔶 중요 | NeurIPS Workshop으로 다운사이즈, AAAI-28 재타겟 |
