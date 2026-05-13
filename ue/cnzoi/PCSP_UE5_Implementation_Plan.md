# PCSP UE5 구현 계획서
**대규모 연속공간 환경 + Behavior Tree 하이브리드 의사결정 구조 통합 계획**

---

## 1. 프로젝트 개요

본 계획서는 논문 *"One Policy, Infinite NPCs: Scalable Persona-Conditioned NPC Control via Shared Reinforcement Learning Policies"*의 핵심 아이디어를 Unreal Engine 5(UE5)의 **연속 공간 시뮬레이션**으로 확장 구현하고, PCSP(Persona-Conditioned Shared Policy)와 **Behavior Tree 기반 하이브리드 NPC 의사결정 구조**를 통합하는 작업의 전체 로드맵이다. 원 논문은 Python 기반 Mini-Inzoi 환경에서 6×6/12×12 그리드, 4~16 에이전트, 최대 20개 행동공간으로 실험했으며, 엔진 통합 부재와 coarse action observability를 한계로 명시했다 [file:21].

이번 UE5 구현의 목표는 네 가지다. 첫째, 논문 §VI의 "No engine integration" 한계를 실제 엔진 통합으로 해소한다 [file:21]. 둘째, 그리드 한 칸 이동 중심의 행동공간을 버리고 UE5 NavMesh 기반 **연속 이동**으로 전환한다 [file:21]. 셋째, 이동과 고수준 의사결정을 분리한 **Behavior Tree + RL 하이브리드 구조**를 구축한다. 넷째, 더 큰 환경 규모와 더 풍부한 관측을 통해 논문의 후속 확장판 수준의 실험 기반을 만든다.

---

## 2. 설계 원칙

### 2.1 v1 기준 시작을 버리는 이유

초안에서는 디버깅 편의성 때문에 v1(6×6, 4 agents, 12 actions)을 시작점으로 제안했지만, 이번 개정안에서는 이를 **최소 호환 기준**으로만 남기고 실제 메인 타깃은 더 큰 환경으로 전환한다. 논문은 v2에서 이미 12×12, 16 agents, 500 personas로 확장 실험을 수행했고, v3에서는 20-action ontology와 richer observability가 핵심 결과를 만들었다 [file:21]. 따라서 UE5 구현이 논문의 약점을 보완하려면, 시작부터 **확장 가능한 구조**로 설계하는 편이 더 타당하다 [file:21].

### 2.2 핵심 설계 철학

- 이동은 독립적 의미론이 아니라 **실행 수단**으로 취급한다.
- RL 정책은 "무엇을 할 것인가"를 결정하고, Behavior Tree는 "어떻게 수행할 것인가"를 제어한다.
- UE5의 강점인 NavMesh, Blackboard, EQS, AIController를 적극 활용한다.
- 관측공간은 그리드 좌표 대신 **어포던스, 사회 맥락, 부분관측, 이벤트 상태** 중심으로 재정의한다.
- 환경 규모는 16 agents를 기본으로 하고, 가능하면 32~64 agents 수준까지 스케일 테스트 가능하게 설계한다.

---

## 3. 목표 환경 스펙

### 3.1 권장 스케일

| 단계 | 월드 규모 | 동시 에이전트 수 | 페르소나 수 | 용도 |
|------|-----------|------------------|-------------|------|
| Debug | Small district | 8 | 100 | 통신/보상 검증 |
| Main | Medium district | 16 | 300~500 | 논문 재현 + 확장 |
| Stress | Large district | 32~64 | 500+ | 확장성/실시간성 평가 |

논문은 v2에서 16 agents, 500 personas까지 실험했고, zero-shot chance가 1.0% 수준으로 더 어려운 설정에서도 동일한 구조적 경향이 유지됨을 보였다 [file:21]. 따라서 UE5 주력 환경은 최소한 이 스케일을 커버해야 하며, 엔진 통합의 가치를 보여주려면 이보다 큰 실시간 다중 NPC 세팅도 시도할 가치가 있다 [file:21].

### 3.2 공간 구조

그리드 셀 기반 공간 대신, UE5 레벨은 **어포던스 존(Affordance Zone)** 중심으로 설계한다. 예시는 Kitchen, Dining, Bedroom, Bathroom, Gym, Office, StudyRoom, Lounge, Park, Shop, SocialHub 등이며, 각 존은 NavMesh 상 목적지 집합과 상호작용 포인트를 가진다. 논문 v3가 location-affordance one-hot 8차원과 social context를 추가해 richer observability를 만들었으므로, UE5에서는 이를 실제 공간 객체 수준으로 확장한다 [file:21].

### 3.3 행동공간 재정의

논문 v3의 20-action ontology는 persona-conditioned behavior의 핵심 실험축이었다 [file:21]. 하지만 UE5에서는 move_up/down/left/right 같은 원시 이동 행동을 제거하고, 아래처럼 **의미론적 행동 + 이동 실행 분리** 구조로 바꾼다.

#### High-level RL/Decision Actions 예시
- EatQuick
- EatSlow
- RestAlone
- RestWithOthers
- FocusedWork
- PlanningWork
- DeepStudy
- CasualLearning
- ExerciseSolo
- ExerciseSocial
- HygieneQuick
- HygieneCareful
- SocializeInitiate
- SocializeRespond
- LeisureIndoor
- LeisureOutdoor
- ShopEssentials
- BrowseArea
- ObserveCrowd
- IdleReflect

이 고수준 행동은 곧바로 애니메이션 명령이 아니라, **Behavior Tree의 커스텀 결정 노드 출력**으로 사용된다. 이후 해당 행동을 만족하는 목적지 검색, 이동, 상호작용 실행은 BT 서브트리가 담당한다.

---

## 4. 하이브리드 의사결정 구조

### 4.1 전체 구조

```
Persona Text
  ↓
Qwen3 Embedding + Low-rank Projection
  ↓
PCSP Shared Policy
  ↓
[Custom Decision Node in Behavior Tree]
  ↓
Blackboard Goal Update
  ↓
BT Subtree Execution
    ├─ MoveTo(TargetAffordance)
    ├─ Wait / Reserve / Retry
    ├─ Interaction Task
    └─ Post-condition Check
```

논문 PCSP는 공유 정책이 persona embedding을 받아 행동 분포를 출력하는 구조이며, InfoNCE consistency objective가 zero-shot persona traceability의 핵심이라고 보고했다 [file:21]. UE5에서는 이 정책을 완전히 버리지 않고, **Behavior Tree 안의 Decision Node**로 삽입해 하이브리드 구조로 재사용한다 [file:21].

### 4.2 Behavior Tree에서의 역할 분담

| 계층 | 담당 | 구현 요소 |
|------|------|-----------|
| Strategic | 다음 의도/활동 선택 | PCSP Decision Node |
| Tactical | 목적지 선택, 예약, 경쟁 해결 | BT Service + EQS + Blackboard |
| Execution | 이동, 상호작용, 애니메이션 | MoveTo Node + Custom Task |
| Recovery | 실패 처리, 재시도, fallback | Decorator + Selector |

이 구조는 논문이 비판한 hand-authored behavior tree의 장점과 한계를 동시에 활용하는 방식이다. 즉, 개별 NPC마다 트리를 따로 짜지 않고, **공유 BT 구조 + 공유 RL 정책 + 페르소나 조건부 파라미터**로 선형적 authoring cost 문제를 피한다 [file:21].

### 4.3 이동은 하나의 노드로 사용

사용자 요구대로 이동은 독립 의사결정이 아니라 **BT 내 실행 노드 하나**로 사용한다. 구체적으로는 `UBTTask_MoveToAffordance` 같은 커스텀 태스크를 만들고, RL 또는 커스텀 결정 노드는 목표 어포던스 타입 또는 목표 액터만 Blackboard에 기록한다.

#### 이동 노드 책임
- 목표 존/목표 액터 검색
- NavMesh 경로 계산
- 점유 여부 확인 및 예약
- 도착 판정
- 실패 시 재탐색 또는 fallback 위치 선택

이 방식은 move action이 정책의 출력을 낭비하는 문제를 줄이고, 페르소나-conditioned decision이 순수 의미론적 행동 차이에 집중하도록 만든다.

### 4.4 커스텀 의사결정 노드 추가

핵심 구현 요소는 `UBTTask_PCSPDecision` 또는 `UBTService_PCSPDecision`이다.

#### 입력
- 현재 NPC 관측 벡터
- persona embedding (64-d projected)
- 최근 행동 히스토리
- 현재 사회 관계/혼잡도/시간대

#### 출력
- `DesiredActionType`
- `DesiredAffordanceTag`
- `InteractionStyle`
- optional `TargetAgentId`

#### 내부 처리
1. Blackboard와 센서 컴포넌트에서 관측 수집
2. Python inference 서버 또는 ONNX/TorchScript 런타임으로 정책 추론
3. 샘플링 또는 argmax로 행동 선택
4. 결과를 Blackboard에 기록
5. 하위 BT 가지 실행

추가로 규칙 기반 fallback을 넣을 수 있다. 예를 들어 hunger가 임계치 이하이면 정책 출력을 무시하고 식사 관련 affordance 탐색 우선순위를 높이는 식이다. 이는 pure RL보다 안전한 실시간 NPC 제어에 유리하다.

---

## 5. 관측공간 재설계

### 5.1 기존 논문 관측공간 한계

논문 v1은 20차원, v3는 33차원 관측을 사용했고, 위치, 시간, 욕구, 타 에이전트 요약, location-affordance, social context, routine regularity를 포함했다 [file:21]. 이는 grid benchmark로는 합리적이지만, UE5 연속 공간에서는 `(x, y)` 좌표 자체가 행동 의미를 충분히 설명하지 못하고, 이동 경로는 NavMesh가 처리할 수 있으므로 관측 의미를 다시 설계하는 편이 낫다 [file:21].

### 5.2 UE5용 관측공간 제안

| 그룹 | 예시 | 비고 |
|------|------|------|
| Self Needs | hunger, sleep, social, leisure, hygiene, fitness, work, learning | 8 |
| Time Context | normalized time, weekday/event flag | 2~4 |
| Current Context | current zone type, occupancy, noise, crowding | 6~10 |
| Nearby Social | 주변 NPC 수, 친밀도 평균, 호환도 최고/최저, 최근 상호작용 여부 | 6~12 |
| Target Availability | eat/work/social affordance availability, queue length | 6~10 |
| Routine Signals | habituality, novelty seeking, recent repetition | 3~6 |
| Persona Memory Hooks | 최근 성공/실패 이벤트, 감정 태그, short memory summary | 4~8 |

권장안은 **약 32~48차원 고정 길이 벡터**다. 이는 논문 v3의 richer observability 철학을 유지하면서도, UE5의 partial observability와 사회적 혼잡 정보를 반영하는 형태다 [file:21].

### 5.3 선택적 멀티모달 확장

향후 확장으로는 벡터 관측 외에 다음을 추가할 수 있다.
- 주변 affordance heatmap의 저해상도 텐서
- 최근 5~10 step action history
- 관계 그래프 요약 임베딩
- 이벤트 메모리 retrieval 결과

단, 1차 구현에서는 재현성과 디버깅을 위해 고정 길이 벡터 관측을 유지하는 것이 바람직하다.

---

## 6. UE5 시스템 아키텍처

### 6.1 핵심 모듈

| 모듈 | 설명 | 구현 방식 |
|------|------|-----------|
| `ASimWorldManager` | 에피소드 진행, 스폰, 시간 흐름, 평가 루프 | C++ Actor/GameMode |
| `ANPCCharacter` | NPC 본체, 상태/애니메이션 보유 | C++ Character |
| `UPersonaComponent` | persona text, embedding, projected vector 저장 | C++ ActorComponent |
| `UNeedsComponent` | 8가지 욕구 및 decay/restore 처리 | C++ ActorComponent |
| `USocialContextComponent` | 관계, 최근 상호작용, 호환도 계산 | C++ ActorComponent |
| `UObservationComponent` | 관측 벡터 생성 및 정규화 | C++ ActorComponent |
| `UAffordanceManager` | 존/상호작용 포인트 등록 및 질의 | World Subsystem |
| `UBTTask_PCSPDecision` | 정책 기반 고수준 행동 선택 | Custom BT Task/Service |
| `UBTTask_MoveToAffordance` | 목표 존/액터까지 이동 | Custom BT Task |
| `UBTTask_PerformInteraction` | 식사/운동/학습/사회행동 실행 | Custom BT Task |
| `UTrajectoryRecorder` | rich trajectory 로그 및 렌더링 | UObject/Subsystem |
| `UPCSPBridge` | Python/ONNX 추론 브리지 | C++ Module |

### 6.2 권장 Behavior Tree 구조

```
Root
 └─ Selector
     ├─ Emergency Branch
     │   └─ Critical Need Handler
     ├─ Persona Decision Branch
     │   ├─ PCSPDecision Service
     │   ├─ Select Target Affordance
     │   ├─ MoveToAffordance
     │   ├─ PerformInteraction
     │   └─ Update Memory/Needs
     └─ Idle/Fallback Branch
         ├─ Wander or Observe
         └─ Re-evaluate
```

### 6.3 Blackboard Key 예시

- `DesiredActionType`
- `DesiredAffordanceTag`
- `TargetActor`
- `TargetLocation`
- `InteractionStyle`
- `UrgencyScore`
- `RecentFailureCount`
- `SocialTargetActor`
- `CurrentZoneTag`
- `bAffordanceReserved`

---

## 7. 학습 및 추론 통합

### 7.1 학습 방식 선택지

| 방식 | 설명 | 장점 | 단점 |
|------|------|------|------|
| Python 외부학습 + UE5 온라인 추론 | 학습은 Python, 게임에서는 inference만 | 안정적, 논문 재현 용이 | 온라인 적응 제한 |
| UE5-in-the-loop 학습 | UE5가 step environment 역할 | 가장 직접적 검증 | 느릴 수 있음 |
| Hybrid curriculum | Python proxy pretrain 후 UE5 finetune | 현실적 절충안 | 파이프라인 복잡 |

> **권장**: Python proxy/pretrain → UE5 fine-tuning 또는 evaluation.

논문은 PPO + InfoNCE consistency + KL diversity 공동학습을 사용했고, consistency loss 제거 시 zero-shot accuracy가 chance로 붕괴했다 [file:21]. 따라서 UE5 통합에서도 이 손실은 반드시 유지되어야 하며, 적어도 offline/pretrain 단계는 기존 Python 구현과 동일하게 가져가는 것이 안전하다 [file:21].

### 7.2 추론 배치 전략

NPC 수가 16~64로 증가하면 매 tick 개별 추론은 비효율적일 수 있다. 따라서 다음 최적화를 권장한다.
- decision tick을 매 프레임이 아닌 0.5~2초 간격으로 설정
- 여러 NPC의 관측을 batch inference로 처리
- persona embedding은 생성 시 1회만 계산 후 캐싱
- projected persona vector도 캐싱

논문은 frozen Qwen3 embedding을 NPC lifetime당 1회 계산하고, 정책 네트워크는 실시간 추론 가능한 소형 MLP(207K params)를 사용했다 [file:21]. 이 구조는 UE5 배치 추론과 궁합이 좋다 [file:21].

---

## 8. 구현 단계 로드맵

### Phase 0: 환경 재설계 문서화 (1주)
- [ ] 기존 Python Mini-Inzoi의 보상/관측/행동 로직 정리
- [ ] UE5용 affordance taxonomy 정의
- [ ] BT-Blackboard-Policy 인터페이스 명세 작성
- [ ] Main/Stress scale 타깃 수치 확정

### Phase 1: 대규모 연속공간 프로토타입 (2~3주)
- [ ] Medium district 레벨 제작
- [ ] 16-agent 동시 스폰/스케줄링
- [ ] NavMesh + affordance zone + interaction point 구축
- [ ] Needs/Social/Observation 컴포넌트 구현
- [ ] Blackboard 기반 기본 BT 골격 완성

### Phase 2: 하이브리드 BT 구조 구현 (2주)
- [ ] `UBTTask_PCSPDecision` 구현
- [ ] `UBTTask_MoveToAffordance` 구현
- [ ] `UBTTask_PerformInteraction` 구현
- [ ] 실패 재시도/예약 충돌 해결/혼잡도 반영
- [ ] 긴급 욕구 처리 branch 추가

### Phase 3: PCSP 정책 통합 및 학습 연결 (2주)
- [ ] persona embedding 캐시 파이프라인 구현
- [ ] projected vector 로딩
- [ ] Python inference server 또는 ONNX 런타임 연결
- [ ] 배치 추론/비동기 추론 최적화
- [ ] reward logging 및 trajectory export

### Phase 4: 규모 확장 및 실험 (2~3주)
- [ ] 32 agents 테스트
- [ ] 64 agents stress test
- [ ] zero-shot persona evaluation 자동화
- [ ] Spearman ρ, policy KL, latency 수집
- [ ] BT-only / RL-only / Hybrid ablation 비교

### Phase 5: 논문/포트폴리오 아티팩트 정리 (1주)
- [ ] 구현 다이어그램 정리
- [ ] rich trajectory 영상 제작
- [ ] UE5 스크린샷/성능표/아키텍처 그림 정리
- [ ] 논문 확장 섹션 초안 작성

---

## 9. 실험 설계 업데이트

### 9.1 새 비교축

| 설정 | 설명 |
|------|------|
| BT-only | 규칙 기반/욕구 우선순위 기반 BT |
| RL-only | BT 없이 정책이 직접 행동/이동 결정 |
| Hybrid-PCSP | 정책이 의도를 결정하고 BT가 수행 |
| Hybrid-NoConsist | consistency loss 제거한 hybrid |
| Hybrid-NoPersona | persona 조건 제거 |

이 비교는 논문의 핵심 주장인 persona-conditioned shared policy의 가치를 유지하면서, UE5 맥락에서 Behavior Tree가 실제로 어떤 보완 역할을 하는지 보여준다 [file:21]. 특히 hybrid 구조는 "behavior tree vs RL"이 아니라 "behavior tree + shared persona policy"라는 새로운 실용 축을 만든다.

### 9.2 추가 지표

- Zero-shot persona identification accuracy
- Semantic-behavioral alignment (Spearman ρ)
- Mean policy KL divergence
- Inference latency per decision batch
- Task completion rate under congestion
- Path efficiency / failed interaction rate
- Human readability of rich trajectory clips

논문은 zero-shot accuracy, semantic-behavioral alignment, latency, rich trajectory observability를 핵심 축으로 제시했다 [file:21]. UE5에서는 여기에 군집도, 경로 실패율, 혼잡 상황 안정성까지 추가하는 것이 타당하다 [file:21].

---

## 10. 리스크 및 대응

| 리스크 | 가능성 | 대응 |
|--------|--------|------|
| BT와 RL 책임 경계가 모호해짐 | 중 | Blackboard 계약 명확화, 출력 키 제한 |
| 많은 NPC에서 경로탐색 비용 급증 | 중 | decision LOD, zone-level planning, crowd simplification |
| 관측공간이 과도하게 커져 학습 불안정 | 중 | 32~48차원 기본안 유지, ablation으로 단계 확장 |
| UE5-in-the-loop 학습 속도 저하 | 높음 | proxy pretrain + UE5 evaluation/fine-tune |
| affordance 경쟁으로 deadlock 발생 | 중 | reservation timeout, fallback affordance, queue logic |

---

## 11. 최종 산출물

- UE5 대규모 life-sim sandbox (16~64 NPC)
- Behavior Tree + PCSP 하이브리드 의사결정 프레임워크
- persona-conditioned NPC 시연 영상
- Python/UE5 비교 실험 결과표
- 논문 확장 초안: **Engine-Integrated Hybrid Persona Control**
- 포트폴리오 프로젝트 문서 및 GitHub 저장소

---

*작성일: 2026년 5월 13일 | 기반 논문: Hong, Y. "One Policy, Infinite NPCs" (Independent Research, 2026)*
