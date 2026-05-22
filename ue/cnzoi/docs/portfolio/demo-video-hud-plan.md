# PCSP UE5 Portfolio Demo Video And HUD Plan

이 문서는 PCSP UE5 포트폴리오 영상을 촬영하기 위한 시나리오, 화면 구성,
HUD 정보 설계, 그리고 "가장 가까운 에이전트 시점으로 빙의" 기능의 구현
요구사항을 정의한다. 목표는 에이전트가 단순히 돌아다니는 장면이 아니라,
persona-conditioned policy, Behavior Tree 실행, affordance 기반 상호작용,
trajectory logging이 한 화면에서 읽히도록 만드는 것이다.

## Goal

영상의 핵심 메시지:

> One shared policy controls many NPCs, but each NPC expresses a distinct
> persona through high-level intent, affordance choice, and UE5-native
> movement/interactions.

시청자가 60-90초 안에 이해해야 하는 것:

- PCSP는 이동 명령을 직접 내리는 시스템이 아니라, `EatQuick`,
  `FocusedWork`, `ExerciseSocial`, `ObserveCrowd` 같은 고수준 의도를 고른다.
- UE5의 Behavior Tree, Blackboard, NavMesh, affordance zone이 그 의도를
  실제 이동과 상호작용으로 실행한다.
- 여러 에이전트가 같은 BT 구조를 공유해도 persona embedding 때문에 행동
  분포가 다르게 나타난다.
- 데모는 시각 장면에서 끝나지 않고, JSONL trajectory와 분석 지표로 이어진다.

## Dependency Order

This demo/HUD work should start after the portfolio engineering extensions have
at least a first implementation pass. The UI is meant to showcase stronger
runtime behavior, not hide missing systems.

Recommended order:

1. Clean up the live hybrid contract items in [hybrid-stack.md](hybrid-stack.md).
2. Implement or partially implement [eqs-congestion.md](eqs-congestion.md) so
   crowded zones produce clearer selection/recovery behavior.
3. Implement or prototype [async-inference.md](async-inference.md) if the demo
   target is 96+ agents or a large-map capture.
4. Extend [observability.md](observability.md) with a live event ring buffer so
   HUD trajectory strips can read the same event stream as JSONL.
5. Build the camera focus and HUD described in this document.

Minimum exception:

- For a near-term 16-64 agent capture, the HUD can start earlier, but it should
  be treated as a thin viewer over existing state. Do not let UI work replace
  EQS/async/runtime improvements in the portfolio backlog.

## Demo Map Policy

실험 재현용 `Map_PCSPDistrict_M`은 보존한다. 포트폴리오 촬영은 복제 맵에서
진행한다.

권장 맵 이름:

- `Content/PCSP/Maps/Map_PCSPDistrict_Portfolio.umap`

복제 맵에서 바꿔도 되는 것:

- 조명, 카메라 앵글, 구역별 색상/간판, 바닥 재질
- agent visibility를 높이기 위한 landmark, path guide, zone label
- 촬영용 `CineCameraActor`, `LevelSequence`, spectator spawn point

주의해서 바꿔야 하는 것:

- `APCSPAffordanceZone` 위치, `Capacity`, `ZoneTag`, `Category`
- `APCSPInteractionPoint` 개수와 배치
- NavMesh bounds, blocked area, spawner 위치
- World Partition의 `Is Spatially Loaded` 설정

이 값들은 실패율과 행동 분포를 바꾼다. 변경 후 최소 smoke capture 기준은
아래와 같다.

| Check | Pass condition |
| --- | --- |
| Zone registration | `FindBestZone` query에서 `reg=10, valid=10` |
| Agent logs | spawned agent 수만큼 `agent_p*.jsonl` 생성 |
| Category coverage | 5분 내 Eat/Rest/Work/Study/Exercise/Hygiene/Social/Observe 중 7개 이상 등장 |
| Failure rate | 64-agent demo에서 `move_failed / (interaction_complete + move_failed) < 5%` |
| HUD possession | 키 입력 후 가장 가까운 `APCSPAgentCharacter` 카메라로 전환 |

## Video Structure

권장 길이: 75-105초.

| Time | Shot | Visual | Point |
| ---: | --- | --- | --- |
| 0-8s | Establishing top-down | 32-64 agents in district, colored affordance zones | 규모와 시스템 전체 구조를 먼저 보여준다. |
| 8-20s | Hybrid stack overlay | `PCSP Decision -> Blackboard -> MoveToAffordance -> PerformInteraction` overlay | "정책은 의도, UE는 실행" 구조를 각인한다. |
| 20-38s | Agent possession #1 | 키 입력으로 가장 가까운 agent 시점 전환, HUD 표시 | 한 에이전트 내부 상태를 읽게 만든다. |
| 38-55s | Persona contrast | 다른 persona 3명 연속 possession: Work/Social/Exercise 성향 | 같은 맵, 같은 BT에서 persona 차이가 보이는 구간. |
| 55-70s | Congestion/recovery | 같은 zone을 원하는 agent들이 예약/대기/재시도 | 단순 wandering이 아니라 affordance contention이 있음을 보여준다. |
| 70-85s | Scale/performance | 16 -> 64 agents split or quick montage | 실시간 확장성과 안정성 강조. |
| 85-105s | Data proof | 로그 파일, histogram, ablation/scale table quick cut | 연구/엔지니어링 산출물로 닫는다. |

## Story Beats

### Beat 1: City Is Alive, But Structured

Camera:

- High-angle flyover or orthographic-like spectator camera.
- Colored zone overlays: Eat, Rest, Work, Study, Exercise, Hygiene, Social,
  Observe, Shop.

On-screen UI:

- Top-right run badge:
  - `HybridPCSP`
  - `64 agents`
  - `ONNX intent policy`
  - `BT/NavMesh execution`
- Bottom timeline strip:
  - interaction count
  - failure rate
  - active categories

Narrative:

- Show many agents moving, but avoid a generic crowd shot lasting too long.
- Cut quickly into the decision mechanics.

### Beat 2: Policy Chooses Intent, BT Executes

Camera:

- Follow one moving agent in third person.
- Add a subtle line or arrow from agent to selected affordance target.

On-screen UI:

- Decision chain panel:
  - `Persona #017`
  - `Observation: needs + social + zone context`
  - `PCSP action: FocusedWork`
  - `Affordance category: Work`
  - `BT task: MoveToAffordance`
  - `Target: Office.Desk.03`

Narrative:

- The viewer should see that the model output is not a raw location.
- The target is resolved by the affordance system.

### Beat 3: Persona Contrast

Camera:

- Possess or follow three different agents in sequence.
- Keep the same location/time context where possible.

Suggested trio:

| Persona angle | Expected visual | HUD highlight |
| --- | --- | --- |
| Work-oriented | routes to Office, `FocusedWork` or `PlanningWork` | Work need / action probability |
| Social-oriented | routes to SocialHub, `SocializeInitiate` | nearby count / affinity |
| Fitness or leisure-oriented | routes to Gym/Park, `ExerciseSolo` or `ObserveCrowd` | fitness/leisure need |

Narrative:

- The contrast is the portfolio money shot. The viewer sees the same
  architecture producing different semantic patterns.

### Beat 4: Congestion Is A Real Runtime Problem

Camera:

- Frame a busy Rest/Social/Work zone.
- Show agents selecting, reserving, and completing interaction points.

On-screen UI:

- Zone occupancy panel:
  - `PCSP.Zone.Work`
  - `occupants / capacity`
  - `free interaction points`
  - `recent failures: AllOverCapacity / none`
- Optional color coding:
  - green: free
  - amber: near capacity
  - red: full

Narrative:

- This beat distinguishes the project from a behavior showcase. It shows
  execution constraints, reservation, and recovery.

### Beat 5: Data Trail

Camera:

- Quick editor/file-system capture or rendered overlay.

On-screen UI:

- `Saved/PCSP/Logs/<stamp>/agent_p017_*.jsonl`
- event rows: `decision`, `interaction_complete`, `move_failed`
- small chart: action histogram by persona or category coverage

Narrative:

- Close by proving that the same run is evaluable, not just visual.

## Possession Feature

### User Experience

During PIE, pressing a configured key should switch the player view to the
nearest `APCSPAgentCharacter`. The possessed/followed agent continues to run
its AI controller and Behavior Tree. The feature is for observation, not for
manual control.

Recommended keys:

| Key | Behavior |
| --- | --- |
| `F` | Focus nearest PCSP agent from current camera/player location |
| `Tab` | Cycle next PCSP agent |
| `Shift+Tab` | Cycle previous PCSP agent |
| `Esc` or `F` again | Return to spectator/free camera |
| `H` | Toggle PCSP HUD |
| `Z` | Toggle zone overlays |

Important design choice:

- Prefer `SetViewTargetWithBlend()` over true `Possess()` for the first
  implementation. The agents are AI-controlled; true possession could disrupt
  `APCSPAIController`, Blackboard state, or Behavior Tree execution.
- If "빙의" must be literal later, use a separate observer pawn plus
  `AttachToComponent` / camera relay, not a controller swap that steals the
  AI controller.

### View Modes

| Mode | Camera behavior | Use |
| --- | --- | --- |
| Follow Third Person | spring-arm behind selected agent | Main portfolio footage |
| Shoulder Debug | closer over-shoulder camera with HUD | Persona/action explanation |
| Top-down Lock | camera above selected agent, tracks target arrow | Affordance target clarity |
| Free Spectator | detached camera | Establishing and transition shots |

Recommended first implementation:

- Add a `UCameraComponent` and optional `USpringArmComponent` to
  `APCSPAgentCharacter` or a BP child.
- Player controller keeps an `ObservedAgent` pointer.
- `FocusNearestAgent()` finds nearest live `APCSPAgentCharacter`, then calls
  `SetViewTargetWithBlend(ObservedAgent, 0.35f)`.
- HUD reads from `ObservedAgent`; no gameplay ownership transfer required.

### Nearest Agent Selection

Search source:

- `TActorIterator<APCSPAgentCharacter>` in current world, or a lightweight
  registry later if agent count grows.

Distance origin:

- Current player camera location if spectator exists.
- Otherwise player pawn location.

Filter:

- valid actor
- not pending kill
- has `UPCSPPersonaComponent`
- optionally only agents within camera frustum for nicer capture

Tie-break:

- smallest distance
- then lowest `PersonaId` for deterministic behavior

## HUD Information Architecture

HUD must make persona-conditioned decision-making visible without covering the
action. Use quiet, compact panels. The center of the screen should stay mostly
clear.

### Layout

```text
+--------------------------------------------------------------------------------+
| Run Badge                                                       Zone Mini Map   |
| HybridPCSP | 64 agents | infer p95 | fail%                     category colors |
|                                                                                |
|                                                                                |
|                     [world view / selected agent]                              |
|                                                                                |
| Agent Card                                      Decision Stack                  |
| Persona #017                                    PCSP action: FocusedWork       |
| Persona text summary                            Category: Work                 |
| Embedding active                                Target: Office.Desk.03         |
| Policy mode: HybridPCSP                         BT: MoveToAffordance           |
|                                                                                |
| Needs Bars                                      Affordance/Zone Panel           |
| Hunger Sleep Social Leisure                     Zone: PCSP.Zone.Work           |
| Hygiene Fitness Work Learning                   Occupancy: 5 / 8               |
|                                                  Reserved: yes/no               |
| Social Context                                  Trajectory Strip                |
| Nearby 4 | mean affinity .42                    last 5 events                  |
+--------------------------------------------------------------------------------+
```

### Panels

#### 1. Run Badge

Purpose: prove the demo mode and scale at a glance.

Fields:

- policy mode: `HybridPCSP`, `BTOnly`, or `HybridNoPersona`
- agent count
- session stamp
- inference mean/p95 if available
- current failure rate if computed live, otherwise omit during live HUD

Data source:

- `pcsp.PolicyMode`
- spawner/run config where available
- optional perf sampler summaries

#### 2. Agent Card

Purpose: establish whose mind we are watching.

Fields:

- `PersonaId`
- short `PersonaText` summary
- embedding status: active / missing / zeroed
- current zone tag
- current location or district area

Data source:

- `UPCSPPersonaComponent::PersonaId`
- `UPCSPPersonaComponent::PersonaText`
- `UPCSPPersonaComponent::HasEmbedding()`
- Blackboard `CurrentZoneTag`

If persona text is too long, show:

- first line summary
- 2-3 trait chips derived offline or manually authored for demo personas

#### 3. Needs Bars

Purpose: show why some actions are urgent.

Fields:

- Hunger
- Sleep
- Social
- Leisure
- Hygiene
- Fitness
- Work
- Learning

Data source:

- `UPCSPNeedsComponent::Values`
- `EPCSPNeed` order:
  `Hunger`, `Sleep`, `Social`, `Leisure`, `Hygiene`, `Fitness`, `Work`,
  `Learning`

Visual:

- Horizontal bars.
- Highlight the most urgent need.
- Mark critical threshold with a small tick.

#### 4. Decision Stack

Purpose: make the hybrid stack legible.

Fields:

- latest PCSP action: `DesiredActionType`
- mapped affordance category
- target affordance tag: `DesiredAffordanceTag`
- target actor / interaction point
- urgency score
- recent failure count
- reservation state
- current BT phase: decision, moving, interacting, recovering

Data source:

- Blackboard keys from `PCSPBlackboard`:
  - `DesiredActionType`
  - `DesiredAffordanceTag`
  - `TargetActor`
  - `TargetLocation`
  - `UrgencyScore`
  - `RecentFailureCount`
  - `bAffordanceReserved`
- Optional state mirrored from BT tasks for cleaner UI.

Visual:

- Four-step vertical chain:
  `Observe -> PCSP Decision -> Affordance Target -> Interaction`
- Current step is highlighted.

#### 5. Affordance/Zone Panel

Purpose: show that actions are grounded in world affordances.

Fields:

- selected zone tag
- category
- occupants / capacity
- free interaction points
- distance to target
- latest failure reason if any

Data source:

- `APCSPAffordanceZone::ZoneTag`
- `APCSPAffordanceZone::Category`
- `APCSPAffordanceZone::Capacity`
- `APCSPAffordanceZone::GetCurrentOccupancy()`
- `APCSPInteractionPoint::IsReserved()`
- `BTTask_MoveToAffordance` failure diagnostics if mirrored live

Visual:

- Zone category color matching world overlay.
- Occupancy meter.
- Reservation icon.

#### 6. Social Context

Purpose: make social actions more than random movement.

Fields:

- nearby count
- mean affinity
- max compatibility
- recent interaction recency
- social target if present

Data source:

- `UPCSPSocialContextComponent::GetSummary()`
- Blackboard `SocialTargetActor`

#### 7. Trajectory Strip

Purpose: connect live behavior to logged evaluation.

Fields:

- last 5 events:
  - `decision`
  - `interaction_complete`
  - `interaction_failed`
  - `move_failed`
- latest reward delta
- latest action/category pair

Data source:

- Ideal: add a small in-memory ring buffer to `UPCSPTrajectoryLogComponent`
  mirroring the rows already emitted to JSONL.
- Minimum viable: HUD keeps its own event buffer by polling Blackboard and
  interaction state transitions.

Visual:

- Compact timeline at lower center or lower right.
- Green for complete, amber for decision, red for failure.

#### 8. Zone Mini Map

Purpose: orient the viewer during agent possession.

Fields:

- simplified district layout
- current agent position
- selected target zone
- category colors

Data source:

- world positions of `APCSPAffordanceZone`
- selected agent position
- target actor/location from Blackboard

Implementation can start as a non-spatial legend if a true minimap is too
expensive.

## HUD Visual Rules

- Keep panels semi-transparent and low-contrast; do not hide the agent.
- Use stable panel sizes so values changing every tick do not resize the UI.
- Use color consistently by affordance category.
- Avoid large explanatory text in the HUD. The video narration or captions can
  explain; HUD should show state.
- For portfolio capture, prefer fewer visible fields with high clarity over
  dense debug dumps.

Recommended category colors:

| Category | Color intent |
| --- | --- |
| Eat | warm yellow |
| Rest | soft blue |
| Work | neutral steel |
| Study | teal |
| Exercise | green |
| Hygiene | cyan |
| Social | coral |
| Observe | violet |
| Shop | amber |
| Idle | gray |

## Implementation Work Breakdown

### D1. Demo Observer Controller

Add or extend a player controller for demo observation.

Responsibilities:

- bind keys: `F`, `Tab`, `Shift+Tab`, `Esc`, `H`, `Z`
- find nearest/cycled `APCSPAgentCharacter`
- set camera view target with blend
- store `ObservedAgent`
- broadcast observed-agent changes to HUD

Suggested class:

- `APCSPDemoPlayerController`

### D2. Agent Camera Mount

Add camera support to the PCSP agent BP or C++ class.

Minimum:

- `USpringArmComponent`
- `UCameraComponent`
- offset tuned for shoulder/follow footage

Alternative:

- create a separate `APCSPAgentCameraProxy` actor that attaches to selected
  agent and is used as the view target. This avoids touching agent components.

### D3. HUD Data Adapter

Create a thin read-only adapter that turns selected agent state into Blueprint
or UMG-friendly fields.

Suggested class:

- `UPCSPAgentDebugViewModel`

Responsibilities:

- read `Persona`, `Needs`, `SocialContext`, Blackboard, target zone
- convert enum values to strings
- expose stable fields for UMG
- never mutate agent state

### D4. UMG Widgets

Suggested widgets:

- `WBP_PCSPDemoHUD`
- `WBP_PCSPSmallRunBadge`
- `WBP_PCSPAgentCard`
- `WBP_PCSPNeedsBars`
- `WBP_PCSPDecisionStack`
- `WBP_PCSPAffordancePanel`
- `WBP_PCSPSocialPanel`
- `WBP_PCSPTrajectoryStrip`
- `WBP_PCSPZoneLegend`

### D5. Zone Overlay

Add optional debug visualization for filming.

Options:

- material instance on zone floor meshes
- translucent box/outline around `APCSPAffordanceZone`
- floating category label above zone center
- target arrow from selected agent to `TargetLocation`

Key:

- `Z` toggles visibility.

### D6. Capture Presets

Prepare two PIE presets:

| Preset | Agent count | Purpose |
| --- | ---: | --- |
| Demo readable | 16 | clear persona/affordance shots |
| Demo scale | 64 | crowd and performance proof |

Use command-line switches when possible:

```text
-PCSP_AgentCount=64 -PCSP_SpawnSeed=0 -PCSP_RunDurationSeconds=300
```

## Minimum Viable Demo

If time is tight, implement only:

1. `F` focuses nearest agent using `SetViewTargetWithBlend`.
2. HUD shows:
   - persona id/text
   - current `DesiredActionType`
   - mapped affordance category
   - target actor/location
   - 8 needs bars
   - current zone occupancy
3. Zone floor colors are visible.
4. Capture three persona-contrast shots and one 64-agent wide shot.

This is enough to avoid the "agents just wandering" problem.

## Capture Checklist

Before recording:

- Confirm active map is `Map_PCSPDistrict_Portfolio`.
- Confirm ONNX and persona cache load:
  `PCSPPolicySubsystem: ready (obs=33, persona_dim=64, n_actions=20)`.
- Confirm `pcsp.PolicyMode=0`.
- Confirm HUD toggle works.
- Confirm nearest-agent focus does not stop Behavior Tree execution.
- Confirm target affordance and zone overlay update while camera follows agent.
- Start with 16 agents for clean close-up shots.
- Repeat with 64 agents for scale shot.

After recording:

- Save session stamp.
- Run `research/scripts/analyze_ue_session.py` on the captured session.
- Export one action histogram or category-coverage chart for the final video
  data-proof beat.

## Risks

| Risk | Mitigation |
| --- | --- |
| True possession stops AI | Use `SetViewTargetWithBlend`, not controller possession. |
| HUD becomes too dense | Use compact default HUD and toggle advanced panels only for technical cutaways. |
| Demo map changes invalidate metrics | Keep experiment map untouched; label demo map results separately. |
| Persona text too long | Pre-author short display summaries for selected demo personas. |
| Zone overlays make footage look like editor debug | Use tasteful translucent floor/outline materials and reserve dense debug UI for short cutaways. |

## Open Follow-ups

- Decide whether `APCSPDemoPlayerController` should live under the PCSP module
  or as a demo-only class outside runtime experiment code.
- Add an in-memory event ring buffer to `UPCSPTrajectoryLogComponent` so the
  HUD can show the same events being written to JSONL.
- Pick 3-5 curated persona IDs for repeatable portfolio capture via
  `pcsp.PersonaIds` / `-PCSP_PersonaIds`.
- Create a short `LevelSequence` for the establishing and scale shots.
