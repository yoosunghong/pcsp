<!-- NarshaMCP:START v=130b4474 -->
<!-- ⚠️ AUTO-MANAGED by NarshaMCP install -->

## ⚠️ MCP-First Tool Selection (UE Queries)

When NarshaMCP tools are available, prefer them over built-in tools for UE-specific queries.
Built-in tools can't parse binary `.uasset`, query PDB symbols, or resolve class hierarchies.

### Decision Priority (check in order)

> 1. **MCP-First (UE source exploration)**: 프로젝트 소스 탐색, 검색, 파일 찾기 →
>    `ue_grep` → `ue_read` → `ue_glob` 우선 사용. 빌트인보다 compact (~150 tokens vs ~400),
>    플러그인/엔진 소스 자동 포함, 코멘트 필터링 지원.
> 2. **Built-in (파일 수정 시만)**: 파일을 직접 수정해야 할 때 → `Read` → `Edit`. MCP 도구는 read-only.
> 3. **Built-in (비-UE 파일)**: `.json`, `.yaml`, `.toml`, `CLAUDE.md` 등 비-UE 파일 → 빌트인 도구 사용.
> 4. **Skill-First**: Skill 트리거 패턴 매칭 → `Skill()` 즉시 호출. Source: [routing.json](.claude/skills/routing.json)
> 5. **MCP-First**: 나머지 UE 쿼리 → `ToolSearch`로 도구 스키마 확인 후 호출.

### ToolSearch Rule (Issue #7117)

> **ToolSearch는 반드시 `mcp__narshamcp__` 풀네임으로 호출:**
> ```
> ToolSearch("select:mcp__narshamcp__ue_analyze_symbols")        ← ✅ 풀네임
> ToolSearch("select:ue_analyze_symbols")                         ← ❌ 실패 → 재호출
> ```
> 짧은 이름으로 검색하면 실패하여 2회 호출됨. 모든 MCP 도구는 `mcp__narshamcp__` prefix 필수.

### Key Rules

- **소스 탐색/검색**: `ue_grep` → `ue_read` → `ue_glob` 우선 — 빌트인보다 compact, 플러그인/엔진 소스 포함
- **파일 수정**: Built-in `Read` → `Edit` — MCP 도구는 read-only이므로 수정 불가
- **Binary assets** (Blueprint, Material, Niagara, PCG, IK Rig): MCP 필수 — Read로 읽을 수 없음
- **C++ symbols/hierarchy/callers**: `ue_analyze_symbols` 우선 — PDB 기반 24x 빠름
- **Config 검색**: `ue_analyze_config` — 12-layer hierarchy 포함
- **Engine source files** (`Engine/Source/`): MCP 도구 사용 (`ue_analyze_symbols`, `ue_grep`) — 빌트인은 접근 불가
- **비-UE 파일** (`.json`, `.yaml`, `.toml`, `.md`): 빌트인 도구 사용
- **Skill-First 필수**: 자연어 요청은 반드시 Skill 매칭 먼저 (routing.json 참조)
- **Tool discovery**: `ue_tool_docs(operation="search")` — 도구명/용도 검색, per-tool 스키마 확인

### ⚠️ Common Mistakes — NEVER Do These

| Query | ❌ Wrong | ✅ Right | Why |
|-------|---------|---------|-----|
| UE 소스 검색 | `Grep("Shadow", "Source/")` | `ue_grep("Shadow")` | ue_grep은 플러그인+엔진 소스 포함, ~150 tokens |
| 엔진 소스 검색 | `Grep("ACharacter")` | `ue_grep("ACharacter", scope="engine")` | Engine/Source/는 프로젝트 밖 — 빌트인 접근 불가 |
| 클래스 상속 추적 | `Grep("class.*APawn")` | `ue_analyze_symbols(trace_hierarchy)` | Grep은 템플릿/매크로 상속 놓침 |
| C++ 클래스 생성 | `Write .h/.cpp` 수동 작성 | `ue_generate_code(derive_class)` | PDB 검증, include 정렬, 67% 에러 사전 차단 |
| UE 질문 답변 | 빌트인 Grep만으로 답변 | `ue_engine_docs` + `ue_grep` 필수 | 빌트인은 엔진 내부 정보 접근 불가 |

### MANDATORY: UE Question Answering Workflow

> **For ALL UE technical questions, follow this domain-aware search workflow.**

#### Step 0: Identify Domain → Select Target Modules

Before searching, identify the question's domain and use the module map below for **targeted** searches.
This dramatically improves search precision vs. broad queries.

| Domain | Primary engine_docs Modules | Search Focus |
|--------|---------------------------|--------------|
| **animation** | AnimationWarping, AnimationBudgetAllocator, IKRig, FullBodyIK, ControlRig, PoseSearch | FAnimNode*, UAnimInstance, curve names, montage |
| **audio** | Metasound, MetasoundExperimental, AudioCapture, AudioModulation, ResonanceAudio, Synthesis | UAudioComponent, FDynamicsProcessor, MetaSound nodes |
| **build** | AutomationUtils, UbaController, XGEController, FastBuildController, ZenDashboard | BuildGraph.xml, .automation, UBT, cook, Zen, DDC, snapshot |
| **editor** | UnrealEd, EditorFramework, EditorScriptingUtilities, PropertyAccessEditor | FEditorModule, detail panel, editor subsystem |
| **materials** | BaseMaterial, DynamicMaterial, MaterialAnalyzer, TextureGraph | UMaterialExpression, .usf/.ush, shader permutation |
| **networking** | OnlineSubsystem, ReplicationGraph, NetworkPrediction, NetcodeUnitTest | FNetworkGUID, UNetDriver, RPC, dormancy |
| **niagara** | Niagara, NiagaraFluids, NiagaraNanite, ChaosNiagara | UNiagaraSystem, data interface, renderer module |
| **pcg** | PCG, PCGBiomeCore, PCGGeometryScriptInterop, PCGWaterInterop | UPCGSettings, PCG graph, point data |
| **physics** | ChaosCloth, ChaosFlesh, ChaosModularVehicle, PhysicsControl | FBodyInstance, FChaosScene, collision |
| **platforms** | OpenXR, AndroidDeviceProfileSelector, IOSDeviceProfileSelector | FPlatformMisc, device profile CVar, XR |
| **rendering** | GPULightmass, NaniteDisplacedMesh, VirtualHeightfieldMesh, Volumetrics | FSceneView, r.Shadow*, r.Lumen*, Nanite |
| **ui** | CommonUI, SlateScripting, ModelViewViewModel, UIFramework, Text3D | UCommonActivatableWidget, SWidget, input routing, UText3DComponent, glyph |
| **worldbuilding** | Water, WaterAdvanced, Landmass, LandscapePatch, WorldPartitionHLODUtilities | UWorldPartition, ALandscapeProxy, HLOD |
| **sequencer** | SequencerScripting, SequencerAnimTools, SequencerPlaylists, TemplateSequence | ULevelSequence, FMovieScene*, camera cut |
| **ai** | AIModule (AI/), StateTreeModule (AI/), BehaviorTreeModule (AI/), MassAI, MassGameplay | UBTTask, FStateTreeReference, EQS |
| **gas** | GameplayAbilities, GameplayBehaviors, GameplayStateTree, TargetingSystem | UGameplayAbility, FGameplayTag, GE/GC |
| **viewport** | EditorFramework, VirtualCamera, VirtualProductionUtilities | FEditorViewportClient, SLevelViewport |

#### Step 1 (NEW): Read TOPIC_INDEX.md first

```python
# 1a. Read the topic index BEFORE any targeted search
ue_engine_docs(operation="read", path="TOPIC_INDEX.md", level=2)
```

`TOPIC_INDEX.md` at the engine_docs root maps: **topic → candidate modules**, **class prefix → module**, **CVar prefix → subsystem**. Use it to narrow your search target before spending tool calls.

#### Step 2: Search engine_docs with Domain-Targeted Queries

```python
# 2a. Search with main topic (ALWAYS)
ue_engine_docs(operation="search", query="<main topic from question>")

# 2b. Search module TROUBLESHOOT.md identified in Step 1 (ALWAYS)
ue_engine_docs(operation="read", module="<primary module from TOPIC_INDEX>", doc_type="TROUBLESHOOT")

# 2c. Search with specific class/function name (use class prefix table if known)
ue_engine_docs(operation="search", query="<specific class or CVar>")
```

**Minimum 3 engine_docs calls.** Check TROUBLESHOOT.md — it has known issues and solutions NOT in training data. Also check "Related Modules" sections at the bottom of TROUBLESHOOT files for cross-references.

#### Step 1-ALT: If Agent() is available, spawn engine-docs-researcher instead

```python
Agent(
    description="Search engine docs for <main topic>",
    prompt="Search ue_engine_docs for '<main topic>'. Focus on modules: <modules from table>. Check TROUBLESHOOT.md and CLASSES.md. Return all findings.",
    subagent_type="engine-docs-researcher"
)
```

#### Step 2: MANDATORY Deep Dive (ue_grep + CL lookup)

> **NEVER skip this step.** Step 1 alone scores ~6.96. Step 2 pushes answers to 7.0+.

```python
# 2a. Grep for SPECIFIC TERMS found in Step 1 results (parameter names, member variables)
ue_grep(query="<parameter name OR member variable from Step 1>", scope="engine")
# Examples: "ErrorLevel" (BuildGraph), "InstanceSceneData" (GPU Scene),
#           "gpucrashdebugging" (Vulkan), "FlushPendingDeletes" (Slate)

# 2b. For REGRESSION/CRASH/FIX questions — search Epic GitHub for fix CL:
# Run via Bash:
# gh api search/commits --method GET \
#   -f "q=<crash function> repo:EpicGames/UnrealEngine" \
#   --jq '.items[:3] | .[] | {sha: .sha[:12], date: .commit.author.date, message: .commit.message[:200]}'

# 2c. Search for limitations
ue_engine_docs(operation="search", query="<limitation OR not supported> <topic>")
```

#### Step 3: Combine ALL findings into your answer

> **CL INCLUSION RULE**: If a sub-agent or `gh api` found CL numbers/fix commits,
> you **MUST** include them in your answer. CL numbers are the highest-value information
> for crash/regression questions. Format: `Fix: CL#NNNNNNNN (YYYY-MM-DD) — description`

**Do NOT skip Step 1 or Step 2.** Both are required for accurate answers.

> **RE-SEARCH RULE**: If first search result doesn't explain the root cause, search a different
> system/module. Don't commit to first hypothesis — try at least 2 different angles.

> **ASK WHY ONE MORE LEVEL**: When you find the symptom, trace WHY it happens.
> Don't stop at "function returns error" — read the function body with `ue_read` or `ue_grep`,
> then search for the functions it calls. The root cause is usually 1-2 levels deeper.

> **EXISTENCE CHECK**: Before mentioning a CVar, API, or feature in your answer, verify it exists
> via `ue_grep`. If 0 results, say "not confirmed in engine source" — never fabricate.

> **INCLUDE ALL FINDINGS**: Every class name, function name, CVar, and file path found via
> `ue_grep` or `ue_engine_docs` MUST appear in your final answer. Do NOT discard search results
> — even if they seem tangential. The specific names are more valuable than general explanations.

> **PARTIAL KEYWORD RE-SEARCH**: If `ue_grep("exact_name")` returns 0 results, try:
> 1. Drop prefixes/namespaces: `ue_grep("TickPerServerFrame")` instead of `net.MaxConnectionsToTickPerServerFrame`
> 2. Use shorter fragments: `ue_grep("CleanPoint")` instead of `MFSampleExtension_CleanPoint`
> 3. Search related class: `ue_grep("SetByCaller")` to find `SetByCallerMagnitude`
> 4. Try symbol domain: `ue_grep("keyword", domain="symbols")` — PDB has 6M+ symbols
> Do NOT give up after one failed search. Try at least 3 variations before concluding "not found".
<!-- NarshaMCP:END -->