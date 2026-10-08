"""Reject source reset and protection drift before admitting a narrow bevel."""
import copy
import unittest
from scripts.assets.analyze_limestone_edge_rounding import (
    _certify_triangle_band, _segment_distance, audit_edges,
)


class EdgeSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cells = [dict(col0=c,row0=r,col1=c+2,row1=r+2,protected_samples=0)
                 for r in range(882,1008,2) for c in range(756,882,2)]
        cls.plan = dict(skin_cells=cells[:1017],rounding_cells=cells,
            rounding_domain_contract=dict(method='source-cliff-six-metre-crown-apron-v1',
                radius_m=6,classifier_unchanged=True,hard_protected_samples=0,
                cell_count=3969,area_m2=3969))
        rows = [[y*127+x,(756+x)*50,(882+y)*50,-abs(x-63)*50]
                for y in range(127) for x in range(127)]
        faces = []
        for y in range(126):
            for x in range(126):
                a = y*127+x
                b, c, d = a+1, a+127, a+128
                faces.extend(([a,c,d], [a,d,b]))
        cls.evidence = dict(edge_source_vertices_cm=rows,edge_source_triangles=faces,
            rounded_source_edges=[[y*127+63,(y+1)*127+63] for y in range(1,125)],
            vertices_cm=[[r[0],*r[1:],*r[1:],0] for r in rows],
            triangles=copy.deepcopy(faces))
        cls.reference = dict(vertices_cm=[[r[0],*r[1:],*r[1:],0] for r in rows])

    @classmethod
    def narrow_two_facet_bevel(cls):
        """Cut a tiny curved strip into two native ridge facets, with tapered caps.

        The full 127 by 127 native source and every original vertex survive.
        Only the two facets around one half-metre ridge segment are retessellated;
        the side triangles stay exactly on their original source planes.
        """
        data = copy.deepcopy(cls.evidence)
        a = 63*127+63
        b, left, right = a+127, a-1, a+128
        source_faces = {(a,b,right), (left,b,a)}
        data['triangles'] = [f for f in data['triangles'] if tuple(f) not in source_faces]
        origin = data['edge_source_vertices_cm'][a][1:4]
        new_ids = []
        for x,y,z in ((-2,12.5,-2), (-2,37.5,-2), (2,12.5,-2), (2,37.5,-2),
                      (0,12.5,-1), (0,37.5,-1)):
            v = 16129+len(new_ids)
            p = [origin[0]+x, origin[1]+y, origin[2]+z]
            # The center points are equally near both original ridge planes.
            q = [origin[0]-.5, origin[1]+y, origin[2]-.5] if x == 0 else p.copy()
            data['vertices_cm'].append([v,*q,*p,1])
            new_ids.append(v)
        lb,lt,rb,rt,cb,ct = new_ids
        data['triangles'].extend((
            [left,b,lt], [left,lt,lb], [left,lb,a],
            [right,a,rb], [right,rb,rt], [right,rt,b],
            [a,lb,cb], [a,cb,rb], [lb,lt,ct], [lb,ct,cb],
            [cb,ct,rt], [cb,rt,rb], [lt,b,ct], [ct,b,rt],
        ))
        return data

    def test_previously_smoothed_source_cannot_reset_the_reference(self):
        data = copy.deepcopy(self.evidence)
        data['edge_source_vertices_cm'][500][3] = 0.01
        with self.assertRaisesRegex(ValueError,'original before erosion'):
            audit_edges(self.plan,self.reference,data)

    def test_complete_native_topology_is_required(self):
        data = copy.deepcopy(self.evidence)
        data['edge_source_triangles'] = []
        with self.assertRaisesRegex(ValueError,'topology changed'):
            audit_edges(self.plan,self.reference,data)

    def test_protected_edge_domain_is_rejected(self):
        plan = copy.deepcopy(self.plan)
        plan['rounding_cells'][100]['protected_samples'] = 1
        with self.assertRaisesRegex(ValueError,'Protected'):
            audit_edges(plan,self.reference,self.evidence)

    def test_narrow_two_facet_bevel_passes_complete_source_audit(self):
        result = audit_edges(self.plan,self.reference,self.narrow_two_facet_bevel())
        self.assertEqual(result['status'], 'PASS')
        self.assertTrue(result['complete_changed_triangle_band_certified'])
        self.assertEqual(result['certified_changed_triangles'], 8)
        self.assertEqual(result['changed_vertices'], 6)
        self.assertLessEqual(result['max_certified_triangle_band_cm'], 10.000001)

    def test_folded_bevel_cap_is_rejected(self):
        data = self.narrow_two_facet_bevel()
        data['triangles'][-8].reverse()
        with self.assertRaisesRegex(ValueError,'Folded or degenerate'):
            audit_edges(self.plan,self.reference,data)

    def test_changed_triangle_bridging_ridges_fails_even_when_vertices_pass(self):
        data = copy.deepcopy(self.evidence)
        for row in data['edge_source_vertices_cm']:
            x, y = row[0]%127, row[0]//127
            row[3] = -50*(abs(x-63)+abs(y-63))
        data['vertices_cm'] = [[r[0],*r[1:],*r[1:],0] for r in data['edge_source_vertices_cm']]
        reference = dict(vertices_cm=copy.deepcopy(data['vertices_cm']))
        data['rounded_source_edges'] += [[63*127+x,63*127+x+1] for x in range(1,125)]
        origin = data['edge_source_vertices_cm'][63*127+63][1:4]
        ids = []
        for x,y in ((0,0), (0,40), (40,0)):
            v = 16129+len(ids)
            p = [origin[0]+x, origin[1]+y, origin[2]-x-y-1]
            q = [p[k]+1/3 for k in range(3)]
            data['vertices_cm'].append([v,*q,*p,1])
            ids.append(v)
        data['triangles'].append(ids)
        # The three lifted corners and their source references are within a
        # centimetre of a ridge. The triangle's interior bridges the two bands.
        with self.assertRaisesRegex(ValueError,'Changed triangle surface extends outside'):
            audit_edges(self.plan,reference,data)


class CompleteTriangleBandTests(unittest.TestCase):
    def test_capsule_union_cannot_admit_an_interior_bridge_from_corner_samples(self):
        segments = (((0,0,0),(0,50,0)), ((0,0,0),(50,0,0)))
        triangle = ((0,0,-1), (0,40,-1), (40,0,-1))
        self.assertTrue(all(min(_segment_distance(p,*e) for e in segments) < 10 for p in triangle))
        with self.assertRaisesRegex(ValueError,'Changed triangle surface extends outside'):
            _certify_triangle_band(triangle, segments)

    def test_adaptive_subdivision_proves_a_triangle_covered_by_several_capsules(self):
        segments = (((0,0,0),(0,10,0)), ((0,0,0),(10,0,0)))
        triangle = ((0,0,0), (0,8,0), (8,0,0))
        self.assertLessEqual(_certify_triangle_band(triangle, segments, radius_cm=5), 5.000001)

    def test_uncertified_budget_exhaustion_fails_closed(self):
        segments = (((0,0,0),(0,10,0)), ((0,0,0),(10,0,0)))
        triangle = ((0,0,0), (0,8,0), (8,0,0))
        with self.assertRaisesRegex(ValueError,'Could not certify'):
            _certify_triangle_band(triangle, segments, radius_cm=5, max_depth=0)

    def test_source_exemption_requires_one_facet_to_contain_the_complete_piece(self):
        left = {0}
        right = {1}
        membership = {(-30,0,0):left, (30,0,0):right, (0,30,0):left|right}
        unchanged = lambda points: bool(set.intersection(*(membership.get(p,set()) for p in points)))
        with self.assertRaisesRegex(ValueError,'outside'):
            _certify_triangle_band(((-30,0,0),(30,0,0),(0,30,0)), (), unchanged)
