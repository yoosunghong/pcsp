# Phase 5 — Architecture & Data-Flow Diagrams

Mermaid source for the architectural figures referenced by the paper extension.
Render with any Mermaid-aware viewer (GitHub renders these inline).

---

## 1. System overview — research ↔ UE5 split

```mermaid
flowchart LR
    subgraph Research["research/ (Python)"]
        Per[personas_300_v3.json] --> Emb[Qwen3 embeddings]
        Emb --> Train[PCSP PPO trainer]
        Env[MiniInzoiV3Env] --> Train
        Train --> Ckpt[policy.pt]
        Ckpt --> Export[export_pcsp_onnx.py]
        Emb --> Export
        Export --> Onnx[pcsp_actor.onnx]
        Export --> EmbJson[persona_embeddings.json]
    end

    subgraph UE5["ue/cnzoi/ (Unreal Engine 5)"]
        Onnx --> Subsys[UPCSPPolicySubsystem]
        EmbJson --> Cache[UPCSPPersonaCache]
        Cache --> Subsys
        Subsys --> BT[BT_PCSPAgent + BB_PCSPAgent]
        BT --> Agent[APCSPAgentCharacter]
        Agent --> Log[UPCSPTrajectoryLogComponent]
        Log --> Jsonl[agent_p*.jsonl]
    end

    subgraph Analysis["research/scripts/"]
        Jsonl --> Analyze[analyze_ue_session.py]
        Analyze --> Cmp[compare_ablations.py]
        Cmp --> Tables[results/ue_sessions/*.json]
    end

    style Research fill:#eef
    style UE5 fill:#efe
    style Analysis fill:#fee
```

---

## 2. Per-decision data flow (single agent, one BT tick)

```mermaid
sequenceDiagram
    autonumber
    participant BT as BTTask_PCSPDecision
    participant NC as NeedsComponent
    participant OC as ObservationComponent
    participant PC as PersonaComponent
    participant PS as UPCSPPolicySubsystem
    participant BB as Blackboard
    participant TL as TrajectoryLogComponent

    BT->>NC: GetMostUrgentNeed()
    NC-->>BT: (need, urgency)
    alt urgency >= 0.85 (emergency)
        Note over BT: bypass throttle
    else throttled (< MinDecisionInterval × (1 + RecentFailureCount))
        BT->>BB: SetValueAsEnum(DesiredActionType, LastAction)
        BT->>BB: SetValueAsFloat(UrgencyScore, ...)
        BT-->>BT: return Succeeded (reuse last action)
    end
    BT->>OC: BuildObservation()
    OC-->>BT: float[33]
    BT->>PC: GetPersonaId()
    PC-->>BT: 1..N
    BT->>PS: RunInferenceWithLogits(obs, persona_id, &logits)
    PS->>PS: read pcsp.PolicyMode CVar
    alt mode == BTOnly
        PS->>PS: NeedsHeuristic(obs) [skip ONNX]
        PS-->>BT: action, logits=zeros
    else mode == HybridNoPersona
        PS->>PS: persona_buffer ← zeros, RunSync
        PS-->>BT: action (argmax remap), logits
    else mode == HybridPCSP
        PS->>PS: persona_buffer ← cache[persona_id], RunSync
        PS-->>BT: action (argmax remap), logits
    end
    BT->>BB: SetValueAsEnum(DesiredActionType, action)
    BT->>BB: SetValueAsFloat(UrgencyScore, ...)
    BT->>TL: RecordDecisionWithLogits(action, urgency, logits)
```

---

## 3. BT subtree after decision

```mermaid
flowchart TD
    Dec[BTTask_PCSPDecision]:::done --> Mov{Move branch}
    Mov --> Mta[BTTask_MoveToAffordance]
    Mta -->|FindBestZone success| Reserve[Reserve InteractionPoint]
    Reserve --> Path[MoveTo via NavMesh]
    Path -->|reach success| Perf[BTTask_PerformInteraction]
    Perf --> NeedRestore[NeedsComponent::AdjustNeed]
    NeedRestore --> Log1[TrajectoryLog: interaction_complete]
    Log1 --> Release[InteractionPoint::Release]

    Mta -->|FindBestZone fail| Fail1[Log: move_failed<br/>failure_reason=FindBestZone:&lt;reason&gt;]
    Reserve -->|race lost| Fail2[Log: move_failed<br/>=interaction_point_reserve_race_lost]
    Path -->|path fail or short| Fail3[Log: move_failed<br/>=path_follow_idle_short:dist=X]
    Perf -->|reservation stolen| Fail4[Log: interaction_failed]

    Fail1 --> Inc[BB.RecentFailureCount += 1]
    Fail2 --> Inc
    Fail3 --> Inc

    classDef done fill:#d4f7d4
    classDef fail fill:#f7d4d4
    class Fail1,Fail2,Fail3,Fail4 fail
```

---

## 4. Three-layer affordance system

```mermaid
flowchart LR
    subgraph L1[Layer 1: Policy Action Space<br/>EPCSPActionType - 20 values]
        A1[EatQuick]
        A2[EatSlow]
        A3[FocusedWork]
        A4[PlanningWork]
        A5[...16 more]
    end

    subgraph L2[Layer 2: Affordance Category<br/>EPCSPAffordanceCategory - 11 values]
        C1[Eat]
        C2[Work]
        C3[...9 more]
    end

    subgraph L3[Layer 3: Gameplay Tags<br/>DT_PCSPAffordanceTags]
        T1[PCSP.Zone.Eat.Kitchen]
        T2[PCSP.Zone.Work.Office]
        T3[...]
    end

    subgraph L4[Layer 4: Level Actors]
        Z1[APCSPAffordanceZone instances<br/>10 actors in Map_PCSPDistrict_M]
        I1[APCSPInteractionPoint children<br/>~80 actors, 1 per capacity slot]
    end

    A1 --> C1
    A2 --> C1
    A3 --> C2
    A4 --> C2
    C1 --> T1
    C2 --> T2
    T1 --> Z1
    T2 --> Z1
    Z1 --> I1
```

---

## 5. Phase 4 ablation runtime switch

```mermaid
flowchart TD
    CVar["pcsp.PolicyMode<br/>console variable<br/>(0/1/2)"]
    CVar -->|0| H[HybridPCSP<br/>ONNX + persona embedding]
    CVar -->|1| B[BTOnly<br/>NeedsHeuristic, no ONNX]
    CVar -->|2| N[HybridNoPersona<br/>ONNX + zeroed persona]

    H --> Log["session_start row:<br/>policy_mode = HybridPCSP"]
    B --> Log
    N --> Log

    Log --> Cmp[compare_ablations.py<br/>aggregates 3 sessions<br/>into one table]

    classDef good fill:#d4f7d4
    classDef bad fill:#f7d4d4
    classDef mid fill:#f7f4d4
    class H good
    class B bad
    class N mid
```

The ablation result colors above match the 2026-05-18 outcome: HybridPCSP =
0% fail / 708 reward (green), BTOnly = 87.6% fail / 395 reward (red),
HybridNoPersona = 13.3% fail / 574 reward (yellow).

---

## Render notes

- All five diagrams render directly in GitHub's Markdown preview.
- For paper inclusion, export each to PDF/PNG via [mermaid-cli](https://github.com/mermaid-js/mermaid-cli):
  ```
  mmdc -i diagrams.md -o ../../../paper/figures/fig_<name>.pdf
  ```
- Diagrams 1, 2, and 3 are the most paper-load-bearing; 4 is reference for
  the architecture writeup; 5 documents the ablation methodology.
