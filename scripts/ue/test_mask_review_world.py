"""Regression coverage for preserving the owner's unsaved world during review."""
import unittest
from unittest.mock import Mock

from scripts.ue.mask_review_world import require_existing_review_world


class ExistingReviewWorldTests(unittest.TestCase):
    def test_matching_live_world_is_returned_without_reloading(self):
        world = Mock()
        world.get_path_name.return_value = '/Game/Worlds/Review.Review'
        editor = Mock()
        editor.get_editor_world.return_value = world
        self.assertIs(require_existing_review_world(editor, '/Game/Worlds/Review'), world)
        self.assertEqual(editor.method_calls, [('get_editor_world', (), {})])

    def test_wrong_world_is_rejected_without_loading_the_requested_map(self):
        world = Mock()
        world.get_path_name.return_value = '/Game/Worlds/Other.Other'
        editor = Mock()
        editor.get_editor_world.return_value = world
        with self.assertRaisesRegex(RuntimeError, 'discards transient roads'):
            require_existing_review_world(editor, '/Game/Worlds/Review')
        self.assertEqual(editor.method_calls, [('get_editor_world', (), {})])

    def test_missing_world_is_rejected(self):
        editor = Mock()
        editor.get_editor_world.return_value = None
        with self.assertRaises(RuntimeError):
            require_existing_review_world(editor, '/Game/Worlds/Review')


if __name__ == '__main__':
    unittest.main()
