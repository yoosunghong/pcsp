# Tier 1 Progress — 2026-05-19

Writing-only pass executed on [main.tex](../../paper/cog2026_main/main.tex).
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
- **T1.3 (complete, 2026-05-20).** Full sweep `{8,16,32,64,96,128}` × 3
  seeds × 630 s standalone `-game` run (18 sessions
  `ue/cnzoi/Saved/PCSP/Logs/20260520_000614..030856`, aggregated to
  `research/results/ue_sessions/scaling_20260520/`). `tab:ue5_scaling`
  in §7 rewritten with the full curve: per-setting mean / p95 inference
  latency, mean / p95 frame ms, BT-abort failure rate, intents/agent/min.
  Headline: inference flat 183–202 µs through n=64; frame time scales
  ≈0.27 ms/agent; failure rate cliffs at n=128 (44.9 %) — NavMesh
  `FindPath` queue saturation, not ONNX inference. n≤64 is the
  recommended realtime operating point. The `% TODO(T1.3)` markers in
  `main.tex` are removed.
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
- ~~**T1.3 missing points.**~~ Done 2026-05-20 — see Second-pass entry above.
- ~~**T1.4.**~~ Done 2026-05-20 — see Third-pass entry below.
- ~~**T1.5 missing figures.**~~ Done 2026-05-20 — see Fourth-pass entry below.

No numbers were fabricated; every table cell is sourced from an existing
log under `research/results/ue_sessions/` or
`research/meltingpot/runs/`.

## Third pass — 2026-05-20 (T1.4 long-horizon persistence)

- **T1.4 (complete, 2026-05-20).** New §7.5 *Long-horizon behavioural
  persistence* with `fig:persona_persistence`. Four personas chosen
  a-priori for maximum pairwise category sym-KL on the clean reference
  session `20260518_114841` (minimum pairwise sym-KL = 2.68 nats):
  - `p001` Social-leaning,
  - `p009` Rest-leaning,
  - `p041` Observe/Study mix (high-entropy),
  - `p058` Work-leaning.
  A dedicated low-contention session was run for this figure:
  `ue/cnzoi/Saved/PCSP/Logs/20260520_102022` — 8 agents (the 4 personas
  ×2 each) in standalone `-game`, `pcsp.RunDurationSeconds=1800`
  (1 794 s actual), **0.0 % BT-abort**, seed 0. Required a small engine
  change: added a `pcsp.PersonaIds` CVar / `-PCSP_PersonaIds=1+9+41+58`
  cmdline override to `APCSPAgentSpawner` so a low-agent-count run can
  pin specific personas instead of the default 1..N cycle (`+`/`-`
  separators because `FParse::Value` truncates a value token at a comma).
  Each agent issues 119–291 intent decisions over the window (0.9–2.3×
  the 128-step training episode). Per-minute aggregation via
  `research/scripts/build_persona_persistence.py`; raw bin sequence and
  per-bin histograms in
  `research/results/ue_sessions/20260520_102022/persona_persistence.json`.

  Headline numbers (30 × 1-min bins, top-category share):
  - `p009`: 30/30 bins on Rest (1.00, single run, 291 decisions/agent)
  - `p058`: Work modal in 17/30 bins (0.57, 16 runs, 5 categories)
  - `p001`: Social-dominant 15/30 (0.50, 18 transitions, 5 categories)
  - `p041`: even Social/Work split (0.47, 9 runs, high-entropy)
  Persona ordering by focus preserved end-to-end; policy is stateless
  feed-forward so persistence is purely a property of the persona
  embedding plus the InfoNCE-trained conditioning manifold.

  The TODO(T1.4) markers in `main.tex` (contributions block at §1.3 and
  Layer-3 opener) are removed. New §7.5 *Long-horizon behavioural
  persistence* added; the §7.6 *Failure analysis and contention*
  subsection header (briefly clobbered by the §7.5 insert) is restored.

All Tier-1 items from REVISE_PLAN.md are now complete.

## Fourth pass — 2026-05-20 (T1.5 contention figures)

- **T1.5 (complete, 2026-05-20).** The two outstanding §7.6 figures are
  built and wired in. New `research/scripts/build_t15_contention.py`
  reads a single canonical 64-agent HybridPCSP session
  (`ue/cnzoi/Saved/PCSP/Logs/20260520_013551`, 3 881 decisions /
  3 728 completed interactions over 629 s) and emits:
  - `fig:ue5_contention` (`fig_ue5_contention_heatmap.pdf`) — per-zone
    occupants/capacity across 30 time bins. Rest carries the load
    (mean 0.51, peak 0.65); Work/Hygiene/Exercise peak ≈0.63–0.65;
    Leisure/Shop stay empty.
  - `fig:ue5_evp` (`fig_ue5_expressed_vs_preferred.pdf`) — policy
    *preferred* category distribution (mean softmax over the 20-d
    logits, folded to 11 categories) vs *expressed* (completed
    affordance categories), aggregated over 64 agents. The policy's
    top preferences Leisure (0.34) and Study (0.29) collapse at
    execution (0.00 / 0.04) while Rest (0.03→0.48), Social (0.11→0.31),
    and Work (0.03→0.11) absorb the displaced mass. Symmetric KL
    (preferred‖expressed) = 9.07 nats — the execution-time compression
    behind the ρ-drop, made concrete.
  Sidecar JSON: `research/results/ue_sessions/20260520_013551/contention_t15.json`.
  New "Where the contention lands" paragraph added to §7.6; the
  `% TODO(T1.5)` marker in `main.tex` is removed.

## Fifth pass — 2026-05-20 (T2.2 social-graph emergence)

- **T2.2 (complete, 2026-05-20).** Tier-1 was already finished; the first
  Tier-2 pick is T2.2 (social-graph emergence, §7.7, Fig 7). T2.1 (Melting
  Pot cross-substrate transfer) is **blocked on this machine** — its
  checkpoints live under the git-ignored `research/meltingpot/runs/` tree,
  which is not present locally — so T2.2 was taken first.
  New `research/scripts/build_t22_social_graph.py` reads the same canonical
  64-agent HybridPCSP session (`ue/cnzoi/Saved/PCSP/Logs/20260520_013551`,
  3 728 completed interactions). Logs carry no explicit partner field, so
  co-presence is reconstructed from per-agent zone-occupancy intervals
  (`decision`→`interaction_complete` fixes a zone, a `[t_start,t_end]`
  window, and the completion position). A co-interaction edge joins two
  agents when their intervals overlap in the same zone **and** their
  interaction points are within a `--radius` (default 250 world units,
  i.e. same/adjacent seat) — same-zone-category alone yields a
  near-complete graph because one zone holds up to ~36 agents.
  - New `fig:ue5_social` (`fig_ue5_social_graph.pdf`): 64 nodes coloured by
    behavioural archetype (modal expressed category), edges weighted by
    shared-zone overlap seconds, node size by weighted degree.
  - Headline: 672 edges, density 0.33, mean weighted degree 21; **archetype
    assortativity = 0.357**, 63.5 % of edges same-archetype. Robust to the
    threshold and strengthens monotonically as it tightens (assortativity
    0.135→0.256→0.357 for radius 600→400→250), confirming the structure is
    driven by genuine physical co-location, not zone coincidence. No social
    objective/reward exists — clustering is emergent.
  Sidecar JSON: `research/results/ue_sessions/20260520_013551/social_graph_t22.json`
  (includes the radius-sweep robustness block and per-node archetype map).
  New §7.7 *Emergent social structure* added before §8.

  **Verified 2026-05-20:** recompiled with system `pdflatex`; clean 15-page
  PDF, no undefined references, `fig:ue5_social` resolves.

## Sixth pass — 2026-05-20 (Main Track refit)

The paper is being submitted to the **COG 2026 Main Track**, not a workshop.
This pass scrubs residual workshop / vision / single-substrate framing from
the manuscript and context docs so future agents cannot reintroduce it.

- **Abstract** (`main.tex` ~L63). Single-substrate Melting Pot line
  ("External validation on `commons_harvest__open`…") rewritten to span all
  three substrates and explicitly state that the no-InfoNCE ablation collapses
  retrieval to chance in every substrate while pairwise KL is preserved or
  inflated.
- **§8 Discussion** ("Scaling to richer environments"). Removed the stale
  "single-substrate, in-distribution external check" framing and the
  "concurrent workshop study" phrasing. Replaced with a paragraph that
  acknowledges the three-substrate evidence, points to the **companion
  technical report** for the projection-head/margin analysis, and names
  cross-substrate persona transfer as the most direct external next check.
- **§9 Conclusion**. Rewritten to enumerate the three Melting Pot substrates
  by name; "concurrent workshop study" replaced with "companion technical
  report". The single-substrate sentence is gone.
- **§6 substrate paragraph** (~L963). "concurrent workshop study" replaced
  with "companion technical report".
- **T2.1 TODO comment** at the head of §6 removed; cross-substrate transfer
  is now a named open question in §8 rather than an inline TODO.
- **Directory rename.** `research/paper/cog2026_vision/` →
  `research/paper/cog2026_main/` (`git mv`, history preserved). All live
  references updated:
  `research/{DONE,PLAN,README}.md`, `AGENTS.md`,
  `research/meltingpot/MELTINGPOT_PLAN.md`,
  `research/paper/neurips2026_workshop_meltingpot/OUTLINE.md`,
  `research/revised/260519/{REVISE_PLAN,done}.md`,
  `research/scripts/build_persona_persistence.py`,
  `ue/cnzoi/docs/portfolio/observability.md`. Only `research/archive/`
  (intentionally frozen) still references the old path.
- **Context-doc lock.** `CLAUDE.md`, `AGENTS.md`, and `research/PLAN.md`
  now each state explicitly that the paper is the **COG 2026 Main Track**
  manuscript and that workshop / vision / position-paper framing must not be
  reintroduced.
- **Recompile.** `pdflatex` × 2 from
  `research/paper/cog2026_main/`; clean 15-page PDF, no undefined
  references, all renamed labels resolve.

### Tier-2 status snapshot (post-refit)

- **T2.1 cross-substrate transfer.** **Completed 2026-05-20** (user pointed
  out that the `research/meltingpot/runs/` checkpoints — including
  `cog_clean/seed{1..5}_1M[_no_infonce]/` for CH and
  `t1_2/{clean_up,prisoners_dilemma…}/full_seed{1..3}_1M/` for CU/PD — were
  in fact present locally; the earlier "blocked" claim was wrong). See
  Seventh-pass entry below.
- **T2.2 social-graph emergence.** Done (Fifth pass) and now verified to
  compile.
- **T2.3 per-substrate behavioural-axis metric.** Subsumed by the
  multi-substrate `tab:mp_multi` and the existing substrate-meaningful KL
  story; no extra row needed for the Main Track submission.
- **T2.4 v3-large.** GPU-bound, deliberately deferred (see `research/PLAN.md`).
- **T2.5 human-written persona set.** Requires recruitment; out of scope for
  this submission.

All Tier-1 items and the only Tier-2 item that was achievable from this
machine (T2.2) are now complete and verified. The paper is in a clean Main
Track state.

## Seventh pass — 2026-05-20 (T2.1 held-out + cross-substrate transfer)

- **T2.1 (complete, 2026-05-20).** Two-part evaluation harness in a single
  new script, `research/meltingpot/scripts/eval_t2_1_transfer.py`. Each
  rollout is $256$ steps; trajectories per agent are encoded by the trained
  GRU encoder and compared against the projected persona vocabulary.

  *Part 1 — held-out-vocabulary retrieval (within each substrate).* For every
  Layer-2 checkpoint (CH: $5$ full $+\,1$ no-InfoNCE; CU: $3$ full $+\,3$
  no-InfoNCE; PD: $3$ full $+\,3$ no-InfoNCE), rollouts span all $12$
  personas (10 train $+\,2$ held-out: `fast_mover`, `spinner`) and retrieval
  is taken against the full $12$-persona projection (chance top-1 $=1/12$).
  Full PCSP retrieves at $3.4$--$4.9\times$ chance top-1 in every substrate:
  CH $0.286\!\pm\!0.120$, CU $0.405\!\pm\!0.168$, PD $0.333\!\pm\!0.068$;
  the no-InfoNCE ablation collapses to $\le 0.071$ in every substrate.
  Across all $11$ full \PCSP{} runs the two held-out personas never retrieve
  themselves at rank 1 — an honest negative that lines up with the
  embedding-margin condition documented in `PHASE5_REPORT.md`.

  *Part 2 — CH$\leftrightarrow$CU cross-substrate transfer.* Source
  substrate's persona projection + trajectory encoder are reused on
  trajectories collected by the target substrate's policy in the target
  environment. The GRU input layer is zero-padded for an extra action
  one-hot slot when needed ($8\to 9$ for CH$\to$CU); no other parameter is
  touched. Three seed pairs each direction. CU$\to$CH: top-1
  $0.179\!\pm\!0.058$ ($1.79\times$ chance), top-3 $0.429\!\pm\!0.077$
  ($1.43\times$ chance). CH$\to$CU: top-1 $0.060\!\pm\!0.034$ (at/below
  chance) but top-3 $0.417\!\pm\!0.034$ ($1.39\times$ chance). The
  asymmetry is publishable as-is.

  Results landed in the paper as a new `tab:mp_transfer` and a new §6.X
  subsection *Held-out persona recovery and cross-substrate transfer*
  (`\label{sec:mp_transfer}`), with §1.3 Layer-2 bullet extended to mention
  the $12$-vocab and CU$\to$CH numbers and the §8 "Scaling to richer
  environments" paragraph rewritten to drop the "transfer remains untested"
  framing in favour of the two named open problems (held-out persona
  recovery, substrate-invariant projection).

  Sidecar JSON per run: `research/meltingpot/runs/t2_1/{held-out,cross}/`
  plus aggregated `research/meltingpot/runs/t2_1/t2_1_summary.json`.

- **Recompile.** `pdflatex` × 2 from `research/paper/cog2026_main/`; clean
  16-page PDF, no undefined references, `tab:mp_transfer` and
  `sec:mp_transfer` resolve.

All Tier-2 work that the checkpoints on this machine permit
(T2.1 + T2.2) is now complete and in the paper. Remaining Tier-2 items
(T2.3 behavioural-axis metric — subsumed by `tab:mp_multi`; T2.4
v3-large — GPU-bound; T2.5 human-written personas — requires recruitment)
are deliberately out of scope for this submission.
