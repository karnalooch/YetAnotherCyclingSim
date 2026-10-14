"""Reject unsafe native readback without starting or mutating Unreal."""
from copy import deepcopy
import unittest

from scripts.worldgen.pcg365_wall_surface import check_continuous_surface, check_normal_transfer


class WallProofTests(unittest.TestCase):
    def setUp(self):
        def point(index, x, y, z, alpha):
            return {"@Points.$Transform": {"translation": [x, y, z], "rotation": [0, 0, 0, 1]},
                    "@Points.$Color": [0, 0, 1, alpha], "@Points.$Density": 1,
                    "@Points.PCGEx/VData": str(((index+1) << 32) | 2), "@Points.GroundHit": "true"}
        self.mesh = {"element_"+str(i): point(i, x, y, 3, a)
                     for i, (x, y, a) in enumerate([(0, 0, 0), (50, 0, .5), (50, 50, 1)])}
        self.encoded = deepcopy(self.mesh)
        self.ground, self.flat = deepcopy(self.mesh), deepcopy(self.mesh)
        for p in self.ground.values():
            p["@Points.$Transform"]["translation"][2] = 0
        for p in self.flat.values():
            p["@Points.$Transform"]["translation"][2] = 1000000
        self.source = {"records": [[0, 0, 1, 150], [0, 1, 1, 150], [1, 1, 1, 150]]}
        self.edges = {"element_"+str(i): {"@Points.PCGEx/EData": str((a << 32) | b)}
                      for i, (a, b) in enumerate([(1, 2), (2, 3), (1, 3)])}
        self.probes = {"element_"+str(i): {"@Points.GroundHit": "true", "@Points.GroundDistance": 1003} for i in range(3)}

    def verify(self):
        return check_continuous_surface(self.source, self.flat, self.ground,
                                        self.encoded, self.mesh, self.edges, self.probes)

    def test_valid_native_triangle(self):
        self.assertEqual(self.verify()["connected_surface_regions"], 1)
        self.assertEqual(check_normal_transfer(self.encoded, self.encoded, self.mesh)["vertices"], 3)

    def test_merged_but_disconnected_mesh_is_rejected(self):
        self.edges = [self.edges, deepcopy(self.edges)]
        with self.assertRaisesRegex(ValueError, "one connected"):
            self.verify()

    def test_missing_protected_input_is_rejected(self):
        self.source["records"].pop()
        with self.assertRaisesRegex(ValueError, "protected input"):
            self.verify()

    def test_insufficient_clearance_is_rejected(self):
        self.source["records"][0][3] = 60
        with self.assertRaisesRegex(ValueError, "clearance"):
            self.verify()

    def test_lost_material_alpha_is_rejected(self):
        self.mesh["element_1"]["@Points.$Color"][3] = 1
        with self.assertRaisesRegex(ValueError, "weight changed"):
            self.verify()

    def test_landscape_intersection_is_rejected(self):
        self.probes["element_1"]["@Points.GroundDistance"] = 999
        with self.assertRaisesRegex(ValueError, "intersects Landscape"):
            self.verify()

    def test_geometry_motion_is_rejected(self):
        self.mesh["element_1"]["@Points.$Transform"]["translation"][2] += 1
        with self.assertRaisesRegex(ValueError, "separation"):
            self.verify()

    def test_normal_drift_is_rejected(self):
        self.mesh["element_1"]["@Points.$Transform"]["rotation"] = [1, 0, 0, 0]
        with self.assertRaisesRegex(ValueError, "normal transfer"):
            check_normal_transfer(self.encoded, self.encoded, self.mesh)


if __name__ == "__main__":
    unittest.main()
