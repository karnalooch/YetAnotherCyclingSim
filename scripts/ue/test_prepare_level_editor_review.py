"""Offline file-system checks for the pinned Level Editor snapshot adapter.

All asset and binary bytes below are synthetic. No test starts Unreal, a build,
a server, Git mutation or network operation, and no fixture is runtime evidence.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

from scripts.ue import prepare_level_editor_review as preparation


LAUNCHER_SHA = "a" * 40


def identity(raw):
    return {"sha256": hashlib.sha256(raw).hexdigest(), "size_bytes": len(raw)}


def write(root, relative, raw):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return path


def tree_bytes(root):
    return {str(path.relative_to(root)): path.read_bytes()
            for path in root.rglob("*") if path.is_file() and not path.is_symlink()}


class SnapshotFixture:
    """Retain the actual receipt shape while replacing large host inputs."""

    def __init__(self, base):
        self.source, self.project, self.checked = (
            base / name for name in ("native-source", "launcher", "checked-evidence"))
        self.destination = base / "review" / "synthetic-session"
        self.documents = {
            name: json.loads((preparation.ROOT / preparation.CHECKED_EVIDENCE / name).read_bytes())
            for name in preparation.PINNED_METADATA
        }
        staged = self.documents["session-preparation.json"]
        dep = copy.deepcopy(staged["source_dependencies"][0])
        png = {"path": sorted(preparation.PNG_DEPENDENCIES)[0]}
        consumer = copy.deepcopy(staged["consumer_assets"][0])
        staged["source_dependencies"] = [dep, png]
        staged["consumer_assets"] = [consumer, copy.deepcopy(dep)]
        self.asset_rows = (
            staged["source_dependencies"] + staged["consumer_assets"]
            + self.documents["road-asphalt-saved-manifest.json"]["assets"])
        for row in self.asset_rows:
            raw = ("SYNTHETIC asset bytes: " + row["path"] + "\n").encode()
            write(self.source, row["path"], raw)
            row.update(identity(raw))
        self.map_sha256 = identity((self.source / preparation.MAP_FILE).read_bytes())["sha256"]
        host = self.documents["host-receipt.json"]
        host["project_root"] = str(self.source)
        host["proof_root"] = str(self.source / preparation.EVIDENCE_RELATIVE)
        for row in host["binary_provenance"]:
            relative = row["relative"]
            if relative in preparation.MODULE_CLOSURES:
                raw = json.dumps({
                    "BuildId": preparation.NATIVE_BUILD_ID,
                    "Modules": preparation.MODULE_CLOSURES[relative],
                }, sort_keys=True).encode()
            else:
                raw = ("SYNTHETIC DLL, not executable: " + relative).encode()
            write(self.source, relative, raw)
            row["original_identity"].update(identity(raw))
            row["copied_identity"].update(identity(raw), path=str(self.source / relative))
        self.project_anchors = {}
        for relative in preparation.PINNED_PROJECT_FILES:
            raw = (preparation.ROOT / relative).read_bytes()
            write(self.project, relative, raw)
            value = identity(raw)
            self.project_anchors[relative] = (value["sha256"], value["size_bytes"])
        # Unrelated files must stay in the source. In particular, startup Python
        # and Saved configuration must never leak into the review project.
        write(self.source, "Content/Python/init_unreal.py", b"SYNTHETIC must not execute\n")
        write(self.source, "Saved/Config/WindowsEditor/EditorPerProjectUserSettings.ini",
              b"SYNTHETIC private source setting\n")
        write(self.source, "Plugins/RoadForge/Unreviewed.txt", b"SYNTHETIC extra\n")
        self.refresh_evidence()

    def refresh_evidence(self):
        self.anchors = {}

        def save(name):
            raw = (json.dumps(self.documents[name], sort_keys=True, indent=2) + "\n").encode()
            value = identity(raw)
            self.anchors[name] = (value["sha256"], value["size_bytes"])
            write(self.source / preparation.EVIDENCE_RELATIVE, name, raw)
            write(self.checked, name, raw)
            return {**value, "path": str(self.source / preparation.EVIDENCE_RELATIVE / name)}

        staged = save("session-preparation.json")
        self.documents["road-asphalt-saved-manifest.json"]["staging_sha256"] = staged["sha256"]
        manifest = save("road-asphalt-saved-manifest.json")
        self.documents["road-asphalt-saved-reloaded.json"].update({
            "map_sha256": self.map_sha256,
            "saved_manifest_sha256": manifest["sha256"],
            "evidence_manifest_sha256": manifest["sha256"],
        })
        reload = save("road-asphalt-saved-reloaded.json")
        self.documents["host-receipt.json"]["proof_files"]["session_preparation"] = staged
        self.documents["saved-road-host-receipt.json"]["proof_files"].update({
            "saved_manifest": manifest, "fresh_reload": reload,
        })
        save("host-receipt.json")
        save("saved-road-host-receipt.json")

    def prepare(self, **overrides):
        args = {
            "source_root": self.source, "project_root": self.project,
            "checked_evidence_root": self.checked, "metadata_anchors": self.anchors,
            "project_anchors": self.project_anchors, "map_sha256": self.map_sha256,
            "synthetic": True,
        }
        args.update(overrides)
        return preparation.prepare(self.destination, LAUNCHER_SHA, **args)


class LevelEditorSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name).resolve()
        self.fixture = SnapshotFixture(self.base)
        # Disk reservation is checked without requiring a large test volume;
        # all file reads, hashing and independent writes remain real.
        self.disk = mock.patch.object(
            preparation.shutil, "disk_usage",
            return_value=SimpleNamespace(free=20 * 1024 ** 3))
        self.disk.start()
        self.addCleanup(self.disk.stop)

    def assert_source_unchanged(self, source_before, project_before):
        self.assertEqual(tree_bytes(self.fixture.source), source_before)
        self.assertEqual(tree_bytes(self.fixture.project), project_before)

    def reject_without_source_change(self, message=None):
        source_before, project_before = tree_bytes(self.fixture.source), tree_bytes(self.fixture.project)
        with self.assertRaisesRegex(ValueError, message or ".*"):
            self.fixture.prepare()
        self.assert_source_unchanged(source_before, project_before)
        self.assertFalse((self.fixture.destination / preparation.RECEIPT_NAME).exists())

    def test_success_is_an_independent_closed_copy_and_never_stream_evidence(self):
        source_before, project_before = tree_bytes(self.fixture.source), tree_bytes(self.fixture.project)
        receipt = self.fixture.prepare()
        self.assertEqual(receipt["status"], "SYNTHETIC_SNAPSHOT_PREPARED")
        self.assertTrue(receipt["synthetic"])
        self.assertEqual(receipt["runtime_source_sha"], preparation.RUNTIME_SHA)
        self.assertEqual(receipt["launcher_sha"], LAUNCHER_SHA)
        self.assertNotEqual(receipt["runtime_source_sha"], receipt["launcher_sha"])
        self.assertEqual(receipt["map_package"], preparation.MAP_PACKAGE)
        self.assertEqual(receipt["map_sha256"], self.fixture.map_sha256)
        self.assertEqual(receipt["identical_duplicate_rows_merged"], 1)
        self.assertFalse(receipt["unreal_launched"])
        self.assertFalse(receipt["stream_verified"])
        self.assertFalse(receipt["performance_pass"])
        self.assertEqual(receipt["stream_status"], "NOT_STARTED")
        self.assertEqual(receipt["owner_visual_status"], "PENDING_FINAL_M3")
        self.assertEqual(receipt["performance_status"], "DEFERRED_AFTER_M3")
        expected_paths = {row["path"] for row in self.fixture.asset_rows}
        expected_paths |= preparation.BINARY_PATHS | set(preparation.PINNED_PROJECT_FILES)
        expected_paths |= {"ReviewEvidence/" + name for name in self.fixture.anchors}
        self.assertEqual({row["path"] for row in receipt["snapshot_files"]}, expected_paths)
        self.assertEqual(receipt["copied_file_count"], len(expected_paths))
        self.assertEqual(receipt["copied_bytes"], sum(row["size_bytes"] for row in receipt["snapshot_files"]))
        self.assertEqual(
            json.loads((self.fixture.destination / preparation.RECEIPT_NAME).read_bytes()), receipt)
        for row in receipt["snapshot_files"]:
            original, copied = Path(row["source_path"]), Path(row["snapshot_path"])
            self.assertEqual(copied.read_bytes(), original.read_bytes())
            self.assertEqual(identity(copied.read_bytes()), {
                "sha256": row["sha256"], "size_bytes": row["size_bytes"]})
            self.assertFalse(original.samefile(copied))
            self.assertFalse(copied.is_symlink())
            self.assertEqual(copied.stat().st_nlink, 1)
        self.assertFalse((self.fixture.destination / "Content/Python").exists())
        self.assertFalse((self.fixture.destination / "Saved").exists())
        self.assertFalse((self.fixture.destination / "Plugins/RoadForge/Unreviewed.txt").exists())
        self.assertEqual((self.fixture.destination / "Config/DefaultEditor.ini").read_bytes(), b"")
        (self.fixture.destination / preparation.MAP_FILE).write_bytes(b"SYNTHETIC local edit")
        self.assert_source_unchanged(source_before, project_before)

    def test_checked_in_anchors_and_project_bytes_match_pins(self):
        for root, anchors in (
            (preparation.ROOT / preparation.CHECKED_EVIDENCE, preparation.PINNED_METADATA),
            (preparation.ROOT, preparation.PINNED_PROJECT_FILES),
        ):
            for relative, (sha, size) in anchors.items():
                with self.subTest(relative=relative):
                    self.assertEqual(identity((root / relative).read_bytes()), {
                        "sha256": sha, "size_bytes": size})

    def test_native_and_checked_evidence_are_authenticated_before_any_parse(self):
        for root in (self.fixture.source / preparation.EVIDENCE_RELATIVE, self.fixture.checked):
            with self.subTest(root=root):
                path = root / "host-receipt.json"
                original = path.read_bytes()
                path.write_bytes(original.replace(b'"issue": 364', b'"issue": 365'))
                with mock.patch.object(preparation, "_read_json") as reader:
                    self.reject_without_source_change("evidence differs")
                    reader.assert_not_called()
                self.assertFalse(self.fixture.destination.exists())
                path.write_bytes(original)

    def test_changed_asset_bytes_fail_hash_check_without_readiness(self):
        path = self.fixture.source / self.fixture.asset_rows[0]["path"]
        raw = path.read_bytes()
        path.write_bytes(bytes([raw[0] ^ 1]) + raw[1:])
        self.reject_without_source_change("bytes differ from pinned copy identity")

    def test_changed_input_size_is_rejected_before_destination_creation(self):
        path = self.fixture.source / preparation.MAP_FILE
        path.write_bytes(path.read_bytes() + b"changed")
        self.reject_without_source_change("source size differs")
        self.assertFalse(self.fixture.destination.exists())

    def test_changed_project_configuration_is_rejected_before_copy(self):
        path = self.fixture.project / "Config/DefaultEngine.ini"
        raw = path.read_bytes()
        path.write_bytes(bytes([raw[0] ^ 1]) + raw[1:])
        self.reject_without_source_change("project configuration differs")
        self.assertFalse(self.fixture.destination.exists())

    def test_path_traversal_windows_aliases_and_startup_content_are_rejected(self):
        row = self.fixture.documents["session-preparation.json"]["source_dependencies"][0]
        original = row["path"]
        for relative in (
            "../outside.uasset", "Content/../outside.uasset", "Content//outside.uasset",
            "D:/outside.uasset", "Content\\outside.uasset", "Content/NUL.uasset",
            "Content/extra./outside.uasset", "Content/Python/init_unreal.py",
        ):
            with self.subTest(relative=relative):
                row["path"] = relative
                self.fixture.refresh_evidence()
                self.reject_without_source_change()
                self.assertFalse(self.fixture.destination.exists())
        row["path"] = original

    def test_duplicate_conflict_and_case_alias_are_rejected(self):
        duplicate = self.fixture.documents["session-preparation.json"]["consumer_assets"][1]
        duplicate["sha256"] = "0" * 64
        self.fixture.refresh_evidence()
        self.reject_without_source_change("conflicting duplicate")
        duplicate["sha256"] = self.fixture.asset_rows[0]["sha256"]
        duplicate["path"] = duplicate["path"].replace("Generated", "generated")
        self.fixture.refresh_evidence()
        self.reject_without_source_change("case-aliased duplicate")
        self.assertFalse(self.fixture.destination.exists())

    def test_existing_destination_is_never_reused(self):
        write(self.fixture.destination, "owner.txt", b"owner content")
        before = tree_bytes(self.fixture.destination)
        self.reject_without_source_change("existing destination")
        self.assertEqual(tree_bytes(self.fixture.destination), before)

    def test_destination_cannot_be_inside_either_source_root(self):
        for root in (self.fixture.source, self.fixture.project):
            with self.subTest(root=root):
                self.fixture.destination = root / "new-review"
                self.reject_without_source_change("must be isolated")
                self.assertFalse(self.fixture.destination.exists())

    def test_source_symlink_is_rejected_and_external_bytes_remain_untouched(self):
        source = self.fixture.source / self.fixture.asset_rows[0]["path"]
        outside = write(self.base, "outside.uasset", source.read_bytes())
        source.unlink()
        source.symlink_to(outside)
        outside_before = outside.read_bytes()
        self.reject_without_source_change("symlink/reparse")
        self.assertEqual(outside.read_bytes(), outside_before)
        self.assertTrue(source.is_symlink())
        self.assertFalse(self.fixture.destination.exists())

    def test_destination_parent_symlink_is_rejected(self):
        outside = self.base / "outside-directory"
        outside.mkdir()
        self.fixture.destination.parent.symlink_to(outside, target_is_directory=True)
        self.reject_without_source_change("symlink/reparse")
        self.assertEqual(list(outside.iterdir()), [])

    def test_windows_reparse_ancestor_is_rejected_before_copy(self):
        target = self.fixture.source / "Content"
        original_lstat = Path.lstat

        def reparse(path):
            value = original_lstat(path)
            if path == target:
                return SimpleNamespace(st_mode=value.st_mode, st_file_attributes=0x400)
            return value

        with mock.patch.object(Path, "lstat", reparse):
            self.reject_without_source_change("symlink/reparse")
        self.assertFalse(self.fixture.destination.exists())

    def test_invalid_binary_manifest_or_provenance_is_rejected(self):
        row = self.fixture.documents["host-receipt.json"]["binary_provenance"][0]
        row["original_identity"]["sha256"] = "0" * 64
        self.fixture.refresh_evidence()
        self.reject_without_source_change("binary provenance differs")
        row["original_identity"]["sha256"] = row["copied_identity"]["sha256"]
        relative = row["relative"]
        raw = json.dumps({"BuildId": "wrong", "Modules": preparation.MODULE_CLOSURES[relative]}).encode()
        write(self.fixture.source, relative, raw)
        row["original_identity"].update(identity(raw))
        row["copied_identity"].update(identity(raw))
        self.fixture.refresh_evidence()
        self.reject_without_source_change("module manifest closure/build identity")
        self.assertFalse(self.fixture.destination.exists())

    def test_checkpoint_status_and_map_hash_are_enforced(self):
        host = self.fixture.documents["saved-road-host-receipt.json"]
        host["fresh_reload_verified"] = False
        self.fixture.refresh_evidence()
        self.reject_without_source_change("saved consumer host proof")
        host["fresh_reload_verified"] = True
        self.fixture.map_sha256 = "0" * 64
        self.fixture.refresh_evidence()
        self.reject_without_source_change("review map is absent or differs")
        self.assertFalse(self.fixture.destination.exists())

    def test_bounded_identity_rejects_boolean_size_and_oversized_file(self):
        row = self.fixture.documents["session-preparation.json"]["source_dependencies"][0]
        for size in (True, preparation.FILE_LIMIT + 1):
            with self.subTest(size=size):
                row["size_bytes"] = size
                self.fixture.refresh_evidence()
                self.reject_without_source_change("invalid or unbounded")
                self.assertFalse(self.fixture.destination.exists())

    def test_five_gib_reserve_is_preserved_before_copy_and_during_copy(self):
        with mock.patch.object(preparation.shutil, "disk_usage", return_value=SimpleNamespace(
                free=preparation.MIN_FREE_BYTES)):
            self.reject_without_source_change("5 GiB")
        self.assertFalse(self.fixture.destination.exists())
        with mock.patch.object(preparation.shutil, "disk_usage", side_effect=[
            SimpleNamespace(free=20 * 1024 ** 3), SimpleNamespace(free=preparation.MIN_FREE_BYTES),
        ]):
            self.reject_without_source_change("reserve changed")
        self.assertEqual(list(self.fixture.destination.iterdir()), [])

    def test_source_mutation_between_preflight_and_copy_prevents_readiness(self):
        path = self.fixture.source / preparation.MAP_FILE
        before = path.read_bytes()
        original_copy = preparation._copy_verified
        changed = False

        def change_before_copy(row, destination):
            nonlocal changed
            if not changed:
                path.write_bytes(before + b"SYNTHETIC external concurrent writer")
                changed = True
            return original_copy(row, destination)

        with mock.patch.object(preparation, "_copy_verified", side_effect=change_before_copy):
            with self.assertRaisesRegex(ValueError, "source changed before copy"):
                self.fixture.prepare()
        self.assertEqual(path.read_bytes(), before + b"SYNTHETIC external concurrent writer")
        self.assertFalse((self.fixture.destination / preparation.RECEIPT_NAME).exists())

    def test_fixture_overrides_require_explicit_synthetic_mode(self):
        before = tree_bytes(self.fixture.source)
        with self.assertRaisesRegex(ValueError, "restricted to the pinned host/checkpoint"):
            self.fixture.prepare(synthetic=False)
        self.assertEqual(tree_bytes(self.fixture.source), before)
        self.assertFalse(self.fixture.destination.exists())


if __name__ == "__main__":
    unittest.main()
