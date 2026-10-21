"""Offline boundary tests; synthetic packages never claim Unreal/server proof."""

import copy
import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts.ci import export_lesson07_material_checkpoint as delivery


class CheckpointTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.host = self.root / "host"
        self.project = self.host / "project"
        self.source_sha = "a" * 40
        self.token = "987654321-1"
        for path in delivery.FULL_PATHS:
            target = self.project / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(delivery.PACKAGE_MAGIC + (path.encode() + b"\x00") * 8)
        self.patch(
            delivery,
            "MI_PIN",
            delivery.record(self.project / delivery.MI, package=True),
        )
        self.patch(
            delivery.shutil, "disk_usage", lambda _: SimpleNamespace(free=10 * 1024**3)
        )
        self.live = {
            "status": "SURFACE_REPAIR_SAVED_NATIVE_READBACK_PENDING_VISUAL",
            "saved": True,
            "failure_count": 0,
            "manifest_sha256": delivery.SURFACE_MANIFEST_SHA256,
            "classification_changed": False,
            "terrain_changed": False,
            "map_saved": False,
            "material_instance_changed": False,
            "normal_flatten_preserved": True,
            "changed_slots": [0, 3],
            "other_slots_preserved": [1, 2, 4],
            "grass_colour_preserved": True,
            "imported": {
                name: delivery.GAME
                + f"/Textures/SurfaceRepair_20261021/T_{name}.T_{name}"
                for name in delivery.TEXTURES
            },
            "saved_array_hashes": {
                key: delivery.digest(self.project / path)
                for key, path in delivery.ARRAYS.items()
            },
        }
        self.probe = {
            "status": "LESSON07_SURFACE_IMPORT_SAVED_IMAGES_REVIEW_PENDING",
            "source_commit": "b" * 40,
            "surface_import_verified": True,
            "identity_stable_across_probe": True,
            "client_exit_code": 0,
            "native_tool_call_attempts": 6,
            "native_tool_attempted": True,
            "native_tool_completed": True,
            "editor_started_or_stopped": False,
        }
        self.producer_token = "123456789-2"
        self.live_path = (
            self.project
            / f"Saved/RuntimeProof/Lesson07SurfaceRepair-20261021/{self.producer_token}/live-import.json"
        )
        self.probe_path = (
            self.host / f"lesson07-remote/reports/{self.producer_token}/probe.json"
        )
        self.pin = self.write_native()
        self.patch(delivery, "SURFACE_PRODUCER", self.pin)

    def patch(self, obj, name, value):
        handle = patch.object(obj, name, value)
        handle.start()
        self.addCleanup(handle.stop)

    def write_native(self):
        for path, value in ((self.live_path, self.live), (self.probe_path, self.probe)):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(delivery.json_bytes(value))
        return {
            "run_token": self.producer_token,
            "source_commit": self.probe["source_commit"],
            "live_import_sha256": delivery.digest(self.live_path),
            "live_import_bytes": self.live_path.stat().st_size,
            "probe_sha256": delivery.digest(self.probe_path),
            "probe_bytes": self.probe_path.stat().st_size,
        }

    def export(self, mode="full"):
        return delivery.export_checkpoint(self.host, mode, self.source_sha, self.token)

    def validate(self, result, mode="full"):
        return delivery.validate_bundle(
            Path(result["directory"]) / "checkpoint.zip",
            result["archive_sha256"],
            result["archive_bytes"],
            result["manifest_sha256"],
            mode,
            self.source_sha,
            self.token,
        )

    def test_full_export_preserves_sources_and_has_only_nine_packages_and_two_receipts(
        self,
    ):
        untouched = self.project / "Content/unrelated.uasset"
        untouched.parent.mkdir(exist_ok=True)
        untouched.write_bytes(b"owner work must not be exported")
        original = {
            path: (self.project / path).read_bytes() for path in delivery.FULL_PATHS
        }
        result = self.export()
        manifest = self.validate(result)
        self.assertEqual(9, result["asset_count"])
        self.assertFalse(result["branch_integrated"])
        self.assertEqual(
            list(delivery.FULL_PATHS), [row["path"] for row in manifest["assets"]]
        )
        with zipfile.ZipFile(Path(result["directory"]) / "checkpoint.zip") as bundle:
            self.assertEqual(
                set(delivery.FULL_PATHS)
                | {"manifest.json", "evidence/probe.json", "evidence/live-import.json"},
                set(bundle.namelist()),
            )
            for path, data in original.items():
                self.assertEqual(data, bundle.read(path))
                self.assertEqual(data, (self.project / path).read_bytes())
        self.assertEqual(b"owner work must not be exported", untouched.read_bytes())
        self.assertFalse((self.project / ".git").exists())

    def test_mi_only_is_explicit_and_does_not_require_or_export_surface_evidence(self):
        self.patch(delivery, "SURFACE_PRODUCER", None)
        self.live_path.write_bytes(b"failed native operation")
        result = self.export("mi-only")
        manifest = self.validate(result, "mi-only")
        self.assertEqual(1, result["asset_count"])
        self.assertEqual({}, manifest["evidence"])
        self.assertIsNone(manifest["surface_producer"])
        with zipfile.ZipFile(Path(result["directory"]) / "checkpoint.zip") as bundle:
            self.assertEqual({delivery.MI, "manifest.json"}, set(bundle.namelist()))

    def test_full_mode_has_no_implicit_mi_fallback_when_producer_is_pending(self):
        self.patch(delivery, "SURFACE_PRODUCER", None)
        with self.assertRaisesRegex(ValueError, "producer pins are pending"):
            self.export()
        self.assertFalse((self.host / delivery.EXPORT_RELATIVE).exists())

    def test_failed_native_receipt_is_rejected_even_if_its_bytes_are_pinned(self):
        self.live["saved"] = False
        self.patch(delivery, "SURFACE_PRODUCER", self.write_native())
        with self.assertRaisesRegex(ValueError, "Native import success"):
            self.export()

    def test_incomplete_or_different_source_probe_is_rejected(self):
        self.probe["native_tool_call_attempts"] = 1
        self.patch(delivery, "SURFACE_PRODUCER", self.write_native())
        with self.assertRaisesRegex(ValueError, "producer probe"):
            self.export()

    def test_changed_native_receipt_or_array_is_not_accepted(self):
        self.live_path.write_bytes(self.live_path.read_bytes() + b" ")
        with self.assertRaisesRegex(ValueError, "receipt bytes"):
            self.export()
        self.write_native()
        array = self.project / delivery.ARRAYS["Normal"]
        array.write_bytes(array.read_bytes() + b"later owner save")
        with self.assertRaisesRegex(ValueError, "Array differs"):
            self.export()

    def test_mi_pin_and_hydrated_package_magic_are_required(self):
        mi = self.project / delivery.MI
        mi.write_bytes(mi.read_bytes() + b"unreviewed scalar change")
        with self.assertRaisesRegex(ValueError, "Macro checkpoint differs"):
            self.export("mi-only")
        mi.write_text(delivery.pointer(delivery.MI_PIN))
        with self.assertRaisesRegex(ValueError, "hydrated Unreal"):
            self.export("mi-only")

    def test_sidecar_and_redirected_source_are_rejected(self):
        mi = self.project / delivery.MI
        sidecar = mi.with_suffix(".ubulk")
        sidecar.write_bytes(b"external bulk payload")
        with self.assertRaisesRegex(ValueError, "sidecar"):
            self.export("mi-only")
        sidecar.unlink()
        original = self.root / "owner-original.uasset"
        mi.rename(original)
        mi.symlink_to(original)
        with self.assertRaisesRegex(ValueError, "redirected path"):
            self.export("mi-only")
        self.assertTrue(original.exists())

    def test_disk_reserve_and_existing_destination_do_not_overwrite(self):
        with patch.object(
            delivery.shutil,
            "disk_usage",
            return_value=SimpleNamespace(free=delivery.RESERVE_BYTES),
        ):
            with self.assertRaisesRegex(ValueError, "disk reserve"):
                self.export("mi-only")
        result = self.export("mi-only")
        archive = Path(result["directory"]) / "checkpoint.zip"
        before = archive.read_bytes()
        with self.assertRaisesRegex(ValueError, "never overwrite"):
            self.export("mi-only")
        self.assertEqual(before, archive.read_bytes())

    def test_mutation_during_copy_never_emits_complete_export_receipt(self):
        copyfileobj = shutil.copyfileobj
        mi = self.project / delivery.MI

        def change_after_copy(source, target, length):
            copyfileobj(source, target, length)
            mi.write_bytes(mi.read_bytes() + b"concurrent owner save")

        with patch.object(
            delivery.shutil, "copyfileobj", side_effect=change_after_copy
        ):
            with self.assertRaisesRegex(ValueError, "changed during export copy"):
                self.export("mi-only")
        self.assertFalse(
            (
                self.host
                / delivery.EXPORT_RELATIVE
                / self.token
                / "export-receipt.json"
            ).exists()
        )

    def test_archive_tampering_and_extra_paths_are_rejected(self):
        result = self.export("mi-only")
        archive = Path(result["directory"]) / "checkpoint.zip"
        archive.write_bytes(archive.read_bytes() + b"changed after transfer")
        with self.assertRaisesRegex(ValueError, "archive identity"):
            self.validate(result, "mi-only")
        with zipfile.ZipFile(archive, "a") as bundle:
            bundle.writestr("../unapproved.uasset", delivery.PACKAGE_MAGIC)
        result.update(
            archive_sha256=delivery.digest(archive),
            archive_bytes=archive.stat().st_size,
        )
        with self.assertRaisesRegex(ValueError, "unapproved paths"):
            self.validate(result, "mi-only")

    def test_explicit_marker_admission_checks_owner_branch_source_and_exclusivity(self):
        event = {
            "repository": {"full_name": delivery.REPOSITORY},
            "sender": {"login": "karnalooch"},
            "ref": "refs/heads/" + delivery.BRANCH,
            "after": self.source_sha,
            "head_commit": {"message": "retain approved checkpoint [l07-export-macro]"},
        }
        path = self.root / "event.json"
        path.write_bytes(delivery.json_bytes(event))
        self.assertEqual("mi-only", delivery.admit_event(path, self.source_sha))
        for key, value in (
            ("sender", {"login": "another-user"}),
            ("ref", "refs/heads/main"),
            ("after", "c" * 40),
            ("head_commit", {"message": "[l07-export-macro] [l07-export-materials]"}),
        ):
            changed = copy.deepcopy(event)
            changed[key] = value
            path.write_bytes(delivery.json_bytes(changed))
            with self.assertRaises(ValueError):
                delivery.admit_event(path, self.source_sha)

    def test_duplicate_json_and_invalid_run_tokens_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "Duplicate JSON"):
            delivery.parse_json(b'{"saved":true,"saved":false}')
        for token in ("../123-1", "123-0", "123-1/child", "123-1\n"):
            with self.assertRaises(ValueError):
                delivery.checked_token(token)

    def test_real_git_lfs_staging_emits_only_exact_pointers_without_remote_operations(
        self,
    ):
        repo = self.root / "isolated-publication"
        repo.mkdir()
        subprocess.run(
            ["git", "init", "--initial-branch=fixture"],
            cwd=repo,
            check=True,
            capture_output=True,
        )
        (repo / ".gitattributes").write_text(
            "*.uasset filter=lfs diff=lfs merge=lfs -text\n"
        )
        for path, pin in [(delivery.MI, delivery.MI_BRANCH_PIN)] + [
            (delivery.ARRAYS[name], pin) for name, pin in delivery.ARRAY_PINS.items()
        ]:
            target = repo / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(delivery.pointer(pin))
        delivery.git(
            repo, "add", "--", ".gitattributes", delivery.MI, *delivery.ARRAYS.values()
        )
        delivery.git(repo, "commit", "-m", "Synthetic baseline pointers")
        self.source_sha = delivery.git(repo, "rev-parse", "HEAD")
        result = self.export()
        manifest = self.validate(result)
        local_commit = delivery.stage_lfs(
            repo, Path(result["directory"]) / "checkpoint.zip", manifest
        )
        self.assertEqual(40, len(local_commit))
        self.assertEqual(self.source_sha, delivery.git(repo, "rev-parse", "HEAD"))
        self.assertEqual(
            set(delivery.FULL_PATHS),
            set(delivery.git(repo, "diff", "--cached", "--name-only").splitlines()),
        )
        for row in manifest["assets"]:
            self.assertEqual(
                delivery.pointer(row).strip(),
                delivery.git(repo, "show", ":" + row["path"]),
            )
        # This is a local fixture for byte verification, not a server readback.
        storage = repo / ".git/lfs"
        delivery.verify_server_objects(storage, manifest["assets"])
        row = manifest["assets"][0]
        oid = row["sha256"]
        (storage / "objects" / oid[:2] / oid[2:4] / oid).write_bytes(
            delivery.PACKAGE_MAGIC + b"corruption"
        )
        with self.assertRaisesRegex(ValueError, "server LFS bytes differ"):
            delivery.verify_server_objects(storage, manifest["assets"])

    def test_workflow_keeps_write_permission_in_hosted_upload_and_uses_host_arbitration(
        self,
    ):
        workflow = (
            Path(__file__).resolve().parents[2]
            / ".github/workflows/lesson07-material-delivery.yml"
        ).read_text()
        export_job = workflow.split("  export:\n", 1)[1].split("  upload_lfs:\n", 1)[0]
        upload_job = workflow.split("  upload_lfs:\n", 1)[1]
        self.assertEqual(1, workflow.count("contents: write"))
        self.assertNotIn("contents: write", export_job)
        self.assertIn("group: yacs-unreal-ci-${{ github.repository }}", export_job)
        self.assertIn("runs-on: ubuntu-latest", upload_job)
        self.assertIn("contents: write", upload_job)
        self.assertNotIn("git push", workflow)
        self.assertNotIn("workflow_dispatch:", workflow)
        self.assertNotIn("Remove-Item", workflow)
        self.assertNotIn("Stop-Process", workflow)


if __name__ == "__main__":
    unittest.main()
