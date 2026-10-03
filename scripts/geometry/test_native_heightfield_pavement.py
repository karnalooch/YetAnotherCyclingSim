import unittest
from collections import Counter
from scripts.geometry.native_heightfield_pavement import build_surface, solidify


class NativePavementTests(unittest.TestCase):
    def test_nonplanar_native_cell_preserves_each_facet_and_closed_slab(self):
        for diagonal in ('a_d','b_c'):
            ground,faces,proof=build_surface([(.1,.1),(.9,.1),(.9,.9),(.1,.9)],
                lambda x,y: x*y,cell_size=1,diagonal=diagonal)
            self.assertAlmostEqual(proof['mesh_area_xy_m2'],.64)
            vertices,triangles=solidify(ground,faces)
            for a,b,c in faces:
                x,y,z=[sum(vertices[i][j] for i in (a,b,c))/3 for j in range(3)]
                expected=min(x,y) if diagonal=='a_d' else max(0,x+y-1)
                self.assertAlmostEqual(z-expected,.04)
            counts=Counter(tuple(sorted(e)) for a,b,c in triangles for e in ((a,b),(b,c),(c,a)))
            self.assertEqual(set(counts.values()),{2})
            directed=Counter(e for a,b,c in triangles for e in ((a,b),(b,c),(c,a)))
            self.assertTrue(all(directed[(b,a)]==n for (a,b),n in directed.items()))

    def test_concave_footprint_preserves_empty_hairpin_island(self):
        outline=[(0,0),(2,0),(2,2),(1.5,2),(1.5,.5),(.5,.5),(.5,2),(0,2)]
        ground,faces,proof=build_surface(outline,lambda x,y:x+y,diagonal='a_d')
        self.assertAlmostEqual(proof['mesh_area_xy_m2'],2.5)
        for a,b,c in faces:
            x,y=[sum(ground[i][j] for i in (a,b,c))/3 for j in range(2)]
            self.assertFalse(.5<x<1.5 and .5<y<2)

    def test_invalid_outline_is_rejected_without_silent_repair(self):
        with self.assertRaisesRegex(ValueError,'Invalid'):
            build_surface([(0,0),(1,1),(1,0),(0,1)],lambda x,y:0,diagonal='a_d')

if __name__=='__main__':
    unittest.main()
