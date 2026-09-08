import types
import unittest

import cycling_physics


class TestCyclingPhysicsModule(unittest.TestCase):
    def test_module_can_be_imported(self):
        self.assertIsInstance(cycling_physics, types.ModuleType)


if __name__ == "__main__":
    unittest.main()
