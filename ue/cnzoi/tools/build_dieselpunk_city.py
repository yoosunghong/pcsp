"""Editor MCP tool script for the Visual map's eastern dieselpunk district.

Execute through ProgrammaticToolset.execute_tool_script (not ordinary Python).
Read get_execution_environment and discover the tool schemas first. Set STAGE,
START and COUNT in the submitted script to run small, resumable batches.
Only this script's City_ actors and three explicitly named landmarks are edited.
Authoring is editor-time; no runtime PCG regeneration or research contract changes.
"""
import json

STAGE = 'surfaces'
START = 0
COUNT = 5
MAP = '/Game/PCSP/Maps/Map_PCSPDistrict_Portfolio_Visual'
FOLDER = 'PCSP_City'
ASSETS = '/Game/PCSP/City/Materials'
TAG = 'PCSP_DieselpunkCity_v1'

def scene(tool, args):
    return execute_tool('editor_toolset.toolsets.scene.SceneTools.' + tool, json.dumps(args))

def actor_tool(tool, args):
    return execute_tool('editor_toolset.toolsets.actor.ActorTools.' + tool, json.dumps(args))

def asset_tool(tool, args):
    return execute_tool('editor_toolset.toolsets.asset.AssetTools.' + tool, json.dumps(args))

def object_tool(tool, args):
    return execute_tool('editor_toolset.toolsets.object.ObjectTools.' + tool, json.dumps(args))

def material_tool(tool, args):
    return execute_tool('editor_toolset.toolsets.material_instance.MaterialInstanceTools.' + tool, json.dumps(args))

def checked_properties(obj, values):
    if not object_tool('set_properties', {'instance':obj, 'values':json.dumps(values)})['returnValue']:
        raise RuntimeError('Could not set properties: ' + str(obj))

def find(name):
    return scene('find_actors', {'name':name, 'tag':'', 'collision_channels':[]})['returnValue']

def exact(name):
    matches = [a for a in find(name) if actor_tool('get_label', {'actor':a})['returnValue'] == name]
    if len(matches) > 1:
        raise RuntimeError('Ambiguous actor label: ' + name)
    return matches[0] if matches else None

def spawn(name, path, xform, folder):
    actor = exact(name)
    if actor is None:
        actor = scene('add_to_scene_from_asset', {'asset_path':path, 'name':name, 'xform':xform, 'snap_to_ground':False})['returnValue']
    else:
        actor_tool('set_actor_transform', {'actor':actor, 'xform':xform})
    checked_properties(actor, {'bIsSpatiallyLoaded':False})
    if not actor_tool('has_tag', {'actor':actor, 'tag':TAG})['returnValue']:
        actor_tool('add_tag', {'actor':actor, 'tag':TAG})
    scene('set_actor_folder', {'actor':actor, 'folder_path':FOLDER + '/' + folder})
    return actor

def material(kind, width, depth):
    # Each cube top has 0..1 UVs. Match U/V repeat to its physical dimensions.
    name = 'MI_City_' + kind + '_' + str(int(width)) + '_' + str(int(depth))
    path = ASSETS + '/' + name
    ref = {'refPath':path + '.' + name}
    if asset_tool('exists', {'path':path})['returnValue']:
        return ref
    parents = {'Road':'Cobblestone', 'Walk':'SideWalkDamaged', 'Court':'CobblestoneB', 'Trim':'SideWalkDamaged'}
    parent_name = 'KB3D_DPK_' + parents[kind]
    ref = material_tool('create', {'folder_path':ASSETS, 'asset_name':name, 'parent':{'refPath':'/Game/dieselpunk/Materials/' + parent_name + '.' + parent_name}})['returnValue']
    for key, value in [('Tile_U',width / 400.0), ('Tile_V',depth / 400.0), ('Tile_UV',1.0)]:
        material_tool('set_scalar_parameter', {'instance':ref, 'name':key, 'value':value})
    tints = {'Road':(0.36,0.39,0.42), 'Walk':(0.82,0.78,0.68), 'Court':(0.62,0.64,0.60), 'Trim':(1.0,0.94,0.76)}
    r,g,b = tints[kind]
    material_tool('set_vector_parameter', {'instance':ref, 'name':'basecolor_mult', 'value':{'r':r,'g':g,'b':b,'a':1.0}})
    asset_tool('save_assets', {'asset_paths':[path]})
    return ref

def surface_specs():
    rows = []
    def rect(name, x0, x1, y0, y1, top, thickness, kind, folder):
        rows.append({'name':'City_' + name, 'x0':x0,'x1':x1,'y0':y0,'y1':y1,'top':top,'thickness':thickness,'kind':kind,'folder':folder})
    rect('Roadbed',16300,45100,-17400,11200,-15,80,'Road','01_Roads')
    blocks = [('SW_Observatory',18400,27900,-15100,-1600), ('SE_Casino',31100,43000,-15100,-1600), ('NW_Civic',18400,27900,1600,9000), ('NE_Factory',31100,43000,1600,9000)]
    for name,x0,x1,y0,y1 in blocks:
        rect('Block_' + name,x0,x1,y0,y1,0,35,'Walk','02_Sidewalks')
        rect('Court_' + name,x0+700,x1-700,y0+700,y1-700,0.5,2,'Court','03_Plazas')
        # Low curb strips define the street without tall barriers at entrances.
        for side,ax,bx,ay,by in [('W',x0,x0+30,y0,y1),('E',x1-30,x1,y0,y1),('S',x0+30,x1-30,y0,y0+30),('N',x0+30,x1-30,y1-30,y1)]:
            rect('Curb_' + name + '_' + side,ax,bx,ay,by,5,20,'Trim','02_Sidewalks')
    # Outer pedestrian promenades; the remaining roadbed forms the ring road.
    rect('Promenade_W',16600,17100,-16500,10200,0.5,35,'Walk','02_Sidewalks')
    rect('Promenade_E',44300,44800,-16500,10200,0,35,'Walk','02_Sidewalks')
    rect('Promenade_S',17100,44300,-17100,-16600,0,35,'Walk','02_Sidewalks')
    rect('Promenade_N',17100,44300,10300,10800,0,35,'Walk','02_Sidewalks')
    # Flush stone crossings mark pedestrian connections across the central roads.
    for suffix,y in [('S',-2300),('N',2300)]:
        rect('Crossing_NS_' + suffix,27900,31100,y-180,y+180,-13,2,'Walk','01_Roads')
    for suffix,x in [('W',26900),('E',32100)]:
        rect('Crossing_EW_' + suffix,x-180,x+180,-1600,1600,-13,2,'Walk','01_Roads')
    # Connect the original PCSP demonstration floor to the eastern city.
    rect('West_Link',16000,18400,-500,500,0.5,35,'Walk','02_Sidewalks')
    return rows

def build_surface(spec):
    w,d = spec['x1']-spec['x0'], spec['y1']-spec['y0']
    xform = {'location':{'x':(spec['x0']+spec['x1'])/2,'y':(spec['y0']+spec['y1'])/2,'z':spec['top']-spec['thickness']/2},'scale':{'x':w/100,'y':d/100,'z':spec['thickness']/100}}
    a = spawn(spec['name'], '/Engine/BasicShapes/Cube.Cube', xform, spec['folder'])
    components = actor_tool('get_components', {'actor':a, 'component_type':{'refPath':'/Script/Engine.StaticMeshComponent'}})['returnValue']
    mat = material(spec['kind'], w, d)
    checked_properties(components[0], {'overrideMaterials':[mat]})
    return {'label':spec['name'],'actor':a,'material':mat}

def landmarks():
    rows = []
    for partial,location in [('KB3D_DPK_BldgLGObservatory_A',{'x':22050,'y':-7850,'z':0}),('KB3D_DPK_BldgLGCasino_A',{'x':36350,'y':-8130,'z':0}),('KB3D_DPK_BldgLGCFactoryHQ_A',{'x':37570,'y':4290,'z':0})]:
        actors = find(partial)
        if len(actors) != 1:
            raise RuntimeError('Expected exactly one existing landmark: ' + partial)
        a = actors[0]
        old = actor_tool('get_actor_transform', {'actor':a})['returnValue']
        # UE 5.8 tool serialization currently fills omitted transform fields with
        # identity. Supply the full transform, including the casino's 90° yaw.
        xform = {'location':location,'rotation':{'pitch':0,'yaw':90 if 'Casino' in partial else 0,'roll':0},'scale':{'x':1,'y':1,'z':1}}
        actor_tool('set_actor_transform', {'actor':a,'xform':xform})
        checked_properties(a, {'bIsSpatiallyLoaded':False})
        scene('set_actor_folder', {'actor':a,'folder_path':FOLDER + '/04_Landmarks'})
        rows.append({'actor':a,'before':old,'after':actor_tool('get_actor_transform', {'actor':a})['returnValue'],'bounds':actor_tool('get_actor_bounds', {'actor':a})['returnValue']})
    return rows

def building_specs():
    return [('City_Library','KB3D_DPK_BldgSMLibrary_A',21000,5500,0), ('City_GeneralStore','KB3D_DPK_BldgMDGeneralStore_A',25000,5300,180)]

def build_building(spec):
    name,asset,x,y,yaw = spec
    a = spawn(name,'/Game/dieselpunk/Actors/' + asset,{'location':{'x':x,'y':y,'z':0},'rotation':{'pitch':0,'yaw':yaw,'roll':0}},'04_Buildings')
    return {'label':name,'actor':a,'bounds':actor_tool('get_actor_bounds',{'actor':a})['returnValue']}

def prop_specs():
    specs=[]
    for side,x,yaw in [('W',27600,90),('E',31400,-90)]:
        for i,y in enumerate([-13800,-10600,-7400,-4200,2800,5700,8300]):
            specs.append(('City_Lamp_' + side + '_' + str(i),'KB3D_DPK_PropLamp_A',x,y,yaw))
    for side,y,yaw in [('S',-1900,0),('N',1770,180)]:
        for i,x in enumerate([19200,22500,25800,33000,36600,40100,42200]):
            specs.append(('City_Lamp_' + side + '_' + str(i),'KB3D_DPK_PropLamp_A',x,y,yaw))
    for i,x in enumerate([20000,22500,25000]):
        specs.append(('City_Bench_Civic_' + str(i),'KB3D_DPK_PropBench_A',x,2450,0))
    specs.extend([('City_BusStop','KB3D_DPK_PropBusStop_A',31700,-5600,90), ('City_PhoneBooth','KB3D_DPK_PropPhoneBooth_A',26300,2600,0), ('City_Civic_Armillary','KB3D_DPK_PropArmillarySphere_A',21000,3000,0)])
    return specs

def build_prop(spec):
    name,asset,x,y,yaw = spec
    a = spawn(name,'/Game/dieselpunk/Actors/' + asset,{'location':{'x':x,'y':y,'z':0},'rotation':{'pitch':0,'yaw':yaw,'roll':0}},'05_StreetFurniture')
    return {'label':name,'actor':a,'bounds':actor_tool('get_actor_bounds',{'actor':a})['returnValue']}

def run():
    current = scene('get_current_level', {})['returnValue']
    if current != MAP:
        raise RuntimeError('Open the Visual map before city authoring: ' + current)
    if STAGE == 'landmarks':
        return {'landmarks':landmarks()}
    stages = {'surfaces':(surface_specs,build_surface),'buildings':(building_specs,build_building),'props':(prop_specs,build_prop)}
    if STAGE not in stages:
        raise RuntimeError('Unknown stage: ' + STAGE)
    specs,builder = stages[STAGE]
    all_specs = specs()
    results = [builder(spec) for spec in all_specs[START:START+COUNT]]
    return {'stage':STAGE,'start':START,'total':len(all_specs),'results':results}
