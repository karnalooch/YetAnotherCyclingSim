import tempfile
import unittest
from pathlib import Path

from scripts.ci.retire_italy_payloads import apply, inventory


class ItalyRetirementTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()

    def payload(self, path, content=b"old Italy map"):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return target

    def test_deletes_only_italy_payloads_and_records_bytes(self):
        old = self.payload(
            "_terrain-recovery-worktree/Content/Prototype/Maps/L_PassoGiauTerrainSpike.umap"
        )
        spanish = self.payload(
            "_terrain-recovery-worktree/Content/Worlds/SaCalobra/test.umap"
        )
        shared = self.payload(
            "_terrain-recovery-worktree/Content/Prototype/Maps/L_CyclingTest.umap"
        )
        cache = self.payload("_terrain-recovery-worktree/.git/lfs/objects/abc")
        plan = inventory(self.root)
        result = apply(plan, self.root, self.root / "receipt.json")
        self.assertFalse(old.exists())
        self.assertEqual(result["reclaimed_payload_bytes"], len(b"old Italy map"))
        self.assertTrue(all(p.exists() for p in [spanish, shared, cache]))

    def test_changed_payload_fails_before_any_delete(self):
        old = self.payload(
            "_embark-terrain-worktree/ExternalAssets/Terrain/PassoGiau/source.tif"
        )
        plan = inventory(self.root)
        old.write_bytes(b"changed data")
        with self.assertRaisesRegex(ValueError, "changed since inventory"):
            apply(plan, self.root, self.root / "receipt.json")
        self.assertTrue(old.exists())

    def test_injected_spanish_or_traversal_entry_is_rejected(self):
        spanish = self.payload(
            "_yacs-retained-lfs/1/Content/Worlds/SaCalobra/test.umap"
        )
        for path in [spanish.relative_to(self.root).as_posix(), "../outside"]:
            plan = inventory(self.root)
            plan["assets"] = [{"path": path, "size_bytes": 0, "sha256": ""}]
            with self.assertRaisesRegex(ValueError, "Unapproved"):
                apply(plan, self.root, self.root / "receipt.json")
        self.assertTrue(spanish.exists())

    def test_pointer_is_not_a_payload_and_archive_italy_is_eligible(self):
        pointer = self.payload(
            "_embark-terrain-worktree/Content/Prototype/Maps/L_PassoGiauTerrainSpike.umap",
            b"version https://git-lfs.github.com/spec/v1\noid sha256:abc\nsize 123\n",
        )
        old = self.payload(
            "_yacs-retained-lfs/123/after-proof/Content/Prototype/Maps/L_PassoGiauTerrainSpike.umap"
        )
        plan = inventory(self.root)
        self.assertEqual(
            [e["path"] for e in plan["assets"]], [old.relative_to(self.root).as_posix()]
        )
        apply(plan, self.root, self.root / "receipt.json")
        self.assertTrue(pointer.exists())


if __name__ == "__main__":
    unittest.main()
