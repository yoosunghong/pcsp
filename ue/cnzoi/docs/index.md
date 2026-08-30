# CNZOI UE5 Documentation

Project docs for the UE5 side of PCSP. See `PLAN.md` for the active task roadmap and `DONE.md` for the decision log.

| Doc | Contents |
|---|---|
| [phase1-editor-setup.md](phase1-editor-setup.md) | Step-by-step UE5 editor guide for Phase 1 project settings, NavMesh, affordance zones, Blackboard, Behavior Tree, Blueprint subclasses |
| [affordance-system.md](affordance-system.md) | Architecture of the three-layer affordance system: action space (20), affordance categories (11), and gameplay tags |
| [phase0/research-environment-summary.md](phase0/research-environment-summary.md) | What the Python Mini-Inzoi v3 environment provides: action ontology, observation schema, reward, persona splits, and the ONNX I/O contract |
| [phase0/affordance-taxonomy.md](phase0/affordance-taxonomy.md) | Canonical 10-category roster, per-zone capacity targets, and capacity provenance from Phase 4 stress runs |
| [phase0/bt-blackboard-policy-contract.md](phase0/bt-blackboard-policy-contract.md) | Wire format between policy, blackboard, and behavior tree: every key, every reader/writer, every contract |
| [phase0/scale-targets.md](phase0/scale-targets.md) | Empirical confirmation of Debug/Main/Stress scale targets with reference runs |
| [portfolio/README.md](portfolio/README.md) | UE5 portfolio engineering roadmap and artifact index |
| [portfolio/mass-1024-scaling.md](portfolio/mass-1024-scaling.md) | Measured Actor/NavMesh ceiling, bounded path admission, Mass-hybrid implementation, and 1,024-NPC benchmark plan |
| [portfolio/diagrams.md](portfolio/diagrams.md) | Architecture and runtime data-flow diagrams (Mermaid) |
| [portfolio/demo-video-hud-plan.md](portfolio/demo-video-hud-plan.md) | Portfolio capture scenario plus nearest-agent camera focus and HUD UI structure |
