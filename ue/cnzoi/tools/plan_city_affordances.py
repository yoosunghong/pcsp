"""Plan the Visual city's affordance relocation from live MCP JSON snapshots.

Ordinary offline Python, no Editor access. Keeps every zone's identity, category,
slot count, minimum XY slot spacing and duration. Fits complete zone footprints into
paved city blocks while excluding buildings and street furniture.
"""
import json
import math
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'Saved/PCSP/CityAffordances'


def read_mcp(path):
    envelope = json.loads(path.read_text(encoding='utf-8-sig'))
    value = json.loads(envelope['content'][0]['text'])['returnValue']
    return json.loads(value) if isinstance(value, str) else value


def rectangle(bounds):
    return (bounds['min']['x'], bounds['max']['x'], bounds['min']['y'], bounds['max']['y'])


def overlaps(a, b, clearance=0):
    return a[0] < b[1]+clearance and b[0] < a[1]+clearance and a[2] < b[3]+clearance and b[2] < a[3]+clearance


def rotate(x, y, yaw):
    return (x, y) if yaw == 0 else (-y, x)


PREFERENCES = {
    'Eat': ['Pub','Shops','Hotel','SE_Casino','Workers','Motel','NW_Civic','Tram'],
    'Rest': ['Apartments','Motel','Hotel','Workers','Library','Church','NW_Civic'],
    'Work': ['NE_Factory','Distillery','Workers','Parliament','Tram','Shops'],
    'Study': ['Library','SW_Observatory','Museum','NW_Civic','Parliament','Church'],
    'Exercise': ['SW_Observatory','Church','Motel','NW_Civic','Pub','Workers'],
    'Hygiene': ['Apartments','Workers','Hotel','Motel','Distillery','NE_Factory','Tram'],
    'Social': ['Church','Pub','SE_Casino','NW_Civic','Apartments','Hotel','Tram'],
    'Shop': ['Shops','Tram','Museum','SE_Casino','NW_Civic','Hotel'],
    'Observe': ['SW_Observatory','Museum','Parliament','Tram','Church','Library'],
    'Idle': [],
}

PRIMARY = {'Apartments':'Rest','Shops':'Shop','Workers':'Work','Hotel':'Rest',
           'Tram':'Observe','Parliament':'Work','Church':'Social','Distillery':'Work',
           'Motel':'Rest','Pub':'Eat','Library':'Study','Museum':'Observe',
           'SW_Observatory':'Observe','SE_Casino':'Social','NW_Civic':'Study','NE_Factory':'Work'}


def plan():
    inventory = read_mcp(OUTPUT / 'inventory-before.json')
    geometry = read_mcp(OUTPUT / 'city-geometry.json')
    blocks = {b['label'].removeprefix('City_Block_'):rectangle(b['bounds']) for b in geometry['blocks']}
    buildings = geometry['buildings'] + geometry['small_buildings'] + geometry['generated_buildings']
    obstacles = [(rectangle(b['bounds']),180,b['label']) for b in buildings]
    obstacles += [(rectangle(b['bounds']),100,b['label']) for b in geometry['props']]
    local_obstacles = {name:[o for o in obstacles if overlaps(rect,o[0],500)] for name,rect in blocks.items()}
    assigned = {name:[] for name in blocks}
    placements = []
    # Fit the largest zone first; stable identities make repeated planning deterministic.
    remaining = sorted(inventory['zones'],key=lambda z:(-z['properties']['capacity'],z['properties']['visualizationIndex']))
    seeded=[]
    force_district={}
    for district,category in PRIMARY.items():
        zone=next(z for z in remaining if z['properties']['category']==category)
        remaining.remove(zone)
        seeded.append(zone)
        force_district[zone['properties']['visualizationIndex']]=district
    zones=seeded+remaining
    for zone in zones:
        props = zone['properties']
        slots = props['interactionSlots']
        assert len(slots) == props['capacity'] > 0
        padding=140
        spacing=props['interactionPointSpacing']
        default_columns=math.ceil(math.sqrt(len(slots)))
        grids=[]
        for columns in sorted(set([default_columns,2,3,4])):
            if columns>len(slots):
                continue
            rows=math.ceil(len(slots)/columns)
            xy=[((i%columns-(columns-1)*0.5)*spacing,(i//columns-(rows-1)*0.5)*spacing) for i in range(len(slots))]
            hx=max(abs(p[0]) for p in xy)+padding
            hy=max(abs(p[1]) for p in xy)+padding
            grids.append((columns,xy,hx,hy))
        pref = PREFERENCES.get(props['category'],[])
        def district_cost(name):
            preference = pref.index(name) if name in pref else (len(pref)+2 if pref else 0)
            same=sum(p['category']==props['category'] for p in assigned[name])
            return preference*2.2 + len(assigned[name])*5 + same*5 + sum(p['capacity'] for p in assigned[name])*0.05
        solution = None
        districts=[force_district[props['visualizationIndex']]] if props['visualizationIndex'] in force_district else sorted(blocks,key=lambda n:(district_cost(n),n))
        for name in districts:
            if len(assigned[name]) >= 9:
                continue
            x0,x1,y0,y1 = blocks[name]
            candidates = []
            orientations=[(yaw,hx if yaw==0 else hy,hy if yaw==0 else hx,columns,xy) for columns,xy,hx,hy in grids for yaw in [0,90]]
            for yaw,hx,hy,columns,xy in orientations:
                for ix in range(int((x1-x0-400-2*hx)//220)+1):
                    x = x0 + 200 + hx + ix*220
                    for iy in range(int((y1-y0-400-2*hy)//220)+1):
                        y = y0 + 200 + hy + iy*220
                        rect = (x-hx,x+hx,y-hy,y+hy)
                        if any(overlaps(rect,o,c) for o,c,_ in local_obstacles[name]):
                            continue
                        if any(overlaps(rect,p['footprint'],160) for p in assigned[name]):
                            continue
                        edge_distance = min(x-x0,x1-x,y-y0,y1-y)
                        nearest = min([math.hypot(x-p['location']['x'],y-p['location']['y']) for p in assigned[name]] or [4000])
                        # Accessible block edges and a spread of small courtyards.
                        score = edge_distance*0.35 + max(0,2600-nearest)*0.7
                        score += ((ix*31+iy*17+props['visualizationIndex']*13)%97)*0.8
                        score += abs(columns-default_columns)*55
                        candidates.append((score,x,y,yaw,rect,columns,xy))
            if candidates:
                _,x,y,yaw,rect,columns,xy = min(candidates)
                solution=(name,x,y,yaw,rect,columns,xy)
                break
        if solution is None:
            raise RuntimeError('No clear city placement for '+zone['label'])
        name,x,y,yaw,rect,columns,xy=solution
        x0,x1,y0,y1=blocks[name]
        authored_slots=[]
        world_slots=[]
        for i,s in enumerate(slots):
            relative={'x':xy[i][0],'y':xy[i][1]}
            dx,dy=rotate(relative['x'],relative['y'],yaw)
            wx,wy=x+dx,y+dy
            # The inner court is 0.5cm above the block; markers get 1cm clearance.
            ground=0.5 if x0+700 <= wx <= x1-700 and y0+700 <= wy <= y1-700 else 0.0
            authored_slots.append({'relativeLocation':{'x':relative['x'],'y':relative['y'],'z':ground+1},'interactionDuration':s['interactionDuration']})
            world_slots.append({'x':wx,'y':wy,'z':ground+1,'ground_z':ground})
        row={'actor':zone['actor'],'original_label':zone['label'],'label':f"City_Affordance_{name}_{props['category']}_{props['visualizationIndex']:03d}",'district':name,'category':props['category'],'zone_tag':props['zoneTag']['tagName'],'visualization_index':props['visualizationIndex'],'capacity':len(slots),'location':{'x':x,'y':y,'z':0},'yaw':yaw,'footprint':rect,'columns':columns,'bounds_padding':padding,'spacing':spacing,'slots':authored_slots,'world_slots':world_slots}
        assigned[name].append(row)
        placements.append(row)
    all_points=[(p['label'],v) for p in placements for v in p['world_slots']]
    minimum_distance=min(math.hypot(a['x']-b['x'],a['y']-b['y']) for i,(_,a) in enumerate(all_points) for _,b in all_points[i+1:])
    assert minimum_distance >= 279.99
    assert len({p['visualization_index'] for p in placements}) == len(placements)
    assert len({p['zone_tag'] for p in placements}) == len(placements)
    report={'level':'/Game/PCSP/Maps/Map_PCSPDistrict_Portfolio_Visual','zone_count':len(placements),'slot_count':len(all_points),'npc_target':1024,'minimum_slot_distance_cm':minimum_distance,'category_slots':dict(Counter({c:sum(p['capacity'] for p in placements if p['category']==c) for c in {p['category'] for p in placements}})),'districts':{name:{'zones':len(rows),'slots':sum(p['capacity'] for p in rows),'categories':dict(Counter(p['category'] for p in rows))} for name,rows in assigned.items()},'placements':sorted(placements,key=lambda p:p['visualization_index'])}
    (OUTPUT/'layout-plan.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='placements'},indent=2))


if __name__ == '__main__':
    plan()
