# UE Actor/Mass Simulation-Tier Behavior Audit

## Outcome

The frozen action-only evaluator now runs directly on canonical UE telemetry.
A 300-second visible UE 5.8 standalone validation used 16 Actor/Behavior Tree
agents and 112 Mass agents with the same 16 sampled persona IDs. The active
export was `no_consist`, seed 7.

Across the 16 paired personas, Actor and Mass action distributions have mean
Jensen--Shannon divergence `0.066` (median `0.051`), and their five-axis trait
predictions agree `71.25%` of the time. The frozen probe's mean balanced
accuracy is `0.458` for Actor trajectories and `0.571` for Mass trajectories.
The paired Mass-minus-Actor delta is `+0.113`, cluster-bootstrap 95% interval
`[+0.013, +0.218]`, paired randomization `p=0.027`.

![UE tier behavior audit](../results/ue_sessions/tier_behavior_20260901_044431/ue_behavior_tier_eval.png)

This single run shows that the Mass tier does not automatically erase the
policy's action-level persona signal. It does **not** establish that Mass is
intrinsically more persona-faithful: Mass produced about twice as many sampled
decisions per persona (62.1 vs 31.8), executes a different movement/interaction
loop, and the evaluator was fitted in Mini-Inzoi rather than UE. A full claim
requires full-PCSP and no-consistency runs across multiple UE seeds with matched
decision windows.

## Telemetry contract

- Actor decision rows now emit `policy_action_index`, the 0--19 index before
  Unreal maps movement outputs to semantic execution actions.
- Mass logs the lowest 16 stable-index entities by default to
  `mass_trajectories.jsonl`; `pcsp.MassTrajectorySampleCount 0` disables it.
- Each Mass row contains time, stable index, persona ID, canonical policy action
  index, executed action name, position, and eight needs.
- The Mass logger batches sampled rows into the existing one-second telemetry
  flush, avoiding a file write for every decision.
- `scripts/evaluate_ue_behavior_tiers.py` consumes only chosen action indices
  for the primary frozen probe. Logged logits are retained for other analysis
  but are not evaluator features.

## Validation evidence

- `cnzoiEditor Win64 Development` compiled successfully on UE 5.8.
- Standalone session `20260901_044431` exited with code 0 after 322 seconds.
- It produced 16 Actor files with explicit action indices and 993 sampled Mass
  decision rows covering all 16 paired personas.
- The checked-in result directory includes a compact canonical copy of the
  source decisions, predictions, metrics, and PNG/SVG figure so the audit does
  not depend on ignored Unreal `Saved/` files.

## Reproduction

From `research/`:

```powershell
conda run -n paper python scripts/evaluate_ue_behavior_tiers.py `
  --session ../ue/cnzoi/Saved/PCSP/Logs/<session> `
  --output results/ue_sessions/tier_behavior_<session>
```
