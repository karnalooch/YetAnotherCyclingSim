import tempfile
import unittest
from pathlib import Path

from scripts.ci.retain_unreal_assets import digest, retain


class RetentionTests(unittest.TestCase):
    def test_preserves_payload_pointer_and_lfs_object_cache(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            workspace = root / "worktree"
            content = workspace / "Content"
            content.mkdir(parents=True)
            asset = content / "terrain.umap"
            asset.write_bytes(b"real binary asset\x00" * 100)
            sha = digest(asset)
            pointer = content / "lazy.uasset"
            pointer.write_bytes(b"version https://git-lfs.github.com/spec/v1\n")
            cache = workspace / ".git/lfs/objects/cached"
            cache.parent.mkdir(parents=True)
            cache.write_bytes(b"cached payload")
            manifest = retain(workspace, root / "retained")
            self.assertEqual(sha, digest(root / "retained/Content/terrain.umap"))
            self.assertFalse(asset.exists())
            self.assertTrue(pointer.exists())
            self.assertEqual(b"cached payload", cache.read_bytes())
            self.assertEqual(1, len(manifest["assets"]))

    def test_existing_archive_fails_without_moving_source(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            asset = root / "worktree/Content/map.umap"
            asset.parent.mkdir(parents=True)
            asset.write_bytes(b"original")
            (root / "retained").mkdir()
            with self.assertRaises(FileExistsError):
                retain(root / "worktree", root / "retained")
            self.assertEqual(b"original", asset.read_bytes())

    def test_archive_inside_worktree_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with self.assertRaises(ValueError):
                retain(root, root / "Saved/retained")

    def test_symlink_asset_is_rejected_without_touching_target(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            target = root / "original.umap"
            target.write_bytes(b"original")
            content = root / "worktree/Content"
            content.mkdir(parents=True)
            (content / "map.umap").symlink_to(target)
            with self.assertRaises(ValueError):
                retain(root / "worktree", root / "retained")
            self.assertEqual(b"original", target.read_bytes())


if __name__ == "__main__":
    unittest.main()
