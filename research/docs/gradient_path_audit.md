# PCSP Gradient-Path Audit

## Outcome

The trainer now optionally records per-loss, per-module gradient L2 norms using
`torch.autograd.grad` immediately before each optimizer step. The diagnostic is
off by default, so ordinary training cost and checkpoint format are unchanged.

On the trained v3-large full seed-42 checkpoint, every expected path is present
and every forbidden direct path is zero:

| Loss | Persona projection | Actor | Critic | Trajectory encoder |
| --- | ---: | ---: | ---: | ---: |
| PPO composite | 2.69e+2 | 1.21e+0 | 2.90e+2 | 0 |
| Consistency (weighted) | 7.87e-1 | 0 | 0 | 3.75e+0 |
| Diversity (weighted) | 4.87e-4 | 1.82e-4 | 0 | 0 |

![Gradient-path audit](../results/gradient_path_audit/gradient_paths.png)

This clarifies the causal interpretation of the objectives. InfoNCE does not
directly update the actor head; it changes behavior only indirectly through the
shared persona projection. Diversity is the only auxiliary loss with a direct
actor path, but under the configured `lambda_diversity=0.01` its measured norm
is roughly three orders of magnitude below the weighted consistency path in
this probe.

The absolute norms are not effect sizes. PPO uses a different projection
learning rate, gradients are clipped before stepping, and the losses operate on
different batches. The audit proves wiring and gives a scale diagnostic; it
does not replace an intervention or behavioral ablation.

## Implementation

- `PCSPConfig.log_attributable_gradients` defaults to `False`.
- When enabled, `PCSPTrainer.update` adds `gradient_norms` for `ppo`,
  `consistency`, and `diversity` to each iteration metric.
- Module groups are persona projection, actor, critic, and trajectory encoder.
- `allow_unused=True` makes absent paths explicit zeros rather than errors.
- The contract test perturbs the identity-initialized FiLM weights before
  checking PPO/diversity topology; at initialization, zero FiLM conditioning
  weights legitimately block those projection gradients until warm-up.

## Reproduction

From `research/`:

```powershell
conda run -n paper python scripts/test_gradient_paths.py
conda run -n paper python scripts/audit_gradient_paths.py --device cuda
```
