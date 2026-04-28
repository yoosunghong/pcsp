

# Research Proposal: Speculative NPC Co-Adaptation

**"RL-Guided Co-Adaptation of sLM Draft Policies for Real-Time Game NPC Decision Making"**

*April 2026 — NeurIPS 2026 Workshop Target*

***

## 1. Motivation \& Problem Statement

실시간 게임 NPC는 두 가지 충돌하는 요구사항을 동시에 만족해야 한다: **저지연 행동 결정**(<50ms)과 **고품질 전략적 판단**. 현재 주류 접근법은 두 문제를 분리해서 다루거나 한쪽을 희생한다.

- **순수 PPO**: 빠르지만 행동이 언어적 추론 없이 암묵적(implicit)
- **LLM 직접 행동 생성**: 품질은 높지만 추론 latency가 수백ms로 실시간 불가
- **Speculative Decoding 선행연구** (arXiv:2512.17250): 고정 세계 모델로 연속 제어 latency를 43.6% 감소시켰으나, draft 모델이 학습 중 개선되지 않음[^1]

본 연구는 이 gap을 다음 질문으로 정의한다:

> *"RL verifier의 수락률 α를 sLM fine-tuning 신호로 역전파하는 Co-Adaptation Loop가, sLM 고정 구조 대비 draft 품질과 RL 샘플 효율을 동시에 향상시키는가?"*

***

## 2. 핵심 아이디어: α-Feedback Co-Adaptation Loop

### 시스템 구조

```
┌─────────────────────────────────────────────────────┐
│              Co-Adaptation Loop                     │
│                                                     │
│  Game State ──► [sLM Draft Policy]                  │
│  (text repr.)    Qwen3-1.7B + LoRA                  │
│                  ↓ K=3 행동 후보 생성               │
│               [RL Verifier]                         │
│                  PPO Agent                          │
│                  ↓ Q-value 기반 수락/기각            │
│        α = accepted / K ──► sLM LoRA update        │
│                  ↓                                  │
│            game_reward ──► PPO update               │
└─────────────────────────────────────────────────────┘
```


### sLM 모델 선택: Qwen3.5-2B 



***

## 3. 핵심 수식화

### Co-Adaptation 학습 목표

**sLM update** (LoRA): 수락된 draft를 positive, 기각된 draft를 negative로 DPO-style로 학습

$$
\mathcal{L}_{\text{sLM}} = -\alpha \cdot \log \pi_{\theta}(a^+ | s) + (1 - \alpha) \cdot \log \pi_{\theta}(a^- | s)
$$

여기서 $\alpha = |A_{\text{accepted}}| / K$ 는 RL verifier의 수락률이고, $a^+$ 는 수락된 draft, $a^-$ 는 기각된 draft이다.

**RL Verifier update** (PPO): 게임 reward로 독립 업데이트

$$
\mathcal{L}_{\text{PPO}} = \mathbb{E}\left[\min\left(r_t(\theta) \hat{A}_t,\ \text{clip}(r_t(\theta), 1-\epsilon, 1+\epsilon)\hat{A}_t\right)\right]
$$

**arXiv:2512.17250과의 차별화 수식**: 해당 논문의 corrector는 오프라인 distillation으로 고정 학습되는 반면, 본 연구의 sLM은 매 episode마다 α로 가중된 온라인 업데이트를 수행한다.[^1]

***

## 4. 실험 설계

### Phase 1: 환경 구축 (5월~6월)

**환경**: PettingZoo AEC 기반 커스텀 5×5 격자 2-agent 전투 환경[^5][^6]

- 행동 공간: {공격, 방어, 이동(4방향)} = 6개 이산 행동
- 상태를 자연어 텍스트로 변환: `"Enemy at (3,2), HP=30, your HP=80, turn=12"`
- 게임 reward: 적 처치(+1), 사망(-1), 생존 유지(+0.01/turn)

**Baseline 4종**:

1. **Pure PPO**: 언어 없음, 상태 벡터 직접 입력
2. **Static sLM + greedy**: Qwen3-1.7B 고정, RL verifier 없음
3. **sLM reward shaping** (ChatPCG 방식): RL이 sLM 출력을 reward로만 사용
4. **arXiv:2512.17250 방식**: frozen sLM + offline-distilled corrector (재현 구현)

### Phase 2: Co-Adaptation 구현 (7월)

```python
for episode in training:
    state_text = env.state_to_text(obs)
    
    # sLM draft (Qwen3-1.7B, /no_think 모드로 latency 최소화)
    drafts = sLM.generate(state_text, K=3, mode="no_think")
    
    # RL verifier (PPO Q-value)
    q_values = RL_verifier.evaluate(obs, drafts)
    accepted = [d for d, q in zip(drafts, q_values) if q > threshold]
    alpha = len(accepted) / K
    
    # 실행
    action = accepted[^0] if accepted else RL_verifier.act(obs)
    obs_next, reward, done, _ = env.step(action)
    
    # Co-Adaptation: sLM LoRA 업데이트
    sLM.dpo_update(positive=accepted, negative=rejected, weight=alpha)
    
    # RL 독립 업데이트
    RL_verifier.ppo_update(reward)
```


### 필수 측정 지표

| 지표 | 목적 |
| :-- | :-- |
| α(수락률) 변화 곡선 (step별) | Co-Adaptation이 실제로 sLM을 개선하는지 검증 |
| Episode cumulative reward (4 baseline 비교) | 최종 성능 |
| Draft entropy (K drafts의 다양성) | sLM mode collapse 감지 |
| Wall-clock latency (ms/step) | 실용성 증명 |
| Sample efficiency (reward/환경 step) | RL 측 개선 정량화 |


***

## 5. 기대 결과 \& Novelty 요약

**2512.17250 대비 핵심 차별점**: 해당 논문은 *"jointly optimizing the speculation mechanism end-to-end with the downstream policy…는 향후 과제"* 라고 명시적으로 남겨둔 문제를  본 연구가 직접 해결한다. Co-Adaptation Loop는 draft 모델을 온라인으로 개선하는 최초의 speculation+RL 통합 구조다.[^1]

**기대 결과**:

- α가 학습 초기 대비 30% 이상 증가 → sLM이 RL verifier의 취향을 학습
- Co-Adapt 구조가 Pure PPO 대비 샘플 효율 20~40% 개선
- Static sLM + greedy 대비 episode reward 개선 (Co-Adapt의 RL 시너지 효과)

***

## 6. 제출 전략 및 타임라인

```
2026년
 4월 말 ~ 5월 2주  │ Qwen3-1.7B LoRA smoke test (RTX 3090)
                  │ PettingZoo 커스텀 환경 repo 세팅
                  │ Related work 초안 (2512.17250 차별화 문장 확정)
 5월 3주 ~ 6월 말  │ Baseline 4종 구현 완료
 7월               │ Co-Adaptation Loop 구현 + α 수렴 실험
 8월 1~3주         │ 실험 완료, 논문 draft (4~6p 워크샵 포맷)
 8월 29일          │ ★ NeurIPS 2026 Workshop 제출
 9월 29일          │ 결과 통보

2027년
 1월               │ 이론 보강 (Lyapunov 수렴 조건) + Unity 환경 확장
 1월 말            │ ICLR 2027 / AAAI 2027 메인 트랙 제출
```


***

## 7. 이번 주 즉시 실행 항목

1. **Smoke test** — `Qwen/Qwen3.5-2B-Instruct` HuggingFace 로드 + RTX 3090에서 LoRA attach 확인
2. **환경 세팅** — PettingZoo 기반 5×5 전투 환경 repo 초기화[^5]
3. **Related Work 문서화** — 2512.17250의 limitation 문장 (`"jointly optimizing… remains future work"`) 인용 문단 작성[^1]
4. Qwen3의 `/no_think` 모드 latency 측정 — 게임 step당 목표 <30ms 달성 가능 여부 확인[^4]

<div align="center">⁂</div>

[^1]: 2512.17250v1.pdf

[^2]: https://qwenlm.github.io/blog/qwen3/

[^3]: https://cdn.jsdelivr.net/gh/yanfeng98/paper-is-all-you-need/papers/00069-Qwen3_Technical_Report.pdf

[^4]: https://www.bentoml.com/blog/the-best-open-source-small-language-models

[^5]: https://github.com/Farama-Foundation/PettingZoo

[^6]: https://www.geeksforgeeks.org/deep-learning/pettingzoo-multi-agent-reinforcement-learning/

[^7]: https://apidog.com/kr/blog/best-qwen-models-kr/

[^8]: https://huggingface.co/collections/Qwen/qwen3

[^9]: https://www.producthunt.com/products/qwen3/launches

[^10]: https://apidog.com/blog/best-qwen-models/

[^11]: https://www.linkedin.com/posts/reshmawithai_slm-vs-llm-activity-7417182947453190144-Mjrs

[^12]: https://dev.to/sienna/qwen3-coder-next-the-complete-2026-guide-to-running-powerful-ai-coding-agents-locally-1k95

[^13]: https://huggingface.co/blog/hf-skills-training

[^14]: https://mlcommons.org/2026/02/vlm-inference-shopify/

[^15]: https://www.intuz.com/blog/best-small-language-models

[^16]: https://openreview.net/forum?id=fLnsj7fpbPI

[^17]: https://en.wikipedia.org/wiki/Qwen

[^18]: https://arxiv.org/html/2604.14493v2

[^19]: https://huggingface.co/Qwen/Qwen3-TTS-12Hz-0.6B-Base/discussions/2/files

[^20]: https://arxiv.org/html/2604.14493v1

[^21]: https://artificialanalysis.ai/models/qwen3-0.6b-instruct

[^22]: https://www.marktechpost.com/2026/04/20/a-coding-implementation-on-microsofts-phi-4-mini-for-quantized-inference-reasoning-tool-use-rag-and-lora-fine-tuning/

[^23]: https://qwen.readthedocs.io/en/latest/getting_started/speed_benchmark.html

[^24]: https://unsloth.ai/blog/phi4

[^25]: https://apxml.com/models/qwen3-0-6b

[^26]: https://www.youtube.com/watch?v=6nLuWRo6MrY

[^27]: https://www.reddit.com/r/LocalLLaMA/comments/1kdsp4z/qwen_3_performance_quick_benchmarks_across/

[^28]: https://huggingface.co/microsoft/Phi-4-mini-instruct/discussions/15

[^29]: https://liner.com/review/qwen3-technical-report

[^30]: https://www.kaggle.com/code/edyvision/fine-tuned-phi-4-mini-financial-aid-chat-usecase

