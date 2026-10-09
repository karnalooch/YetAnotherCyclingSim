"""Whole-map routing, native coverage and evidence tamper rejection."""

from __future__ import annotations

import copy
import io
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
import textwrap
import time
import unittest
from pathlib import Path
from unittest import mock

from scripts.ci import sa_calobra_whole_map_workflow as workflow
from scripts.ci.test_sa_calobra_detail_native_workflow import WORKFLOW, enabled, jobs


def expand_github_expressions(source):
    """Model Actions substitution before parsing, without expanding PowerShell."""
    values = {
        "github.sha": "a" * 40,
        "github.run_id": "1234567890",
        "github.run_attempt": "1",
        "steps.cache.outputs.mode": "static",
        "steps.cache.outputs.compile_kind": "none",
        "steps.cache.outputs.reason": "verified-equivalent-proof",
        "steps.fingerprints.outputs.compile": "b" * 64,
        "steps.fingerprints.outputs.proof": "c" * 64,
    }

    def replace(match):
        expression = match.group(1).strip()
        if expression not in values:
            raise ValueError("Unmodeled GitHub expression: " + expression)
        return values[expression]

    return re.sub(r"\$\{\{(.*?)\}\}", replace, source, flags=re.DOTALL)


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
            "/capture/whole-map-prep/diagnostics/",
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

    def test_github_expansion_preserves_ordinary_powershell_variables(self):
        # Actions expands the SHA inside this double-quoted error message
        # before PowerShell sees it. The unexpanded token caused the CI failure.
        source = (
            "throw \"checkout HEAD '$actual' != caller SHA '${{ github.sha }}'\"\n"
            'Write-Host "$env:GITHUB_SHA ${ordinary} $($actual)"\n'
            "$metadata = @{ head = $actual; passed = $true }\n"
            "Write-Host '${{github.run_id}}-${{ github.run_attempt }}'\n"
        )
        expected = source.replace("${{ github.sha }}", "a" * 40).replace(
            "${{github.run_id}}-${{ github.run_attempt }}", "1234567890-1"
        )
        self.assertEqual(expand_github_expressions(source), expected)
        with self.assertRaisesRegex(ValueError, "Unmodeled GitHub expression"):
            expand_github_expressions("${{ github.unmodeled_field }}")

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
                    input=expand_github_expressions(textwrap.dedent(source)),
                    text=True,
                    capture_output=True,
                    timeout=30,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class CommittedEvidenceRefreshTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.repo = Path(self.temporary.name) / "repo"
        self.repo.mkdir()
        self.blobs = {
            relative: f'{{\n  "fixture": {index}\n}}\n'.encode()
            for index, (relative, _, _) in enumerate(workflow.COMMITTED_EVIDENCE)
        }
        self.pins = tuple(
            (relative, workflow.digest(data), len(data))
            for relative, data in self.blobs.items()
        )
        pins = mock.patch.object(workflow, "COMMITTED_EVIDENCE", self.pins)
        self.addCleanup(pins.stop)
        pins.start()
        workflow.git(self.repo, "init", "-q")
        workflow.git(self.repo, "config", "core.autocrlf", "false")
        workflow.git(self.repo, "config", "commit.gpgsign", "false")
        hooks = self.repo / ".git" / "fixture-hooks"
        hooks.mkdir()
        workflow.git(self.repo, "config", "core.hooksPath", str(hooks))
        for relative, data in self.blobs.items():
            path = self.repo / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        workflow.git(self.repo, "add", "--", *self.blobs)
        self.commit()

    def commit(self):
        workflow.git(
            self.repo,
            "-c",
            "user.name=Workflow Fixture",
            "-c",
            "user.email=workflow-fixture@example.invalid",
            "commit",
            "-qm",
            "Fixture input",
        )
        self.head = workflow.git(self.repo, "rev-parse", "HEAD").decode().strip()

    def stale_checkout(self):
        before = {}
        for relative, data in self.blobs.items():
            before[relative] = data.replace(b"\n", b"\r\n")
            (self.repo / relative).write_bytes(before[relative])
        return before

    def assert_bytes(self, expected):
        for relative, data in expected.items():
            self.assertEqual((self.repo / relative).read_bytes(), data)

    def warm_checkout(self):
        source = self.repo
        attributes = source / ".gitattributes"
        attributes.write_bytes(b"* text=auto\n")
        workflow.git(source, "add", "--", ".gitattributes")
        self.commit()
        old = self.head
        attributes.write_bytes(
            (
                "* text=auto\n" + "".join(path + " -text\n" for path in self.blobs)
            ).encode()
        )
        workflow.git(source, "add", "--", ".gitattributes")
        self.commit()
        current = self.head
        self.repo = Path(self.temporary.name) / "runner"
        workflow.git(
            source,
            "clone",
            "--quiet",
            "--no-checkout",
            "--config",
            "core.autocrlf=true",
            str(source),
            str(self.repo),
        )
        workflow.git(self.repo, "checkout", "--quiet", "--detach", old)
        # A fresh/racy checkout records zero sizes and misses the runner bug.
        # Age before refreshing the OLD attributes so Git caches real CRLF sizes.
        aged = time.time() - 3600
        for relative in self.blobs:
            os.utime(self.repo / relative, (aged, aged))
        workflow.git(self.repo, "update-index", "--refresh")
        workflow.git(self.repo, "reset", "--hard", current)
        workflow.git(self.repo, "checkout-index", "--force", "--", *self.blobs)
        self.assertEqual(workflow.git(self.repo, "status", "--porcelain"), b"")
        self.assert_bytes(
            {
                relative: data.replace(b"\n", b"\r\n")
                for relative, data in self.blobs.items()
            }
        )

    def assert_clean_refresh(self, rewritten):
        receipt = workflow.refresh_committed_evidence(self.repo, self.head)
        self.assertEqual(receipt["rewritten_files"], rewritten)
        self.assertEqual(receipt["index_refreshed_files"], 3)
        self.assertEqual(receipt["head_tree"], receipt["index_tree_before"])
        self.assertEqual(receipt["head_tree"], receipt["index_tree_after"])
        self.assert_bytes(self.blobs)
        self.assertEqual(workflow.git(self.repo, "status", "--porcelain"), b"")
        self.assertEqual(
            workflow.git(self.repo, "write-tree").decode().strip(), receipt["head_tree"]
        )
        self.assertEqual(
            workflow.git(self.repo, "rev-parse", "HEAD").decode().strip(), self.head
        )

    def test_warmed_attribute_migration_restores_bytes_and_clean_unchanged_index(self):
        self.warm_checkout()
        self.assert_clean_refresh(3)

    def test_retry_refreshes_stale_index_when_raw_bytes_already_match(self):
        self.warm_checkout()
        for relative, data in self.blobs.items():
            (self.repo / relative).write_bytes(data)
        status = workflow.git(self.repo, "status", "--porcelain").decode().splitlines()
        self.assertEqual(set(status), {" M " + relative for relative in self.blobs})
        self.assert_clean_refresh(0)

    def test_preexisting_staged_change_rejects_before_any_write(self):
        before = self.stale_checkout()
        staged = self.repo / "staged.json"
        staged.write_bytes(b'{"preserve":true}\n')
        workflow.git(self.repo, "add", "--", staged.name)
        tree = workflow.git(self.repo, "write-tree")
        with self.assertRaisesRegex(ValueError, "Pre-existing staged changes"):
            workflow.refresh_committed_evidence(self.repo, self.head)
        self.assert_bytes(before)
        self.assertEqual(workflow.git(self.repo, "write-tree"), tree)

    def test_crlf_refresh_changes_only_allowlisted_files_and_is_idempotent(self):
        before = self.stale_checkout()
        unrelated = self.repo / "unrelated.json"
        unrelated.write_bytes(b'{"keep":true}\r\n')
        receipt = workflow.refresh_committed_evidence(self.repo, self.head)
        self.assertEqual(receipt["exact_sha"], self.head)
        self.assertEqual(receipt["rewritten_files"], 3)
        self.assertEqual([row["path"] for row in receipt["files"]], list(self.blobs))
        for row in receipt["files"]:
            relative = row["path"]
            self.assertEqual(row["before"]["sha256"], workflow.digest(before[relative]))
            self.assertEqual(row["before"]["size_bytes"], len(before[relative]))
            self.assertEqual(
                row["after"]["sha256"], workflow.digest(self.blobs[relative])
            )
            self.assertEqual(row["after"]["size_bytes"], len(self.blobs[relative]))
        self.assert_bytes(self.blobs)
        self.assertEqual(unrelated.read_bytes(), b'{"keep":true}\r\n')
        with mock.patch.object(
            Path, "write_bytes", side_effect=AssertionError("write")
        ):
            second = workflow.refresh_committed_evidence(self.repo, self.head)
        self.assertEqual(second["rewritten_files"], 0)

    def test_last_committed_hash_mismatch_rejects_before_any_write(self):
        relative = next(reversed(self.blobs))
        (self.repo / relative).write_bytes(b'{"unexpected":true}\n')
        workflow.git(self.repo, "add", "--", relative)
        self.commit()
        before = self.stale_checkout()
        with self.assertRaisesRegex(ValueError, "Pinned committed source changed"):
            workflow.refresh_committed_evidence(self.repo, self.head)
        self.assert_bytes(before)

    def test_last_committed_size_mismatch_rejects_before_any_write(self):
        before = self.stale_checkout()
        relative, sha, size = self.pins[-1]
        pins = self.pins[:-1] + ((relative, sha, size + 1),)
        with (
            mock.patch.object(workflow, "COMMITTED_EVIDENCE", pins),
            self.assertRaisesRegex(ValueError, "Pinned committed size changed"),
        ):
            workflow.refresh_committed_evidence(self.repo, self.head)
        self.assert_bytes(before)

    def test_later_reparse_ancestor_rejects_before_any_write(self):
        before = self.stale_checkout()
        blocked = (self.repo / next(reversed(self.blobs))).parent
        no_link = workflow.no_link

        def reject_reparse(path):
            if path == blocked:
                raise ValueError("Evidence cannot contain a symlink or reparse point")
            return no_link(path)

        with (
            mock.patch.object(workflow, "no_link", side_effect=reject_reparse),
            self.assertRaisesRegex(ValueError, "symlink or reparse point"),
        ):
            workflow.refresh_committed_evidence(self.repo, self.head)
        self.assert_bytes(before)

    def test_wrong_exact_head_rejects_before_any_write(self):
        before = self.stale_checkout()
        with self.assertRaisesRegex(ValueError, "Checkout exact head changed"):
            workflow.refresh_committed_evidence(self.repo, "0" * 40)
        self.assert_bytes(before)

    def test_actual_readback_must_match_after_writing(self):
        self.stale_checkout()
        write_bytes = Path.write_bytes

        def corrupt_write(path, data):
            return write_bytes(path, data + b"\r")

        with (
            mock.patch.object(Path, "write_bytes", corrupt_write),
            self.assertRaisesRegex(ValueError, "Committed evidence readback failed"),
        ):
            workflow.refresh_committed_evidence(self.repo, self.head)

    def test_cli_prints_full_receipt_without_creating_unused_output_root(self):
        self.stale_checkout()
        root = self.repo / "not-created"
        output = io.StringIO()
        with (
            mock.patch(
                "sys.argv",
                [
                    "workflow",
                    "refresh-committed",
                    "--repo",
                    str(self.repo),
                    "--root",
                    str(root),
                    "--exact-sha",
                    self.head,
                ],
            ),
            mock.patch("sys.stdout", output),
        ):
            workflow.main()
        receipt = json.loads(output.getvalue())
        self.assertEqual(receipt["status"], "COMMITTED_EVIDENCE_REFRESHED")
        self.assertEqual(len(receipt["files"]), 3)
        self.assertEqual(receipt["rewritten_files"], 3)
        self.assertFalse(root.exists())


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


class WholeMapV8GuardSequenceTests(unittest.TestCase):
    """A successful 43+8 capture must not bypass v8 geometry guards."""

    @staticmethod
    def valid_rows():
        from scripts.ue.sa_calobra_whole_map_witness import (
            WITNESS_IDS,
            WITNESS_MODES,
        )

        sequence = workflow.CAPTURE_PAIRS + tuple(
            (identity, mode) for identity in WITNESS_IDS for mode in WITNESS_MODES
        )
        return [
            {"frame_id": identity, "landscape_mode": mode}
            for identity, mode in sequence
        ]

    def test_complete_43_primary_plus_8_diagnostics_accepted(self):
        rows = self.valid_rows()
        self.assertEqual(len(rows), 51)
        self.assertIs(workflow.verify_native_mode_sequence(rows), rows)

    def test_missing_reordered_or_duplicate_guards_fail_closed(self):
        original = self.valid_rows()
        variants = [
            original[:-1],
            original[:43],
            original[:43] + original[44:45] + original[43:44] + original[45:],
            original[:-1] + [original[-2]],
            original[:42] + original[43:],
            original + [original[-1]],
        ]
        for changed in variants:
            with self.subTest(length=len(changed), tail=changed[-2:]):
                with self.assertRaisesRegex(ValueError, "guard order"):
                    workflow.verify_native_mode_sequence(changed)

    def test_rejects_mode_or_camera_identity_mutation(self):
        for column, forged in (
            ("frame_id", "unrelated-landscape"),
            ("landscape_mode", "prepared"),
        ):
            rows = self.valid_rows()
            rows[-1] = dict(rows[-1], **{column: forged})
            with self.subTest(column=column):
                with self.assertRaisesRegex(ValueError, "guard order"):
                    workflow.verify_native_mode_sequence(rows)


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
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        frames = Path(temporary.name) / "frames.csv"
        frames.write_bytes(
            workflow.git(
                workflow.ROOT, "cat-file", "blob", "HEAD:" + workflow.SURVEY_FILE
            )
        )
        self.survey_views = workflow.read_original_survey_views(frames)
        owner = "/Game/Worlds/SaCalobra/L_SaCalobraAccepted_20261004.L_SaCalobraAccepted_20261004:PersistentLevel.Landscape_0"
        actors = sorted([owner, owner.rsplit(".", 1)[0] + ".Camera_0"])
        self.near_probes, native_probes, extras = [], [], {}

        def trace(start, end, hit):
            return {
                "start_cm": start,
                "end_cm": end,
                "hit_cm": hit,
                "owner_excluded_control_hit_cm": None,
            }

        for name, (row, column, rgba, role, halo_sha) in zip(
            workflow.NEAR_VIEWS, workflow.NEAR_TARGETS
        ):
            x, y = column * 50, row * 50
            target, camera = [x, y, 40000.0], [x + 100, y, 40250.0]
            distance = math.dist(camera, target)
            self.poses[name] = {"camera": camera, "target": target, "fov": 60.0}
            source = {
                "row": row,
                "column": column,
                "pixel_window": [column - 8, row - 8, 17, 17],
                "xy_cm": [x, y],
                "center_rgba": list(rgba),
                "purpose_role": role,
                "physical_demand_band": "UNASSIGNED",
                "input_sha256": dict(workflow.NEAR_INPUTS),
                "halo_data_sha256": {
                    "material_weights_rgba8": halo_sha,
                    "availability_l8": workflow.digest(bytes([255]) * 289),
                    "inference_l8": workflow.digest(bytes(289)),
                    "exclusion_reasons_l8": workflow.digest(bytes(289)),
                },
                "support": {
                    "cells": 289,
                    "availability255_cells": 289,
                    "inference0_cells": 289,
                    "exclusion0_cells": 289,
                    "basis": "Pinned raster identity and independently decoded CPU windows",
                },
            }
            probe = {
                "owner_path": owner,
                "world_actor_paths": actors,
                "ignored_actor_paths": [path for path in actors if path != owner],
                "nominal_camera_offset_cm": [100, 0, 250],
                "rendered_pixel_depth_verified": False,
                "target_trace": trace([x, y, 150000], [x, y, -150000], target),
                "eye_ground_trace": trace(
                    [x + 100, y, 150000], [x + 100, y, -150000], [x + 100, y, 40000.0]
                ),
                "aim_trace": trace(
                    camera,
                    [
                        value + 25 * (value - eye) / distance
                        for value, eye in zip(target, camera)
                    ],
                    target,
                ),
                "target_distance_cm": distance,
                "hit_distance_cm": distance,
                "camera_clearance_cm": 250.0,
            }
            self.near_probes.append(copy.deepcopy(source))
            native_probes.append(
                {"frame_id": name, "source_probe": source, "landscape_probe": probe}
            )
            extras[name] = {
                "kind": "source_grid_landscape_near",
                "source_probe": source,
                "landscape_probe": probe,
            }
        for name, original in self.survey_views.items():
            self.poses[name] = {
                key: original[key] for key in ("camera", "target", "fov")
            }
            extras[name] = {
                "kind": "pinned_original_survey",
                "survey_source": original["survey_source"],
            }
        self.report = {
            "capture_plan": [],
            "captures": [],
            "near_landscape_probes": native_probes,
            "source_scene": {
                "landscape_actor_path": owner,
                "seam_probe": {
                    "target_cm": seam[:],
                    "original_source_delta_cm": 0.0,
                    "defect_admitted": False,
                    "boundary_xy_cm": [37800, 44100, 44100, 50400],
                },
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
            self.report["capture_plan"][-1].update(extras.get(name, {}))
            self.report["captures"][-1].update(extras.get(name, {}))
        self.rehash(self.report)

    def verify(self, report=None):
        return workflow.verify_capture_plan(
            self.report if report is None else report,
            self.pilot,
            self.near_probes,
            self.survey_views,
        )

    @staticmethod
    def rehash(report):
        report["capture_plan_sha256"] = workflow.digest(
            workflow.canonical(report["capture_plan"])
        )

    def test_required_forty_three_frames_and_matched_modes_pass(self):
        self.assertEqual(len(workflow.CAPTURE_PAIRS), 43)
        self.assertEqual(len(workflow.PREPARED_VIEWS), 21)
        self.assertEqual(len(self.verify()), 43)
        self.assertEqual(
            {
                mode: sum(pair[1] == mode for pair in workflow.CAPTURE_PAIRS)
                for mode in (
                    "baseline",
                    "prepared",
                    "domains",
                    "checker",
                    "normal-near",
                    "normal-far",
                )
            },
            {
                "baseline": 9,
                "prepared": 21,
                "domains": 4,
                "checker": 7,
                "normal-near": 1,
                "normal-far": 1,
            },
        )

    def test_missing_duplicated_or_reordered_modes_are_rejected(self):
        for variant in (
            "missing",
            "missing-near",
            "missing-far",
            "duplicate",
            "reordered",
        ):
            with self.subTest(variant=variant):
                report = copy.deepcopy(self.report)
                if variant == "missing":
                    report["captures"].pop()
                elif variant in ("missing-near", "missing-far"):
                    target = (
                        workflow.NEAR_VIEWS[0]
                        if variant == "missing-near"
                        else workflow.FAR_VIEWS[0]
                    )
                    report["captures"] = [
                        row for row in report["captures"] if row["frame_id"] != target
                    ]
                elif variant == "duplicate":
                    report["captures"][-1] = report["captures"][0]
                else:
                    report["captures"][0], report["captures"][1] = (
                        report["captures"][1],
                        report["captures"][0],
                    )
                with self.assertRaisesRegex(ValueError, "inventory changed"):
                    self.verify(report)

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
                    self.verify(report)

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
            self.verify(report)

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
            self.verify(report)

    def test_rehashed_near_source_and_incomplete_probe_metadata_are_rejected(self):
        for mutation in (
            "source-hash",
            "window",
            "halo",
            "classification",
            "missing-probe",
            "capture-drift",
        ):
            with self.subTest(mutation=mutation):
                report = copy.deepcopy(self.report)
                source = report["near_landscape_probes"][0]["source_probe"]
                if mutation == "source-hash":
                    source["input_sha256"]["material-weights.png"] = "0" * 64
                elif mutation == "window":
                    source["pixel_window"][0] += 1
                elif mutation == "halo":
                    source["halo_data_sha256"]["availability_l8"] = "0" * 64
                elif mutation == "classification":
                    source["physical_demand_band"] = "A"
                elif mutation == "missing-probe":
                    report["near_landscape_probes"].pop()
                else:
                    capture = next(
                        row
                        for row in report["captures"]
                        if row["frame_id"] == workflow.NEAR_VIEWS[0]
                    )
                    capture["source_probe"] = {}
                self.rehash(report)
                with self.assertRaises(ValueError):
                    self.verify(report)

    def test_consistent_near_camera_lift_outside_five_metres_is_rejected(self):
        report = copy.deepcopy(self.report)
        name = workflow.NEAR_VIEWS[0]
        frame = next(row for row in report["capture_plan"] if row["frame_id"] == name)
        target = frame["target"]
        probe = frame["landscape_probe"]
        probe["eye_ground_trace"]["hit_cm"][2] = target[2] + 600
        camera = [target[0] + 100, target[1], target[2] + 750]
        distance = math.dist(camera, target)
        probe.update(
            camera_clearance_cm=150,
            target_distance_cm=distance,
            hit_distance_cm=distance,
        )
        probe["aim_trace"]["start_cm"] = camera
        probe["aim_trace"]["end_cm"] = [
            value + 25 * (value - eye) / distance for value, eye in zip(target, camera)
        ]
        for row in report["capture_plan"]:
            if row["frame_id"] == name:
                row["camera"] = camera
        for row in report["captures"]:
            if row["frame_id"] == name:
                row.update(camera_location_cm=camera, target_distance_cm=distance)
        self.rehash(report)
        with self.assertRaisesRegex(ValueError, "source-bound1..5m placement"):
            self.verify(report)

    def test_near_hit_owner_controls_target_and_rendered_depth_claim_are_checked(self):
        for mutation in (
            "wrong-owner",
            "ignored-owner",
            "missing-control",
            "control-hit",
            "shifted-target",
            "near-hit",
            "rendered-depth",
        ):
            with self.subTest(mutation=mutation):
                report = copy.deepcopy(self.report)
                frame = next(
                    row
                    for row in report["capture_plan"]
                    if row["frame_id"] == workflow.NEAR_VIEWS[0]
                )
                probe = frame["landscape_probe"]
                if mutation == "wrong-owner":
                    probe["owner_path"] += "_Other"
                elif mutation == "ignored-owner":
                    probe["ignored_actor_paths"].append(probe["owner_path"])
                elif mutation == "missing-control":
                    del probe["target_trace"]["owner_excluded_control_hit_cm"]
                elif mutation == "control-hit":
                    probe["aim_trace"]["owner_excluded_control_hit_cm"] = frame[
                        "target"
                    ][:]
                elif mutation == "shifted-target":
                    probe["target_trace"]["hit_cm"][0] += 50
                elif mutation == "near-hit":
                    camera, target = frame["camera"], frame["target"]
                    distance = math.dist(camera, target)
                    probe["aim_trace"]["hit_cm"] = [
                        eye + 50 * (value - eye) / distance
                        for value, eye in zip(target, camera)
                    ]
                    probe["hit_distance_cm"] = 50
                else:
                    probe["rendered_pixel_depth_verified"] = True
                self.rehash(report)
                with self.assertRaises(ValueError):
                    self.verify(report)

    def test_rehashed_far_camera_and_observation_provenance_cannot_replace_pinned_csv(
        self,
    ):
        for name in workflow.FAR_VIEWS:
            for mutation in (
                "camera",
                "target",
                "fov",
                "csv-hash",
                "index",
                "band",
                "physical-registration",
            ):
                with self.subTest(name=name, mutation=mutation):
                    report = copy.deepcopy(self.report)
                    changed = copy.deepcopy(self.poses[name])
                    if mutation in ("camera", "target"):
                        changed[mutation][0] += 10
                    elif mutation == "fov":
                        changed["fov"] = 80.0
                    for frame, capture in zip(
                        report["capture_plan"], report["captures"]
                    ):
                        if frame["frame_id"] != name:
                            continue
                        frame.update(changed)
                        capture.update(
                            camera_location_cm=changed["camera"],
                            target_cm=changed["target"],
                            fov_deg=changed["fov"],
                            target_distance_cm=math.dist(
                                changed["camera"], changed["target"]
                            ),
                        )
                        source = frame["survey_source"]
                        if mutation == "csv-hash":
                            source["sha256"] = "0" * 64
                        elif mutation == "index":
                            source["index"] += 1
                        elif mutation == "band":
                            source["proposal_band"] = "D"
                        elif mutation == "physical-registration":
                            source["physical_surface_registered"] = True
                    self.rehash(report)
                    with self.assertRaisesRegex(ValueError, "Pinned original B/C"):
                        self.verify(report)


class WholeMapNearRasterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PIL import Image

        cls.data = {}
        for name, mode, fill in (
            ("material-weights.png", "RGBA", (0, 0, 0, 0)),
            ("sample-availability.png", "L", 255),
            ("inference-kind.png", "L", 0),
            ("exclusion-reasons.png", "L", 0),
        ):
            with Image.new(mode, (4033, 4033), fill) as raster:
                if mode == "RGBA":
                    for row, column, rgba, _, _ in workflow.NEAR_TARGETS:
                        raster.paste(rgba, (column - 8, row - 8, column + 9, row + 9))
                stream = io.BytesIO()
                raster.save(stream, format="PNG")
                cls.data[name] = stream.getvalue()
        cls.data["exclusion-reasons.tif"] = cls.make_tiff()

    @staticmethod
    def make_tiff(*, excluded=False):
        import numpy as np
        from rasterio.io import MemoryFile
        from rasterio.transform import Affine

        values = np.zeros((4033, 4033), dtype=np.uint16)
        if excluded:
            row, column = workflow.NEAR_TARGETS[0][:2]
            values[row - 8, column - 8] = 64
        with MemoryFile() as memory:
            with memory.open(
                driver="GTiff",
                width=4033,
                height=4033,
                count=1,
                dtype="uint16",
                crs="EPSG:25831",
                transform=Affine(0.5, 0, 483000, 0, -0.5, 4409516.5),
                nodata=65535,
                compress="DEFLATE",
            ) as raster:
                raster.write(values, 1)
            return memory.read()

    def test_all_cells_are_decoded_with_source_hashes_and_registered_centres(self):
        probes = workflow.decode_near_windows(self.data)
        self.assertEqual(len(probes), 3)
        for probe, (row, column, rgba, _, _) in zip(probes, workflow.NEAR_TARGETS):
            self.assertEqual(probe["center_rgba"], list(rgba))
            self.assertEqual(probe["xy_cm"], [column * 50, row * 50])
            self.assertEqual(
                probe["halo_data_sha256"]["material_weights_rgba8"],
                workflow.digest(bytes(rgba) * 289),
            )
            self.assertEqual(
                probe["input_sha256"],
                {name: workflow.digest(raw) for name, raw in self.data.items()},
            )
            self.assertEqual(probe["support"]["exclusion0_cells"], 289)

    def test_one_bad_corner_rejects_support_even_when_the_centre_is_valid(self):
        from PIL import Image

        row, column = workflow.NEAR_TARGETS[0][:2]
        for name, value in (
            ("sample-availability.png", 0),
            ("inference-kind.png", 1),
            ("exclusion-reasons.png", 64),
        ):
            with self.subTest(name=name):
                data = dict(self.data)
                with Image.open(io.BytesIO(data[name])) as raster:
                    raster.putpixel((column - 8, row - 8), value)
                    output = io.BytesIO()
                    raster.save(output, format="PNG")
                    data[name] = output.getvalue()
                with self.assertRaisesRegex(ValueError, "exclusion|full17x17"):
                    workflow.decode_near_windows(data)

    def test_original_uint16_exclusion_cannot_be_hidden_by_zero_png(self):
        data = dict(self.data)
        data["exclusion-reasons.tif"] = self.make_tiff(excluded=True)
        with self.assertRaisesRegex(ValueError, "TIFF/PNG exclusion"):
            workflow.decode_near_windows(data)

    def test_wrong_source_bytes_are_rejected_before_raster_decoding(self):
        with tempfile.TemporaryDirectory() as temporary:
            bundle = Path(temporary)
            (bundle / "material-weights.png").write_bytes(b"wrong source")
            with (
                mock.patch.object(workflow, "decode_near_windows") as decode,
                self.assertRaisesRegex(ValueError, "Near source byte identity"),
            ):
                workflow.read_near_probes(bundle, {})
            decode.assert_not_called()

    def test_stale_or_line_ending_changed_survey_is_rejected(self):
        original = workflow.git(
            workflow.ROOT, "cat-file", "blob", "HEAD:" + workflow.SURVEY_FILE
        )
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "frames.csv"
            for changed in (original + b"\n", original.replace(b"\r\n", b"\n")):
                path.write_bytes(changed)
                with self.assertRaisesRegex(ValueError, "survey CSV byte identity"):
                    workflow.read_original_survey_views(path)


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
