# MELTINGPOT_PROPOSAL.md

**Research Proposal: Persona-Conditioned Shared Policies on Melting Pot — From Identity-Conditioned Toy Agents to Socially Embedded Multi-Agent Systems**

**Status:** Research roadmap. Not a commitment to implementation in the current paper cycle.
**Project:** PCSP (Persona-Conditioned Shared Policy)
**Target venues:** ICML, NeurIPS (D&B track + main track), ICLR, AAMAS, NeurIPS Cooperative AI / Agentic AI workshop
**Author:** PCSP Research Group
**Date:** 2026-05-14

---

## 1. Executive Summary

PCSP, as developed against Mini-Inzoi v3, demonstrates that a single shared policy conditioned on a frozen LLM persona embedding, regularized by an InfoNCE trajectory-level consistency loss, can reproduce zero-shot persona-conditioned behavior with measurable identification accuracy. The environment is, however, deliberately minimal: a small grid, a coarse action ontology (`Discrete(20)`), and predominantly single-agent-of-interest interaction dynamics. The work establishes feasibility but does not pressure-test the central claim — that *linguistically expressed identity* survives *task-coupled, socially embedded, multi-agent decision making*.

This proposal frames the next phase of the program: integrating PCSP with **Melting Pot 2.0** (DeepMind) as the standard external benchmark for population-level social cognition and emergent multi-agent behavior. Melting Pot is the dominant credible benchmark for evaluating generalization of multi-agent policies across novel co-players, novel social dilemmas, and novel population compositions. Within this benchmark we propose a research program organized around four scientific questions:

1. Does a frozen-LLM persona embedding produce *behaviorally distinguishable* policies under social and adversarial pressure, or does reward optimization collapse identity?
2. Can persona-conditioned populations form *stable, identity-correlated social conventions* (turn-taking, role specialization, fairness norms) that hand-designed populations do not?
3. Does PCSP exhibit *traceable identity*: can a third-party observer recover the persona that generated a held-out trajectory across novel co-players?
4. Can persona text be used as a *control surface* for social behavior — i.e., does shifting persona text predictably shift social outcomes (cooperation rate, free-riding, retaliation)?

These questions move PCSP from "controllable NPC" to "controllable social agent," which we argue is the more important scientific and engineering object.

---

## 2. Motivation

### 2.1 Why Melting Pot, beyond Mini-Inzoi

Mini-Inzoi v3 was designed to optimize one quantity: whether a persona-conditioned shared policy produces persona-distinguishable trajectories at low engineering cost. It succeeds at that, and only that. Its limitations as a venue for the central PCSP claim are concrete:

- **Coarse action ontology.** `Discrete(20)` collapses most of the interesting decision space. Most observed behavioral variance is between high-level activity *bins* (work, sleep, socialize) rather than micro-level strategy.
- **Weak agency coupling.** Other agents are environmental decor rather than strategic counterparties. Persona therefore expresses as activity preference, not as social strategy.
- **No partial observability stress.** State is essentially fully observable. Persona cannot manifest through inference style, memory use, or risk attitudes.
- **No social dilemmas.** No agent has reason to defect, free-ride, retaliate, or coordinate. Persona traits like "selfish," "cooperative," "vindictive," "fair" cannot be expressed because the environment offers no payoff structure that distinguishes them.
- **Identification metric saturates trivially.** Many archetypes are linearly separable on time-of-day occupancy histograms; the human and automated 2AFC results have plateaued.
- **No external benchmark anchor.** Reviewers correctly point out that any result on a self-designed environment is conditional on environment design. PCSP needs an externally credible testbed.

Melting Pot directly addresses each of these:

- A library of 50+ substrates, each with non-trivial action spaces (typically `Discrete(8)`–`Discrete(20+)`, but composed over RGB observations and rich state).
- Partial observability through egocentric RGB views.
- Genuine multi-agent strategic structure: collective action problems, exploitation/altruism trade-offs, coordination games, territorial dynamics, reputation effects.
- Standardized **evaluation populations**: held-out co-players designed to test generalization, not just training performance.
- An established baseline corpus (A3C, PPO, OPRE, MAPPO, MA-POCA, exploiter-pair evaluation, etc.) that gives reviewers a known reference frame.

### 2.2 Scientific motivation: from "diverse actions" to "diverse strategies"

The PCSP claim — that natural-language persona is a tractable conditioning variable for behaviorally coherent agents — is only scientifically interesting if persona survives contact with *consequential decisions*. The most consequential decisions are social: when to cooperate, when to defect, when to share, when to coordinate, who to follow.

The deep question is whether a frozen text encoder's representation of identity is *load-bearing* under reward pressure. There are three plausible regimes:

1. **Identity collapse.** Under sufficient reward pressure, all personas converge to the same locally optimal policy. Persona embedding is decoded but ignored. PCSP under InfoNCE consistency would in principle resist this, but it is an empirical question whether the consistency loss is strong enough to maintain identity at non-trivial cost in reward.
2. **Identity preservation with cost.** Persona-coherent behavior persists, but at measurable reward cost. The trade-off curve between reward and identity-recoverability becomes a scientific object in its own right.
3. **Identity-driven strategy diversification.** Personas converge to *different* local equilibria. The same environment admits multiple coherent strategies; persona selects among them rather than away from optimum. This is the most interesting regime: persona acts as an equilibrium-selection mechanism.

Distinguishing these regimes requires social environments where reward pressure can be calibrated and identity can be independently measured. Melting Pot is the standard such testbed.

### 2.3 Benchmark credibility motivation

A serious main-track paper on persona-conditioned social agents requires:

- An evaluation surface that reviewers recognize as non-trivial and non-cherry-picked.
- A held-out evaluation protocol that the authors cannot retroactively shape.
- Baselines that did not originate in the same lab as the proposed method.
- Substrates that other groups can reproduce without engineering work specific to ours.

Melting Pot provides all four. Mini-Inzoi cannot. Therefore the Melting Pot effort is *not* a downstream demo — it is the venue that decides whether the central PCSP claim is reportable to ICML/NeurIPS-class venues.

### 2.4 Why now

The prerequisites have landed: v3 ablations are complete, InfoNCE consistency is established as the load-bearing component, the architecture-dependent FiLM vs concat question is settled enough for paper claims, and v3-large (20-action, 16-agent, 500-persona) is the next planned scaling step. Melting Pot integration should be designed in parallel with v3-large to amortize the scaling engineering across both targets.

---

## 3. Main Hypotheses

We commit, in advance of running experiments, to the following falsifiable hypotheses. Each is paired with an explicit prediction and a clearly defined failure case.

### H1 — Identity-Distinguishable Policies under Reward Pressure

> **Claim.** A frozen-LLM persona embedding, conditioned through FiLM/concat into a shared PPO policy and regularized by InfoNCE trajectory consistency, produces *behaviorally distinguishable* policies across personas in Melting Pot substrates, where the distinguishability is measurable from trajectory observations alone (no persona oracle).
>
> **Prediction.** A held-out trajectory classifier reaches identification accuracy substantially above chance, on at least three substrates from distinct categories (collective action, coordination, territorial), under unseen co-player populations.
>
> **Failure case.** Classifier accuracy collapses to chance under social dilemmas — i.e., identity is observable in trivial environments and disappears the moment behavior is reward-coupled. This is the *identity collapse* regime and would itself be a publishable negative result with implications for the limits of language conditioning.

### H2 — Persona-Correlated Convention Emergence

> **Claim.** Populations composed of PCSP agents with correlated persona traits (e.g., a population of "cooperative" personas vs. "competitive" personas) converge to qualitatively different social conventions (allocation patterns, turn-taking, retaliation norms), and these conventions are *predictable from population persona statistics*.
>
> **Prediction.** On substrates such as `commons_harvest` and `clean_up`, persona-population statistics (mean cooperativeness, dispersion of risk aversion) explain a substantial fraction of variance in social-outcome metrics (Gini of returns, defection rate, public-good provision rate) across population seeds.
>
> **Failure case.** Outcomes are indistinguishable across population persona statistics, or are predicted equally well by population *size* and random seed. This would imply that persona text does not transmit to population-level behavior and would call into question the premise that linguistic identity is the operative variable.

### H3 — Trajectory-Level Identity Traceability under Novel Co-Players

> **Claim.** Persona is recoverable from a held-out trajectory even when the agent is embedded in a *novel population* (different co-player policies than those seen during training).
>
> **Prediction.** Persona identification accuracy under Melting Pot's held-out evaluation populations remains within a bounded margin (preregistered) of in-distribution identification accuracy.
>
> **Failure case.** Identification accuracy is high in-distribution but collapses under held-out populations. This regime is informative: persona is a function of *co-player distribution* rather than an intrinsic trait of the agent, which would imply persona is more accurately modeled as a *response style* than a *trait*.

### H4 — Persona as Controllable Surface for Social Outcomes

> **Claim.** Editing persona text in *semantically interpretable* ways (e.g., adding "tends to share resources with strangers") shifts social-outcome metrics in the predicted direction with statistically reliable effect sizes.
>
> **Prediction.** Pre-registered persona edits produce signed shifts in social-outcome metrics (cooperation rate, sharing, retaliation latency) consistent with the semantic edit direction, under matched seeds.
>
> **Failure case.** Edits produce inconsistent or random shifts, or are dominated by environment seed. This would imply persona conditioning is not a *control surface* but rather a *label* that the policy learns to ignore beyond what is needed for identification.

### H5 — Reward-Identity Trade-off Frontier

> **Claim.** Across personas and substrates, there exists a measurable trade-off frontier between *task reward* and *identity recoverability*, and this frontier is shifted favorably by InfoNCE consistency relative to ablations.
>
> **Prediction.** Pareto front of (reward, identification accuracy) for PCSP-full lies above the front for PCSP-no-consistency, with no substrate exhibiting a free-lunch regime (where both reward and identity improve simultaneously without a regularizer change).
>
> **Failure case.** No trade-off exists (free lunch everywhere) — implying the environments are not strategically rich enough to expose identity-vs-reward conflict, and we have failed to leave Mini-Inzoi conceptually. This is an environment-selection failure, not a method failure, and dictates which substrates are admissible for the main claim.

---

## 4. Expected Contributions

We commit to the following contributions, scoped to be defensible at a main ML venue:

1. **A persona-conditioned PCSP integration with Melting Pot 2.0**, with a clean adaptation of the v3 PCSP code path to Melting Pot's substrate API. Open-sourced under the existing repository's MIT license.
2. **A benchmark protocol** for persona-conditioned multi-agent evaluation: training population construction, held-out persona splits orthogonal to held-out co-player splits, and a documented set of substrates classified by social-dilemma category.
3. **A metric suite** for identity-conditioned social agents: trajectory–persona mutual information estimation, convention-emergence indicators, persona–outcome controllability indices, and identification-vs-reward Pareto curves.
4. **Empirical characterization** of how persona conditioning interacts with social dilemmas: which substrate categories preserve identity, which collapse it, and which produce identity-driven equilibrium selection.
5. **Negative results, treated as first-class contributions**, on substrates where identity collapses or convention emergence fails — including diagnostic analyses that distinguish *method* failure from *environment* failure.
6. **A controllability study** demonstrating (or refuting) that natural-language persona edits act as a *causal* control surface on social outcomes under matched seeds, with confidence intervals.

We deliberately do *not* claim:

- That PCSP outperforms task-specialized MARL methods on raw reward. PCSP optimizes a different objective (identity-conditioned diversity at low marginal cost) and reward parity is sufficient, not required.
- That a frozen LLM is the best persona encoder in absolute terms. The frozen-encoder constraint is a deliberate ablation against persona-encoder co-adaptation; lifting it is a separate study.
- That Melting Pot results generalize to commercial life-simulation games. They do not, and that limitation is explicit.

---

## 5. Risks and Limitations

We enumerate substantive risks that will materially affect publishability and engineering scope. Each carries a mitigation plan.

### 5.1 Identity collapse under reward pressure

If H1 fails — i.e., personas become indistinguishable under any non-trivial reward gradient — the main PCSP claim does not transfer to Melting Pot. This is the single largest risk.

- **Mitigation:** Calibrate reward scale per substrate. Run a reward-pressure sweep where the InfoNCE coefficient is varied across orders of magnitude. Treat the Pareto frontier (H5) as the primary scientific object; report identity-collapse as a finding rather than a null result.

### 5.2 Substrate-induced confounding

Different substrates have different observation modalities (RGB egocentric), different episode lengths, and different population sizes. Per-substrate effects could swamp the persona effect.

- **Mitigation:** Use a small set (4–6) of pre-selected substrates with documented category coverage. Report per-substrate results separately. Avoid aggregated metrics across heterogeneous substrates as the headline number.

### 5.3 Persona-encoder bottleneck

A frozen ~600M-parameter encoder may not adequately separate persona texts in a way that is *behaviorally relevant* under social pressure. Persona embeddings that are perceptually close in encoder space may need to produce behaviorally distant policies.

- **Mitigation:** Continue using LoRA projection (load-bearing in v3). Ablate against a learned projection trained jointly with the policy. Report identification accuracy and embedding–behavior alignment separately; if encoder is the bottleneck, this is detectable and informative.

### 5.4 Compute scale

Melting Pot training at credible scale is non-trivial. A typical baseline run consumes 1e8–1e9 environment steps per population.

- **Mitigation:** Stage training (small-scale shakedown, then full-scale on 2–3 priority substrates). Use distributed PPO with vectorized environments (see `MELTINGPOT_FEAT.md` §Systems). Budget realistic GPU-weeks rather than claiming runs we cannot execute.

### 5.5 Population-level confound

Persona-correlated populations interact with population composition (e.g., a population of "cooperative" personas is also a less *adversarial* population). Effects attributed to persona may be mediated by population composition.

- **Mitigation:** Design factorial population sweeps where persona mean and persona dispersion are varied independently. Use mixed personas in matched seeds as the control. Pre-register the analysis plan in the spec document.

### 5.6 Evaluation overfitting

Melting Pot has known evaluation populations. We commit to not training on evaluation populations, but the temptation to tune hyperparameters on evaluation scores is well-documented.

- **Mitigation:** Hold out one substrate entirely for final evaluation; do all hyperparameter selection on a separate substrate set. Report this split structure in the paper. Run final evaluation as a single locked pass after the method is frozen.

### 5.7 Reproducibility surface

Multi-agent RL is notoriously seed-fragile. Persona conditioning compounds variance.

- **Mitigation:** Minimum 5 seeds per cell, bootstrap CIs for all reported numbers. No headline claims at fewer seeds. Public seed list, public configs, version-pinned dependencies.

### 5.8 Scope creep into general MARL claims

It is tempting to extend the work into general MARL contributions (improved exploration, communication learning). This dilutes the PCSP-specific claim.

- **Mitigation:** Hold the line on persona-conditioning as the contribution. Defer general MARL extensions to follow-up work.

### 5.9 Confounding with v3-large

If v3-large and Melting Pot are run in parallel, attribution of method improvements to either environment is unclear.

- **Mitigation:** Keep v3-large and Melting Pot as separate experimental tracks with separate paper-claim allocations. v3-large supports scaling claims; Melting Pot supports social-emergence and external-validity claims.

---

## 6. Research Roadmap

The roadmap is staged so that early phases are useful even if later phases are abandoned. Each phase produces an artifact suitable for a workshop submission, with the full main-track paper landing only after Phase 4.

### Phase 0 — Scoping and Decision (2 weeks)

- Reproduce a small Melting Pot baseline (PPO on `commons_harvest__simple`) end-to-end, locally.
- Confirm engineering feasibility on internal compute.
- Lock the substrate list for the program (target: 4–6 substrates covering collective action, coordination, territorial, exploitation).
- Decision point: either proceed to Phase 1 or formally defer Melting Pot in `research/PLAN.md`.

### Phase 1 — Persona-Conditioned PCSP on a Single Substrate (4–6 weeks)

- Adapt v3 PCSP code path to one substrate (`commons_harvest__open` recommended as a starting point).
- Re-confirm the load-bearing role of InfoNCE consistency by ablating against `no-consist` and `no-diverse` baselines.
- Produce a workshop-grade artifact (NeurIPS Cooperative AI or AAMAS workshop).

### Phase 2 — Multi-Substrate Generalization (6–8 weeks)

- Extend to the full substrate set.
- Run held-out persona splits (orthogonal to held-out co-player splits provided by Melting Pot).
- Build the trajectory-level identification classifier as a standardized evaluation tool, not just a sanity check.
- Report identification-vs-reward Pareto curves (H5).

### Phase 3 — Convention and Controllability Studies (6 weeks)

- Population-statistics → social-outcome regression (H2).
- Persona-edit controllability experiments (H4), with pre-registered edits.
- Cross-population convention transfer (do conventions formed under one population persist under a different population?).

### Phase 4 — Paper-Grade Consolidation (6–8 weeks)

- Final substrate evaluation with locked method.
- Statistical testing, bootstrap CIs, multiple-testing correction across substrates.
- Figure generation, ablation tables, qualitative case studies of emergent conventions.
- Writing.

### Phase 5 — Open Release (2 weeks)

- Code, configs, evaluation populations, seed lists, persona text sets released.
- Trajectory dumps for at least one substrate (subject to size constraints).
- Reproducibility checklist filled per NeurIPS standards.

---

## 7. Framing: Toy Persona to Social Agents

A useful framing for reviewers and for ourselves is the *axis of social embedding*:

| Axis | Mini-Inzoi v3 | v3-Large | Melting Pot |
| :-- | :-- | :-- | :-- |
| Action space | `Discrete(20)` | `Discrete(20)` | `Discrete(7)` over RGB |
| Observation | Symbolic state | Symbolic state | Egocentric RGB, partial |
| Co-player coupling | Cosmetic | Crowd-level | Strategic |
| Reward structure | Persona-aligned | Persona-aligned | Game-theoretic |
| Identity expression channel | Activity preference | Activity preference + crowd dynamics | Strategy, communication, role |
| Failure mode of persona | Trivially recoverable | Crowded | Reward-pressed |

The PCSP program's scientific arc is the migration of persona from a *labelling* variable (Mini-Inzoi) to a *strategic-style* variable (Melting Pot). The motivating claim of the program — that *language is a viable identity channel for agents* — is only validated if persona survives that migration.

---

## 8. Concepts Made Explicit

### 8.1 Social emergence

We mean specifically: stable behavioral regularities (allocation patterns, retaliation rules, signaling conventions) that arise from agent–agent interaction and are not directly programmed by reward shaping. Persona-correlated emergence is the central object.

### 8.2 Identity consistency

The property that an agent's behavior remains classifiable as belonging to a single persona across episodes, co-player compositions, and environment seeds. Operationalized as trajectory-classifier accuracy on held-out trajectories.

### 8.3 Convention formation

Stable equilibria selected by a population. Operationalized as: low variance in social-outcome metrics across episodes after a burn-in period, and high predictability of next-episode outcomes from prior-episode outcomes. We measure convention strength (sharpness of equilibrium) and convention identity (which equilibrium).

### 8.4 Strategic adaptation

Within-episode and across-episode behavioral change in response to co-player behavior. We measure adaptation as: change in policy output distribution conditional on co-player action history, vs. baseline of co-player-agnostic behavior.

### 8.5 Controllable social agents

Agents whose *social behavior* (not just task behavior) is steerable by an interpretable input. Persona text is the candidate control surface. Steerability is measured by H4's persona-edit experiments.

### 8.6 Persona traceability under social pressure

The capacity to recover persona identity from trajectories even when the agent has been optimized hard against a task reward and embedded with unfamiliar co-players. Distinct from in-distribution identification; this is the harder evaluation.

### 8.7 Reward optimization vs identity preservation

The Pareto frontier between task reward and identity-classifier accuracy. We treat this as a primary scientific output of the program, not as a single-number trade-off.

### 8.8 Emergent coordination conventions

Conventions that arise in coordination-game substrates (`coordination_room`, `pure_coordination`) where multiple equilibria are reward-equivalent and the population selects among them. Persona-correlated convention identity is the H2 prediction.

---

## 9. Position Relative to Existing Work

- **Melting Pot benchmark papers (Leibo et al., Agapiou et al.):** establish the evaluation surface; PCSP is a candidate method to evaluate.
- **OPRE (Vezhnevets et al.) and related opponent-modeling methods:** provide a reference for how shared policies can be conditioned on co-player identity. PCSP differs in conditioning on *intrinsic* identity (persona text) rather than *extrinsic* identity (observed co-player behavior).
- **Persona-conditioned LLM-as-agent work (Generative Agents, Voyager, Park et al.):** provide the persona-as-language framing. PCSP differs by collapsing persona into a fixed embedding consumed by a fast RL policy, decoupling persona-richness from inference cost.
- **MARL diversity methods (DIAYN, Diverse Skill Discovery, FOX):** provide a frame for *unsupervised* policy diversification. PCSP differs by sourcing diversity from a *prescribed* persona distribution, with identity-recoverability as a constraint rather than an objective.

The Melting Pot program is what positions PCSP at the intersection of these literatures rather than adjacent to any one of them.

---

## 10. Out of Scope

We explicitly exclude from this proposal:

- LLM-as-policy approaches and any inference-time LLM call from inside the RL loop.
- Online persona-encoder fine-tuning during PPO training.
- Communication-channel learning between agents (separate research program).
- Real-time game-engine integration (handled in the parallel UE5 track under `ue/cnzoi/`).
- Human-in-the-loop persona editing during training.

These are deferred to follow-up work; their inclusion would dilute the focal claim.

---

## 11. Decision Criteria

We will treat the Melting Pot program as successful and paper-ready if and only if:

- H1 holds on at least 3 substrates from distinct categories, with identification accuracy CIs separated from chance.
- H5 produces a non-degenerate Pareto frontier on at least 2 substrates.
- One of {H2, H3, H4} produces a substantive positive result with effect size large enough to survive multiple-testing correction.

If only H1 holds, the work is a workshop paper. If H1 plus one of {H2,H3,H4} holds, it is a main-track submission. If H1 fails, the work is a structured negative result paper with implications for the limits of language-conditioned agents — also publishable but at a different venue.
