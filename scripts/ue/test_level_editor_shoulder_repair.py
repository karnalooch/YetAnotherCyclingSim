"""Pure planner regression cases. Execution requires owner authorization."""
import unittest
from scripts.ue.level_editor_shoulder_repair import _segment, _weight, validate_observation


class ShoulderRepairBoundsTests(unittest.TestCase):
    def test_radial_taper_uses_xy_not_camera_altitude(self):
        self.assertEqual(_weight((0, 0, -10000), (0, 0, 10000)), 1)
        self.assertEqual(_weight((3250, 0, 0), (0, 0, 0)), .5)
        self.assertEqual(_weight((3500, 0, 0), (0, 0, 0)), 0)

    def test_wall_matching_rejects_foreign_xy(self):
        self.assertIsNone(_segment((50, 1, 10), (0, 0, 0), (100, 0, 0)))
        self.assertIsNone(_segment((101, 0, 10), (0, 0, 0), (100, 0, 0)))
        self.assertEqual(_segment((50, 0, -10), (0, 0, 0), (100, 0, 0)), .5)

    def test_observation_refuses_frozen_road_change(self):
        state = {'schema_version': 1, 'state': 'original', 'road_unchanged': False,
                 'landscape_mutated': False, 'radius_cm': 3000., 'taper_cm': 500.,
                 'targets': [], 'road_summary': {}}
        with self.assertRaisesRegex(ValueError, 'Frozen authority'):
            validate_observation(state)

class ShoulderRepairWallTests(unittest.TestCase):
    def fixture(self):
        from scripts.ue import road_shoulder_sources as sources
        rows = tuple(tuple((float(j * 50), float(i * 1000), 100.) for j in range(27)) for i in range(5))
        owner = {'sections_cm': rows, 'kind': 'ordinary', 'support_label': 'YACS_PERSIST_SUPPORT_000', 'window_id': 'test'}
        positions = [p for row in rows for p in row]
        lookup = {p: i for i, p in enumerate(positions)}
        faces = [tuple(lookup[p] for p in triangle) for _, triangle in sources.iter_expected_triangles(owner)]
        wall_top, wall_bottom = [], []
        for i in range(4):
            for column in (0, 26):
                a, b = rows[i][column], rows[i + 1][column]
                offset = len(positions)
                positions.extend((a, b, (a[0], a[1], 0.), (b[0], b[1], 0.)))
                faces.extend(((offset, offset + 1, offset + 2), (offset + 1, offset + 3, offset + 2)))
                wall_top.extend((offset, offset + 1))
                wall_bottom.extend((offset + 2, offset + 3))
        witnesses = [[i, *face, *(v for vid in face for v in positions[vid])] for i, face in enumerate(faces)]
        return owner, {'witness_triangles': witnesses, 'summary': {'vertex_count': len(positions)}}, wall_top, wall_bottom

    def test_duplicate_wall_upper_vertices_follow_top_and_bottom_stays(self):
        from scripts.ue.level_editor_shoulder_repair import _plan
        owner, snapshot, top, bottom = self.fixture()
        changes, receipt = _plan(owner, snapshot, (650., 2000., 1000.), lambda p: 90.)
        self.assertGreater(receipt['wall_vertices'], 0)
        self.assertTrue(any(v in changes for v in top))
        self.assertFalse(any(v in changes for v in bottom))
        self.assertTrue(all(changes[v][2] == 90. for v in top if v in changes))

    def test_excessive_terrain_delta_rejects_before_native_mutation(self):
        from scripts.ue.level_editor_shoulder_repair import _plan
        owner, snapshot, _, _ = self.fixture()
        with self.assertRaisesRegex(ValueError, 'more than 50 cm'):
            _plan(owner, snapshot, (650., 2000., 1000.), lambda p: -100.)
