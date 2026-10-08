"""Reject source reset and protection drift before admitting a narrow bevel."""
import copy
import unittest
from scripts.assets.analyze_limestone_edge_rounding import audit_edges


class EdgeSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cells = [dict(col0=c,row0=r,col1=c+2,row1=r+2,protected_samples=0)
                 for r in range(882,1008,2) for c in range(756,882,2)]
        cls.plan = dict(skin_cells=cells[:1017],rounding_cells=cells,
            rounding_domain_contract=dict(method='source-cliff-six-metre-crown-apron-v1',
                radius_m=6,classifier_unchanged=True,hard_protected_samples=0,
                cell_count=3969,area_m2=3969))
        rows = [[y*127+x,(756+x)*50,(882+y)*50,0]
                for y in range(127) for x in range(127)]
        cls.evidence = dict(edge_source_vertices_cm=rows,edge_source_triangles=[])
        cls.reference = dict(vertices_cm=[[r[0],*r[1:],*r[1:],0] for r in rows])

    def test_previously_smoothed_source_cannot_reset_the_reference(self):
        data = copy.deepcopy(self.evidence)
        data['edge_source_vertices_cm'][500][3] = 0.01
        with self.assertRaisesRegex(ValueError,'original before erosion'):
            audit_edges(self.plan,self.reference,data)

    def test_complete_native_topology_is_required(self):
        with self.assertRaisesRegex(ValueError,'topology changed'):
            audit_edges(self.plan,self.reference,self.evidence)

    def test_protected_edge_domain_is_rejected(self):
        plan = copy.deepcopy(self.plan)
        plan['rounding_cells'][100]['protected_samples'] = 1
        with self.assertRaisesRegex(ValueError,'Protected'):
            audit_edges(plan,self.reference,self.evidence)
