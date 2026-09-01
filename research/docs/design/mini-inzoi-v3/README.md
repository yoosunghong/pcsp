# Mini-Inzoi v3 Design

The v3 contract is split by concern so a task does not need to load one historical monolith.

| Document | Authoritative scope |
| --- | --- |
| [ontology-and-observations.md](ontology-and-observations.md) | Stable 20-action IDs, observation layout, and flat-action decision |
| [training-and-validation.md](training-and-validation.md) | Rewards, compatibility, persona conversion, retraining, and acceptance gates |

**Code anchors:** `src/env/v3_constants.py`, `src/env/mini_inzoi_v3.py`, `src/env/action_semantics.py`, and `scripts/test_env_v3.py`.

Changing an action ID, observation slice, or reward term is an API change: update both contracts, `research/PLAN.md`, the UE bridge contract when relevant, and record checkpoint impact in `DONE.md`.
