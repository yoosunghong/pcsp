# Mini-Inzoi v3: Ontology and Observation Contract

v3 makes persona-relevant behavior observable in the rollout. It keeps a flat `Discrete(20)` interface: 16 activities and four grid-movement actions. Action ordering is checkpoint-compatible API and must not be reordered.

| IDs | Actions | Persona-visible distinction |
| --- | --- | --- |
| 0–1 | `focused_work`, `planning_work` | deep/solo vs structured/slow work |
| 2–3 | `eat_quick`, `eat_slow` | fast intake vs savoring |
| 4–5 | `sleep`, `nap` | full vs brief recovery |
| 6–7 | `socialize_initiate`, `socialize_respond` | proactive vs reactive social behavior |
| 8–9 | `exercise_intense`, `exercise_light` | high vs low effort |
| 10–11 | `read_deep`, `read_casual` | learning vs leisure style |
| 12 | `clean` | hygiene/self-care |
| 13–15 | `rest_alone`, `rest_with_others`, `explore` | solo, group, and novelty-seeking leisure |
| 16–19 | `move_up`, `move_down`, `move_left`, `move_right` | grid navigation only |

`ACTION_STYLE_PROFILE` is the stable `(20, 5)` Big-Five-aligned table; exact names, restore table, and Korean rendering live in `src/env/v3_constants.py` and `src/env/action_semantics.py`.

| Slice | Dim | Meaning |
| --- | ---: | --- |
| position | 2 | normalized row and column |
| time of day | 1 | normalized hour |
| needs | 8 | normalized need values |
| affordance | 8 | nearest world-object affordance one-hot |
| social context | 3 | nearby count, conversation, last-responder flags |
| routine | 2 | repeat count and time since novelty |
| other agents | `3 × (N-1)` | normalized position and last action per peer |

The base 4-agent environment is 33 dimensions; the 16-agent v3-large variant is 69. Affordance, social, and routine are the explicit persona-observability handles. Their order and normalization are part of the ONNX/training contract.

The single `n_actions` actor head makes v3 a controlled action-count change. Revisit a factorized intent/style head only after an actionable held-out compositional-generalization result demonstrates a bottleneck.
