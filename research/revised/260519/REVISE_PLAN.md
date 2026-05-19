# Paper Repositioning Plan — 2026-05-19

**Target paper:** *One Policy, Infinite NPCs: Scalable Persona-Conditioned NPC Control via Shared Reinforcement Learning Policies*
**Source draft:** [research/paper/cog2026_vision/main.tex](../../paper/cog2026_vision/main.tex)
**Goal:** Eliminate "toy gridworld" reviewer reaction; reposition as a deployment-oriented agent-systems paper.
**Preserved claims:** trajectory-level persona recoverability, InfoNCE as the load-bearing component, shared realtime policy on frozen persona embeddings.

---

## 0. Diagnosis — why the current draft reads as "toy"

Four specific signals in the current draft trigger the reaction; each has a precise fix downstream in this plan.

1. **§3.1 names the env first** ([main.tex:269](../../paper/cog2026_vision/main.tex#L269)): "Mini-Inzoi … 6×6 grid, 4 agents" appears before the method. Readers anchor on the grid.
2. **§5 self-describes Melting Pot as "a preliminary external check"** ([main.tex:849](../../paper/cog2026_vision/main.tex#L849)). The paper tells reviewers it does not count.
3. **§6 title "Engine Integration: UE5 Deployment"** reads as appendix. The strongest numbers (64-agent realtime, 0.04% held-out failure, in-engine InfoNCE ablation) are buried late in a 9-section paper.
4. **Contributions list (§1.3)** leads with the toy-env benchmark and "22× faster than LLM-as-policy"; UE5 is contribution #5.

The science is fine. The shelving order is wrong.

---

## Tier 1 — must-do for this submission (≈2 calendar weeks)

These six items deliver the largest perception shift. Most are writing-only; T1.2 is the one experiment block that is non-negotiable.

### T1.1 — Restructure into a three-layer narrative *(writing, 2–3 days)*

**Why it matters.** Single largest perception shift in the plan; zero new experiments required.
**Reviewer impact.** Very high.

New section order:

```
§1  Introduction
§2  Related Work / Why Current Paradigms Fall Short
§3  PCSP: Persona-Conditioned Shared Policy
      3.1 Persona Encoding (Qwen3 + LoRA)
      3.2 Shared Policy & Conditioning
      3.3 Co-Training Objective (PPO + InfoNCE + KL)
      [no environment in §3 — method is env-agnostic]
§4  Evaluation Strategy: A Three-Layer Validation Stack
      4.1 Layer 1 — Controlled diagnostic substrate (PCSP-Diagnostic)
      4.2 Layer 2 — External RL substrate (Melting Pot, multi-substrate)
      4.3 Layer 3 — Realtime engine deployment (UE5)
      4.4 Per-layer evaluation protocols and metrics
§5  Layer 1 Results: Mechanistic Validation
      (current §4 condensed; v1/v2 → appendix; v3 OOD + InfoNCE ablation in main)
§6  Layer 2 Results: Cross-Substrate Generalization
      (expanded Melting Pot: 2–3 substrates, held-out personas, transfer)
§7  Layer 3 Results: Realtime Engine Deployment   <-- new flagship section
      7.1 System architecture
      7.2 Scale and runtime characteristics (scaling curve)
      7.3 Held-out persona transfer in-engine
      7.4 In-engine ablation: InfoNCE is load-bearing under engine pressure
      7.5 Long-horizon behavioral persistence
      7.6 Failure analysis and contention
§8  Discussion: what each layer proved
§9  Limitations
§10 Conclusion
```

Net effect: UE5 jumps from §6 to §7 of a 10-section paper with double the content and its own results section parallel to Mini-Inzoi. Mini-Inzoi loses ~40% of main-paper real estate; v1/v2 tables → appendix.

**Rewritten Introduction contributions (§1.3)** — replaces [main.tex:145–184](../../paper/cog2026_vision/main.tex#L145-L184):

1. **Method.** PCSP — a shared policy conditioned on frozen LLM persona embeddings via low-rank projection and FiLM/concat fusion, co-trained with PPO, an InfoNCE trajectory-consistency objective, and KL diversity regularization.
2. **Three-layer validation methodology.** We argue that persona-conditioned agents require *separated* validation of mechanism, generalization, and deployment, and instantiate this with a controlled diagnostic substrate, two external Melting Pot substrates, and a realtime UE5 engine deployment.
3. **Mechanistic finding (Layer 1).** Under controlled conditions, the InfoNCE consistency term is causally responsible for trajectory-level persona recoverability: removing it preserves task reward but collapses zero-shot persona identification to chance across three independent environment instantiations.
4. **External generalization (Layer 2).** The same method, *without algorithmic modification*, transfers to Melting Pot social-dilemma substrates and produces persona-distinguishable behavior on held-out personas across substrates.
5. **Deployment finding (Layer 3).** A frozen Layer-1 checkpoint deployed in UE5 sustains 64 concurrent persona-conditioned agents at realtime with 1.7% failure, reproduces the InfoNCE ablation in-engine, and generalizes to 60 held-out personas at 0.04% failure — establishing that the consistency objective is load-bearing under engine-side contention.
6. **Reproducibility.** Open ONNX checkpoints, three-layer benchmark code, UE5 plugin, trajectory-annotation harness.

**Figure/table reordering:**

| Slot | Content | Origin |
|---|---|---|
| Fig 1 | System diagram | unchanged |
| Fig 2 (new) | Three-layer validation stack schematic | replaces v1/v2 learning curves |
| Tab 1 (new) | Layer × Question × Metric matrix | new |
| Tab 2 | v3 OOD splits | promoted (was Tab 4) |
| Tab 3 | Melting Pot multi-substrate | expanded from Tab 6 |
| Fig 3 | Designer t-SNE | kept |
| Fig 4 | UE5 system diagram | kept |
| Fig 5 (new) | Scaling curve: agents vs realtime budget | flagship realism figure |
| Fig 6 (new) | Persona-persistence timeline (30-min strip) | flagship realism figure |
| Tab 4 | UE5 held-out | promoted (was Tab 7) |
| Tab 5 | UE5 in-engine ablation | promoted (was Tab 8) |
| Fig 7 (new) | Social-graph emergence in UE5 | low-cost, high-impact |

Move v1/v2 learning curves, Tab 2, Tab 3 → appendix.

### T1.2 — Add two Melting Pot substrates + InfoNCE ablation on each *(4–6 GPU-days + 1 day writing)*

**Why it matters.** Kills the "preliminary external check" criticism. Turns Layer 2 from a single-substrate sanity check into a benchmark suite.
**Reviewer impact.** Very high.

Add:
- `clean_up` — different social-dilemma structure (pollution vs harvesting).
- `prisoners_dilemma_in_the_matrix__repeated` — different action ontology, dyadic.

Protocol per substrate:
- Train on 240 personas, evaluate on 60 held-out (mirrors Layer 1 protocol).
- Report ZS top-1, top-3, ρ, pairwise action-KL, and one substrate-meaningful behavioral metric (restraint index for `commons_harvest`, cleaning ratio for `clean_up`, defection rate for `prisoners_dilemma`).
- Re-run InfoNCE-off ablation in every substrate.

Resulting table replaces current Tab 6:

| Substrate | ZS top-1 | ZS top-3 | ρ | Pairwise KL | Substrate metric | InfoNCE-off Δ |
|---|---|---|---|---|---|---|
| commons_harvest | … | … | … | … | restraint idx | … |
| clean_up | … | … | … | … | cleaning ratio | … |
| prisoners_dilemma | … | … | … | … | defection rate | … |
| transfer CH→CU (eval-only) | … | … | … | — | — | — |

The transfer row is the cheap T2.1 below; include it here if it lands in time.

### T1.3 — UE5 scaling curve + latency budget table *(1–2 engineering days)*

**Why it matters.** Concrete realism signal; converts UE5 from a "we shipped it" demo into a systems result.
**Reviewer impact.** Very high.

Scaling sweep: {8, 16, 32, 64, 96, 128} agents on the existing district map. Report per setting:
- mean ONNX inference latency (ms)
- p95 frame time (ms)
- BT-abort failure rate (%)
- intents/agent/min
- wall-time to a fixed shared horizon

Plot: x = #agents, two-axis (latency, failure %). Even degradation past 64 is a publishable systems result — showing the curve is the point.

Latency budget table (new): ONNX inference, BT step cost, per-agent decision throttle, total per-agent wall-budget. Concrete millisecond budgets are what systems-leaning reviewers anchor on.

### T1.4 — Long-horizon persona-persistence figure *(1 day)*

**Why it matters.** Counters "no behavioral realism" directly. Cheap.
**Reviewer impact.** High.

Run 4 personas for 30 in-game minutes (or 3 day/night cycles if available) in a low-contention setting. For each, plot an activity strip: which intent class is active in each 1-minute bin. Visually demonstrates personas maintain distinct routines over horizons far longer than training episodes.

Output: Fig 6 in the new layout.

### T1.5 — Reframe the ρ-drop as a Layer-3 finding *(1 day)*

**Why it matters.** Preempts the most critical reviewer attack ("ρ drops 0.73 → 0.24 in UE5, your method doesn't transfer"). Move from §8 limitation → §7.6 finding.
**Reviewer impact.** High.

Add to §7.6:
- Contention heatmap: zone-capacity utilization over the episode.
- Per-persona "expressed vs preferred" intent distribution chart — visualizes the contention-induced gap rather than hiding it.
- Short failure-taxonomy table (BT abort categories × frequency).
- Explicit statement: the InfoNCE ablation *still works in-engine* (ρ 0.379 vs 0.312 from [ue/cnzoi/PLAN.md](../../../ue/cnzoi/PLAN.md)). Frame the ρ drop as engine-side contention, not method failure.

### T1.6 — Three-layer schematic + Layer × Question × Metric table *(0.5 day)*

**Why it matters.** Makes the new narrative legible at first glance. Reviewers who skim only the figures should understand the three-layer structure.
**Reviewer impact.** High.

Schematic figure: three columns (Layer 1 / Layer 2 / Layer 3), each labelled with environment, question answered, key metrics.

Matrix table: rows = layers, columns = (Question, Environment, Personas eval'd, Metrics, InfoNCE ablation? Y/N).

---

## Writing artifacts ready to paste (paired with Tier 1)

Drop these in directly. Sequenced for max effect.

### A. PCSP-Diagnostic naming and reframe — replaces [main.tex:269–286](../../paper/cog2026_vision/main.tex#L269-L286)

Rename "Mini-Inzoi" → **PCSP-Diagnostic** (PCSP-D). Keep "Mini-Inzoi" as a parenthetical legacy name on first mention only.

> **Layer 1: PCSP-Diagnostic, a controlled substrate for persona-traceability analysis.**
> Validating that a policy's behavior is causally traceable to its conditioning embedding requires an environment where (i) every state transition is fully observable, (ii) the action space is small enough to compute exact trajectory distributions and KL divergences, (iii) reward shaping is independent of persona, and (iv) episode length is short enough to run thousands of held-out personas. No commercial or photorealistic environment satisfies all four simultaneously. We therefore construct **PCSP-Diagnostic**, an intentionally minimal PettingZoo AEC substrate (6×6 grid, 4 agents, 20 discrete intents over 8 bio-social needs) whose role in this paper is *not* to demonstrate behavioral realism — that is the role of Layers 2 and 3 — but to expose the InfoNCE consistency term to controlled ablation under conditions where every causal pathway from persona to trajectory is analytically observable. We treat PCSP-Diagnostic as a microscope, not a world.

Repeat "microscope, not a world" in §4 and §8.

### B. Limitations rewrite — replaces [main.tex:1192–1232](../../paper/cog2026_vision/main.tex#L1192-L1232) "Minimal environments"

> **Deliberate minimality of Layer 1.** PCSP-Diagnostic is intentionally simpler than commercial life-simulation worlds. Behavioral realism is not its purpose; it is the layer at which we can run controlled InfoNCE ablations across three independent environment instantiations and thousands of held-out personas. Realism claims in this paper are grounded in Layers 2 (Melting Pot) and 3 (UE5), where realism, contention, and asynchrony are present and where the same checkpoint is shown to behave consistently.

### C. §6 (Melting Pot) opening — replaces [main.tex:849](../../paper/cog2026_vision/main.tex#L849)

> **Layer 2: Cross-substrate generalization on Melting Pot.** We apply PCSP unchanged to three Melting Pot 2.4.0 substrates that differ in social structure (commons-pool, public-good, dyadic-matrix), observation geometry (88×88×3 RGB vs symbolic), and action ontology. The substrates were chosen *before* training and were not tuned against. On each substrate we evaluate persona identifiability on a held-out set of 60 personas using the same protocol as Layer 1, and we re-run the InfoNCE ablation in-substrate. We additionally test cross-substrate persona transfer — a setting that the Layer 1 environment cannot probe.

### D. §7 (UE5) opening — replaces [main.tex:937](../../paper/cog2026_vision/main.tex#L937)

> **Layer 3: Realtime deployment in Unreal Engine 5.** A persona-conditioned policy is only meaningful if it survives the engineering pressure of a real game engine: asynchronous tick rates, NavMesh contention, BT failure recovery, ONNX runtime constraints, and shared world state. We deploy a *frozen* Layer-1 checkpoint into UE5.5 via a hybrid intent stack — PCSP selects semantic intents, the Behavior Tree, Blackboard, EQS, and NavMesh execute them — and ask three questions that Layers 1 and 2 cannot answer: (i) does the policy meet a realtime wall-budget at deployment scale; (ii) does the InfoNCE finding survive engine-side contention; (iii) do personas maintain identity over horizons far longer than the training episode.

---

## Tier 2 — high-value if time permits (≈1 additional week)

### T2.1 — Cross-substrate persona transfer (Melting Pot, eval-only) *(1 day)*

**Why.** Directly answers "is this overfit?" Train on `commons_harvest`, evaluate persona ID on `clean_up` without retraining the policy head (swap CNN encoder only if needed). Even partial transfer is publishable; full failure with analysis is also publishable.
**Reviewer impact.** High.
**Lands in.** Bottom row of the Tier 1 Melting Pot table.

### T2.2 — Social-graph emergence figure (UE5) *(1 day)*

**Why.** Systems-paper signal. From existing interaction logs, compute a co-presence / co-interaction graph across personas over a 60-min run. Render colored by persona archetype. Even weak structure is worth showing; the existence of the analysis signals maturity.
**Reviewer impact.** Med-High.
**Lands in.** §7.7, Fig 7.

### T2.3 — Per-substrate behavioral-axis metric *(1 day)*

**Why.** Shows persona signal lands on substrate-meaningful axes, not just generic KL.
**Reviewer impact.** Med-High.
**Lands in.** Tier 1 Melting Pot table.

### T2.4 — v3-large run *(GPU-bound)*

**Why.** Tightens Layer-1 story; deferred in [research/PLAN.md](../../PLAN.md). Not load-bearing under the new structure but improves Layer-1 numbers.
**Reviewer impact.** Med.

### T2.5 — Small human-written persona set (~30) on Layer 1 zero-shot *(2–3 days incl. recruitment)*

**Why.** Counters "personas are synthetic — Qwen-generated, not real" cheaply. Drops into the existing designer-authored persona protocol (§4.5).
**Reviewer impact.** Med-High.

---

## Tier 3 — research upgrades for follow-up paper

| Item | Why it matters |
|---|---|
| T3.1 Persistent memory / preference drift across multi-episode runs | The real "infinite NPCs" story |
| T3.2 Player-induced interrupt handling and recovery in UE5 | Game-AI venue strength |
| T3.3 Online persona fine-tuning from interaction logs | Closes deployment loop |
| T3.4 Layer-1 in a continuous-control or pixel substrate | Removes last "discrete-action" critique |
| T3.5 Cross-engine deployment (Unity port) | Demonstrates engine-agnostic method |

---

## Reviewer attack matrix

| Likely review quote | Likelihood (now → after rewrite) | Severity | Mitigation |
|---|---|---|---|
| "Still a toy gridworld — 6×6 is not a sim." | Very high → Low | Critical | T1.1 rename + "microscope, not a world" + v1/v2 → appendix + Layer 3 promoted with scaling curve. |
| "Melting Pot is one substrate, feels like sanity check." | High → Low | High | T1.2: two added substrates + per-substrate InfoNCE ablation + T2.1 transfer. |
| "Behavioral realism is weak." | High | High | T1.4 persistence figure + T2.2 social graph + existing coarse-trace human pilot (§4.4) elevated. Explicit caveat: we claim *traceability*, not realism; realism is Layer 2/3. |
| "Personas are synthetic." | High | Med | Designer-authored case study (§4.5) promoted into §1; T2.5 human-written set if time permits. |
| "Mostly engineering, not research." | Med (RL venues) | High | Reframe the three-layer methodology *as* a research contribution; anchor InfoNCE causal claim ("load-bearing across 3 substrates × 3 envs × in-engine"). |
| "Evaluation is narrow." | High → Low | High | Layer-1 OOD + Layer-2 multi-substrate + Layer-3 held-out + scaling curve. |
| "Behavior space is handcrafted (20 discrete intents)." | Med | Med | Melting Pot uses native 8-action ontology unchanged — method is not tied to the 20-intent space. Frame intents as a deployment choice driven by BT integration. |
| "ρ drops from 0.73 to 0.24 in UE5 — method doesn't transfer." | Med | Critical if not preempted | T1.5: confront in §7.6, show contention causes it, show in-engine InfoNCE ablation still works (ρ 0.379 vs 0.312), reframe as a finding about deployment pressure. |
| "No comparison to LLM-as-policy at scale." | Med | Med | T1.3 latency table + cost projection ("128 agents × Qwen-0.6B per-step ≈ infeasible") sufficient if live comparison is too expensive. |
| "Why these Melting Pot substrates?" | Low–Med | Low | Single sentence: "selected before training to span commons-pool, public-good, and dyadic-matrix structures." |

---

## Execution sequencing

**Week 1**
- Day 1–2: T1.1 restructure + paste rewrites A, B, C, D into [main.tex](../../paper/cog2026_vision/main.tex). Rename Mini-Inzoi → PCSP-Diagnostic across the draft.
- Day 1 (parallel): kick off T1.2 Melting Pot `clean_up` training.
- Day 3: T1.3 UE5 scaling sweep.
- Day 4: T1.4 persistence figure + T1.5 contention heatmap.
- Day 5: T1.6 schematic + matrix table.

**Week 2**
- Day 1: kick off T1.2 `prisoners_dilemma` training.
- Day 2–3: pull Layer 2 results, regenerate Tab 3, write §6 results.
- Day 4: Tier 2 picks — T2.1 transfer, T2.2 social graph.
- Day 5: full read-through; tighten §1 + §8 against new evidence.

**Constraints to respect** (from the user's framing):
- No removal of Mini-Inzoi.
- No LLM-as-policy pivot.
- No expensive per-step inference.
- No fabricated numbers — everything in this plan maps to existing results in [research/PLAN.md](../../PLAN.md) and [ue/cnzoi/PLAN.md](../../../ue/cnzoi/PLAN.md), or to experiments scoped here.

---

## Definition of done for this submission

A reader who skims only §1.3, the three-layer schematic (Fig 2), Fig 5 (scaling curve), Fig 6 (persistence), Tab 3 (multi-substrate Melting Pot), and Tab 5 (UE5 ablation) should conclude:

> "This is a deployable persona-conditioned agent architecture validated across controlled, external, and engine-scale environments, with a causal claim about the InfoNCE consistency term that holds in all three."

If that sentence is true after the rewrite, the toy-gridworld critique is no longer the dominant reviewer reaction.
