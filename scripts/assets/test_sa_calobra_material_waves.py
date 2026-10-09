"""Guard resumable staging against memory pressure and duplicate work."""

import unittest

from scripts.ue.sa_calobra_material_waves import Waves


class WaveTests(unittest.TestCase):
    def test_memory_pause_does_not_consume_the_next_stage(self):
        memory = {"free_physical": 0, "free_commit": 0}
        waves = Waves(iter([{"phase": "IMPORT"}, {"phase": "BUILD"}]), lambda: memory)
        self.assertEqual(waves.advance()["phase"], "PAUSED_LOW_MEMORY")
        self.assertEqual(waves.completed, [])
        memory.update(free_physical=16 * 1024**3, free_commit=24 * 1024**3)
        self.assertEqual(waves.advance()["phase"], "IMPORT")
        self.assertEqual(len(waves.completed), 1)
        self.assertEqual(waves.advance()["phase"], "BUILD")
        self.assertEqual(waves.advance()["phase"], "COMPLETE")
        with self.assertRaises(RuntimeError):
            waves.advance()

    def test_reentry_is_rejected_without_consuming_work(self):
        waves = Waves(iter([{"phase": "IMPORT"}]))
        waves.running = True
        with self.assertRaises(RuntimeError):
            waves.advance()
        self.assertEqual(waves.completed, [])

    def test_failure_cannot_implicitly_restart(self):
        def failing():
            yield {"phase": "IMPORT"}
            raise ValueError("native failure")

        waves = Waves(
            failing(),
            lambda: {
                "free_physical": 16 * 1024**3,
                "free_commit": 24 * 1024**3,
            },
        )
        waves.advance()
        with self.assertRaises(ValueError):
            waves.advance()
        self.assertEqual(waves.status, "FAILED")
        self.assertFalse(waves.running)
        with self.assertRaises(RuntimeError):
            waves.advance()


if __name__ == "__main__":
    unittest.main()
