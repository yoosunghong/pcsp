# Persona Projection Audit

## Portfolio claim

The learned PCSP projection preserves a measurable, but deliberately compressed,
persona signal. On the fixed 240-train / 60-test v3 split, a train-only-tuned
linear probe recovers the five Big Five levels from projected embeddings at
`0.799` mean balanced accuracy (`0.333` chance), compared with `0.898` from the
raw Qwen embeddings.

This is not evidence that all semantic geometry is preserved. Pairwise cosine
similarities correlate only `rho=0.404` between the raw and projected spaces.
The 64-dimensional output has numerical rank 16, as required by its rank-16
factorization, and effective rank `3.87`. The policy therefore consumes a
strongly concentrated task representation rather than a general-purpose copy
of the language embedding.

## Per-axis held-out result

| Axis | Raw 1024-d | Projected 64-d | Delta |
| --- | ---: | ---: | ---: |
| Extraversion (E) | 0.800 | 0.733 | -0.067 |
| Neuroticism (N) | 0.815 | 0.735 | -0.080 |
| Agreeableness (A) | 0.941 | 0.757 | -0.184 |
| Conscientiousness (C) | 0.973 | 0.869 | -0.104 |
| Openness (O) | 0.958 | 0.903 | -0.056 |
| **Mean** | **0.898** | **0.799** | **-0.098** |

Agreeableness loses the most linearly recoverable information, while openness
and conscientiousness remain strongest. This identifies a concrete follow-up:
the projection should be checked against independent behavioral evidence before
claiming that every trait survives equally well.

![Projection audit](../../results/persona_projection_audit/projection_audit.png)

## Protocol

- Frozen embeddings: `results/embeddings/persona_embeddings_300.npy`.
- Projection: `results/pcsp_v3/full/policy.pt`.
- Split: `data/personas/train_240_v3.json` and `test_60_v3.json`.
- Probe: standardized multiclass ridge regression; regularization selected by
  deterministic stratified five-fold cross-validation on the training set only.
- Metrics: held-out balanced accuracy and macro F1.
- Spectral statistics use centered embeddings. Rank uses a relative `1e-6`
  singular-value threshold.

The probe is diagnostic, not a causal claim: the source persona text explicitly
describes these traits, and the audit measures linear recoverability rather than
whether the downstream policy actually acts on each dimension.

## Reproduction

From `research/`:

```powershell
conda run -n paper python scripts/audit_persona_projection.py
```

Machine-readable outputs are in `results/persona_projection_audit/`.
