# Research Documentation

Read the smallest document that answers the current task. `PLAN.md` is the active checklist and `DONE.md` is the chronological decision log; neither replaces a technical contract or reproducible result report.

| Area | Start here | Purpose |
| --- | --- | --- |
| Environment design | [design/mini-inzoi-v3/README.md](design/mini-inzoi-v3/README.md) | v3 action, observation, reward, and compatibility decisions |
| Evaluation evidence | [evaluations/](evaluations/) | Frozen protocols and result-bound interpretation |
| UE bridge evidence | [integration/ue-simulation-tier-behavior.md](integration/ue-simulation-tier-behavior.md) | Actor/Mass behavior-preservation validation |

## Maintenance rules

- Stable interfaces and ontologies belong in `design/`.
- A fixed result with artifacts and a reproduction command belongs in `evaluations/` (or `integration/` for cross-runtime work).
- Add only short dated summaries to `DONE.md`; do not append experiment narratives to a design document.
- When a document gains a second independent concern, split it and make its parent a navigation page.
- Update links in `README.md`, `PLAN.md`, `DONE.md`, scripts, and UE docs in the same change.
