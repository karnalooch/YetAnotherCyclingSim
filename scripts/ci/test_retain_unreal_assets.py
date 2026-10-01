import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.ci.retain_unreal_assets import digest, retain


class RetentionTests(unittest.TestCase):
    def test_retains_non_unreal_lfs_payload_from_real_git_repository(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            workspace = root / "worktree"
            workspace.mkdir()
            for args in (["init"], ["lfs", "install", "--local"]):
                subprocess.run(
                    ["git", *args], cwd=workspace, check=True, capture_output=True
                )
            (workspace / ".gitattributes").write_text(
                "*.png filter=lfs diff=lfs merge=lfs -text\n"
            )
            image = workspace / "source.png"
            image.write_bytes(b"source image binary\x00" * 100)
            subprocess.run(
                ["git", "add", ".gitattributes", "source.png"],
                cwd=workspace,
                check=True,
                capture_output=True,
            )
            manifest = retain(workspace, root / "retained")
            self.assertEqual(
                b"source image binary\x00" * 100,
                (root / "retained/source.png").read_bytes(),
            )
            self.assertEqual("source.png", manifest["assets"][0]["path"])
            self.assertTrue(any((workspace / ".git/lfs/objects").rglob("*")))

    def test_preserves_payload_pointer_and_lfs_object_cache(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            workspace = root / "worktree"
            content = workspace / "Content"
            content.mkdir(parents=True)
            subprocess.run(
                ["git", "init"], cwd=workspace, check=True, capture_output=True
            )
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
            content.parent.mkdir(parents=True)
            if os.name == "nt":
                # Directory junctions exercise the escape guard without the
                # administrator-only Windows symbolic-link privilege.
                external = root / "external"
                external.mkdir()
                target = external / "map.umap"
                target.write_bytes(b"original")
                subprocess.run(
                    ["cmd", "/c", "mklink", "/J", str(content), str(external)],
                    check=True,
                    capture_output=True,
                )
            else:
                content.mkdir()
                (content / "map.umap").symlink_to(target)
            with self.assertRaises(ValueError):
                retain(root / "worktree", root / "retained")
            self.assertEqual(b"original", target.read_bytes())


if __name__ == "__main__":
    unittest.main()
