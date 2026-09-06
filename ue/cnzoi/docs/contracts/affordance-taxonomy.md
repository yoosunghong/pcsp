# Phase 0 — UE5 Affordance Taxonomy

Phase 0 calls for a canonical taxonomy of zone categories, sub-tags, and
capacity targets. The three-layer architecture (action ↔ category ↔ tag) is
already documented in [`../architecture/affordance-system.md`](../architecture/affordance-system.md);
this file pins the **specific instances** the medium district must place and
the capacity targets validated in Phase 4.

## Canonical zone roster (`Map_PCSPDistrict_M`)

10 categories. Each one needs at least one `BP_AffordanceZone` actor with the
listed tag and integrated interaction slots equal to capacity.

| Category | Root tag | Sub-tag actually placed | Capacity | Interaction points | Sized for |
|---|---|---:|---:|---:|---|
| Eat | `PCSP.Zone.Eat` | `Kitchen` | 8 | 8 | 64 agents at v3 frequency |
| Rest | `PCSP.Zone.Rest` | `BedroomLounge` | 20 | 20 | 64-agent peak (highest demand) |
| Work | `PCSP.Zone.Work` | `Office` | 12 | 12 | Held-out personas demand profile |
| Study | `PCSP.Zone.Study` | `Library` | 4 | 4 | Low base demand |
| Exercise | `PCSP.Zone.Exercise` | `Gym` | 4 | 4 | Low base demand |
| Hygiene | `PCSP.Zone.Hygiene` | `Bathroom` | 6 | 6 | Raised from 4 after 2026-05-18 held-out run |
| Social | `PCSP.Zone.Social` | `SocialHub` | 20 | 20 | 64-agent peak (second-highest demand) |
| Leisure | `PCSP.Zone.Leisure` | — | — | — | **No zone — folded into Observe via the v3 movement remap (see below)** |
| Shop | `PCSP.Zone.Shop` | `Shop` | 4 | 4 | Policy emits `BrowseArea` ~0.25% — minimum |
| Observe | `PCSP.Zone.Observe` | `Park` | 4 | 4 | Covers v3 indices 16–19 + `ObserveCrowd` |

**Effective taxonomy is 9 categories, not 10.** The `Leisure` enum value
exists in `EPCSPAffordanceCategory` but has no zone in the level — the v3
movement remap (`PCSPPolicySubsystem.cpp`) routes v3 indices 16/18
(`LeisureOutdoor`) and 17/19 (`ObserveCrowd`) through the Park/Observe zone via
`UPCSPPolicySubsystem::ActionToCategory`. This is recorded in the Phase 4
16-agent baseline entry of `PLAN.md`.

## Capacity provenance

Numbers came from Phase 4 stress runs, not from first principles:

- **Rest & Social = 20** — set after the 64-agent 3-run progression
  (`20260517_150713` → `224132` → `230327`). Lower values produced
  `FindBestZone:AllOverCapacity` spikes that drove the failure rate above 80%.
- **Work = 12, Hygiene = 6** — raised after the 2026-05-18 held-out
  zero-shot run (`20260518_112540`) showed Work `AllOverCapacity` failures
  at 99.4% of all failures when single-Office capacity met the held-out
  demand profile. After raising both, the clean held-out run
  (`20260518_140432`) hit 0.04% failure rate over 2,792 interactions.
- **Eat, Study, Exercise, Shop, Observe = 4–8** — base values that held up
  under all stress runs because demand never saturated them.

If you change persona distribution (different `personas_300_v3.json` or a
custom split), re-run the diagnostic recipes in
[`../../PLAN.md` §B](../../PLAN.md) to see whether `AllOverCapacity` shifts to
new bottleneck zones.

## Zone-actor placement rules

Carried over from Phase 4 and pinned here so future map edits don't regress:

1. **World Partition** — every `BP_AffordanceZone` and
   `BP_PCSPAgentSpawner` must have `Is Spatially Loaded = false`. With no
   `WorldPartitionStreamingSource` present (AI-only pawns), spatially loaded
   actors outside the editor camera's startup radius never spawn, so the
   subsystem registers fewer zones than the map contains. See the 2026-05-17
   streaming fix in `PLAN.md`.
2. **NavMesh** — every Zone-owned interaction slot must lie on a navigable area.
   `BTTask_MoveToAffordance::TryBeginMove` calls
   `SetReachTestIncludesAgentRadius(false)` so a 3 m `AcceptanceRadius` means
   3 m to the goal, not 3 m + agent capsule. Don't increase the acceptance
   radius to "fix" arrival failures — fix the navmesh hole.
3. **Reservation** — lives in `APCSPAffordanceZone::InteractionSlots`. Capacity
   is derived from slot count, and the Zone bounds expand automatically to contain
   all slots plus padding. Each slot renders a circular floor marker in its
   Zone's stable unique color; targeting NPCs reuse exactly that color.
   `APCSPInteractionPoint` exists only as legacy migration input.

## What changes if you extend the taxonomy

If you add a new category (e.g., `Cook`), update **all four** layers, in this
order:

1. `EPCSPAffordanceCategory` in `PCSPTypes.h` — add the enum value before `Idle`/`None`.
2. `UPCSPPolicySubsystem::ActionToCategory` — add the action→category mapping.
3. `DT_PCSPAffordanceTags` — register `PCSP.Zone.Cook` (and any sub-tags).
4. Map — place at least one `BP_AffordanceZone` with the new tag, set
   `Is Spatially Loaded = false`, and configure its integrated slot count.

Then re-export `pcsp_actor.onnx` only if the new category needs new
`EPCSPActionType` entries — i.e. if the action vocabulary changes. Adding a
category that just re-routes an existing action does not require retraining.
