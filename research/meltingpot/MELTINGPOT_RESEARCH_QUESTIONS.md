# MELTINGPOT_RESEARCH_QUESTIONS.md

**Research Questions: PCSP × Melting Pot — Pre-Paper Brainstorm**

**Status:** Long-form research-question catalog suitable for translating directly into paper sections, workshop abstracts, and grant proposals.
**Audience:** Future authors of the PCSP–Melting Pot paper(s); reviewers internal to the lab; collaborators reasoning about scope.
**Cross-references:** `MELTINGPOT_PROPOSAL.md` for the high-level program; `MELTINGPOT_FEAT.md` for architecture; `MELTINGPOT_PLAN.md` for the work breakdown.

The questions are organized into nine themes. Each question carries:

- **Motivation:** why the question is worth answering, and which broader literature it engages with.
- **Hypothesis:** the *signed* prediction the lab will commit to before experiments run.
- **Required experiments:** the minimal experimental setup that would constitute a fair test.
- **Expected observations:** what the result tables / figures would look like if the hypothesis holds.
- **Failure cases:** the regimes in which the hypothesis would be falsified, and what failure would imply scientifically.
- **Possible interpretations:** alternative explanations the result must be defended against.

This document is meant to read like a research lab's internal pre-paper brainstorm. It is not edited for length.

---

## Theme A — Persona-Conditioned Convention Emergence

### A1. Do persona-correlated populations form distinguishable social conventions?

**Motivation.** Convention formation is a well-studied object in multi-agent systems (Lewis, Shoham–Tennenholtz, Hawkins). PCSP introduces a new variable: the population is composed of agents with *prescribed* linguistic identities. The question is whether identity-correlated populations select different equilibria, or whether equilibrium selection is dominated by environment seed and population *size*. Engages with: equilibrium selection, social-norm emergence, multi-agent learning dynamics.

**Hypothesis.** Populations with high mean *cooperativeness* (as inferred from persona texts) converge to *equilibria with higher public-good provision and lower variance of returns* in mixed-motive substrates (e.g., `commons_harvest`, `clean_up`), relative to populations with low mean cooperativeness, with effect sizes detectable across substrate seeds.

**Required experiments.**
- Factorial sweep: persona-mean cooperativeness × persona-dispersion × substrate × seed.
- Minimum 5 environment seeds per cell, minimum 3 population-composition seeds per cell.
- Mixed-effects regression of convention metric on persona-population statistics with substrate and seed as random effects.

**Expected observations.**
- A scatter (population mean cooperativeness vs. public-good provision rate) with a clearly positive slope and tight CI, on at least two substrates.
- A regression report showing population-statistics-explained variance is substantially larger than seed-explained variance.

**Failure cases.**
- Slope is null or negative.
- Variance is dominated by substrate seed.
- *Implication:* persona text does not transmit to population-level dynamics; persona may be a *labeling* variable but not a *causal* one for social outcomes.

**Possible interpretations.**
- Even a positive result must rule out the alternative that persona-mean correlates with *exploration intensity* (a population of cooperators is also a population that defects less aggressively during exploration), which could explain convention differences without invoking identity.
- The "cooperativeness" labeling itself is a measurement choice; multiple labelings (e.g., manual annotation, LLM-based scoring, behavioral pretest) should agree on the population ordering.

---

### A2. Are conventions formed under one population *transferable* to another population?

**Motivation.** A convention that vanishes when a fraction of the population is replaced is a fragile convention. Strong conventions in human societies survive partial population turnover. The question is whether PCSP populations form robust conventions or fragile ones.

**Hypothesis.** Conventions formed under a homogeneous-persona population persist with measurable strength when up to 30% of the population is replaced with held-out personas of the same dominant trait, but degrade sharply when replaced with personas of opposing traits.

**Required experiments.**
- Train a population to equilibrium on a substrate.
- Replace fractions ∈ {10%, 30%, 50%, 70%} of the population with held-out personas drawn from (a) same-trait pool, (b) opposing-trait pool, (c) uniform pool.
- Measure convention metric stability over a fixed evaluation window post-replacement.

**Expected observations.**
- A monotone degradation curve as a function of replacement fraction.
- The same-trait curve degrades slower than the opposing-trait curve.

**Failure cases.**
- All curves degrade equally fast. Implies the population's behavior is a function of its current composition, not a transferred convention.
- All curves are flat. Implies the convention is not learned at the population level but is enforced by individual policies regardless of who else is present.

**Possible interpretations.**
- Even if degradation is asymmetric, the asymmetry might reflect *policy* differences (held-out personas of opposing traits behave differently regardless of convention) rather than *convention* differences. The ablation against a B0-unconditioned replacement controls for this.

---

### A3. Do persona-correlated conventions outperform persona-blind populations on social welfare metrics?

**Motivation.** A practical question for game designers: does identity conditioning improve population-level outcomes, or does it just diversify them? Engages with: cooperative AI as a normative agenda.

**Hypothesis.** On collective-action substrates, populations of personas pre-selected for trait-coherence (e.g., all "cooperative") achieve higher *Pareto-aggregated* social welfare than persona-blind populations at matched training cost.

**Required experiments.**
- Match training environment steps across PCSP populations and B0-unconditioned populations.
- Define a Pareto-aggregated welfare metric per substrate (e.g., mean return × (1 − Gini)).
- Compare across substrates.

**Expected observations.**
- A clear advantage for trait-coherent PCSP populations on collective-action substrates, with no advantage (or a disadvantage) on coordination substrates where diversity is harmful.

**Failure cases.**
- No advantage anywhere. Implies persona conditioning is welfare-neutral.
- Advantage everywhere. Suspicious; check for confounds.

**Possible interpretations.**
- A welfare advantage might come from reduced policy-variance rather than identity per se. Control: a population trained with the diversity regularizer disabled and persona conditioning *active* isolates the contribution of variance reduction.

---

## Theme B — Identity Collapse Under Reward Pressure

### B1. Does identity collapse occur under high reward pressure?

**Motivation.** The central scientific concern of the program. If reward optimization eliminates identity-distinguishing variance, PCSP's claim of *persona-conditioned social agents* does not transfer to consequential decisions.

**Hypothesis.** At sufficiently high effective reward signal (large reward scale, no identity-preservation regularization), trajectory-classifier identification accuracy collapses to chance for PCSP-no-consist; PCSP-full degrades but does not collapse.

**Required experiments.**
- Reward-scale sweep × InfoNCE coefficient sweep, on at least 2 substrates.
- Identification classifier evaluated at fixed compute budget.
- Report identification accuracy as a function of (reward scale × consistency coefficient).

**Expected observations.**
- A 2D surface (reward scale × consistency coefficient → identification accuracy) showing a clear collapse for low consistency and high reward scale.
- A non-collapse region for high consistency that may or may not be reachable at the corresponding reward.

**Failure cases.**
- No collapse anywhere. Implies the reward signal is too weak or the persona embedding too informative. Increase reward scale or expand persona corpus.
- Collapse everywhere, even at high consistency. Implies InfoNCE is insufficient as a preservation mechanism; consider stronger structural priors.

**Possible interpretations.**
- Collapse may reflect *task convergence* (all personas correctly solving the task with identical optimal policy) rather than *identity destruction*. Distinguish by checking whether the substrate admits multiple ε-optimal policies; if it does not, identity collapse is uninformative for that substrate.

---

### B2. Is there a Pareto frontier between task reward and identity recoverability?

**Motivation.** This is the lab's primary scientific output for the program. A clean trade-off curve is more informative than a single-number benchmark.

**Hypothesis.** Per substrate, there exists a non-trivial Pareto frontier of (mean return, identification accuracy) traced by varying `α_consist`. The frontier under PCSP-full strictly dominates the frontier under PCSP-concat on archetype-stratified splits.

**Required experiments.**
- Per substrate: sweep `α_consist` ∈ {0, 0.01, 0.1, 1.0, 10.0}; sweep `α_div` ∈ {0, 0.01, 0.1}.
- Plot Pareto front in (return, identification accuracy) space.
- Compare conditioning variants on the same plot.

**Expected observations.**
- A non-monotone front: at α_consist = 0, identification ≈ chance and return ≈ ceiling; at very high α_consist, identification ≈ 1 and return drops; an interior knee with both high.

**Failure cases.**
- No interior knee. Implies the substrate does not admit identity-aware near-optimal policies; persona is forced to choose reward or identity.
- Convex frontier (free lunch). Implies neither objective conflicts; the substrate is not strategically rich.

**Possible interpretations.**
- A knee may also be produced by *underfitting* at low consistency. Verify by extending training compute at low-α points.

---

### B3. Does identity collapse correlate with substrate category?

**Motivation.** A taxonomy of "where identity survives" is useful both scientifically and as guidance for downstream applications.

**Hypothesis.** Identity survives more robustly on *exploration* and *coordination* substrates, where multiple equilibria exist, than on *pure collective-action* substrates with a unique global optimum.

**Required experiments.**
- Identification accuracy reported per substrate, grouped by social-dilemma category.
- Multiple-substrate analysis with mixed-effects model: category as fixed effect, substrate as random effect.

**Expected observations.**
- A category-level pattern: coordination > exploration > exploitation > pure collective-action in identification retention.

**Failure cases.**
- No category-level pattern. Implies identity survival is substrate-idiosyncratic; we cannot generalize across substrate categories.

**Possible interpretations.**
- Multi-equilibrium substrates may simply be *easier to learn diverse policies on*. A more careful test: matched-difficulty substrates within categories.

---

## Theme C — Strategic Adaptation vs Personality Preservation

### C1. Can personas adapt strategically while preserving identifiable identity?

**Motivation.** A *cautious* persona should still flee a clearly losing fight, and a *cooperative* persona should still retaliate against persistent exploitation. Identity is not behavior-locked; it is a *bias*, not a *constraint*. The question is whether PCSP learns this distinction.

**Hypothesis.** PCSP agents shift action distributions in response to co-player provocation (matched-seed comparison: same persona, exploitative co-player vs. cooperative co-player), but the *magnitude and shape* of adaptation differ across personas in a persona-correlated way.

**Required experiments.**
- Fix persona, fix environment seed, vary co-player policy (cooperative scripted, defector scripted, mixed).
- Measure action-distribution shift relative to baseline.
- Repeat across personas; measure inter-persona variance of adaptation profiles.

**Expected observations.**
- A "fingerprint" of adaptation per persona: vindictive personas escalate retaliation faster; cooperative personas have higher patience; risk-averse personas withdraw earlier.

**Failure cases.**
- All personas adapt identically. Implies identity does not modulate strategic response; persona is a *style* not a *strategic disposition*.
- No personas adapt. Implies the policy is not learning context-sensitive behavior, which is a more fundamental problem.

**Possible interpretations.**
- Adaptation differences may reflect different baseline behaviors rather than different *responses*. Control: report adaptation as the *change* relative to the matched persona's baseline, not the absolute action distribution.

---

### C2. Are persona-correlated adaptation profiles transferable across substrates?

**Motivation.** If a "vindictive" persona's adaptation profile in `commons_harvest` is uncorrelated with the same persona's adaptation profile in `clean_up`, the trait label is hollow.

**Hypothesis.** Adaptation profiles are correlated across substrates within the same persona, with correlation strength exceeding what is explained by baseline-behavior similarity.

**Required experiments.**
- Per persona, compute adaptation profiles on multiple substrates.
- Compute cross-substrate within-persona correlation; compare to between-persona correlation.

**Expected observations.**
- Within-persona cross-substrate correlation exceeds between-persona correlation by a margin that survives bootstrap CI.

**Failure cases.**
- No within-persona consistency. Implies persona-conditioning is substrate-specific decoration without trait-level coherence.

**Possible interpretations.**
- Cross-substrate consistency may also reflect a shared *encoder bias* (the encoder maps all "vindictive" texts to similar embeddings, which produce similar adaptation regardless of substrate). This is a feature, not a bug, but it should be reported as a finding about the encoder.

---

## Theme D — Social Equilibrium Formation

### D1. Are persona-conditioned populations more *stable* in their equilibria than persona-blind populations?

**Motivation.** Stability — low variance of population behavior at convergence — is a quality of equilibrium. Persona conditioning might add stability (by binding each policy to a fixed strategy) or remove it (by adding stochastic per-agent bias).

**Hypothesis.** PCSP-full populations have lower episode-to-episode variance of convention metrics at convergence than B0-unconditioned populations on the same substrates.

**Required experiments.**
- Train PCSP-full and B0 populations to convergence on each substrate.
- Measure across-episode variance of convention metric over a fixed evaluation window.
- Compare with permutation tests across seeds.

**Expected observations.**
- PCSP-full variance is meaningfully lower.

**Failure cases.**
- PCSP-full variance is higher or equal. Implies persona conditioning adds inter-agent disagreement without resolving it into equilibrium.

**Possible interpretations.**
- Lower variance might come from PCSP being *under-trained* (a less-trained policy is more deterministic). Control: equalize training compute and equalize policy entropy at evaluation.

---

### D2. Do mixed-persona populations select Pareto-superior equilibria?

**Motivation.** Mixed populations might exploit role specialization to reach Pareto-superior outcomes vs. homogeneous populations.

**Hypothesis.** Mixed populations with deliberately complementary persona traits (e.g., cooperators + enforcers) achieve higher social welfare than homogeneous populations on substrates with role complementarity (e.g., `clean_up`).

**Required experiments.**
- Construct homogeneous (all cooperative), heterogeneous-complementary (cooperators + enforcers), and heterogeneous-conflicting (cooperators + free-riders) populations.
- Measure social welfare per population.

**Expected observations.**
- Complementary > homogeneous > conflicting on welfare.

**Failure cases.**
- Conflicting populations match or exceed homogeneous. Implies complementarity is not load-bearing; population identity statistics dominate composition.

**Possible interpretations.**
- A welfare advantage for complementary populations might reflect *training-time selection effects* — complementary populations might be easier to optimize. Verify by holding training algorithm and population size constant.

---

## Theme E — Controllable Social Behavior

### E1. Are persona text edits a causal control surface for social outcomes?

**Motivation.** The strongest practical claim of PCSP is that natural-language identity is a *control surface* — that designers can steer agents by editing text rather than by retraining. This requires *causal* effect, not just correlation.

**Hypothesis.** Pre-registered persona edits in a semantically interpretable direction produce signed shifts in social-outcome metrics consistent with the edit direction, under matched seeds, with effect sizes that survive multiple-testing correction.

**Required experiments.**
- Pre-register a set of persona edits and predicted effect directions before any experiments. Commit `PREREG.md` to git.
- Run matched-seed comparisons: original persona vs. edited persona, identical environment seed and co-player composition.
- Report signed effect sizes per edit with bootstrap CIs.

**Expected observations.**
- Sign agreement above chance with binomial CI; ideally ≥75% sign agreement across ≥30 edits.

**Failure cases.**
- Sign agreement at chance. Implies persona text edits do not act as a causal control surface.
- Sign agreement above chance but unreliable per edit. Implies persona is a *coarse* control surface — average effect is in the predicted direction, individual edits are unreliable.

**Possible interpretations.**
- Edits may operate through *encoder embedding shifts* rather than through *semantic content*. Check by running an "embedding ablation": replace edit-induced embedding shifts with random shifts of matched magnitude; if random shifts produce equivalent behavior changes, the encoder is the operative agent, not the semantics.

---

### E2. How granular is the control surface?

**Motivation.** A control surface that can shift "cooperativeness" but not "punishment style" is less useful than one that can shift both. What is the resolution of identity in the embedding space?

**Hypothesis.** Persona axes that are linguistically prominent in the training corpus (cooperativeness, risk-aversion, sociability) are controllable; axes that are subtle (specific punishment style, fairness conception) are not.

**Required experiments.**
- Construct edits along multiple persona axes of varying linguistic prominence.
- Measure controllability per axis.

**Expected observations.**
- A scatter (axis prominence vs. controllability) with a positive slope.

**Failure cases.**
- All axes equally (un)controllable. Implies controllability is axis-blind, which is implausible and would warrant a closer look at the corpus.

**Possible interpretations.**
- Axis prominence may be operationalized in multiple ways (token frequency, encoder-attention pattern, human annotation). Report all and check robustness.

---

### E3. Does controllability transfer across substrates?

**Motivation.** A useful control surface is substrate-invariant: editing a persona's cooperativeness should shift cooperation in any cooperative-relevant substrate.

**Hypothesis.** The signed effect of a persona edit is correlated across substrates within the same persona-and-edit pair, with cross-substrate correlation exceeding 0.5 for high-prominence axes.

**Required experiments.**
- Apply each pre-registered edit on multiple substrates.
- Compute cross-substrate correlation of signed effects.

**Expected observations.**
- Correlation > 0.5 for high-prominence axes; weaker for low-prominence axes.

**Failure cases.**
- No cross-substrate correlation. Implies controllability is substrate-local and the control surface does not generalize.

**Possible interpretations.**
- Substrate-specific failures may reflect *substrate semantics* that the persona text does not engage (e.g., "cooperativeness" has no bite in a substrate without a cooperation channel).

---

## Theme F — Emergent Role Specialization

### F1. Do persona-correlated populations develop role specialization?

**Motivation.** Role specialization — different agents taking different functional positions — is a hallmark of mature social systems. PCSP populations may develop specialization driven by persona, by training history, or not at all.

**Hypothesis.** In mixed-persona populations on substrates with role complementarity (`clean_up`, `territory`), the action histograms of different personas show statistically significant divergence; the divergence pattern is predictable from persona embeddings.

**Required experiments.**
- Train mixed-persona populations to convergence.
- Cluster agents by action histogram; assign roles to clusters.
- Test whether persona embedding predicts role cluster membership above chance.

**Expected observations.**
- Persona embedding predicts role membership with accuracy substantially above chance, on relevant substrates.

**Failure cases.**
- Persona does not predict role. Implies specialization is driven by training-history factors (initialization, replay buffer) rather than identity.
- No specialization at all. Implies the population is collapsing onto a uniform policy.

**Possible interpretations.**
- Specialization may be partly driven by *spatial position at training time*. Control with seed-randomized spawn positions.

---

### F2. Is role specialization stable under population change?

**Motivation.** A robust specialization should persist when individual agents are replaced.

**Hypothesis.** Roles persist when an agent is replaced by another agent with a similar persona embedding; roles disrupt when replaced with a dissimilar persona.

**Required experiments.**
- Train to convergence; identify the role of each agent.
- Replace one agent at a time with a held-out persona (similar / dissimilar in embedding space).
- Measure role disruption.

**Expected observations.**
- Similar-persona replacements preserve roles; dissimilar replacements disrupt.

**Failure cases.**
- Replacements always preserve roles. Implies roles are environmentally enforced, not identity-driven.
- Replacements always disrupt roles. Implies roles are agent-specific and not transferable.

---

## Theme G — Population-Level Behavioral Dynamics

### G1. How do persona-population dynamics evolve over training?

**Motivation.** Snapshot evaluation hides training-time dynamics: when do persona effects emerge? When (if ever) do they collapse?

**Hypothesis.** Identification accuracy rises early in training (driven by the InfoNCE objective), then may degrade later as the policy specializes for reward. The temporal profile is substrate-dependent.

**Required experiments.**
- Evaluate identification accuracy at fixed training-step intervals.
- Plot identification trajectories per substrate.

**Expected observations.**
- A rise-then-plateau or rise-then-fall pattern per substrate.

**Failure cases.**
- Monotone rise everywhere. Implies no reward-vs-identity conflict (consistent with B-theme failures).
- Flat near chance everywhere. Implies the InfoNCE objective is failing.

**Possible interpretations.**
- Temporal dynamics depend on training schedules (learning rate, entropy coefficient). Reporting requires multiple schedules.

---

### G2. Are population-level dynamics predictable from initial population statistics?

**Motivation.** If outcomes are predictable from initial population composition, design becomes scientific.

**Hypothesis.** Final-state social-outcome metrics are predictable from initial persona-population statistics + substrate, with predictability above what is achievable from population *size* alone.

**Required experiments.**
- Construct populations with varying persona statistics.
- Train each to convergence.
- Regress final-state outcomes on initial statistics.

**Expected observations.**
- R² substantially exceeding the size-only baseline.

**Failure cases.**
- No prediction. Implies population dynamics are dominated by training-time stochasticity.

---

## Theme H — Semantic-to-Behavior Alignment

### H1. Is the persona-embedding-to-behavior mapping smooth?

**Motivation.** A smooth mapping is interpolable: interpolating embeddings between two personas should produce interpolated behavior. Non-smooth mappings undermine the controllability claim.

**Hypothesis.** Embedding interpolation between two training personas produces behavior whose social-outcome metrics are monotonically interpolated between the two endpoints.

**Required experiments.**
- Select pairs of personas with clearly different outcomes.
- Interpolate embeddings at 5 points along the line.
- Evaluate social outcomes per interpolation point.

**Expected observations.**
- Monotone interpolation on most outcome axes.

**Failure cases.**
- Non-monotone interpolation. Implies the embedding space contains *non-trivial geometry* — interpolation crosses behavioral basins. Could be informative rather than negative.
- Constant behavior across interpolation. Implies the policy is *only* sensitive to a thresholded embedding, not the embedding itself.

**Possible interpretations.**
- Non-monotonicity may signal *attractor structure* in the policy (multiple ε-optimal policies separated by behavioral basins). This itself is a paper-worthy finding.

---

### H2. Does semantic similarity in persona text predict behavioral similarity?

**Motivation.** The premise of PCSP is that natural-language semantics → behavior. This must be measurable.

**Hypothesis.** Spearman correlation between *semantic* persona similarity (manual / LLM-graded) and *behavioral* similarity (JS-divergence of action distributions) is positive and substantial.

**Required experiments.**
- Compute pairwise semantic similarity over the persona corpus via at least two methods (manual annotation on a subset; LLM-graded across corpus).
- Compute pairwise behavioral similarity.
- Report Spearman correlation per substrate.

**Expected observations.**
- Correlation > 0.4 on most substrates; > 0.5 on multi-equilibrium substrates.

**Failure cases.**
- Correlation near zero. Implies the encoder maps semantically similar personas to behaviorally dissimilar embeddings, or the policy ignores embedding similarity.

---

### H3. Does the trajectory encoder represent persona content or behavioral signature?

**Motivation.** The trajectory encoder produces a vector aligned to the persona embedding. Is it aligned because trajectories reflect *identity* (rich content) or merely a *fingerprint* (low-dim behavioral signature)?

**Hypothesis.** The trajectory encoder representation has higher mutual information with persona text content than with low-dimensional behavioral summaries (e.g., action histogram), on multi-equilibrium substrates.

**Required experiments.**
- Train probes: trajectory-encoder representation → persona text features; trajectory-encoder representation → action histogram features.
- Compare probe accuracy.

**Expected observations.**
- Encoder representation contains more persona-text-aligned information than action-histogram information, on substrates that admit multiple equilibria.

**Failure cases.**
- Encoder is mostly an action-histogram summary. Implies identity is reducible to a coarse behavioral fingerprint; the language channel is redundant.

---

## Theme I — Multi-Agent Identity Consistency

### I1. Is persona identity preserved across population changes?

**Motivation.** A persona is supposed to be *intrinsic*. If it shifts under population change, it is more accurately modeled as a *role*.

**Hypothesis.** A given persona's action distribution at matched states is more stable across population compositions than the population's collective action distribution.

**Required experiments.**
- Fix persona, vary co-player composition (including held-out compositions).
- Sample matched states across compositions.
- Compute action-distribution variance per persona; compare to population-level variance.

**Expected observations.**
- Persona-level variance < population-level variance.

**Failure cases.**
- Persona-level variance ≥ population-level. Implies persona is fully reactive to population composition; identity is not intrinsic.

**Possible interpretations.**
- Stability may be confounded by the fraction of *states encountered* that are shared across compositions. Control by restricting analysis to a common state distribution.

---

### I2. Can a third-party observer recover persona across novel populations?

**Motivation.** This is the operational version of H3 from the proposal.

**Hypothesis.** The trajectory-level identification classifier, trained on training-population trajectories, retains substantial accuracy on trajectories generated under Melting Pot's held-out evaluation populations.

**Required experiments.**
- Train the classifier on training-population trajectories.
- Evaluate on held-out population trajectories of the same personas.
- Compare against an upper-bound classifier trained on held-out-population trajectories directly.

**Expected observations.**
- Modest accuracy drop (≤15 percentage points) from training-population to held-out-population evaluation.

**Failure cases.**
- Accuracy drops to chance under held-out populations. Implies persona is a function of co-player distribution, not an intrinsic trait.

**Possible interpretations.**
- A small drop is expected because trajectories under different populations visit different state distributions. The question is whether *identifying* features (e.g., action conditional on a matched state) transfer.

---

### I3. Is persona stable within an episode under within-episode population shocks?

**Motivation.** A within-episode population shock (a co-player suddenly defects) tests whether persona governs the *response*, not just the steady-state behavior.

**Hypothesis.** Persona explains a substantial fraction of within-episode behavior-response variance to a co-player shock, beyond what is explained by current observation alone.

**Required experiments.**
- Construct a synthetic within-episode shock (scripted co-player switches strategy at a fixed step).
- Measure agent response per persona.
- Decompose variance into persona-attributable vs. observation-attributable.

**Expected observations.**
- Persona-attributable variance is substantial.

**Failure cases.**
- All response is observation-attributable. Implies persona is irrelevant to within-episode strategic response.

---

## Cross-Theme Methodological Questions

### M1. What is the right unit of statistical analysis?

The fundamental unit is the (substrate, seed, persona, population, run) tuple. Aggregation across substrates is suspect; aggregation across seeds within a (substrate, persona, population) cell is the minimum unit for CI computation. Document this in the paper's methods section.

### M2. How should we report negative results?

Negative results — identity collapse, controllability failure, convention non-emergence — are first-class scientific contributions. Treat them as such in the paper structure. A failed hypothesis on substrate X should be reported with the same rigor as a success on substrate Y. Do not relegate them to the appendix.

### M3. How should we discount the FiLM/concat debate?

The v3 finding is that FiLM vs. concat is *split-dependent*. Carry this forward as a known phenomenon, not as a method claim. Do not make a headline claim that FiLM > concat in Melting Pot.

### M4. What should the program's primary result figure look like?

A single figure with one Pareto front (return vs. identification accuracy) per substrate, with PCSP-full and key ablations marked, would be the highest-leverage figure. All other figures support this one.

### M5. What is the scope of a single paper?

Themes A, B, E, plus a representative subset of {C, D, F, G, H, I} likely fit a single main-track paper. Themes that fail empirically can be deferred to a workshop note. Themes that produce major positive results may justify a second paper.

---

## Coda: What We Are Really Asking

Strip away the technical scaffolding, and the program asks one question:

> *Can a frozen embedding of a natural-language identity hold up under the pressure of consequential social decision-making, well enough that the resulting agent population looks like a society of distinguishable individuals rather than a homogeneous reward-optimizing crowd?*

Every research question above is an instance of that question with a specific operationalization, a specific environment, and a specific metric. The Melting Pot program's value, regardless of the sign of the answer, is in producing a defensible, calibrated answer.
