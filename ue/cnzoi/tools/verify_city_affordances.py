"""Read-only MCP checks; prepend PLACEMENTS for the selected batch.

Compares actual serialized slots, identities and transforms with the approved
offline geometry plan. Samples the first, middle and last slot against ground;
the offline audit checks all slot clearances and footprints, not just samples.
"""
import json
import math

TRACE_GROUND = True


def call(tool,args):
    return execute_tool(tool,json.dumps(args))['returnValue']


def run():
    obj='editor_toolset.toolsets.object.ObjectTools.'
    actor='editor_toolset.toolsets.actor.ActorTools.'
    scene='editor_toolset.toolsets.scene.SceneTools.'
    results=[]
    failures=[]
    for row in PLACEMENTS:
        a=row['actor']
        props=json.loads(call(obj+'get_properties',{'instance':a,'properties':['zoneTag','category','visualizationIndex','capacity','interactionSlots','bAutoGenerateGrid','bIsSpatiallyLoaded']}))
        transform=call(actor+'get_actor_transform',{'actor':a})
        yaw=math.radians(transform['rotation']['yaw'])
        errors=[]
        if props['zoneTag']['tagName']!=row['zone_tag'] or props['visualizationIndex']!=row['visualization_index'] or props['category']!=row['category']:
            errors.append('identity mismatch')
        if props['capacity']!=row['capacity'] or len(props['interactionSlots'])!=row['capacity']:
            errors.append('capacity mismatch')
        if props['bAutoGenerateGrid'] or props['bIsSpatiallyLoaded']:
            errors.append('unexpected generation or streaming flag')
        world=[]
        for slot in props['interactionSlots']:
            p=slot['relativeLocation']
            world.append({'x':transform['location']['x']+math.cos(yaw)*p['x']-math.sin(yaw)*p['y'],'y':transform['location']['y']+math.sin(yaw)*p['x']+math.cos(yaw)*p['y'],'z':transform['location']['z']+p['z']})
        for actual,expected in zip(world,row['world_slots']):
            if any(abs(actual[k]-expected[k])>0.05 for k in ['x','y','z']):
                errors.append('world slot mismatch')
                break
        samples=[]
        for index in (sorted(set([0,len(world)//2,len(world)-1])) if TRACE_GROUND else []):
            p=world[index]
            hit=call(scene+'trace_world',{'start':{'x':p['x'],'y':p['y'],'z':150},'end':{'x':p['x'],'y':p['y'],'z':-100}})
            ground=None if hit is None else 150-hit
            expected=row['world_slots'][index]['ground_z']
            samples.append({'slot':index,'expected_ground_z':expected,'actual_ground_z':ground})
            if ground is None or abs(ground-expected)>0.1:
                errors.append('ground mismatch at slot '+str(index))
        if errors:
            failures.append({'label':row['label'],'errors':errors})
        results.append({'label':row['label'],'capacity':props['capacity'],'samples':samples})
    return {'zone_count':len(results),'slot_count':sum(r['capacity'] for r in results),'failures':failures,'zones':results}
