"""Retained candidate installation must preserve owner files and proof bytes."""

from __future__ import annotations

import contextlib
import copy
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.assets import install_sa_calobra_whole_map_prep as installer
from scripts.ue import sa_calobra_whole_map_prep as prep


def sha(payload):
    return hashlib.sha256(payload).hexdigest()


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.proof, self.project = self.root / "proof", self.root / "project"
        self.proof.mkdir()
        self.project.mkdir()
        (self.project / "YetAnotherCyclingSim.uproject").write_text(
            '{"FileVersion":3}', encoding="utf-8"
        )
        self.head = "b" * 40
        names = (
            "material-weights.png",
            "sample-availability.png",
            "inference-kind.png",
            "exclusion-reasons.tif",
            "exclusion-reasons.png",
            "source-material-input-manifest.json",
            "source-placement-manifest.json",
            "component230-triangle-bands.json",
            "sector-coverage.json",
        )
        bundle = self.proof / "whole-map-prep"
        bundle.mkdir()
        outputs = []
        for name in names:
            data = ("fixture " + name).encode()
            (bundle / name).write_bytes(data)
            outputs.append({"path": name, "sha256": sha(data), "size_bytes": len(data)})
        for name, key in (
            ("material-weights.png", "WEIGHTS_SHA"),
            ("sample-availability.png", "AVAILABILITY_SHA"),
            ("inference-kind.png", "INFERENCE_SHA"),
            ("exclusion-reasons.tif", "EXCLUSIONS_SHA"),
        ):
            value = next(row["sha256"] for row in outputs if row["path"] == name)
            stub = patch.object(prep, key, value)
            stub.start()
            self.addCleanup(stub.stop)
        producer = (
            prep.ROOT / "scripts/assets/prepare_sa_calobra_whole_map_surface_prep.py"
        )
        material_recipe = {"material_formula": prep.FORMULA}
        manifest = {
            "status": "WHOLE_MAP_MATERIAL_PREPARATION_CANDIDATE",
            "geometry_mutation": False,
            "current_cover_admitted": False,
            "expected_landscape_component_count": 1024,
            "grid": prep.GRID,
            "world_mapping": prep.WORLD_MAPPING,
            "coverage": {"cells": 4033 * 4033},
            "recipe": material_recipe,
            "recipe_sha256": sha(prep.canonical(material_recipe)),
            "producer_file": producer.relative_to(prep.ROOT).as_posix(),
            "producer_sha256_lf": sha(producer.read_bytes().replace(b"\r\n", b"\n")),
            "outputs": outputs,
            "sources": {row["path"]: row for row in outputs},
        }
        manifest["fingerprint"] = sha(prep.canonical(manifest))
        self.write("whole-map-prep/surface-prep-manifest.json", manifest)
        self.manifest_sha = sha((bundle / "surface-prep-manifest.json").read_bytes())
        self.payloads, generated, retained = {}, [], []
        for asset in installer.ASSETS:
            stem = "Content/" + asset.removeprefix("/Game/")
            suffixes = (
                (".uasset", ".ubulk", ".uexp")
                if asset.endswith("T_WholeMapWeights")
                else (".uasset",)
            )
            members = []
            for suffix in suffixes:
                name = stem + suffix
                data = ("native package fixture " + name).encode()
                source = "generated-assets/" + Path(name).name
                path = self.proof / source
                path.parent.mkdir(exist_ok=True)
                path.write_bytes(data)
                row = {"file": name, "sha256": sha(data), "size_bytes": len(data)}
                members.append(row)
                retained.append(
                    {
                        "path": source,
                        "source_file": name,
                        "asset": asset,
                        "sha256": row["sha256"],
                        "size_bytes": len(data),
                    }
                )
                self.payloads[name] = data
            generated.append(dict(members[0], asset=asset, package_files=members))
        recipe = prep.rendering_recipe()
        self.master = {
            "schema_version": 1,
            "status": "WHOLE_MAP_FIXED_MASTER_SAVED",
            "exact_sha": self.head,
            "master": prep.MASTER_PATH,
            "instance": prep.INSTANCE_PATH,
            "map_saved": False,
            "geometry_changed": False,
            "prep_manifest_sha256": self.manifest_sha,
            "rendering_recipe": recipe,
            "rendering_recipe_sha256": sha(prep.canonical(recipe)),
            "generated_assets": generated,
        }
        self.retained = {
            "schema_version": 1,
            "status": "GENERATED_MATERIAL_PACKAGES_RETAINED",
            "exact_sha": self.head,
            "files": retained,
            "source_preserved": True,
            "destination_verified": True,
        }
        self.native = {
            "status": "WHOLE_MAP_EVIDENCE_VERIFIED",
            "exact_sha": self.head,
            "surface_manifest_sha256": self.manifest_sha,
            "surface_manifest_fingerprint": manifest["fingerprint"],
            "component_count": 1024,
            "primary_frame_count": 43,
            "native_trial_applied": False,
        }
        self.capture = {
            "status": "WHOLE_MAP_PREPARATION_PASS",
            "exact_sha": self.head,
            "capture_complete": True,
            "fresh_process_master_verified": True,
            "prep_manifest_sha256": self.manifest_sha,
            "error": None,
        }
        self.cleanup = {
            "status": "PASS",
            "exact_sha": self.head,
            "tracked_checkout_unchanged": True,
            "retained_source_unchanged": True,
            "prepared_bundle_unchanged": True,
            "errors": [],
        }
        self.publish_receipts()

    def write(self, name, value):
        path = self.proof / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((json.dumps(value, indent=2) + "\n").encode())

    def publish_receipts(self):
        self.write("whole-map-master-receipt.json", self.master)
        digest = sha((self.proof / "whole-map-master-receipt.json").read_bytes())
        self.retained["master_receipt_sha256"] = digest
        self.capture["master_receipt_sha256"] = digest
        self.write("generated-assets-verification.json", self.retained)
        self.write("capture/whole-map-prep/whole-map-prep-receipt.json", self.capture)
        self.write("native-proof-verification.json", self.native)
        self.write("checkout-restoration.json", self.cleanup)

    def run_install(self, apply=False):
        return installer.install(self.proof, project=self.project, apply=apply)

    def assert_nothing_installed(self):
        self.assertFalse((self.project / "Content").exists())

    def test_dry_run_verifies_every_source_without_creating_content(self):
        before = {
            p.relative_to(self.proof): p.read_bytes()
            for p in self.proof.rglob("*")
            if p.is_file()
        }
        report = self.run_install()
        self.assertEqual(report["status"], "WHOLE_MAP_PREP_INSTALL_DRY_RUN")
        self.assertEqual(report["package_count"], 3)
        self.assertEqual(report["member_count"], 5)
        self.assertEqual(set(report["missing"]), set(self.payloads))
        self.assertEqual(report["restored"], 0)
        self.assertFalse(report["map_saved"])
        self.assertFalse(report["transient_v8_reconstructed"])
        self.assert_nothing_installed()
        self.assertEqual(
            before,
            {
                p.relative_to(self.proof): p.read_bytes()
                for p in self.proof.rglob("*")
                if p.is_file()
            },
        )

    def test_apply_includes_all_sidecars_and_identical_repeat_is_idempotent(self):
        report = self.run_install(True)
        self.assertEqual(report["restored"], 5)
        before = {}
        for name, payload in self.payloads.items():
            path = self.project / name
            self.assertEqual(path.read_bytes(), payload)
            before[name] = path.stat().st_mtime_ns
        repeated = self.run_install(True)
        self.assertEqual(repeated["restored"], 0)
        self.assertEqual(repeated["existing_verified"], 5)
        self.assertEqual(repeated["missing"], [])
        self.assertEqual(
            before,
            {name: (self.project / name).stat().st_mtime_ns for name in self.payloads},
        )

    def test_corrupt_last_source_fails_before_any_destination_write(self):
        source = self.proof / self.retained["files"][-1]["path"]
        payload = source.read_bytes()
        source.write_bytes(b"X" + payload[1:])
        with self.assertRaisesRegex(ValueError, "content mismatch"):
            self.run_install(True)
        self.assert_nothing_installed()

    def test_source_size_mismatch_is_rejected_before_hashing_payload(self):
        source = self.proof / self.retained["files"][0]["path"]
        source.write_bytes(b"wrong size")
        with patch.object(installer, "verify") as verify:
            with self.assertRaisesRegex(ValueError, "content mismatch"):
                self.run_install(True)
            verify.assert_not_called()
        self.assert_nothing_installed()

    def test_missing_or_unrecorded_source_sidecar_is_rejected(self):
        extra = self.proof / "generated-assets/T_WholeMapWeights.uptnl"
        extra.write_bytes(b"unrecorded")
        with self.assertRaisesRegex(ValueError, "Unrecorded file"):
            self.run_install(True)
        extra.unlink()
        (self.proof / self.retained["files"][-1]["path"]).unlink()
        with self.assertRaisesRegex(ValueError, "member is missing"):
            self.run_install(True)
        self.assert_nothing_installed()

    def test_existing_differing_owner_file_is_never_replaced(self):
        name = next(name for name in self.payloads if name.endswith(".ubulk"))
        owner = self.project / name
        owner.parent.mkdir(parents=True)
        owner.write_bytes(b"owner changes")
        with self.assertRaisesRegex(ValueError, "content mismatch"):
            self.run_install(True)
        self.assertEqual(owner.read_bytes(), b"owner changes")
        self.assertEqual([p for p in owner.parent.iterdir()], [owner])

    def test_unknown_existing_sidecar_fails_without_touching_owner_bytes(self):
        primary = next(
            name for name in self.payloads if name.endswith("Weights.uasset")
        )
        owner = (self.project / primary).with_suffix(".uptnl")
        owner.parent.mkdir(parents=True)
        owner.write_bytes(b"unrecorded owner bulk")
        with self.assertRaisesRegex(ValueError, "existing package sidecar"):
            self.run_install(True)
        self.assertEqual([p for p in owner.parent.iterdir()], [owner])

    def test_relative_absolute_and_windows_paths_cannot_escape_either_side(self):
        original = copy.deepcopy(self.retained)
        for field in ("path", "source_file"):
            for name in (
                "../outside",
                "/outside",
                "D:/runner/Content/file.uasset",
                "Content\\file.uasset",
            ):
                with self.subTest(field=field, name=name):
                    self.retained = copy.deepcopy(original)
                    self.retained["files"][0][field] = name
                    self.publish_receipts()
                    with self.assertRaisesRegex(ValueError, "Unsafe"):
                        self.run_install(True)
        self.assert_nothing_installed()

    def test_generated_member_path_cannot_leave_its_fixed_family(self):
        self.master["generated_assets"][0]["package_files"][0]["file"] = (
            "Content/Worlds/SaCalobra/Unrelated.uasset"
        )
        self.publish_receipts()
        with self.assertRaisesRegex(ValueError, "outside the fixed package family"):
            self.run_install(True)
        self.assert_nothing_installed()

    def test_duplicate_targets_and_missing_primary_fail_before_restore(self):
        self.retained["files"][-1] = copy.deepcopy(self.retained["files"][0])
        self.publish_receipts()
        with self.assertRaisesRegex(ValueError, "Duplicate retained"):
            self.run_install(True)
        self.master["generated_assets"][-1]["package_files"] = self.master[
            "generated_assets"
        ][-1]["package_files"][1:]
        self.publish_receipts()
        with self.assertRaisesRegex(ValueError, "primary identity"):
            self.run_install(True)
        self.assert_nothing_installed()

    def test_master_hash_current_recipe_and_prepared_bytes_are_bound(self):
        self.master["rendering_recipe"]["scalar_defaults"]["NearDetailStartCm"] += 1
        self.write("whole-map-master-receipt.json", self.master)
        with self.assertRaisesRegex(ValueError, "receipt is stale"):
            self.run_install(True)
        self.publish_receipts()
        with self.assertRaisesRegex(ValueError, "rendering recipe"):
            self.run_install(True)
        self.master["rendering_recipe"] = prep.rendering_recipe()
        self.publish_receipts()
        (self.proof / "whole-map-prep/sector-coverage.json").write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "Preparation input changed"):
            self.run_install(True)
        self.assert_nothing_installed()

    def test_failed_stale_or_unrestored_native_evidence_is_not_installed(self):
        for record, key, value, expected in (
            (self.native, "status", "FAILED", "native preparation"),
            (self.capture, "exact_sha", "c" * 40, "native preparation"),
            (self.cleanup, "prepared_bundle_unchanged", False, "conservation"),
        ):
            with self.subTest(key=key):
                old = record[key]
                record[key] = value
                self.publish_receipts()
                with self.assertRaisesRegex(ValueError, expected):
                    self.run_install(True)
                record[key] = old
        self.assert_nothing_installed()

    def test_source_and_destination_symlink_escapes_fail(self):
        outside = self.root / "outside"
        outside.mkdir()
        source = self.proof / self.retained["files"][0]["path"]
        payload = source.read_bytes()
        target = outside / "payload"
        target.write_bytes(payload)
        source.unlink()
        try:
            source.symlink_to(target)
        except OSError as error:
            self.skipTest("Symlink creation is unavailable: " + str(error))
        with self.assertRaisesRegex(ValueError, "escapes"):
            self.run_install(True)
        source.unlink()
        source.write_bytes(payload)
        (self.project / "Content").symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "escapes"):
            self.run_install(True)
        self.assertEqual(list(outside.iterdir()), [target])

    def test_workspace_config_resolves_destination_and_rejects_escape(self):
        config = {"schema_version": 1, "project": "project"}
        config.update({name: name for name in ("data", "cache", "checkpoints", "work")})
        path = self.root / "workspace.json"
        path.write_text(json.dumps(config), encoding="utf-8")
        result = installer.install(self.proof, workspace_config=path)
        self.assertEqual(result["project"], str(self.project.resolve()))
        config["project"] = "../outside-project"
        path.write_text(json.dumps(config), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "must remain below"):
            installer.install(self.proof, workspace_config=path)
        with self.assertRaisesRegex(ValueError, "exactly one"):
            installer.install(self.proof, project=self.project, workspace_config=path)
        self.assert_nothing_installed()

    def test_cli_defaults_to_read_only_and_requires_explicit_destination(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            status = installer.main(
                ["--proof-root", str(self.proof), "--project", str(self.project)]
            )
        self.assertEqual(status, 0)
        self.assertFalse(json.loads(output.getvalue())["applied"])
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            installer.main(["--proof-root", str(self.proof)])
        self.assert_nothing_installed()


if __name__ == "__main__":
    unittest.main()
