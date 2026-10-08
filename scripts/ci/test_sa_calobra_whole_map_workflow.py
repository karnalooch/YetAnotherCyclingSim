"""Whole-map routing, native coverage and evidence tamper rejection."""

from __future__ import annotations

import copy
import json
import math
import re
import shutil
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

from scripts.ci import sa_calobra_whole_map_workflow as workflow
from scripts.ci.test_sa_calobra_detail_native_workflow import WORKFLOW, enabled, jobs


class WholeMapWorkflowRoutingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.jobs = jobs()
        cls.job = cls.jobs["wholemap-material"]

    def test_owner_marker_selects_only_whole_map_work(self):
        self.assertEqual(
            [
                name
                for name, job in self.jobs.items()
                if enabled(job, message="[wholemap-material]")
            ],
            ["wholemap-material"],
        )
        self.assertIn("runs-on: [self-hosted, yacs-ue58]", self.job)

    def test_wrong_actor_repository_branch_or_event_cannot_start(self):
        for key, value in (
            ("github.actor", "contributor"),
            ("github.repository", "fork/YetAnotherCyclingSim"),
            ("github.ref", "refs/heads/main"),
            ("github.event_name", "workflow_dispatch"),
        ):
            with self.subTest(key=key):
                self.assertFalse(
                    enabled(self.job, message="[wholemap-material]", **{key: value})
                )
        self.assertFalse(enabled(self.job, message="ordinary maintenance"))

    def test_every_mixed_marker_is_rejected_without_starting_legacy_jobs(self):
        for other in (
            "[detail-pilot]",
            "[detail-native]",
            "[tpp-survey]",
            "[tpp-retain]",
            "[tpp-docs]",
        ):
            with self.subTest(other=other):
                self.assertEqual(
                    [
                        name
                        for name, job in self.jobs.items()
                        if enabled(job, message="[wholemap-material] " + other)
                    ],
                    [],
                )

    def test_verified_cache_never_borrows_a_fresh_material_pass(self):
        ordered = (
            "Select persistent Unreal cache before isolated cleanup",
            "Retain previous owner-handoff LFS payloads before sanitization",
            "Sanitize tracked workspace while preserving verified build outputs",
            "Resolve immutable whole-map inputs in the configured workspace",
            "Hydrate only the frozen scene and full-grid material inputs",
            "Test preparation boundaries and prepare all immutable source bundles",
            "Verify installed exact-version material and Landscape API source",
            "Fingerprint the exact compile and Automation inputs",
            "Resolve verified Unreal execution mode",
            "Prepare fixed master then capture the entire native working map",
            "Verify complete native inventory and fresh capture provenance",
            "Verify unchanged map checkout and all retained source bytes",
        )
        positions = [self.job.index(name) for name in ordered]
        self.assertEqual(positions, sorted(positions))
        self.assertEqual(self.job.count("./scripts/ci/Invoke-YacsUnrealCi.ps1 "), 1)
        self.assertIn("$parameters.SkipBuild = $true", self.job)
        record = self.job.split(
            "Record and publish only this job's successful non-static proof", 1
        )[1].split("      - name:", 1)[0]
        self.assertIn("steps.cache.outputs.mode != 'static'", record)
        self.assertIn("-Action Record", record)
        self.assertIn("unreal_ci_workspace publish", record)
        capture = self.job.split(
            "Prepare fixed master then capture the entire native working map", 1
        )[1].split("      - name:", 1)[0]
        self.assertNotIn("if: ${{", capture)
        self.assertEqual(
            capture.count("Start-Process -FilePath $engine.UnrealEditorPath"), 1
        )
        self.assertIn("name = 'master'", capture)
        self.assertIn("name = 'capture'", capture)
        self.assertIn("retain-master", capture)
        for forbidden in (
            "Bootstrap-YacsPcgEx",
            "Invoke-YacsSaCalobraPcgExCliff.ps1",
            "workflow_dispatch",
            "YACS_SA_CALOBRA_TPP_SURVEY = '1'",
            "git push",
            "contents: write",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, self.job)

    def test_provenance_and_persistent_inputs_are_explicit(self):
        for requirement in (
            "load_workspace",
            "$workspace.data 'world-data/sa-calobra-working-v1/pcg-masks-v1-2026-10-04'",
            "--placement-inputs $env:YACS_WHOLE_MAP_PLACEMENT",
            "--placement $env:YACS_WHOLE_MAP_PLACEMENT",
            "ref: ${{ github.sha }}",
            "ExpectedBranch = 'HEAD'",
            "--exact-sha $env:GITHUB_SHA",
            "YACS_DETAIL_NATIVE",
            "5.8.2-56702186",
            "MaterialExpressionCameraPositionWS.h",
            "Engine/Content/Maps/Entry.umap",
            "'/Engine/Maps/Entry'",
        ):
            with self.subTest(requirement=requirement):
                self.assertIn(requirement, self.job)
        self.assertNotIn("D:\\yacs\\project", self.job)
        self.assertNotIn("Content/**", self.job)
        self.assertNotIn("yacs-unreal-ci-${{ github.repository }}", self.job)

    def test_compact_retention_includes_reusable_packages_and_failure_logs(self):
        upload = self.job.split(
            "Upload compact whole-map renders and independently verified receipts", 1
        )[1]
        for required in (
            "/whole-map-prep/",
            "/generated-assets/",
            "/capture/whole-map-prep/frames/",
            "/capture/whole-map-prep/*.json",
            "/capture-readiness.json",
            "/whole-map-*.log",
            "/build-automation/",
            "retention-days: 90",
        ):
            self.assertIn(required, upload)
        for omitted in (
            "/native-input/",
            "/priming/",
            ".zip",
            "/Content/",
            "YACS_UNREAL_WORKTREE",
        ):
            self.assertNotIn(omitted, upload)
        text = WORKFLOW.read_text(encoding="utf-8")
        for path in (
            "scripts/ci/sa_calobra_whole_map_workflow.py",
            "scripts/ci/test_sa_calobra_whole_map_workflow.py",
            "scripts/assets/prepare_sa_calobra_whole_map_surface_prep.py",
            "scripts/ue/build_sa_calobra_whole_map_master.py",
            "scripts/ue/sa_calobra_whole_map_prep.py",
            "scripts/ue/capture_sa_calobra_whole_map_prep.py",
        ):
            self.assertIn('"' + path + '"', text.split("permissions:", 1)[0])

    @unittest.skipUnless(
        shutil.which("pwsh"), "PowerShell 7 is verified by hosted and native CI"
    )
    def test_every_embedded_powershell_step_parses_before_editor_work(self):
        scripts = re.findall(
            r"        run: \|\n(.*?)(?=\n      - name:|\Z)", self.job, flags=re.DOTALL
        )
        for index, source in enumerate(scripts):
            with self.subTest(step=index):
                result = subprocess.run(
                    [
                        shutil.which("pwsh"),
                        "-NoProfile",
                        "-NonInteractive",
                        "-Command",
                        "$tokens=$null; $errors=$null; [void][System.Management.Automation.Language.Parser]::ParseInput([Console]::In.ReadToEnd(), [ref]$tokens, [ref]$errors); if ($errors.Count -gt 0) { $errors | Out-String | Write-Output; exit 1 }",
                    ],
                    input=textwrap.dedent(source),
                    text=True,
                    capture_output=True,
                    timeout=30,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class WholeMapNativeBindingTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.rows = [
            {
                "component": "/Game/Worlds/SaCalobra/L_SaCalobraAccepted_20261004.Landscape.LandscapeComponent_"
                + str(index),
                "expected_material": workflow.object_path(workflow.MASTER),
                "assigned_instance": workflow.object_path(workflow.INSTANCE),
                "all_instances_match": True,
                "override_is_none": True,
                "MaterialInstances": 1,
                "MaterialInstancesDynamic": 0,
                "render_instance_count": 1,
            }
            for index in range(1024)
        ]
        self.summary = {
            "status": "ALL_NATIVE_ROOTS_MATCH",
            "component_count": 1024,
            "expected_component_count": 1024,
            "includes_hidden_component230": True,
            "verified_again_after_captures": True,
            "expected_root_material": workflow.object_path(workflow.MASTER),
            "assigned_instance": workflow.object_path(workflow.INSTANCE),
            "file": "landscape-material-bindings.json",
        }

    def write(self):
        path = self.root / self.summary["file"]
        path.write_bytes(json.dumps(self.rows).encode())
        self.summary["sha256"] = workflow.file_row(path)["sha256"]

    def test_all_native_parent_chains_include_the_hidden_source_component(self):
        self.write()
        self.assertEqual(
            len(workflow.verify_material_bindings(self.root, self.summary)), 1024
        )

    def test_partial_duplicate_and_missing_hidden_component_are_rejected(self):
        original = copy.deepcopy(self.rows)
        for variant in ("partial", "duplicate", "hidden"):
            with self.subTest(variant=variant):
                self.rows = copy.deepcopy(original)
                if variant == "partial":
                    self.rows.pop()
                elif variant == "duplicate":
                    self.rows[1] = copy.deepcopy(self.rows[0])
                else:
                    self.rows[230]["component"] += "_substitute"
                self.write()
                with self.assertRaises(ValueError):
                    workflow.verify_material_bindings(self.root, self.summary)

    def test_one_false_parent_fallback_or_unrendered_instance_rejects_whole_grid(self):
        original = copy.deepcopy(self.rows)
        variants = (
            ("all_instances_match", False),
            ("override_is_none", False),
            ("expected_material", workflow.object_path(workflow.INSTANCE)),
            ("assigned_instance", "/Engine/DefaultMaterials/DefaultMaterial"),
            ("render_instance_count", 0),
            ("MaterialInstances", 0),
            ("MaterialInstancesDynamic", 1),
            ("MaterialInstances", True),
            ("render_instance_count", math.inf),
        )
        for key, value in variants:
            with self.subTest(key=key, value=value):
                self.rows = copy.deepcopy(original)
                self.rows[230][key] = value
                self.write()
                with self.assertRaises(ValueError):
                    workflow.verify_material_bindings(self.root, self.summary)

    def test_post_capture_binding_file_replacement_fails_its_hash(self):
        self.write()
        (self.root / self.summary["file"]).write_bytes(b"[]")
        with self.assertRaisesRegex(ValueError, "hash changed"):
            workflow.verify_material_bindings(self.root, self.summary)

    def test_post_capture_inventory_and_final_reaudit_are_mandatory(self):
        self.write()
        for key in ("verified_again_after_captures", "includes_hidden_component230"):
            with self.subTest(key=key):
                summary = dict(self.summary, **{key: False})
                with self.assertRaises(ValueError):
                    workflow.verify_material_bindings(self.root, summary)


class WholeMapCaptureCoverageTests(unittest.TestCase):
    def setUp(self):
        self.pilot = json.loads(
            (workflow.ROOT / workflow.PILOT / "pilot/manifest.json").read_text()
        )
        self.poses = {
            row["frame_id"]: {key: row[key] for key in ("camera", "target", "fov")}
            for row in self.pilot["frames"]
        }
        for x, x_cm in enumerate((25000, 100000, 175000)):
            for y, y_cm in enumerate((25000, 100000, 175000)):
                self.poses[f"ground-{x}-{y}"] = {
                    "camera": [x_cm - 3000, y_cm - 4000, 42000],
                    "target": [x_cm, y_cm, 40000],
                    "fov": 60.0,
                }
        for index, name in enumerate(
            ("dominant-wall", "overview-north", "overview-south")
        ):
            self.poses[name] = {
                "camera": [50000 * (index + 1), 20000, 80000],
                "target": [100000, 100000, 50000],
                "fov": 58.0,
            }
        seam = [44100.0, 47250.0, 40000.0]
        for name, scale in (("seam-close", 1), ("seam-distant", 8)):
            self.poses[name] = {
                "camera": [
                    value + scale * offset
                    for value, offset in zip(seam, (1800, 1200, 1400))
                ],
                "target": seam[:],
                "fov": 60.0,
            }
        self.report = {
            "capture_plan": [],
            "captures": [],
            "source_scene": {
                "seam_probe": {
                    "target_cm": seam[:],
                    "original_source_delta_cm": 0.0,
                    "defect_admitted": False,
                    "boundary_xy_cm": [37800, 44100, 44100, 50400],
                }
            },
        }
        for name, mode in workflow.CAPTURE_PAIRS:
            pose = self.poses[name]
            self.report["capture_plan"].append(
                dict(
                    pose,
                    frame_id=name,
                    mode=mode,
                    kind="fixture",
                    resolution=[1920, 1080],
                )
            )
            self.report["captures"].append(
                {
                    "frame_id": name,
                    "mode": mode,
                    "kind": "fixture",
                    "camera_location_cm": pose["camera"],
                    "target_cm": pose["target"],
                    "camera_rotation_deg": [0.0, 0.0, 0.0],
                    "fov_deg": pose["fov"],
                    "resolution": [1920, 1080],
                    "viewmode": "lit",
                    "dynamic_shadows": True,
                    "target_distance_cm": math.dist(pose["camera"], pose["target"]),
                }
            )
        self.rehash(self.report)

    @staticmethod
    def rehash(report):
        report["capture_plan_sha256"] = workflow.digest(
            workflow.canonical(report["capture_plan"])
        )

    def test_required_thirty_views_and_matched_modes_pass(self):
        self.assertEqual(len(workflow.CAPTURE_PAIRS), 30)
        self.assertEqual(len(workflow.PREPARED_VIEWS), 16)
        self.assertEqual(len(workflow.verify_capture_plan(self.report, self.pilot)), 30)

    def test_missing_duplicated_or_reordered_modes_are_rejected(self):
        for variant in ("missing", "duplicate", "reordered"):
            with self.subTest(variant=variant):
                report = copy.deepcopy(self.report)
                if variant == "missing":
                    report["captures"].pop()
                elif variant == "duplicate":
                    report["captures"][-1] = report["captures"][0]
                else:
                    report["captures"][0], report["captures"][1] = (
                        report["captures"][1],
                        report["captures"][0],
                    )
                with self.assertRaisesRegex(ValueError, "inventory changed"):
                    workflow.verify_capture_plan(report, self.pilot)

    def test_camera_drift_diagnostics_and_shadow_disabling_are_rejected(self):
        variants = (
            ("camera_location_cm", [0, 0, 0]),
            ("target_cm", [0, 0, 0]),
            ("camera_rotation_deg", [0, math.nan, 0]),
            ("fov_deg", 90),
            ("resolution", [1280, 720]),
            ("viewmode", "unlit"),
            ("dynamic_shadows", False),
            ("target_distance_cm", 0),
        )
        for key, value in variants:
            with self.subTest(key=key):
                report = copy.deepcopy(self.report)
                report["captures"][0][key] = value
                with self.assertRaises(ValueError):
                    workflow.verify_capture_plan(report, self.pilot)

    def test_rehashed_pilot_camera_plan_cannot_change_original_pose(self):
        report = copy.deepcopy(self.report)
        for frame, capture in zip(report["capture_plan"], report["captures"]):
            if frame["frame_id"] == "window-0023-forward-00000":
                frame["camera"][0] += 100.0
                capture["camera_location_cm"] = frame["camera"][:]
                capture["target_distance_cm"] = math.dist(
                    frame["camera"], frame["target"]
                )
        self.rehash(report)
        with self.assertRaises(ValueError):
            workflow.verify_capture_plan(report, self.pilot)

    def test_matched_seam_target_cannot_move_between_near_and_far(self):
        report = copy.deepcopy(self.report)
        index = next(
            i
            for i, row in enumerate(report["capture_plan"])
            if row["frame_id"] == "seam-distant"
        )
        report["capture_plan"][index]["target"][0] += 50.0
        report["captures"][index]["target_cm"] = report["capture_plan"][index][
            "target"
        ][:]
        report["captures"][index]["target_distance_cm"] = math.dist(
            report["capture_plan"][index]["camera"],
            report["capture_plan"][index]["target"],
        )
        self.rehash(report)
        with self.assertRaises(ValueError):
            workflow.verify_capture_plan(report, self.pilot)


class WholeMapMemoryAndFileTests(unittest.TestCase):
    def test_near_far_observation_is_recomputed_without_claiming_improvement(self):
        from scripts.ue.capture_sa_calobra_whole_map_prep import paired_normal_response

        near = (32, 16, 3, bytes([100, 100, 100]) * (32 * 16))
        far = (32, 16, 3, bytes([100, 100, 100]) * (32 * 16))
        report = {
            "captures": [
                {
                    "mode": mode,
                    "file": "frames/test-" + mode + ".png",
                    "sha256": str(index) * 64,
                }
                for index, mode in enumerate(("normal-near", "normal-far"))
            ]
        }
        response = paired_normal_response(near, far)
        self.assertEqual(response["status"], "NO_CLEAR_SHADING_RESPONSE")
        response["files"] = [
            {"file": row["file"], "sha256": row["sha256"]} for row in report["captures"]
        ]
        report["near_far_material_response"] = response
        with tempfile.TemporaryDirectory() as temporary:
            for variant in ("valid", "missing", "stale_metric", "wrong_source_hash"):
                with self.subTest(variant=variant):
                    changed = copy.deepcopy(report)
                    if variant == "missing":
                        changed.pop("near_far_material_response")
                    elif variant == "stale_metric":
                        changed["near_far_material_response"][
                            "changed_pixels_at_least_2_levels"
                        ] += 1
                    elif variant == "wrong_source_hash":
                        changed["near_far_material_response"]["files"][0]["sha256"] = (
                            "f" * 64
                        )
                    with mock.patch(
                        "scripts.ue.sa_calobra_detail_capture.decode_png",
                        side_effect=[near, far],
                    ):
                        if variant == "valid":
                            workflow.verify_normal_response(Path(temporary), changed)
                        else:
                            with self.assertRaisesRegex(ValueError, "near/far shading"):
                                workflow.verify_normal_response(
                                    Path(temporary), changed
                                )

    def test_package_sidecars_are_inventoried_and_rebound(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            primary = workflow.asset_path(repo, workflow.MASTER)
            primary.parent.mkdir(parents=True)
            primary.write_bytes(b"primary package")
            bulk = primary.with_suffix(".ubulk")
            bulk.write_bytes(b"external texture bytes")
            members = []
            for path in (primary, bulk):
                row = workflow.file_row(path, path.relative_to(repo).as_posix())
                members.append(
                    {
                        "file": row["path"],
                        "sha256": row["sha256"],
                        "size_bytes": row["size_bytes"],
                    }
                )
            package = {"asset": workflow.MASTER, **members[0], "package_files": members}
            self.assertEqual(len(workflow.verify_package_files(repo, package)), 2)
            missing = copy.deepcopy(package)
            missing["package_files"].pop()
            with self.assertRaisesRegex(ValueError, "incomplete"):
                workflow.verify_package_files(repo, missing)
            bulk.write_bytes(b"changed external texture bytes")
            with self.assertRaisesRegex(ValueError, "byte identity"):
                workflow.verify_package_files(repo, package)

    def test_memory_gates_use_actual_free_bytes_and_unchanged_thresholds(self):
        expected = (("before_preparation", 8, 12), ("before_all1024_binding", 6, 8))
        rows = [
            {
                "stage": name,
                "status": "PASS",
                "minimum_free_physical_gib": physical,
                "minimum_free_commit_gib": commit,
                "memory": {
                    "free_physical": physical * 1024**3,
                    "free_commit": commit * 1024**3,
                },
            }
            for name, physical, commit in expected
        ]
        workflow.verify_memory_checkpoints(rows, expected)
        for index, key in (
            (0, "free_physical"),
            (0, "free_commit"),
            (1, "free_physical"),
            (1, "free_commit"),
        ):
            with self.subTest(index=index, key=key):
                changed = copy.deepcopy(rows)
                changed[index]["memory"][key] -= 1
                with self.assertRaisesRegex(ValueError, "Insufficient memory"):
                    workflow.verify_memory_checkpoints(changed, expected)
        changed = copy.deepcopy(rows)
        changed[1]["minimum_free_physical_gib"] = 5
        with self.assertRaisesRegex(ValueError, "thresholds changed"):
            workflow.verify_memory_checkpoints(changed, expected)

    def test_retained_file_content_size_and_path_cannot_drift(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "payload.json"
            path.write_bytes(b'{"original":true}\n')
            row = workflow.file_row(path)
            workflow.verify_row(root, row)
            path.write_bytes(b'{"original":fals}\n')
            with self.assertRaisesRegex(ValueError, "byte identity"):
                workflow.verify_row(root, row)
            for relative in (
                "../payload.json",
                "/payload.json",
                "./payload.json",
                "folder\\payload.json",
                "folder//payload.json",
            ):
                with self.subTest(relative=relative), self.assertRaises(ValueError):
                    workflow.relative_file(root, relative)


if __name__ == "__main__":
    unittest.main()
