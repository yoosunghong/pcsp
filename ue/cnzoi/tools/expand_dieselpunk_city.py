"""MCP editor authoring stages for the 4x visual district.

Submit after the contents of build_dieselpunk_city.py in the same tool script.
This reuses its checked spawn/material helpers; no ordinary Python UE import.
STAGE/START/COUNT select resumable batches. PCG execution remains a direct call.
"""
STAGE = 'curated'
START = 0
COUNT = 20
TAG = 'PCSP_DieselpunkCity_v2'
GRAPH = {'refPath':'/Game/PCSP/City/PCG/PCG_DieselpunkCityBlock.PCG_DieselpunkCityBlock'}

def pcg(tool,args):
    return execute_tool('PCGToolset.PCGToolset.'+tool,json.dumps(args))['returnValue']

def xf(x,y,z=0,yaw=0,sx=1,sy=1,sz=1):
    return {'location':{'x':x,'y':y,'z':z},'rotation':{'pitch':0,'yaw':yaw,'roll':0},'scale':{'x':sx,'y':sy,'z':sz}}

def blocks_v2():
    return [
        ('Apartments',47200,56700,-15100,-1600),('Hotel',59900,71800,-15100,-1600),
        ('Shops',47200,56700,1600,9000),('Tram',59900,71800,1600,9000),
        ('Parliament',18400,27900,13500,27000),('Church',31100,43000,13500,27000),
        ('Workers',47200,56700,13500,27000),('Distillery',59900,71800,13500,27000),
        ('Motel',18400,27900,30200,37600),('Pub',31100,43000,30200,37600),
        ('Library',47200,56700,30200,37600),('Museum',59900,71800,30200,37600)]

def expansion_surfaces():
    rows=[]
    def rect(name,x0,x1,y0,y1,top,thickness,kind='Walk',folder='02_Sidewalks'):
        rows.append({'name':'City_'+name,'x0':x0,'x1':x1,'y0':y0,'y1':y1,'top':top,'thickness':thickness,'kind':kind,'folder':folder})
    # Exact footprint: 57600 x 57200 cm; old area was 28800 x 28600 cm.
    rect('Roadbed',16300,45000,-17400,39800,-15,80,'Road','01_Roads')
    rect('Roadbed_East',46800,73900,-17400,39800,-15,80,'Road','01_Roads')
    for n,x0,x1,y0,y1 in blocks_v2():
        rect('Block_'+n,x0,x1,y0,y1,0,35)
        rect('Court_'+n,x0+700,x1-700,y0+700,y1-700,0.5,2,'Court','03_Plazas')
        for side,ax,bx,ay,by in [('W',x0,x0+30,y0,y1),('E',x1-30,x1,y0,y1),('S',x0+30,x1-30,y0,y0+30),('N',x0+30,x1-30,y1-30,y1)]:
            rect('Curb_'+n+'_'+side,ax,bx,ay,by,5,20,'Trim')
    rect('Promenade_W_North',16600,17100,11200,39000,0,35)
    rect('Promenade_East',73100,73600,-16600,39000,0,35)
    rect('Promenade_North',17100,45000,39000,39500,0,35)
    rect('Promenade_NorthEast',46800,73100,39000,39500,0,35)
    rect('Promenade_SouthEast',47200,73100,-17100,-16600,0,35)
    for side,x0,x1 in [('West',44300,45000),('East',46800,47200)]:
        rect('Promenade_E' if side=='West' else 'CanalBank_'+side,x0,x1,-17400,39800,0,450)
    rect('Canal_Bottom',45000,46800,-17400,39800,-450,70,'Road','06_Canal')
    rect('Canal_Water',45000,46800,-17400,39800,-230,10,'Water','06_Canal')
    for i,y in enumerate([0,11900,28600]):
        rect('Bridge_Deck_'+str(i),44300,47500,y-700,y+700,-10,100,'Road','07_Bridges')
        for side,ya,yb in [('S',y-1050,y-700),('N',y+700,y+1250)]:
            rect('Bridge_Walk_'+str(i)+side,44300,47500,ya,yb,0,110,'Walk','07_Bridges')
            edge_y=ya if side=='S' else yb-40
            rect('Bridge_Parapet_'+str(i)+side,44700,47100,edge_y,edge_y+40,110,110,'Trim','07_Bridges')
        for x in [45000,46600]:
            rect('Bridge_Pier_'+str(i)+'_'+str(x),x,x+200,y-1050,y+1250,-100,350,'Trim','07_Bridges')
    # Long quays with openings at each bridge; 85cm tall low parapets.
    for i,(y0,y1) in enumerate([(-17400,-1100),(1250,10800),(13150,27500),(29850,39800)]):
        for x in [44920,46800]:
            rect('Quay_Parapet_'+str(x)+'_'+str(i),x,x+80,y0,y1,85,110,'Trim','06_Canal')
    return rows

def surface_v2(spec):
    if spec['kind'] != 'Water':
        return build_surface(spec)
    w,d=spec['x1']-spec['x0'],spec['y1']-spec['y0']
    a=spawn(spec['name'],'/Engine/BasicShapes/Cube.Cube',xf((spec['x0']+spec['x1'])/2,(spec['y0']+spec['y1'])/2,spec['top']-spec['thickness']/2,0,w/100,d/100,spec['thickness']/100),spec['folder'])
    c=actor_tool('get_components',{'actor':a,'component_type':{'refPath':'/Script/Engine.StaticMeshComponent'}})['returnValue'][0]
    checked_properties(c,{'overrideMaterials':[{'refPath':ASSETS+'/M_City_CanalWater.M_City_CanalWater'}]})
    return {'label':spec['name'],'actor':a}

def curated_specs():
    return [('Hotel','KB3D_DPK_BldgMDHotelNoir_A',180),('Tram','KB3D_DPK_BldgMDTramStation_A',0),('Parliament','KB3D_DPK_BldgLGParliament_A',90),('Church','KB3D_DPK_BldgLGRiveterChurch_A',0),('Distillery','KB3D_DPK_BldgLGIronsideDistellery_A',180),('Museum','KB3D_DPK_BldgMDMuseum_A',180)]

def curated(spec):
    district,asset,yaw=spec
    _,x0,x1,y0,y1=[r for r in blocks_v2() if r[0]==district][0]
    cx,cy=(x0+x1)/2,(y0+y1)/2
    a=spawn('City_'+district+'_Landmark','/Game/dieselpunk/Actors/'+asset,xf(cx,cy,0,yaw),'04_Landmarks')
    b=actor_tool('get_actor_bounds',{'actor':a})['returnValue']
    w,d=b['max']['x']-b['min']['x'],b['max']['y']-b['min']['y']
    scale=min(1.0,(x1-x0-1600)/w,(y1-y0-1600)/d)
    dx,dy=(b['max']['x']+b['min']['x'])/2-cx,(b['max']['y']+b['min']['y'])/2-cy
    actor_tool('set_actor_transform',{'actor':a,'xform':xf(cx-dx*scale,cy-dy*scale,0,yaw,scale,scale,scale)})
    return {'label':'City_'+district+'_Landmark','asset':asset,'actor':a,'scale':scale,'bounds':actor_tool('get_actor_bounds',{'actor':a})['returnValue']}

def pcg_specs():
    # Area and spacing are tuned to the measured KitBash building footprints.
    return [
        ('Apartments','BldgSMApartments_A',51950,-8350,4200,6000,2800,4000,0,1.0),
        ('Shops','BldgSMApartmentsStore_A',51600,5300,4300,3200,4300,3200,0,0.85),
        ('Workers','BldgSMFactoryApartments_A',51600,20250,4300,5600,4300,5600,180,0.8),
        ('Motel','BldgSMAceMotel_A',23150,33900,3800,3000,3800,3000,0,0.85),
        ('Pub','BldgSMHalcyonPub_A',37050,33900,4800,3000,4800,3000,180,0.8),
        ('Library','BldgSMLibrary_A',51950,33900,3800,3000,3800,3000,0,1.0)]

def instance(spec):
    name,asset,x,y,ex,ey,sx,sy,yaw,scale=spec
    params={'ActorClass':{'refPath':'/Game/dieselpunk/Actors/KB3D_DPK_'+asset+'.KB3D_DPK_'+asset+'_C'},'AreaHalfSize':{'x':ex,'y':ey,'z':0},'LotSpacing':{'x':sx,'y':sy,'z':100},'LayoutSeed':42+len(name)*11,'Facing':{'pitch':0,'yaw':yaw,'roll':0},'MinScale':{'x':scale,'y':scale,'z':scale},'MaxScale':{'x':scale,'y':scale,'z':scale},'GeneratedLabel':'PCG_City_'+name,'FillRatio':1.0}
    a=exact('City_PCG_'+name)
    if a is None:
        a=pcg('SpawnGraphInstance',{'graph':GRAPH,'name':'City_PCG_'+name,'transform':xf(x,y,0,0,ex/100,ey/100,10),'jsonParams':json.dumps(params)})['actor']
    else:
        actor_tool('set_actor_transform',{'actor':a,'xform':xf(x,y,0,0,ex/100,ey/100,10)})
        pcg('SetGraphInstanceParams',{'pCGVolume':a,'jsonParams':json.dumps(params)})
    checked_properties(a,{'bIsSpatiallyLoaded':False})
    scene('set_actor_folder',{'actor':a,'folder_path':FOLDER+'/08_PCG_Blocks'})
    return {'label':'City_PCG_'+name,'actor':a,'params':params}

def structure_specs():
    return [('City_Bridge_Covered_0','KB3D_DPK_PropWalkway_D',45900,950,0,0,1.25),('City_Bridge_Covered_1','KB3D_DPK_PropWalkway_E',45900,12850,0,0,1.8),('City_Bridge_Covered_2','KB3D_DPK_PropWalkway_D',45900,29550,0,180,1.25),('City_Canal_Arch','KB3D_DPK_PropArch_A',45900,36000,0,0,1.5)]

def structure(spec):
    name,asset,x,y,z,yaw,sx=spec
    a=spawn(name,'/Game/dieselpunk/Actors/'+asset,xf(x,y,z,yaw,sx,1,1),'07_Bridges')
    return {'label':name,'actor':a,'bounds':actor_tool('get_actor_bounds',{'actor':a})['returnValue']}

def extra_props():
    specs=[]
    for name,x0,x1,y0,y1 in blocks_v2():
        for corner,x,y in [('SW',x0+350,y0+350),('SE',x1-350,y0+350),('NW',x0+350,y1-350),('NE',x1-350,y1-350)]:
            specs.append(('City_Lamp_'+name+'_'+corner,'KB3D_DPK_PropLamp_A',x,y,0))
    for side,x in [('W',44600),('E',47000)]:
        for i,y in enumerate([-14500,-10500,-6500,-2500,4000,8000,16000,20500,24500,32500,37500]):
            specs.append(('City_QuayLamp_'+side+'_'+str(i),'KB3D_DPK_PropLamp_A',x,y,90 if side=='W' else -90))
    return specs

def run():
    if scene('get_current_level',{})['returnValue']!=MAP:
        raise RuntimeError('Open the Visual map before authoring.')
    choices={'surfaces':(expansion_surfaces,surface_v2),'curated':(curated_specs,curated),'pcg':(pcg_specs,instance),'structures':(structure_specs,structure),'props':(extra_props,build_prop)}
    specs,builder=choices[STAGE]
    rows=specs()
    return {'stage':STAGE,'total':len(rows),'start':START,'results':[builder(s) for s in rows[START:START+COUNT]]}
