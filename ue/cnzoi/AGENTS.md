# NarshaMCP MCP Tools for Unreal Engine Development

Quick reference for using NarshaMCP MCP server with OpenAI Codex.

---

## Quick Start

NarshaMCP provides **39 MCP tools** for Unreal Engine C++ and Blueprint development:
- **19 Policy Tools** - Domain-based operations (symbols, blueprints, gameplay, auth, etc.)
- **8 Sub-Tools** - Sequencer (4) + Editor (4) focused operations
- **6 Standalone Tools** - Universal search, workflow execution, task management

**Common Workflows**:
1. **Symbol Search** → `ue_analyze_symbols(operation="search_symbols", query="ACharacter")`
2. **Blueprint Analysis** → `ue_manage_blueprint(operation="get_structure", asset_path="/Game/BP_Player")`
3. **Error Auto-Fix** → `ue_fix_errors(mode="smart", error_message="C2065: undeclared")`
4. **Code Generation** → `ue_generate_code(operation="derive_class", base_class="ACharacter")`

---

## Policy Tools Reference

### 1. ue_analyze_symbols
**Purpose**: C++ symbol search, caller tracing, class hierarchy

**Key Operations**:
- `search_symbols` - Find symbols by pattern (50ms PDB-based)
- `find_callers` - Trace function callers recursively
- `get_methods` - List class methods with signatures
- `trace_hierarchy` - Get inheritance chain

**Example**:
```python
ue_analyze_symbols(
    operation="search_symbols",
    query="*Controller",
    symbol_type="class",
    project_root="E:/MyProject"
)
```

---

### 2. ue_trace_execution
**Purpose**: Blueprint execution flow tracing

**Key Operations**:
- `trace_execution_flow` - Follow node execution
- `trace_ability_flow` - GAS ability activation
- `trace_from_input` - Input → Ability → C++ flow

---

### 3. ue_manage_blueprint
**Purpose**: Blueprint analysis, creation, modification (48 operations)

**Smart Routing**: `operation="smart"` auto-detects intent from parameters

**Common Operations**:
- `get_structure` - Full Blueprint metadata
- `add_node` - Insert new node
- `connect_nodes` - Wire nodes together
- `create` - Generate new Blueprint

---

### 4. ue_manage_gameplay
**Purpose**: GameplayTag/GAS/Input management (15 operations)

**Smart Routing**: Auto-detects from `tag`, `ability_name`, or `input_action` parameters

**Decision Tree**:
- Find abilities by tag? → `search_tags` + `tag` parameter
- Trace ability activation? → `trace_abilities` + `ability_name`
- Find InputAction? → `find_input_action` + `ability_class`
- Trace key → ability → C++? → `trace_input_flow` + `input_action`

**Example**:
```python
ue_manage_gameplay(
    operation="trace_input_flow",
    input_action="IA_Jump",
    project_root="E:/MyProject"
)
```

---

### 5. ue_manage_ai
**Purpose**: StateTree + BehaviorTree unified management (23 operations)

**Usage**: `ai_type="statetree"` or `"behaviortree"`

**Operations**: `get_structure`, `modify_state`, `create`, etc.

---

### 6. ue_manage_pcg
**Purpose**: PCG analysis + modification (32 operations)

**Operations**: `get_structure`, `search_graphs`, `trace_flow`, `set_parameter`

---

### 7. ue_generate_code
**Purpose**: Boilerplate code generation (20 operations)

**V2 Operations** (PDB-based dynamic generation):
- `derive_class` - Generate from ANY UE class
- `suggest_class` - Get recommendations (no code)
- `scaffold_class` - Minimal skeleton
- `batch_class` - Multiple classes at once

**Example**:
```python
ue_generate_code(
    operation="derive_class",
    base_class="ACharacter",
    class_name="AMyHero",
    output_dir="Source/MyGame/Characters",
    features=["gas_setup"]
)
```

---

### 8. ue_fix_errors
**Purpose**: Auto error resolution + preflight (16 modes)

**Smart Mode** (RECOMMENDED): `mode="smart"` auto-routes based on parameters

**Modes**:
- `auto` - Auto-fix from build log
- `manual` - Fix specific error message
- `preflight` - Validate before compilation
- `dependency_check` - Validate asset references

**Example**:
```python
ue_fix_errors(
    mode="smart",
    error_message="C2065: 'AMyActor': undeclared identifier"
)
```

---

### 9-14. Other Policy Tools

- **ue_analyze_config** - Config search/modification
- **ue_check_health** - Server health status
- **ue_manage_material** - Material analysis + modification (18 ops)
- **ue_cache_control** - Cache management (23 ops)
- **ue_manage_niagara** - Niagara VFX analysis + modification (26 ops)
- **ue_analyze_insights** - Performance profiling (45 ops)
- **ue_manage_rigging** - Control Rig + IK Rig/Retargeter (25 ops)
- **ue_auth** - Authentication (4 ops)
- **ue_sequencer_structure** - Sequencer structure (20 ops, sub-tool)
- **ue_sequencer_tracks** - Track management (17 ops, sub-tool)
- **ue_sequencer_keyframes** - Keyframe operations (13 ops, sub-tool)
- **ue_sequencer_playback** - Playback control (22 ops, sub-tool)
- **ue_editor_actors** - Actor management (24 ops, sub-tool)
- **ue_editor_assets** - Asset operations (27 ops, sub-tool)
- **ue_editor_debug** - Debugging (23 ops, sub-tool)
- **ue_editor_automation** - Automation (25 ops, sub-tool)

---

## Standalone Tools

1. **ue_search_assets** - Universal asset search across all types
2. **ue_run_workflow** - Elite workflow executor for multi-step tasks
3. **ue_batch_editor_operations** - Batch editor command execution on one WebSocket session
4. **search_tool_docs** - Search tool documentation by keyword
5. **get_tool_docs** - Retrieve docs for a specific tool
6. **ue_engine_docs** - Engine documentation lookup

---

## Common Codex Workflows

### Workflow 1: Find All References to a Symbol

**Goal**: Trace who calls `ApplyDamage` function

**Steps**:
1. Search symbol:
   ```python
   ue_analyze_symbols(operation="search_symbols", query="ApplyDamage")
   ```

2. Find callers:
   ```python
   ue_analyze_symbols(operation="find_callers", function_name="ApplyDamage", recursive_depth=2)
   ```

**Output**: Call graph showing C++ → Blueprint → C++ chains

---

### Workflow 2: Fix Compilation Error

**Goal**: Auto-fix "C2065: undeclared identifier" error

**Steps**:
1. Smart mode (auto-routes to manual mode):
   ```python
   ue_fix_errors(mode="smart", error_message="C2065: 'AMyActor': undeclared identifier")
   ```

**Output**: Fixed code with 95%+ accuracy

**Supported Errors**: Missing includes, namespace issues, UPROPERTY errors, Blueprint references

---

### Workflow 3: Generate Lyra Character Class

**Goal**: Create production-ready character with GAS integration

**Steps**:
1. Derive class:
   ```python
   ue_generate_code(
       operation="derive_class",
       base_class="ACharacter",
       class_name="AMyHero",
       output_dir="Source/MyGame/Characters",
       features=["gas_setup"]
   )
   ```

**Output**:
- Complete .h + .cpp files
- PDB-validated includes
- Preflight-checked code
- 100% compilation success

---

## Codex-Specific Tips

### Tip 1: Use Smart Mode
Many tools support auto-routing:
- `ue_fix_errors(mode="smart")` - Detects error type
- `ue_manage_gameplay(operation="smart")` - Routes based on params
- `ue_manage_blueprint(operation="smart")` - Detects intent

### Tip 2: Leverage Resources API
Browse assets without tool calls:
- `blueprint://list` - All Blueprints
- `material://list` - All Materials
- `config://list` - All config sections

### Tip 3: Check Health First
Before running tools:
```python
ue_check_health(project_root="E:/MyProject")
```
Verifies: PDB index, metadata cache, server status

---

## Troubleshooting

### Issue: "PDB index not found"
**Solution**: Build project first to generate PDB files

### Issue: "Blueprint metadata not found"
**Solution**: Run `ue_check_health` to trigger background indexing (~30s)

### Issue: "Tool timeout"
**Solution**: Increase Codex timeout in settings (default 30s → 60s for modification tools)

---

## Performance Benchmarks

- **Symbol search**: 50ms (24x faster than Glob)
- **Blueprint metadata**: 100ms (500x faster than Commandlet)
- **Class hierarchy**: 100% accurate (PDB-based, not heuristic)
- **Error auto-fix**: 95%+ accuracy (12 fix strategies)
- **Code generation**: 1-3s (100% compilation success)

---

## Available Workflows (Skills)

NarshaMCP provides pre-built multi-tool workflows for complex tasks.
These are available as Claude Code Skills (`.claude/skills/`) and documented here for Codex users.

| Workflow | Purpose | MCP Tools Used |
|----------|---------|----------------|
| **Blueprint Flow Tracer** | Trace Input → Animation execution flow | `ue_manage_gameplay` + `ue_trace_execution` + `ue_analyze_symbols` |
| **Unreal Error Doctor** | Auto-diagnose and fix compilation errors | `ue_fix_errors` (smart mode) |
| **Module Mapper** | Resolve module dependencies and linker errors | `ue_analyze_symbols` + `ue_fix_errors` |
| **Performance Health Check** | Project-wide 5-category health analysis | `ue_check_health` + `ue_search_assets` + `ue_analyze_config` |
| **Caller Graph Visualizer** | Visualize call graphs with Mermaid diagrams | `ue_analyze_symbols` (find_callers) |
| **Asset Modification Wizard** | Safe bulk Blueprint/PCG modification | `ue_manage_blueprint` + `ue_manage_pcg` |
| **Execution Flow Explorer** | Bidirectional call graph tracing | `ue_analyze_symbols` + `ue_trace_execution` |

**For Codex users**: You can replicate these workflows by calling the listed MCP tools in sequence.

---

## Command to Skill Compatibility (Issue #5153)

Codex does not auto-load `.claude/commands/*.md`.
To expose workflows in Codex Skills UI, use skill folders under:

```text
$CODEX_HOME/skills/    # default: ~/.codex/skills/
```

Command parity mapping:

| Legacy Command | Codex Skill Folder | Primary Use |
|----------|----------|----------------|
| `ci-verify` | `ci-verify` | CI + issue-goal verification |
| `ci-monitor` | `ci-monitor` | CI status loop + auto-recovery monitoring |
| `deploy-test` | `deploy-test` | Release package -> install -> build -> MCP validation |
| `issue-find` | `issue-find` | Actionable issue triage |
| `issue-setup` | `issue-setup` | Issue prepare + assignee + branch |
| `issue-start` | `issue-start` | Setup + exploration + plan loop |
| `issue-verify` | `issue-verify` | Goal/evidence/test verification |
| `launch-editor` | `launch-editor` | Open Unreal Editor from `.env` |
| `mcp-analyze` | `mcp-analyze` | Session MCP usage analysis |
| `mcp-deploy` | `mcp-deploy` | Fast MCP binary deploy |
| `ns-review` | `ns-review` | Unified review + auto-fix loop |
| `plan-review` | `plan-review` | Iterative plan scoring loop |
| `status` | `status` | Branch/issue progress status report |
| `test-iterate` | `test-iterate` | Edge-case iteration until clean-pass target |
| `test-run` | `test-run` | Smart test routing and verification |

Example prompts in Codex:
- "Use issue-start skill for issue 5153 with target 9.5."
- "Run issue-verify in strict mode for current branch."
- "Use ci-verify for issue 5153 and show unmet goals."
- "Run ns-review in strict mode and report unresolved risks."
- "Use test-iterate for MCP tool edge-case bug hunting."

---

## Additional Resources

- GitHub: https://github.com/Next-Stage-Inc/ue-code-mcp
- Policy Tools Guide: docs/POLICY_TOOLS_OVERVIEW.md
- Tool Reference: docs/TOOL_REFERENCE.md
- Codex Setup: docs/getting-started/platforms/CODEX_SETUP.md
