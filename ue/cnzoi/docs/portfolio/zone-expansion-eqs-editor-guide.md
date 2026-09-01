# 1,024-NPC Zone Expansion and EQS Authoring Guide

## Purpose and boundary

The current level has roughly one authored zone per active semantic category.
That is sufficient for the 16--64 Actor prototype, but it makes a 1,024-NPC
district look sparse and makes every selection policy converge on the same
small set of destinations.  This guide creates the editor-owned content needed
for the next runtime pass:

1. many visually distinct destinations for the Mass background tier;
2. enough physical interaction capacity for the Hero Actor tier; and
3. one reusable EQS query asset whose final scoring is supplied by C++.

Do **not** create 1,024 zone actors.  NPC count and destination count should
scale differently: the Mass tier shares routes and aggregates density, while
Hero Actors reserve real interaction points.  The target below is 96 zones and
592 interaction points, which gives spatial variety without turning level
authoring or World Partition into the next bottleneck.

The C++ runtime will continue to choose the semantic category.  The zone/EQS
layer selects a concrete instance only; it must not alter the PCSP 20-action
ontology or the 33-dimensional observation contract.

## Target zone budget

Create these instances in `Map_PCSPDistrict_Portfolio` first.  Once proven,
mirror them into `Map_PCSPDistrict_M` only if that map remains part of the
benchmark protocol.

### Current editor inventory (2026-09-01)

The live MCP discovery pass found 10 registered zone actors and 210 referenced
interaction points. All have `Capacity == InteractionPoints.Num()` and are
non-spatially-loaded. One legacy `Leisure` zone (16 points) remains in the
map; manually reclassify it as `Observe` / `PCSP.Zone.Observe.View_01` when
authoring the expanded district, because the runtime folds Leisure intent into
Observe. The 96 instance tags in `Config/DefaultGameplayTags.ini` are already
reserved for the authoring pass.

### Validated placement surface and persistence gate (2026-09-01)

The supplied plane reference `(-10, -470, 0)` is covered by two adjacent
`Floor` actors at `(-190, -470, 0)` and `(400, -470, 0)`. Each is scaled
`(15, 15, 1)` and together exposes a continuous practical placement surface
from approximately `X=-7,690..7,900`, `Y=-7,970..7,030`, `Z=0`; the current
`NavMeshBoundsVolume` and `RecastNavMesh` cover this surface. No authored
building StaticMeshActor is present in this map, so this pass must distribute
destinations across the navigable floor sectors rather than claim building
interiors that do not exist.

The stock live MCP can spawn World Partition external actors and can persist
their initial packages after an editor Save, but its generic property writer
does **not** persist changes to `Category`, `ZoneTag`, or `InteractionPoints`.
Reload resets those values to defaults. Do not bulk-spawn with this toolset
until a property-saving editor utility/toolset is available: it would create
hundreds of default, unregistered actors. A five-actor Rest probe was created,
reloaded, verified, and removed; the map is back to its 10-zone baseline.

The project now supplies that utility as the editor-only commandlet
`UPCSPZoneLayoutCommandlet`. It was run successfully on 2026-09-01 after the
EQS asset was saved, producing 86 zones and 382 points through native UnrealEd
property serialization. The resulting external-actor package count is 704
(the prior 236 plus exactly 468 new actors). The commandlet refuses to run
unless the map has the expected 10-zone baseline, preventing accidental
duplicate expansion. Its source is
`Source/cnzoiEditor/Private/PCSPZoneLayoutCommandlet.cpp`.

When the persistence gate is fixed, use nine navigable sectors centred at
`(-5,200,-5,200)`, `(0,-5,200)`, `(5,200,-5,200)`,
`(-5,200,-470)`, `(0,-470)`, `(5,200,-470)`,
`(-5,200,4,300)`, `(0,4,300)`, `(5,200,4,300)`. Keep each zone centre at
least 600 cm from a sector edge, arrange its interaction points in a
200--300 cm local grid, and snap every point to ground before the NavMesh
reachability check. Rotate category assignment across the nine sectors rather
than creating same-category rows.

| Semantic category | Zone instances | Interaction points per zone | Total points | Typical authored places |
| --- | ---: | ---: | ---: | --- |
| Rest | 16 | 6 | 96 | apartments, lounges, quiet rooms |
| Social | 14 | 8 | 112 | plazas, cafes, club rooms |
| Work | 12 | 6 | 72 | offices, co-working blocks |
| Eat | 10 | 6 | 60 | food court, kitchens, stalls |
| Study | 10 | 6 | 60 | library bays, classrooms |
| Observe | 10 | 8 | 80 | park overlooks, promenades |
| Exercise | 8 | 6 | 48 | gym bays, courts, trails |
| Hygiene | 8 | 4 | 32 | restroom and washroom blocks |
| Shop | 8 | 4 | 32 | shops and market stalls |
| **Total** | **96** | — | **592** | — |

`Leisure` remains intentionally folded into `Observe`; do not add a separate
Leisure zone category.  Keep each zone's `Capacity` equal to its actual number
of valid `BP_InteractionPoint` children.  Capacity must never be inflated to
mask missing interaction points.

Spread each category over at least three district sectors.  Place Rest, Social,
Work, Eat, and Observe in more than five sectors; these are the highest-value
destinations for visible crowd distribution.  Use several route alternatives
between sectors rather than placing all instances along one central corridor.

## Zone actor authoring

1. Open `Map_PCSPDistrict_Portfolio` and save a checkpoint copy before bulk
   placement.
2. Drag `BP_AffordanceZone` into the level.  Duplicate an existing instance
   only when its category and interaction-point composition match.
3. Set the exact `Category` and matching `ZoneTag`.  Use one stable tag per
   instance, for example `PCSP.Zone.Rest.Apt_01` and
   `PCSP.Zone.Social.Plaza_02`; never reuse instance tags.
4. Size `Bounds` to the functional destination area, not the whole building.
   Adjacent zones must not overlap unless they represent separate floors or
   explicit alternatives.
5. Add the required `BP_InteractionPoint` actors within the bounds, add every
   point to the zone's `InteractionPoints` array, and set `Capacity` to that
   array count.  Verify every point is reachable on the NavMesh.
6. Set **Is Spatially Loaded = false** for every zone and interaction point.
   This is required because the runtime selector must see every destination
   even when there is no local player streaming source.
7. Use an editor folder per category and sector, e.g.
   `PCSP/Zones/Rest/North/Apt_01`, rather than a single flat Outliner list.

After each category is placed, run Simulate PIE with 16 Hero Actors.  Confirm
the log does not report `AllCategoryMismatch`, missing interaction points, or
unreachable targets.  Do a 64-Hero stress run after all 96 zones are present;
that run is the capacity baseline for the new congestion scorer.

## EQS asset: create now

Create the reusable query asset before the custom PCSP tests are compiled.
The asset may initially use only the standard tests below; its custom tests
are appended in the final section when the code exposes them.

1. In Content Browser, create the folder `Content/PCSP/AI/EQS/`.
2. Create an **Environment Query** named `EQS_PCSP_SelectAffordanceZone`.
3. Add a **Generator: Actors Of Class**:
   - *Searched Actor Class*: `APCSPAffordanceZone` (or `BP_AffordanceZone` if
     that is the selectable class in the editor).
   - *Search Center*: `Querier`.
   - do not set a radius limit here; C++ rejects nonmatching category/capacity
     candidates before accepting the EQS result.
4. Add a **Distance** test:
   - *Test Purpose*: Score Only.
   - *Filter Type*: Minimum 200 cm, Maximum 20,000 cm.
   - *Scoring Equation*: Inverse Linear.
   - *Weight*: `0.50`.
5. Add a **Pathfinding / Path Length** test:
   - *Test Purpose*: Filter and Score.
   - *Path From Context*: Querier.
   - *Path To Item*: enabled.
   - *Discard Unreachable*: enabled.
   - *Filter Type*: Maximum 25,000 cm.
   - *Scoring Equation*: Inverse Linear.
   - *Weight*: `0.25`.
6. Save the asset.  Do not connect it to `BT_PCSPAgent` yet; the C++ task will
   execute it directly and retain `FindBestZone` as its safe fallback.

## EQS tests to append after the C++ congestion pass

When `UEnvQueryTest_PCSPOccupancy`,
`UEnvQueryTest_PCSPReservationPressure`, and
`UEnvQueryTest_PCSPRecentFailureBias` appear in the editor, add them after
Path Length in this order:

| Test | Purpose | Scoring | Weight | Filter |
| --- | --- | --- | ---: | --- |
| PCSP Occupancy | Filter and Score | inverse linear availability | 0.60 | reject capacity `0` |
| PCSP Reservation Pressure | Score | inverse linear | 0.30 | none |
| PCSP Recent Failure Bias | Score | prefer unseen/recently successful zones | 0.15 | none |

Leave score normalization enabled.  The runtime adds a small deterministic
per-agent tie-breaker; do not add an uncontrolled random generator node to the
asset, because it would make repeated benchmark seeds harder to compare.

## Editor verification checklist

- [ ] 96 distinct zone tags; every tag is unique.
- [ ] 592 valid interaction points; each belongs to exactly one zone.
- [ ] `Capacity == InteractionPoints.Num()` for every zone.
- [ ] all actors are non-spatially-loaded and visible in a standalone run.
- [ ] NavMesh covers every interaction point and at least two sector-to-sector
      routes exist for all high-demand categories.
- [ ] the saved query is exactly
      `Content/PCSP/AI/EQS/EQS_PCSP_SelectAffordanceZone`.
- [ ] 16-Hero PIE smoke and 64-Hero congestion baseline have been captured.

## Hand-off to C++ work

Once the asset and zones are saved, report the map and asset paths.  The next
runtime change will: add weighted selection telemetry, invoke this query with
the desired category, fall back safely on timeout/no result, and compare the
64-Hero baseline against the prior deterministic nearest-zone selector.  Only
after that baseline is established should ZoneGraph/MassCrowd, shared route
caching, and density-aware admission replace the Mass straight-line movement.
