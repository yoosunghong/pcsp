# SUBSTRATES.md — Phase 0 Substrate Selection

**Status:** Phase 0 deliverable. Selection is a recommendation pending the Phase 0 decision review.
**Updated:** 2026-05-14
**Cross-references:** `MELTINGPOT_PROPOSAL.md` (H1–H5), `MELTINGPOT_PLAN.md` (Phase 0 §Tasks), `BUDGET.md` (compute cost).

---

## 1. Inventory

Melting Pot 2.4.0 ships **49 substrates**. Full list with player counts and roles is regenerable via
`scripts/list_meltingpot_substrates.py` (TBD) or directly from `meltingpot.substrate.SUBSTRATES`.

---

## 2. Classification

Each substrate is placed in exactly one primary category. Where a substrate spans categories (e.g. `chicken_in_the_matrix` is both a coordination and a mixed-motive game), the dominant payoff structure decides.

### A. Common-pool resource / collective action

Overuse vs. sustainable harvest of a shared, depletable resource. Public-good variants placed here when the dominant tension is free-riding.

- `commons_harvest__open`
- `commons_harvest__closed`
- `commons_harvest__partnership`
- `clean_up` (positive-externality public good)
- `externality_mushrooms__dense`
- `factory_commons__either_or`

### B. Coordination (matching-equilibrium)

Multiple Pareto-rankable equilibria, no defection incentive once locked in. Persona expectations should predict which equilibrium population converges on.

- `pure_coordination_in_the_matrix__arena`, `__repeated`
- `rationalizable_coordination_in_the_matrix__arena`, `__repeated`
- `bach_or_stravinsky_in_the_matrix__arena`, `__repeated` (battle-of-sexes — coordination + distributional conflict)
- `stag_hunt_in_the_matrix__arena`, `__repeated` (risk-dominant vs. payoff-dominant)
- `boat_race__eight_races`
- `coop_mining`
- `collaborative_cooking__cramped`, `__ring`, `__forced`, `__asymmetric`, `__circuit`, `__crowded`, `__figure_eight`

### C. Mixed-motive matrix (PD family)

Defection is dominant or partially dominant.

- `prisoners_dilemma_in_the_matrix__arena`, `__repeated`
- `chicken_in_the_matrix__arena`, `__repeated`
- `coins`

### D. Territorial / property

Spatial appropriation, claiming or defending tiles/regions. Includes zero-sum team variants.

- `territory__open`, `__rooms`, `__inside_out`
- `paintball__capture_the_flag`, `__king_of_the_hill`

### E. Asymmetric roles / exploitation

Distinct role payoffs are core to the game; populations cannot be composed homogeneously.

- `daycare` (parent / child)
- `hidden_agenda` (crewmate / impostor)
- `predator_prey__alley_hunt`, `__open`, `__orchard`, `__random_forest`
- `fruit_market__concentric_rivers` (apple_farmer / banana_farmer)
- `allelopathic_harvest__open` (player_who_likes_green / player_who_likes_red)

### F. Adversarial cycle / non-transitive

Rock-paper-scissors–style payoff cycles, exploitation is policy-class-dependent.

- `running_with_scissors_in_the_matrix__one_shot`, `__repeated`, `__arena`

### G. Reciprocity / norm emergence

Slow-burn conventions; not directly tied to a Nash analysis.

- `chemistry__two_metabolic_cycles`, `__two_metabolic_cycles_with_distractors`
- `chemistry__three_metabolic_cycles`, `__three_metabolic_cycles_with_plentiful_distractors`
- `gift_refinements`

---

## 3. Selection for the program

The plan asks for 4–6 substrates covering ≥3 categories. **Recommended: 5 substrates spanning categories A, B, C, D.** Category E (asymmetric roles) is held out as a *side study* because role-conditioned populations confound the persona-population-statistics analyses central to H2.

| # | Substrate | Cat. | Players | Held-out scenarios | Why included |
|---|---|---|---|---|---|
| 1 | `commons_harvest__open` | A | 7 | **2** | Canonical CPR; Melting Pot baseline. Anchor for H1, H2. *Caveat: only 2 held-out scenarios — H3 evidence will be thin from this substrate alone.* |
| 2 | `clean_up` | A | 7 | 23 | Public-good complement — positive-externality contribution, not extraction. Tests identification under inverted incentive sign. Carries the bulk of H3 evidence in Category A. |
| 3 | `prisoners_dilemma_in_the_matrix__arena` | C | 8 | 22 | Direct anchor to PD literature; clean cooperation/defection labels for the identification classifier. |
| 4 | `stag_hunt_in_the_matrix__repeated` | B | 2 | 10 | Smallest-population coordination test. Risk-dominant vs. payoff-dominant choice gives a binary persona-driven prediction for H4 controllability. |
| 5 | `territory__rooms` | D | 9 | 14 | Spatial property dynamics, largest population in the set. Orthogonal to consumption-based dilemmas. |

Category coverage: A×2, B×1, C×1, D×1 → **4 categories, ≥3 satisfied.**
Player-count span: 2 / 7 / 7 / 8 / 9 → enough variance to test population-size scaling without ballooning compute.
All five have single-role (`default`) populations, allowing homogeneous-population sweeps without role-balancing constraints.

### Alternate / side-study substrates

If compute permits expanding past 5:

- **`bach_or_stravinsky_in_the_matrix__repeated`** (2 players, B). Battle-of-sexes — adds *distributional* conflict to coordination, sharper test of persona-mediated equilibrium selection. Drop-in replacement for stag_hunt if a single Category-B substrate is preferred over both.
- **`running_with_scissors_in_the_matrix__repeated`** (2, F). Non-transitive payoff — adds a test where persona prediction must be cycle-aware, not just cooperation-axis-aligned.

### Substrates explicitly de-scoped from the main claim

Held out because they confound either the population-composition analysis or the identification classifier:

- All `predator_prey__*` (Category E). Two-role asymmetry; identification labels would mostly recover role, not persona.
- `hidden_agenda` (Category E). Role asymmetry + game-of-deception payoff; persona-driven prediction is muddled by deception strategy.
- `daycare` (Category E). Same.
- All `collaborative_cooking__*` (Category B). High-skill manipulation environments; persona signal swamped by motor-skill learning.
- `chemistry__*` (Category G). Long-horizon norm emergence is interesting for a follow-up but adds episode-length cost; defer.

These may appear in side-bar appendix experiments but **must not enter Phase 3–4 headline metrics**.

---

## 4. Decision-review checklist

Before promoting this selection from "recommendation" to "committed":

- [ ] Confirm engineering-trainer path (`BUDGET.md` §5) so per-run cost numbers are real, not extrapolated.
- [ ] Run a 100k-step env-only stress on each of the 5 substrates to catch ones with unusable RGB dimensions or surprising step-time.
- [ ] Verify the identification classifier can fit on each substrate's observation tensor without OOM at the batch sizes Phase 4 needs.
- [x] Confirm Melting Pot's held-out evaluation populations (`meltingpot.scenario`) exist for all 5 — done; counts (2 / 23 / 22 / 10 / 14) above. **H3 risk:** `commons_harvest__open` only has 2 scenarios; consider adding `commons_harvest__closed` or `__partnership` if H3 needs more CPR statistical power.
