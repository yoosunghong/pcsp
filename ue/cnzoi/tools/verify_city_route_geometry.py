"""Audit tagged city geometry and optional real Mass route snapshots.

Run from the project root with ordinary Python/numpy. This checks authored
geometry and recorded positions independently of the C++ reverse-field code.
"""
import argparse
from collections import deque
import json
from pathlib import Path

import numpy as np


def unwrap(path):
    value = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    if 'content' in value:
        value = json.loads(value['content'][0]['text'])
    if 'returnValue' in value:
        value = value['returnValue']
        if isinstance(value, str):
            value = json.loads(value)
    return value


def rectangles(rows):
    return np.array([[r['bounds']['min']['x'], r['bounds']['max']['x'],
                      r['bounds']['min']['y'], r['bounds']['max']['y']]
                     for r in rows])


def inside(points, rects, padding=0):
    hit = np.zeros(len(points), dtype=bool)
    for x0, x1, y0, y1 in rects:
        hit |= ((points[:, 0] >= x0-padding) & (points[:, 0] <= x1+padding)
                & (points[:, 1] >= y0-padding) & (points[:, 1] <= y1+padding))
    return hit


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--session', type=Path)
    args = parser.parse_args()
    base = Path('Saved/PCSP/CityNavigation')
    geometry = unwrap(base/'tag-result.json')
    surfaces = rectangles(geometry['walkable'])
    obstacles = rectangles(geometry['obstacles'])
    cell = 200.
    origin = np.floor((surfaces[:, [0, 2]].min(axis=0)-cell)/cell)*cell
    size = np.ceil((surfaces[:, [1, 3]].max(axis=0)+cell-origin)/cell).astype(int)
    width, height = size
    yy, xx = np.mgrid[:height, :width]
    points = np.column_stack([origin[0]+(xx.ravel()+.5)*cell,
                              origin[1]+(yy.ravel()+.5)*cell])
    walkable = (inside(points, surfaces) & ~inside(points, obstacles, 230)).reshape(height, width)
    def cell_of(point):
        x, y = np.floor((np.asarray(point[:2])-origin)/cell).astype(int)
        return int(x), int(y)
    sx, sy = cell_of([65850, -12650])
    spawn_axis = np.linspace(-1600, 1600, 65)
    spawn_points = np.array([[65850+x, -12650+y] for x in spawn_axis for y in spawn_axis])
    spawn_cells = np.floor((spawn_points-origin)/cell).astype(int)
    blocked_spawn_samples = int((~walkable[spawn_cells[:,1],spawn_cells[:,0]]).sum())
    visited = np.zeros_like(walkable)
    queue = deque([(sx, sy)])
    visited[sy, sx] = True
    while queue:
        x, y = queue.popleft()
        for nx, ny in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
            if 0 <= nx < width and 0 <= ny < height and walkable[ny,nx] and not visited[ny,nx]:
                visited[ny,nx] = True
                queue.append((nx,ny))
    plan = unwrap('Saved/PCSP/CityAffordances/layout-plan.json')
    unreachable = []
    for row in plan['placements']:
        p = row['location']
        x, y = cell_of([p['x'], p['y']])
        if not visited[y,x]:
            unreachable.append(row['label'])
    report = {'walkable_actors':len(surfaces), 'obstacles':len(obstacles),
              'grid_size':size.tolist(), 'walkable_cells':int(walkable.sum()),
              'spawn_connected_cells':int(visited.sum()),
              'spawn_grid_samples':len(spawn_points), 'blocked_spawn_samples':blocked_spawn_samples,
              'zone_count':len(plan['placements']), 'unreachable_zone_centers':unreachable,
              'bridge_centers_connected':[bool(visited[cell_of([45900,y])[1],cell_of([45900,y])[0]])
                                          for y in (0,11900,28600)]}
    if args.session:
        samples = [json.loads(line) for line in (args.session/'mass_routes.jsonl').read_text().splitlines() if line]
        positions = np.asarray([s['pos'] for s in samples])
        blocked = inside(positions, obstacles, 40)
        unsupported = ~inside(positions, surfaces)
        stats = [json.loads(line) for line in (args.session/'mass_stats.jsonl').read_text().splitlines() if line]
        west = {s['id'] for s in samples if s['pos'][0] < 45000}
        east = {s['id'] for s in samples if s['pos'][0] > 46800}
        bridge_users = [len({s['id'] for s in samples if 45000 < s['pos'][0] < 46800
                            and abs(s['pos'][1]-y) <= 1250}) for y in (0,11900,28600)]
        report['runtime'] = {'session':str(args.session), 'samples':len(samples),
            'unique_npcs':len({s['id'] for s in samples}), 'seconds':max(s['t'] for s in samples),
            'arrivals':sum(s['arrivals'] for s in stats),
            'route_moves':sum(s.get('route_moves',0) for s in stats),
            'route_blocked':sum(s.get('route_blocked',0) for s in stats),
            'obstacle_intrusions_40cm':int(blocked.sum()), 'unsupported_positions':int(unsupported.sum()),
            'npcs_crossed_canal':len(west & east),
            'bridge_users_south_middle_north':bridge_users,
            'zones_seen_interacting':len({s['zone'] for s in samples if s['interacting']}),
            'bad_examples':[samples[i] for i in np.flatnonzero(blocked|unsupported)[:10]]}
    destination = base/('runtime-route-validation.json' if args.session else 'geometry-validation.json')
    destination.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))
    assert not unreachable and all(report['bridge_centers_connected']), 'Disconnected city geometry'
    assert blocked_spawn_samples == 0, 'Spawn area includes a blocked grid cell'
    if args.session:
        assert not blocked.any() and not unsupported.any(), 'Runtime route entered unsafe geometry'


if __name__ == '__main__':
    main()
