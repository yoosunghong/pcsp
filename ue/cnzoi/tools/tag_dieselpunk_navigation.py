"""Tag the expanded city surfaces and obstacles for shared Mass routing.

Run through the official ProgrammaticToolset in the open Visual map. The tags
are ordinary Actor Tags, so designers can opt surfaces or obstacles in/out in
Details without rebuilding C++.
"""
import json

CITY_FOLDER = 'PCSP_City'
WALKABLE_TAG = 'PCSP.City.Walkable'
OBSTACLE_TAG = 'PCSP.City.Obstacle'

WALKABLE_PREFIXES = (
    'City_Roadbed', 'City_Block_', 'City_Court_', 'City_Promenade',
    'City_CanalBank_', 'City_Bridge_Deck_', 'City_Bridge_Walk_',
    'City_Crossing_', 'City_West_Link',
)


def call(name, args):
    return execute_tool(name, json.dumps(args))['returnValue']


def run():
    scene = 'editor_toolset.toolsets.scene.SceneTools.'
    actor_tools = 'editor_toolset.toolsets.actor.ActorTools.'
    actors = call(scene + 'get_actors_in_folder', {
        'folder_path': CITY_FOLDER, 'recursive': True})
    walkable = []
    obstacles = []
    for actor in actors:
        label = call(actor_tools + 'get_label', {'actor': actor})
        is_walkable = label.startswith(WALKABLE_PREFIXES)
        is_obstacle = (label.startswith('PCG_City_')
                       or 'Bldg' in actor['refPath']
                       or label.startswith(('City_Lamp_', 'City_Bench_',
                                            'City_QuayLamp_', 'City_Quay_Parapet_',
                                            'City_Bridge_Parapet_'))
                       or label in ('City_Library', 'City_GeneralStore',
                                    'City_BusStop', 'City_PhoneBooth', 'City_Civic_Armillary'))
        if is_walkable:
            if not call(actor_tools + 'has_tag', {'actor': actor, 'tag': WALKABLE_TAG}):
                call(actor_tools + 'add_tag', {'actor': actor, 'tag': WALKABLE_TAG})
            walkable.append({'actor': actor, 'label': label,
                             'bounds': call(actor_tools + 'get_actor_bounds', {'actor': actor})})
        if is_obstacle:
            if not call(actor_tools + 'has_tag', {'actor': actor, 'tag': OBSTACLE_TAG}):
                call(actor_tools + 'add_tag', {'actor': actor, 'tag': OBSTACLE_TAG})
            obstacles.append({'actor': actor, 'label': label,
                              'bounds': call(actor_tools + 'get_actor_bounds', {'actor': actor})})
    if len(walkable) < 30 or len(obstacles) < 144:
        raise RuntimeError('Unexpected navigation inventory: walkable=%d obstacles=%d'
                           % (len(walkable), len(obstacles)))
    return {'walkable_count': len(walkable), 'obstacle_count': len(obstacles),
            'walkable': walkable, 'obstacles': obstacles}
