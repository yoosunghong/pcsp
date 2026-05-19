# Tier 1 Progress — 2026-05-19

Writing-only pass executed on [main.tex](../../paper/cog2026_vision/main.tex).
Compiles cleanly to 12 pages.

## Completed (writing)

- **T1.1 Restructure.** §1.3 rewritten to the new 6-item three-layer
  contributions list. §3 split: method-only opener; environment description
  moved out. New §4 *Evaluation Strategy: A Three-Layer Validation Stack*
  inserted with Layer 1/2/3 framing and per-layer protocols (§4.4 absorbs the
  old evaluation-protocol subsection). §5 retitled *Layer 1 Results:
  Mechanistic Validation*. §6 retitled *Layer 2 Results: Cross-Substrate
  Generalization (Melting Pot)*. §7 retitled *Layer 3 Results: Realtime Engine
  Deployment (UE5)*.
- **Paste A** (PCSP-Diagnostic naming + "microscope, not a world" reframe)
  applied in new §4.1.
- **Paste B** (Limitations rewrite — "deliberate minimality of Layer 1")
  applied in §9.
- **Paste C** (Melting Pot opening) applied in §6; "preliminary external
  check" language removed.
- **Paste D** (UE5 §7 opening) applied.
- **T1.5 ρ-drop reframe.** New §7.6 *Failure analysis and contention*
  promotes the ρ-drop from limitation to a Layer-3 finding; §9 entry now
  points to §7.6 rather than duplicating it.
- **Rename.** Mini-Inzoi → \PCSPD across the draft; one parenthetical
  legacy mention in the abstract and one in §4.1.
- **Appendix.** v1/v2 learning curves (Fig 2), `tab:results_v1`,
  `tab:results_v2`, `fig:zeroshot`, and `fig:kl` relocated to a new
  Appendix A (`app:v1v2`). Cross-references resolve.

## Second pass — 2026-05-19 (T1.2 launch + T1.3/T1.5/T1.6 partial)

- **T1.2 (complete).** Multi-substrate sweep finished:
  `research/meltingpot/runs/t1_2/{clean_up,prisoners_dilemma_in_the_matrix__repeated}/`,
  3 seeds × {full, no\_infonce} × 1M env-steps per substrate (12/12 runs).
  Aggregated to `research/meltingpot/runs/t1_2_summary.json`. New
  `tab:mp_multi` (replaces single-substrate `tab:mp_clean`) lists all three
  substrates with mean$\pm$std over seeds; §6 rewritten with multi-substrate
  framing and the takeaway paragraph now quantifies the consistency-loss
  collapse pattern in every substrate (top-1 0.564/0.690/0.625 → 0.071/0.095/0.125,
  KL holding or inflating). Contributions §1.3 updated to drop the single-
  substrate language.

  Headline numbers (1M env-steps, 10 train personas, chance top-1 = 0.10):
  - `commons_harvest__open` (5 seeds full / 1 seed abl): top-1 0.564 → 0.071
  - `clean_up`              (3 seeds each):              top-1 0.690 → 0.095
  - `prisoners_dilemma_…__repeated` (3 seeds each):      top-1 0.625 → 0.125
- **T1.3 (partial).** New `tab:ue5_scaling` placed in §7 with the three
  validated scales (16/32/64 from existing sessions) plus the latency-budget
  paragraph (0.5 s decision throttle, ≤2 ONNX calls/agent/s, ≤128 calls/s
  at 64 agents, 30–60 FPS PIE wall budget). 8 / 96 / 128 agent points
  flagged inline as `% TODO(T1.3)` — those need new PIE runs.
- **T1.5 (partial).** New `tab:ue5_failures` BT-abort taxonomy in §7.6,
  drawn directly from `research/results/ue_sessions/*/summary.json`
  failure_reason_totals (FindBestZone, zone_no_free_interaction_point,
  path_follow_idle_short) across HybridPCSP / held-out / NoConsist /
  HybridNoPersona / BTOnly. Contention heatmap and
  expressed-vs-preferred chart still need per-tick zone-occupancy and
  per-persona logit dumps; left as `% TODO(T1.5)`.
- **T1.6.** Replaced the placeholder matrix table with a real TikZ
  three-layer schematic (`fig:three_layer`) plus an expanded
  `tab:layer_matrix` (Layer × Substrate × Question × Personas × Metrics ×
  InfoNCE-ablation). TikZ libraries `arrows.meta, calc, positioning` added
  to the preamble.

Paper recompiles cleanly to 13 pages with no undefined references.

## Still not done — requires new experiments

- **T1.2 aggregation.** Once PD finishes, regenerate Tab 3 (multi-substrate
  table) from `t1_2/*/{full,no_infonce}_seed{1,2,3}_1M/logs.jsonl` and
  rewrite the §6 results paragraph.
- **T1.3 missing points.** Run PIE at 8, 96, 128 agents (the 64-agent
  ceiling note in `docs/phase5/paper_extension.md` flags that 128+ needs
  async batched inference + World Partition streaming sources).
- **T1.4.** Long-horizon persona-persistence figure (4 personas × 30
  in-game minutes, 1-min activity strip) — needs new UE5 PIE run with a
  per-minute intent-class logger.
- **T1.5 missing figures.** Contention heatmap (per-zone occupancy over
  the episode); per-persona expressed-vs-preferred intent chart (requires
  comparing full-stack action distributions against the persona's
  unconstrained Layer-1 policy or against HybridNoPersona).

No numbers were fabricated; every table cell is sourced from an existing
log under `research/results/ue_sessions/` or
`research/meltingpot/runs/`.
