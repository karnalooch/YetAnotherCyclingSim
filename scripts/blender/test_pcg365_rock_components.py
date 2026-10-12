"""Pure component graph checks; Blender is not imported or executed."""

import importlib.util
from pathlib import Path
import unittest

SPEC = importlib.util.spec_from_file_location(
    "rock_components", Path(__file__).with_name("inspect_pcg365_rock_components.py")
)
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


class ComponentsTests(unittest.TestCase):
    def test_disconnected_components_stable(self):
        faces = [[0, 1, 2], [2, 1, 3], [4, 5, 6], [6, 5, 7], [8, 9, 10]]
        self.assertEqual(m.face_components(faces), [[0, 1], [2, 3], [4]])
        self.assertEqual(m.face_components(faces), m.face_components(faces))

    def test_vertex_contact_is_connected_without_weld(self):
        self.assertEqual(m.face_components([[0, 1, 2], [2, 3, 4]]), [[0, 1]])
        self.assertEqual(m.face_components([[0, 1, 2], [3, 4, 5]]), [[0], [1]])

    def test_empty(self):
        self.assertEqual(m.face_components([]), [])


if __name__ == "__main__":
    unittest.main()
