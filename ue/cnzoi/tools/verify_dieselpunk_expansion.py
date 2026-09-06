"""Read-only MCP verification. Prepend build_dieselpunk_city.py helpers."""
def run():
    if scene('get_current_level',{})['returnValue'] != MAP:
        raise RuntimeError('Unexpected open level')
    generated=find('PCG_City_')
    originals=[exact(n) for n in ['KB3D_DPK_BldgLGObservatory_A','KB3D_DPK_BldgLGCasino_A','KB3D_DPK_BldgLGCFactoryHQ_A','City_Library','City_GeneralStore']]
    curated=find('_Landmark')
    rows=[]
    for a in generated+[a for a in originals if a]+curated:
        rows.append({'label':actor_tool('get_label',{'actor':a})['returnValue'],'actor':a,'bounds':actor_tool('get_actor_bounds',{'actor':a})['returnValue'],'transform':actor_tool('get_actor_transform',{'actor':a})['returnValue']})
    overlaps=[]
    for i,a in enumerate(rows):
        for b in rows[i+1:]:
            aa,bb=a['bounds'],b['bounds']
            if all(min(aa['max'][k],bb['max'][k])-max(aa['min'][k],bb['min'][k])>1 for k in ['x','y']):
                overlaps.append([a['label'],b['label']])
    furniture=[]
    for a in scene('get_actors_in_folder',{'folder_path':FOLDER+'/05_StreetFurniture','recursive':True})['returnValue']:
        furniture.append({'label':actor_tool('get_label',{'actor':a})['returnValue'],'bounds':actor_tool('get_actor_bounds',{'actor':a})['returnValue']})
    furniture_overlaps=[]
    for a in furniture:
        for b in rows:
            aa,bb=a['bounds'],b['bounds']
            if all(min(aa['max'][k],bb['max'][k])-max(aa['min'][k],bb['min'][k])>1 for k in ['x','y']):
                furniture_overlaps.append([a['label'],b['label']])
    samples=[]
    for x,y,expected in [(29500,-8000,-15),(29500,20000,-15),(58000,-8000,-15),(58000,20000,-15),(73000,20000,-15),(47600,15500,0),(44500,20000,0),(45900,0,-10),(45900,11900,-10),(45900,28600,-10),(45900,6000,-230),(45900,19000,-230)]:
        hit=scene('trace_world',{'start':{'x':x,'y':y,'z':200},'end':{'x':x,'y':y,'z':-600}})['returnValue']
        samples.append({'x':x,'y':y,'expected_z':expected,'hit_z':None if hit is None else 200-hit})
    spatial_flags=[]
    for a in generated:
        props=json.loads(object_tool('get_properties',{'instance':a,'properties':['bIsSpatiallyLoaded']})['returnValue'])
        if props.get('bIsSpatiallyLoaded'):
            spatial_flags.append(a)
    return {'level':MAP,'generated_count':len(generated),'building_count':len(rows),'building_xy_overlaps':overlaps,'buildings':rows,'furniture_count':len(furniture),'furniture_building_overlaps':furniture_overlaps,'ground_samples':samples,'unexpected_spatially_loaded_generated_actors':spatial_flags,'city_actor_count':len(scene('get_actors_in_folder',{'folder_path':FOLDER,'recursive':True})['returnValue'])}
