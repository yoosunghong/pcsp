# NarshaMCP MCP Server - Antigravity Workspace Rules

Project-specific rules for Google Antigravity integration with NarshaMCP MCP server.

---

## Project Context

This is an **Unreal Engine project** with NarshaMCP MCP integration, providing:
- **36+ MCP tools** for C++ and Blueprint development
- **PDB-based symbol search** (50ms response time, 24x faster)
- **Binary parser** for Blueprint/Material/PCG metadata (100-2,500x faster)
- **Auto error resolution** with 95%+ accuracy
- **Code generation** from templates with 100% compilation success

---

## Available Tools

### Analysis Tools (6)

1. **ue_analyze_symbols** - C++ symbol search, call graph, hierarchy
   - Use for: Symbol discovery, caller tracing, class analysis
   - Key operations: `search_symbols`, `find_callers`, `get_methods`

2. **ue_trace_execution** - Blueprint execution flow tracing
   - Use for: Debugging Blueprint logic, GAS ability tracing
   - Key operations: `trace_execution_flow`, `trace_ability_flow`

3. **ue_manage_blueprint** - Blueprint CRUD (66 operations)
   - Smart routing: `operation="smart"` auto-detects intent
   - Use for: Blueprint analysis, node manipulation, creation

4. **ue_manage_gameplay** - GameplayTag/GAS/Input (17 operations)
   - Smart routing: tag → search, ability → trace, input → flow
   - Use for: GAS development, input binding, tag management

5. **ue_manage_ai** - StateTree/BehaviorTree/EQS (33 operations)
   - Unified interface: `ai_type="statetree"` or `"behaviortree"`
   - Use for: AI analysis, state modification, tree creation

6. **ue_manage_pcg** - PCG analysis + modification (32 operations)
   - Use for: Procedural content pipeline development
   - Key operations: `get_structure`, `search_graphs`, `trace_flow`

### Workflow Tools (4)

7. **ue_fix_errors** - Auto error resolution (20 operations)
   - Smart mode: `mode="smart"` auto-routes based on params
   - Use for: Compilation errors, preflight checks, dependency validation

8. **ue_generate_code** - Boilerplate generation (21 operations)
   - V2 operations: `derive_class`, `suggest_class`, `scaffold_class`
   - Use for: Class generation, module setup, plugin scaffolding

9. **ue_analyze_config** - Config search/modification
   - Use for: Console variable management, ini file editing

10. **ue_check_health** - Server health status
    - Use for: Pre-flight checks, troubleshooting

### Additional Policy Tools (9)

11. **ue_manage_material** - Material CRUD (18 operations)
    - Use for: Material analysis, parameter tuning, shader debugging

12. **ue_cache_control** - Cache management (29 operations)
    - Use for: Performance optimization, cache invalidation, path validation

13. **ue_manage_niagara** - Niagara VFX (26 operations)
    - Use for: Particle systems, emitter management, parameter tuning

14. **ue_analyze_insights** - Insights profiling (45 operations)
    - Use for: CPU/GPU bottleneck analysis, trace comparison, optimization

15. **ue_manage_rigging** - Control Rig + IK Rig/Retargeter (25 operations)
    - Use for: Animation rig analysis, node editing, IK solver/goal/chain inspection (use `rig_type` param)

16. **ue_build_pipeline** - Build/Cook/Package (9 operations)
    - Use for: Editor builds, cooking, packaging, commandlet execution

17. **ue_manage_project_ops** - World Partition/DDC/SC (27 operations)
    - Use for: WP status, DDC health, source control operations

18. **ue_analyze_source** - C++ source analysis: macros, preprocessor, patterns (10 operations)
    - Use for: UE_LOG/DOREPLIFETIME macro analysis, replication cross-check, state machine tracing

19. **ue_diff** - Cross-check and mismatch detection (5 operations)
    - Use for: Replication audit, class hierarchy delta, config comparison, override cascade

### Sub-Tools (8)

- **ue_sequencer_structure** (19 ops) - Sequencer structure analysis
- **ue_sequencer_tracks** (17 ops) - Track management
- **ue_sequencer_keyframes** (13 ops) - Keyframe operations
- **ue_sequencer_playback** (22 ops) - Playback control
- **ue_editor_actors** (24 ops) - Actor manipulation in level
- **ue_editor_assets** (27 ops) - Asset management and compilation
- **ue_editor_automation** (28 ops) - Editor automation/testing
- **ue_editor_debug** (23 ops) - Runtime debugging and inspection

### Standalone Tools (8)

20. **ue_search_assets** - Universal asset search
21. **ue_run_workflow** - Workflow executor
22. **ue_batch_editor_operations** - Batch WebSocket operations
23. **ue_tool_docs** - Tool documentation search and retrieval
24. **ue_engine_docs** - UE engine documentation
25. **ue_glob** - File pattern matching (Content/ + Source/ + Config/)
26. **ue_grep** - Source code text search (project + plugin + engine)
27. **ue_read** - Source file reading with symbol context

### Hidden Tools (7)

- **cancel_task** - Cancel specific task
- **list_active_tasks** - List all active tasks
- **cancel_all_tasks** - Cancel all tasks
- **get_task_status** - Get task status
- **get_task_result** - Get task result
- **list_tasks** - List tasks
- **ue_marketplace** - Skill marketplace search and install

---

## Tool Selection Quick Reference

<!-- Source: .claude/agents/unreal-specialist.md — sync when specialist is updated -->

Route queries to the correct tool based on asset/entity patterns:

| Pattern | Tool | Example Operation |
|---------|------|-------------------|
| `*Controller`, `A*`, `U*` | `ue_analyze_symbols` | `search_symbols`, `find_callers` |
| `BP_*`, `GA_*`, `BPC_*` | `ue_manage_blueprint` | `get_structure`, `add_node` |
| `M_*`, `MI_*`, `MF_*` | `ue_manage_material` | `search_materials`, `set_parameter` |
| `LS_*`, `CIN_*` | `ue_sequencer_structure` | `get_structure`, `list_sequences` |
| `ST_*`, `BT_*` | `ue_manage_ai` | `get_structure`, `modify_state` |
| `NS_*`, VFX | `ue_manage_niagara` | `search_systems`, `set_parameter` |
| `r.*`, `*.ini` | `ue_analyze_config` | `search_config`, `modify_config` |
| PCG query | `ue_manage_pcg` | `get_structure`, `search_graphs` |
| `.utrace` | `ue_analyze_insights` | `smart_analyze` |
| UE macros (`UE_LOG`, `DOREPLIFETIME`) | `ue_analyze_source` | `find_macro_invocations`, `cross_check` |
| Replication audit, config diff | `ue_diff` | `replication_audit`, `compare_configs` |
| Compile error | `ue_fix_errors` | `mode="smart"` (recommended) |
| Editor control | `ue_editor_*` | `capture_screenshot`, `spawn_actor` |

### Common Tool Selection Mistakes

| Wrong | Correct |
|-------|---------|
| `ue_analyze_config` for `M_*` queries | `ue_manage_material` |
| `ue_analyze_symbols` for `BP_*` queries | `ue_manage_blueprint` |
| `ue_manage_blueprint` for `LS_*` queries | `ue_sequencer_structure` |
| Filesystem paths (`C:\...`) | Unreal asset paths (`/Game/...`) |

### Multi-Tool Orchestration Skills

For tasks requiring 2+ tool calls in sequence, use workflow skills:
- **material-analysis** — Material structure + hierarchy + performance metrics
- **pcg-workflow** — PCG batch audit, asset migration, graph cloning
- **blueprint-flow** — Blueprint structure + execution tracing
- **ue-dev-cycle** — Analyze → implement → build → fix loop
- **caller-graph-visualizer** — Refactoring safety via call graph analysis

---

## Workflow Guidelines (Gemini 3 Pro Optimized)

### Task Decomposition Strategy

When handling complex UE development tasks, follow this 4-phase approach:

**1. Discovery Phase** (use analysis tools)
- Identify symbols: `ue_analyze_symbols`
- Understand structure: `ue_manage_blueprint`, `ue_manage_ai`
- Check dependencies: `ue_fix_errors(mode="dependency_check")`

**2. Planning Phase** (analysis + artifacts only — NO modifications)
- Create markdown plan artifact: "Generate implementation plan for [feature]"
- Use Antigravity's task lists to track progress
- Break down into subtasks with dependencies
- **Allowed**: `ue_analyze_symbols`, `ue_check_health`, `ue_trace_execution`, `ue_search_assets`, `ue_analyze_config`, `ue_analyze_insights`, `ue_engine_docs`, and any read-only operation (`get_structure`, `search_*`, `list_*`, `get_*`)
- **Forbidden**: `ue_generate_code`, `ue_fix_errors(auto)`, `ue_manage_*(add_node/set_parameter/create)`, `ue_editor_actors(spawn/delete)`, or any operation that writes/modifies project state

**3. Implementation Phase** (use modification tools)
- Generate code: `ue_generate_code`
- Modify assets: `ue_manage_blueprint`, `ue_manage_material`
- Validate changes: `ue_fix_errors(mode="preflight")`

**4. Verification Phase** (use health checks)
- Check health: `ue_check_health`
- Run tests: `ue_editor_assets(operation="compile_blueprints")`
- Visualize results: `ue_editor_debug(operation="draw_debug")`

---

### Phase Behavior (task_boundary)

NarshaMCP workflows follow a strict plan-then-execute pattern. This maps to
Antigravity's task boundary concept:

**task_boundary: plan**
- **Goal**: Understand the problem and generate an implementation plan
- **Permitted**: All analysis/read-only tools (`ue_analyze_symbols`, `ue_check_health`,
  `ue_trace_execution`, `ue_search_assets`, `ue_analyze_config`, `ue_analyze_insights`,
  `ue_engine_docs`, and any `get_*`/`search_*`/`list_*` operation)
- **Forbidden**: Any tool call that creates, modifies, or deletes project artifacts
  (code files, Blueprints, Materials, actors, configs)
- **Output**: Markdown artifact with implementation steps, file paths, and dependencies

**task_boundary: execute**
- **Goal**: Implement the plan from the previous phase
- **Permitted**: All tools, including modification tools
- **Prerequisite**: A plan artifact must exist before entering execute phase
- **Pattern**: Follow plan steps sequentially, validate after each major change
  using `ue_fix_errors(mode="preflight")` or `ue_check_health`

**task_boundary: verify**
- **Goal**: Confirm implementation correctness
- **Permitted**: Analysis tools + `ue_fix_errors(mode="preflight")` +
  `ue_editor_assets(operation="compile_blueprints")`
- **Forbidden**: New modifications (only fixes for failed verifications)

---

### Artifact Generation Best Practices

Antigravity excels at markdown artifact generation. Leverage for:

**1. Implementation Plans**
- Break complex features into numbered steps
- Include file paths, class names, function signatures
- Mark dependencies between steps

**2. Code Review Summaries**
- Document changes across multiple files
- Highlight architectural decisions
- Track technical debt items

**3. Testing Checklists**
- Verification steps for each feature
- Edge cases to validate
- Performance benchmarks to measure

**4. Migration Guides**
- Blueprint → C++ conversion steps
- Deprecation warnings
- Breaking change documentation

**5. Architecture Diagrams**
- Use Mermaid for system visualizations
- Class hierarchy diagrams
- Data flow diagrams

**Example Prompt**:
```text
Generate a detailed implementation plan (as artifact) for adding a new GAS ability.
Include:
- Required classes and files
- GameplayTag setup
- Input binding configuration
- Testing checklist
```

---

### Gemini 3 Pro Deep Think Mode

For complex UE architecture questions, enable Deep Think mode:

**Use Cases**:
- Designing GAS ability inheritance hierarchy
- Optimizing Blueprint execution flow
- Planning PCG graph architecture
- Analyzing material shader performance
- Refactoring large C++ class hierarchies

**Pattern**:
```text
[Deep Think] Design a scalable GameplayAbility system for 100+ abilities.
Consider: memory usage, activation cost, tag organization, modularity, network replication.
```

**Benefits**:
- Longer reasoning time for complex decisions
- More thorough analysis of trade-offs
- Better architectural recommendations

---

## Google Cloud Integration Potential

Antigravity has native Google Cloud MCP integration. Combine with NarshaMCP for enterprise workflows:

### Firebase Integration
```text
# Store UE symbol index in Firestore for team sharing
# Query Blueprint metadata via Firebase MCP
# Real-time collaboration on project configurations
```

**Setup**: Add Firebase MCP server alongside uecodegen in `~/.gemini/antigravity/mcp_config.json`

### BigQuery Integration
```text
# Analyze asset metadata at scale
# Query performance metrics from CI/CD builds
# Generate reports on Blueprint complexity trends
```

**Use Case**: Track technical debt over time, optimize asset usage patterns

### AlloyDB for PostgreSQL
```text
# Store project metadata centrally for multi-project queries
# Team collaboration on UE codebases
# Historical symbol search across versions
```

**Use Case**: Enterprise teams with multiple UE projects

---

## Common Patterns

### Pattern 1: Trace Input → Ability → C++ Flow

**Goal**: Understand complete input handling path

**Workflow**:
1. Find input action:
   ```python
   ue_manage_gameplay(operation="find_input_action", ability_class="GA_Jump")
   ```

2. Trace flow:
   ```python
   ue_manage_gameplay(operation="trace_input_flow", input_action="IA_Jump")
   ```

3. Analyze C++ code:
   ```python
   ue_analyze_symbols(operation="search_symbols", query="HandleJump")
   ```

**Artifact**: Create flow diagram in markdown showing Input → InputMapping → Ability → C++ → Gameplay Effect

---

### Pattern 2: Material Performance Analysis

**Goal**: Optimize material shader complexity

**Workflow**:
1. Search materials:
   ```python
   ue_manage_material(operation="search_materials", query="M_*", limit=10)
   ```

2. Get shader nodes:
   ```python
   ue_manage_material(operation="get_nodes", material_path="/Game/Materials/M_Character")
   ```

3. Analyze complexity:
   - Count node types
   - Identify expensive operations (sine, cosine, texture samples)
   - Check instruction count

4. **Generate artifact**: Performance report with recommendations

---

### Pattern 3: Blueprint → C++ Migration

**Goal**: Convert Blueprint logic to optimized C++

**Workflow**:
1. Get Blueprint structure:
   ```python
   ue_manage_blueprint(operation="get_structure", asset_path="/Game/BP_Character")
   ```

2. Analyze execution flow:
   ```python
   ue_trace_execution(operation="trace_execution_flow", blueprint_path="/Game/BP_Character")
   ```

3. Generate C++ class:
   ```python
   ue_generate_code(operation="derive_class", base_class="ACharacter", class_name="AMyCharacter")
   ```

4. Port logic manually (guided by Blueprint structure)

5. Validate:
   ```python
   ue_fix_errors(mode="preflight", file_paths=["Source/MyGame/MyCharacter.cpp"])
   ```

**Artifact**: Migration checklist with function mappings (Blueprint node → C++ function)

---

## Performance Expectations

Set Antigravity timeouts appropriately for UE development:

| Tool | Typical Time | Recommended Timeout |
|------|--------------|---------------------|
| ue_analyze_symbols | 50-100ms | 10s |
| ue_manage_blueprint | 100-200ms | 20s |
| ue_trace_execution | 200-500ms | 30s |
| ue_fix_errors | 500-2000ms | 60s |
| ue_generate_code | 1-3s | 90s |
| ue_editor_actors/assets/automation/debug | 500-5000ms | 120s (WebSocket roundtrip) |

**Note**: Increase timeouts for large projects (>10GB assets)

---

## Troubleshooting

### Issue: "PDB index not found"
**Symptom**: Symbol search returns no results

**Solution**:
1. Build project to generate PDB files
2. Run `ue_check_health(project_root="E:/MyProject")`
3. Verify PDB files exist in `Intermediate/Build/Win64/`

---

### Issue: "Blueprint metadata not cached"
**Symptom**: Blueprint tools return "metadata not found"

**Solution**:
1. Wait for background indexing (~30s on first run)
2. Check `ue_check_health` → metadata status should show "indexed"
3. If persistent, rebuild project

---

### Issue: "Tool timeout"
**Symptom**: Antigravity reports timeout errors

**Solution**:
1. Increase timeout in Antigravity settings
2. Default 30s → Recommended 60s for modification tools
3. For editor control: 120s (WebSocket can be slow)

---

### Issue: "Editor not responding to control commands"
**Symptom**: `ue_editor_automation`/`ue_editor_actors` returns errors

**Solution**:
1. Verify Editor is running with Remote Control plugin enabled
2. Check WebSocket connection: `http://localhost:30010/remote/info`
3. Restart Editor if connection lost

---

## Additional Resources

- **GitHub Repository**: https://github.com/Next-Stage-Inc/ue-code-mcp
- **Policy Tools Overview**: docs/reference/POLICY_TOOLS_OVERVIEW.md
- **Antigravity Setup Guide**: docs/getting-started/platforms/ANTIGRAVITY_SETUP.md
- **Tool Reference**: docs/reference/TOOL_REFERENCE.md
- **Performance Benchmarks**: docs/technical/performance/PERFORMANCE.md

---

## Notes for Gemini 3 Pro

**Strengths** (leverage these):
- Long-context understanding (handle large Blueprint graphs)
- Multimodal reasoning (analyze screenshots from `capture_screenshot`)
- Agentic workflows (multi-step tasks with artifact generation)
- Integration with Google Cloud services

**Best Practices**:
- Use artifacts for all planning and documentation
- Enable Deep Think for architectural decisions
- Combine NarshaMCP tools with Google Cloud MCP servers for enterprise workflows
- Generate Mermaid diagrams for complex system visualizations
