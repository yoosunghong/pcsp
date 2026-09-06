"""MCP ProgrammaticToolset script; prepend PLACEMENTS decoded from the plan.

Apply in small batches. No new native Point actors: zones own their serialized
InteractionSlots and HISM floor markers. The caller must snapshot live state
and disk packages before running this script.
"""
import json

MAP = '/Game/PCSP/Maps/Map_PCSPDistrict_Portfolio_Visual'


def call(tool,args):
    return execute_tool(tool,json.dumps(args))['returnValue']


def run():
    scene='editor_toolset.toolsets.scene.SceneTools.'
    actor='editor_toolset.toolsets.actor.ActorTools.'
    obj='editor_toolset.toolsets.object.ObjectTools.'
    if call(scene+'get_current_level',{}) != MAP:
        raise RuntimeError('Open the intended Visual map before authoring.')
    if call('EditorToolset.EditorAppToolset.IsPIERunning',{}):
        raise RuntimeError('Stop PIE before authoring affordances.')
    results=[]
    for row in PLACEMENTS:
        a=row['actor']
        before=json.loads(call(obj+'get_properties',{'instance':a,'properties':['zoneTag','category','visualizationIndex']}))
        if before['zoneTag']['tagName'] != row['zone_tag'] or before['visualizationIndex'] != row['visualization_index'] or before['category'] != row['category']:
            raise RuntimeError('Zone identity changed after planning: '+row['original_label'])
        values={'bAutoGenerateGrid':False,'interactionSlots':row['slots'],'interactionPointCount':row['capacity'],'boundsPadding':row['bounds_padding'],'bIsSpatiallyLoaded':False}
        if not call(obj+'set_properties',{'instance':a,'values':json.dumps(values)}):
            raise RuntimeError('Could not set authored slots: '+row['label'])
        call(actor+'set_actor_transform',{'actor':a,'xform':{'location':row['location'],'rotation':{'pitch':0,'yaw':row['yaw'],'roll':0},'scale':{'x':1,'y':1,'z':1}}})
        if not call(actor+'set_label',{'actor':a,'label':row['label']}):
            raise RuntimeError('Could not label zone')
        call(scene+'set_actor_folder',{'actor':a,'folder_path':'PCSP_City/09_Affordances/'+row['district']})
        after=json.loads(call(obj+'get_properties',{'instance':a,'properties':['capacity','interactionSlots','bAutoGenerateGrid','bIsSpatiallyLoaded']}))
        if after['capacity'] != row['capacity'] or len(after['interactionSlots']) != row['capacity'] or after['bAutoGenerateGrid'] or after['bIsSpatiallyLoaded']:
            raise RuntimeError('Zone reconstruction failed: '+row['label'])
        results.append({'label':row['label'],'capacity':after['capacity']})
    return {'zones':len(results),'slots':sum(r['capacity'] for r in results),'results':results}
