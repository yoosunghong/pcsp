# Portfolio Visual Evidence

This page separates measured performance evidence from architectural runtime
proof. Every figure is generated from a checked-in JSON artifact; no value is
transcribed into an image by hand.

## Persona Conditioning Ablation

![Persona conditioning ablation](assets/persona-ablation-evidence.png)

The hybrid PCSP stack with persona input preserves distinct action patterns
while completing more interactions and nearly eliminating movement failures.
Removing only the persona input makes the agents' action distributions almost
identical even though the rest of the runtime remains unchanged.

Source:
[`research/results/ue_sessions/ablation_20260518_154827/ablation.json`](../../../../research/results/ue_sessions/ablation_20260518_154827/ablation.json)

## Actor / Behavior Tree Scaling Ceiling

![Actor and Behavior Tree scaling evidence](assets/actor-scaling-evidence.png)

The visible three-seed Actor baseline stays inside the 60 FPS frame budget
through 96 agents on average, but movement reliability begins to degrade above
64. At 128 agents, frame p95 crosses 16.67 ms and movement failure reaches
44.9%. ONNX inference remains a sub-millisecond cost, so the evidence points to
navigation request bursts and affordance contention as the first hard ceiling.

Source:
[`research/results/ue_sessions/scaling_20260520/scaling_curve.json`](../../../../research/results/ue_sessions/scaling_20260520/scaling_curve.json)

## 1,024-NPC Hybrid Runtime Proof

![Mass hybrid runtime proof](assets/mass-hybrid-runtime-proof.png)

The compatibility smoke verifies that the shared PCSP intent path, Actor hero
tier, Mass background tier, and all three telemetry streams execute together at
1,024 total NPCs. The test ran offscreen and was throttled, so its frame timing
is deliberately excluded from the figure and from portfolio performance claims.

Source:
[`research/results/ue_sessions/mass_smoke_20260831/per_session.json`](../../../../research/results/ue_sessions/mass_smoke_20260831/per_session.json)

## Visible 128–1,024 NPC Mass Scaling

![Visible Mass scaling evidence](assets/mass-scaling-evidence.png)

The visible UE 5.8 standalone sweep completed 12/12 runs across four population
sizes and three seeds. From 128 to 1,024 NPCs, frame p95 changes from 29.90 to
30.15 ms while the 1,024-NPC hero tier records zero movement failures. The
absolute frame time remains above the 16.67-ms target, so the figure supports a
bounded incremental-cost claim rather than a 60-FPS claim.

Source:
[`research/results/ue_sessions/mass_scaling_20260901/scaling_curve.json`](../../../../research/results/ue_sessions/mass_scaling_20260901/scaling_curve.json)

## Reproducing The Figures

From the repository root:

```powershell
conda run -n paper python ue/cnzoi/tools/generate_portfolio_visuals.py
```

The script writes both PNG previews and vector SVG masters to
`ue/cnzoi/docs/portfolio/assets/`.

## Capture Work Still Required

The static evidence layer and visible Mass sweep are complete. Remaining
portfolio visuals require targeted capture work:

1. Capture Unreal Insights CPU, render, navigation, Mass, and memory tracks.
2. Capture the portfolio map at 16-agent close-up, 64-agent crowd, persona
   contrast, congestion recovery, and 1,024-NPC wide shots.
3. Record the HUD/camera demo sequence and edit the final video.
