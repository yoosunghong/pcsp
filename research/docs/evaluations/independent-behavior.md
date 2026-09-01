# Independent Behavioral Trait Evaluation

## Outcome

The independent evaluator does **not** reproduce the large advantage for the
full PCSP objective seen by the model-internal trajectory-embedding metric.
Using action statistics only, held-out mean Big Five balanced accuracy is
`0.482` for full PCSP and `0.511` for no-consistency. The paired bootstrap 95%
interval for full minus no-consistency is `[-0.056, -0.002]`, and a paired
persona-level randomization test gives `p=0.050`.

Adding state summaries and state-action response features raises absolute
scores but does not separate the variants: `0.556` full versus `0.558`
no-consistency, delta interval `[-0.033, 0.030]`, `p=0.875`.

The defensible portfolio conclusion is therefore narrower than the earlier
internal metric suggested: InfoNCE is load-bearing for alignment between the
learned trajectory encoder and persona projection, but this experiment does
not show that it improves independently observable Big Five behavior.

![Independent behavior evaluation](../../results/independent_behavior_v3_large/independent_behavior_eval.png)

## Frozen protocol

- Policies: v3-large `full` and `no_consist`, seeds 42/43/44.
- Personas: first 320 training personas for evaluator fitting, remaining 80
  training personas for calibration, and 100 policy-held-out personas for the
  final evaluator test.
- Rollouts: one 200-step trajectory per persona, policy seed, and variant;
  3,000 trajectories total.
- Primary features (`445`): 20-way action histogram, 20x20 transition matrix,
  per-action run lengths, and semantic action-group autocorrelation.
- Secondary features (`749`): primary features plus ego observation summaries
  and action-conditioned need deltas.
- Evaluator: a single standardized, class-balanced ridge probe per Big Five
  axis, trained on both variants so the comparison uses identical weights.
  Regularization and temperature use only the calibration personas.
- Uncertainty: 1,000 persona-cluster bootstrap resamples and 1,000 paired
  persona-level variant randomizations.

The evaluator module has no import path to the PCSP policy, persona projection,
policy logits, or learned trajectory encoder. The rollout script imports the
policy only to produce actions, then passes observation/action sequences into
the frozen feature extractor.

## Per-axis action-only results

| Axis | Full | No consistency |
| --- | ---: | ---: |
| E | 0.869 | 0.978 |
| N | 0.428 | 0.414 |
| A | 0.492 | 0.497 |
| C | 0.243 | 0.274 |
| O | 0.381 | 0.394 |

Most of the independently recoverable action-only signal is extraversion.
Conscientiousness is below chance after the train-to-held-out distribution
shift, so the mean score must not be presented as uniform five-trait fidelity.

## Reproduction

From `research/`:

```powershell
conda run -n paper python scripts/test_independent_behavior.py
conda run -n paper python scripts/run_independent_behavior_eval_v3_large.py --device cuda
```

Subsequent evaluator-only runs can add `--reuse-cache`. Results, frozen feature
schema, evaluator weights, predictions, and the compressed feature cache are in
`results/independent_behavior_v3_large/`.
