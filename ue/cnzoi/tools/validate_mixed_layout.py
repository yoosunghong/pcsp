"""Read-only audit of the persisted Portfolio layout (run in Unreal Python)."""
import math
from collections import Counter

import unreal


def validate():
    path = "/Game/PCSP/Maps/Map_PCSPDistrict_Portfolio"
    assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level(path)
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    zones = sorted(
        (actor for actor in actors if isinstance(actor, unreal.PCSPAffordanceZone)),
        key=lambda zone: (zone.get_actor_location().y, zone.get_actor_location().x),
    )
    # The district has two sanctioned shapes: the original 96/592 layout and the
    # capacity-expanded 118/1704 one produced by -ExpandCapacity.
    expected_slots = {96: 592, 118: 1704}
    zone_count = len(zones)
    assert zone_count in expected_slots, zone_count
    columns = 12
    rows = -(-zone_count // columns)
    min_slot_spacing = 419.9 if zone_count == 96 else 279.9
    max_same_category_neighbors = 0 if zone_count == 96 else 6
    categories = []
    slots = []
    footprints = []
    indices = set()
    for index, zone in enumerate(zones):
        location = zone.get_actor_location()
        assert abs(location.x - ((index % columns) - (columns - 1) / 2) * 2500) < 0.1
        assert abs(location.y - ((index // columns) - (rows - 1) / 2) * 2000) < 0.1
        categories.append(str(zone.get_editor_property("category")))
        indices.add(zone.get_editor_property("visualization_index"))
        local_slots = zone.get_editor_property("interaction_slots")
        assert len(local_slots) == zone.get_editor_property("capacity")
        assert not zone.get_editor_property("interaction_points")
        extent_x = extent_y = 0.0
        for slot in local_slots:
            relative = slot.get_editor_property("relative_location")
            extent_x = max(extent_x, abs(relative.x))
            extent_y = max(extent_y, abs(relative.y))
            slots.append((location.x + relative.x, location.y + relative.y))
        padding = zone.get_editor_property("bounds_padding")
        footprints.append((location.x, location.y, extent_x + padding, extent_y + padding))
    assert len(slots) == expected_slots[zone_count], len(slots)
    assert indices == set(range(zone_count))
    neighbors = sum(
        categories[index] == categories[other]
        for index in range(zone_count)
        for other in (index + 1, index + columns)
        if other < zone_count and (other != index + 1 or index % columns != columns - 1)
    )
    overlaps = sum(
        abs(a[0] - b[0]) < a[2] + b[2] and abs(a[1] - b[1]) < a[3] + b[3]
        for index, a in enumerate(footprints) for b in footprints[index + 1:]
    )
    minimum = min(math.dist(a, b) for index, a in enumerate(slots) for b in slots[index + 1:])
    # The seeded interleave drives same-category neighbours to zero on the 96-zone
    # district. The expanded one packs 20 Idle plazas into 118 cells, so allow a
    # small residue rather than pretending the greedy repair always reaches zero.
    assert neighbors <= max_same_category_neighbors, neighbors
    assert overlaps == 0, overlaps
    assert minimum >= min_slot_spacing, minimum
    assert not any(isinstance(actor, unreal.PCSPInteractionPoint) for actor in actors)
    unreal.log(f"PCSP_SAVED_LAYOUT PASS zones={len(zones)} slots={len(slots)} "
               f"same_category_neighbors={neighbors} overlaps={overlaps} min_slot_distance={minimum:.1f}")
    unreal.log(f"PCSP_SAVED_LAYOUT category_counts={dict(Counter(categories))}")
    for actor in actors:
        if isinstance(actor, unreal.PCSPAgentSpawner):
            unreal.log(f"PCSP_SAVED_LAYOUT spawner={actor.get_name()} "
                       f"actors={actor.get_editor_property('agent_count')} "
                       f"mass={actor.get_editor_property('mass_entity_count')}")


if __name__ == "__main__":
    validate()
