"""Reversible #459 ordinary-shoulder repair near the current viewport.

Only native, source-matched derived support positions change. Landscape and
asphalt are read-only. No save, camera movement, arbitrary AOI or proof admission.
"""
from __future__ import annotations

import math
from scripts.ue import road_shoulder_sources as sources
from scripts.ue.road_shoulder_network import inspect_mesh

RADIUS_CM = 3000.0
TAPER_CM = 500.0
MAX_DELTA_CM = 50.0
EPS_CM = 0.02


def require(condition, message):
    if not condition:
        raise ValueError(message)


def _weight(point, center):
    return max(0.0, min(1.0, (RADIUS_CM + TAPER_CM - math.dist(point[:2], center[:2])) / TAPER_CM))


def _segment(point, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    length2 = dx * dx + dy * dy
    require(length2 > 1e-8, 'Degenerate support perimeter')
    t = ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy) / length2
    if not -1e-6 <= t <= 1 + 1e-6:
        return None
    t = max(0., min(1., t))
    if math.hypot(point[0] - a[0] - t * dx, point[1] - a[1] - t * dy) > EPS_CM:
        return None
    return t


def _plan(owner, snapshot, center, trace):
    """Authenticate actual oriented faces, then plan all top AND wall vertices."""
    rows = owner['sections_cm']
    witnesses = snapshot['witness_triangles']
    vertices = {}
    for row in witnesses:
        for i, vid in enumerate(row[1:4]):
            p = tuple(row[4 + i * 3:7 + i * 3])
            require(vid not in vertices or vertices[vid] == p, 'Inconsistent native vertex')
            vertices[vid] = p
    require(len(vertices) == snapshot['summary']['vertex_count'], 'Unreferenced support vertices')
    top_ids = {}
    for tid, expected in sources.iter_expected_triangles(owner):
        actual = witnesses[tid]
        require(actual[0] == tid, 'Native triangle ordering differs')
        for vid, p, target in zip(actual[1:4], [actual[4:7], actual[7:10], actual[10:13]], expected):
            require(math.dist(p, target) <= EPS_CM, 'Native support does not match frozen top')
            key = tuple(target)
            require(key not in top_ids or top_ids[key] == vid, 'Ambiguous duplicated top vertex')
            top_ids[key] = vid
    # Keep both owner ends fixed, including their cross-road end walls. This
    # additional five-metre taper prevents seams with the untouched neighbours.
    station = [0.]
    for a, b in zip(rows, rows[1:]):
        station.append(station[-1] + math.dist(a[13][:2], b[13][:2]))
    delta = {}
    for i, row in enumerate(rows):
        end_weight = max(0., min(1., station[i] / TAPER_CM, (station[-1] - station[i]) / TAPER_CM))
        for column in (0, 1, 25, 26):
            p = row[column]
            weight = _weight(p, center) * end_weight
            if not weight:
                continue
            dz = 8. if column in (1, 25) else trace(p) - p[2]
            require(abs(dz) <= MAX_DELTA_CM, 'Terrain contact requires more than 50 cm; owner rejected')
            delta[top_ids[p]] = dz * weight
    require(any(abs(v) > EPS_CM for v in delta.values()), 'No repairable shoulder in viewport AOI')
    # Native support walls have separate vertices, including clipped crossings.
    # Infer their retained bottom from each exact XY column; map upper edge to
    # the authenticated perimeter. A crossing without vertical extent cannot
    # safely change topology in this bounded position-only operation.
    perimeter = [(rows[i][c], rows[i + 1][c]) for i in range(len(rows) - 1) for c in (0, 26)]
    perimeter += [(rows[i][c], rows[i][c + 1]) for i in (0, len(rows) - 1) for c in range(26)]
    top_set = set(top_ids.values())
    wall_ids = set(vertices) - top_set
    buckets = {}
    for vid in wall_ids:
        p = vertices[vid]
        buckets.setdefault((round(p[0], 4), round(p[1], 4)), []).append(p[2])
    for vid in sorted(wall_ids):
        p = vertices[vid]
        candidates = []
        for a, b in perimeter:
            t = _segment(p, a, b)
            if t is None:
                continue
            upper = a[2] + t * (b[2] - a[2])
            dz = (1 - t) * delta.get(top_ids[a], 0.) + t * delta.get(top_ids[b], 0.)
            candidates.append((upper, dz))
        require(candidates, 'Wall vertex is not on source perimeter')
        upper, dz = candidates[0]
        require(all(abs(z - upper) <= EPS_CM and abs(d - dz) <= EPS_CM for z, d in candidates), 'Ambiguous wall ownership')
        bottom = min(buckets[(round(p[0], 4), round(p[1], 4))])
        require(p[2] <= upper + EPS_CM, 'Wall extends above source top')
        if abs(dz) <= 1e-8:
            continue
        height = upper - bottom
        require(height > EPS_CM, 'Active clipped wall crossing needs topology repair; owner rejected')
        require(upper + dz >= bottom - EPS_CM, 'Repair would invert existing wall; owner rejected')
        ratio = max(0., min(1., (p[2] - bottom) / height))
        delta[vid] = dz * ratio
    changes = {vid: (vertices[vid][0], vertices[vid][1], vertices[vid][2] + dz)
               for vid, dz in delta.items() if abs(dz) > 1e-8}
    require(all(_weight(vertices[vid], center) > 0 for vid in changes), 'Interpolated wall extends outside AOI')
    return changes, {'label': owner['support_label'], 'window_id': owner['window_id'],
                     'changed_vertices': len(changes), 'wall_vertices': len(set(changes) & wall_ids),
                     'max_displacement_cm': max(abs(delta[v]) for v in changes),
                     'bounds_cm': [[min(p[k] for p in changes.values()) for k in range(3)],
                                   [max(p[k] for p in changes.values()) for k in range(3)]]}


def validate_observation(state, initial=None):
    require(isinstance(state, dict) and state.get('schema_version') == 1, 'Repair schema differs')
    require(state.get('state') in ('original', 'applied'), 'Repair state differs')
    require(state.get('road_unchanged') is True and state.get('landscape_mutated') is False, 'Frozen authority changed')
    require(state.get('radius_cm') == RADIUS_CM and state.get('taper_cm') == TAPER_CM, 'Repair bounds differ')
    require(isinstance(state.get('targets'), list) and len(state['targets']) <= 1, 'Repair owner bound differs')
    for row in state['targets']:
        require(0 < row['max_displacement_cm'] <= MAX_DELTA_CM and row['changed_vertices'] > 0, 'Repair displacement differs')
    if initial is not None:
        validate_observation(initial)
        require(state['road_summary'] == initial['road_summary'], 'Frozen road buffers changed')
    return state


class ShoulderRepair:
    def __init__(self, api, world, manifest):
        self.api, self.world = api, world
        self.manifest = manifest
        self.active = None
        self.receipts = []
        self.road = None
        self.actors = {}
        for actor in api.get_editor_subsystem(api.EditorActorSubsystem).get_all_level_actors():
            label = actor.get_actor_label()
            if label.startswith('YACS_PERSIST_SUPPORT_') or label == 'YACS_PERSIST_ROAD':
                require(label not in self.actors, 'Duplicate repair owner')
                self.actors[label] = actor
        require('YACS_PERSIST_ROAD' in self.actors, 'Frozen road missing')
        self.road = self.actors['YACS_PERSIST_ROAD'].get_dynamic_mesh_component()
        self.road_summary = inspect_mesh(api, self.road)['summary']
        self.initial = self.observe()

    def _trace(self, p):
        a = self.api
        actors = a.get_editor_subsystem(a.EditorActorSubsystem).get_all_level_actors()
        landscapes = {x.get_path_name() for x in actors if isinstance(x, a.LandscapeProxy)}
        require(landscapes, 'Native Landscape collision owner missing')
        ignore = [x for x in actors if x.get_path_name() not in landscapes]
        start, end = (p[0], p[1], p[2] + 200.), (p[0], p[1], p[2] - 200.)
        hit = a.SystemLibrary.line_trace_single(self.world, a.Vector(*start), a.Vector(*end),
                    a.TraceTypeQuery.ECC_VISIBILITY, True, ignore, a.DrawDebugTrace.NONE, True)
        require(hit is not None, 'Landscape trace missed')
        result = a.GameplayStatics.break_hit_result(hit)
        require(isinstance(result, tuple) and len(result) == 18, 'Native hit result signature differs')
        actor, impact = result[9], result[5]
        require(result[0] is True and actor is not None and actor.get_path_name() in landscapes,
                'Trace did not hit authenticated native Landscape')
        require(abs(impact.x-p[0]) < 1. and abs(impact.y-p[1]) < 1. and math.isfinite(impact.z), 'Landscape impact differs from ray')
        return float(impact.z)

    def observe(self):
        current = inspect_mesh(self.api, self.road)['summary']
        require(current == self.road_summary, 'Frozen road buffer changed')
        if self.active:
            component, original, backup, before, after = self.active
            require(component.get_dynamic_mesh() == original, 'Foreign support mesh replaced repair')
            require(inspect_mesh(self.api, component)['summary'] == after, 'Repair mesh changed outside bridge')
        return validate_observation({'schema_version': 1, 'state': 'applied' if self.active else 'original',
                    'radius_cm': RADIUS_CM, 'taper_cm': TAPER_CM, 'road_unchanged': True,
                    'landscape_mutated': False, 'road_summary': current, 'targets': list(self.receipts)})

    def apply(self):
        require(self.active is None, 'Restore current repair before applying again')
        self.observe()
        plan = sources.load_sources()
        require(plan['source_identity'] == self.manifest['shoulder_network']['source_identity'], 'Frozen source identity differs')
        center, _ = self.api.get_editor_subsystem(self.api.UnrealEditorSubsystem).get_level_viewport_camera_info()
        center = (float(center.x), float(center.y), float(center.z))
        owners = sorted((o for o in plan['owners'] if o['kind'] == 'ordinary'),
                        key=lambda o: min(math.dist(p[:2], center[:2]) for row in o['sections_cm'] for p in (row[0], row[26])))
        require(owners and min(math.dist(p[:2], center[:2]) for row in owners[0]['sections_cm'] for p in (row[0], row[26])) < RADIUS_CM, 'No ordinary shoulder near current viewport')
        owner = owners[0]
        component = self.actors[owner['support_label']].get_dynamic_mesh_component()
        before = inspect_mesh(self.api, component)
        records = [r for r in self.manifest['shoulder_network']['owners'] if r['support_label'] == owner['support_label']]
        require(len(records) == 1 and before['summary'] == records[0]['after_mesh'], 'Native support differs from saved authenticated buffers')
        count = before['summary']['triangle_count']
        snapshot = inspect_mesh(self.api, component, count)
        changes, receipt = _plan(owner, snapshot, center, self._trace)
        original = component.get_dynamic_mesh()
        backup = self.api.DynamicMesh()
        self.api.GeometryScript_MeshDecomposition.copy_mesh_to_mesh(original, backup)
        clone = self.api.DynamicMesh()
        self.api.GeometryScript_MeshDecomposition.copy_mesh_to_mesh(original, clone)
        for vid, position in sorted(changes.items()):
            result = self.api.GeometryScript_MeshEdits.set_vertex_position(clone, vid, self.api.Vector(*position), False)
            require(isinstance(result, tuple) and result[-1] is True, 'Native vertex setter rejected source-matched ID')
        # Copy into the existing bound mesh: object transfer would dirty the map.
        require(component.get_dynamic_mesh() == original, 'Support changed during preparation')
        try:
            self.api.GeometryScript_MeshDecomposition.copy_mesh_to_mesh(clone, original)
            require(component.get_dynamic_mesh() == original, 'Native bound mesh changed')
            after = inspect_mesh(self.api, component)['summary']
            for key in ('vertex_count', 'triangle_count', 'uv_set_count', 'triangle_corner_normals_uv_blake3', 'material_ids_blake3'):
                require(after[key] == before['summary'][key], 'Clone changed preserved topology/material/normal/UV buffers')
            require(after['positions_indices_blake3'] != before['summary']['positions_indices_blake3'], 'Native repair made no position change')
            self.active = (component, original, backup, before['summary'], after)
            self.receipts = [receipt]
            return self.observe()
        except Exception:
            if component.get_dynamic_mesh() == original:
                self.api.GeometryScript_MeshDecomposition.copy_mesh_to_mesh(backup, original)
                require(inspect_mesh(self.api, component)['summary'] == before['summary'], 'Repair rollback proof failed')
            self.active, self.receipts = None, []
            raise

    def restore(self):
        self.observe()
        if self.active:
            component, original, backup, before, after = self.active
            require(component.get_dynamic_mesh() == original, 'Foreign support mesh cannot be overwritten')
            self.api.GeometryScript_MeshDecomposition.copy_mesh_to_mesh(backup, original)
            require(inspect_mesh(self.api, component)['summary'] == before, 'Original support rollback differs')
            self.active, self.receipts = None, []
        return self.observe()


