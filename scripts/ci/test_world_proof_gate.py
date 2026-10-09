from __future__ import annotations

import copy
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from scripts.ci import world_proof_gate as gate

ROOT = Path(__file__).resolve().parents[2]
POLICY = json.loads((ROOT / ".gumball/world-proof-policy.json").read_text())
HEAD = "a" * 40


def fixture(name="stage3g-environment"):
    scenario = POLICY["scenarios"][name]
    summary = {
        "Head": HEAD,
        "Result": "PASS",
        "EditorExitCode": 0,
        "Resolution": "1920x1080",
        "VSync": "disabled",
        "TargetFps": 60,
        "ReferenceGpuMatched": True,
        "GpuNames": ["NVIDIA GeForce RTX 2070 SUPER"],
        "AllowedOverBudgetRatio": 0.05,
        "FrameBudgetMs": gate.BUDGET_MS,
        "P95FrameBudgetMs": gate.BUDGET_MS,
        "P95GpuBudgetMs": gate.BUDGET_MS,
        "ScenarioId": name,
        "MapPackage": scenario["map_package"],
        "ComponentCount": 1024,
        "TerrainSha256": "b" * 64,
        "SettingsSha256": "c" * 64,
        "ScreenPercentage": 100,
        "DynamicResolution": False,
        "MapSha256": "d" * 64,
        "ConsumerManifestSha256": "e" * 64,
        "MaterialParent": scenario.get("material_parent"),
        "MaterialComponentCount": 1024,
        "RenderInstanceCount": 1024,
        "LightingPreserved": True,
        "Sectors": [
            {
                "Sector": s,
                "SampleCount": 120,
                "PositiveGpuSampleCount": 120,
                "FrameP95Ms": 10,
                "GpuP95Ms": 8,
                "OverBudgetRatio": 0,
                "Pass": True,
            }
            for s in scenario["sectors"]
        ],
    }
    csv = "sector,frame_ms,game_ms,draw_ms,rhi_ms,gpu_ms\n" + "".join(
        f"{s},10,2,3,1,8\n" * 120 for s in scenario["sectors"]
    )
    return summary, csv, scenario


class WorldProofTests(unittest.TestCase):
    def test_material_changes_also_require_saved_consumer(self):
        needed = gate.requirements(["scripts/ue/sa_calobra_whole_map_prep.py"], POLICY)
        self.assertIn("sa-calobra-material", needed)
        self.assertIn("sa-calobra-terrain", needed)

    def test_worlds_are_distinct_and_docs_do_not_require_gpu(self):
        self.assertEqual(
            gate.requirements(["Content/Worlds/SaCalobra/L_Test.umap"], POLICY),
            ["sa-calobra-terrain"],
        )
        self.assertEqual(
            gate.requirements(["Content/Prototype/Maps/L_CyclingTest.umap"], POLICY),
            ["stage3g-environment"],
        )
        self.assertEqual(
            gate.requirements(
                ["worldgen/terrain/benchmarks/sa_calobra/README.md"], POLICY
            ),
            [],
        )
        self.assertEqual(
            gate.requirements(["Content/Worlds/NewWorld/map.umap"], POLICY),
            ["UNMAPPED_WORLD"],
        )

    def test_only_registered_source_evidence_avoids_gpu(self):
        evidence = POLICY["source_evidence_paths"]
        self.assertEqual(gate.requirements(evidence, POLICY), [])
        for path in (
            "worldgen/terrain/benchmarks/sa_calobra/world_data/derived_masks.json",
            "worldgen/terrain/benchmarks/sa_calobra/world_data/new_receipt.json",
            "worldgen/terrain/benchmarks/sa_calobra/import_manifest.json",
            "Content/Worlds/SaCalobra/L_Test.umap",
        ):
            with self.subTest(path=path):
                self.assertEqual(
                    gate.requirements([*evidence, path], POLICY),
                    ["sa-calobra-terrain"],
                )
        self.assertIn(
            "stage3g-environment",
            gate.requirements(
                [*evidence, "Content/Prototype/Maps/L_CyclingTest.umap"], POLICY
            ),
        )

    def test_source_evidence_cannot_be_a_wildcard_or_escape_path(self):
        for path in ("worldgen/*.json", "worldgen/../Content/Worlds/map.json"):
            policy = copy.deepcopy(POLICY)
            policy["source_evidence_paths"] = [path]
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, "exact"):
                gate.requirements([path], policy)

    def test_only_draft_defers_and_unknown_event_fails_closed(self):
        self.assertEqual(gate.phase("pull_request", "true"), "DEFERRED_DRAFT")
        self.assertEqual(gate.phase("pull_request", "false"), "REQUIRED")
        self.assertEqual(gate.phase("push", "false"), "REQUIRED")
        self.assertEqual(gate.phase("schedule", "false"), "STATIC_ONLY")
        for event, draft in (
            ("issue_comment", "false"),
            ("pull_request", ""),
            ("pull_request", "False"),
        ):
            with self.assertRaises(ValueError):
                gate.phase(event, draft)

    def test_valid_raw_samples_are_recomputed_for_each_scenario(self):
        for name in POLICY["scenarios"]:
            summary, csv, scenario = fixture(name)
            result = gate.validate_evidence(summary, csv, scenario, name, HEAD)
            self.assertEqual(result["result"], "PASS")

    def test_wrong_sha_gpu_resolution_budget_and_result_fail(self):
        for field, value in (
            ("Head", "d" * 40),
            ("GpuNames", ["RTX 4090"]),
            ("Result", "FAIL"),
            ("EditorExitCode", 1),
            ("Resolution", "1280x720"),
            ("VSync", "enabled"),
            ("TargetFps", 30),
            ("AllowedOverBudgetRatio", 0.50),
            ("FrameBudgetMs", 33.3),
        ):
            with self.subTest(field=field):
                summary, csv, scenario = fixture()
                summary[field] = value
                with self.assertRaises(ValueError):
                    gate.validate_evidence(
                        summary, csv, scenario, "stage3g-environment", HEAD
                    )

    def test_forged_summary_cannot_hide_bad_missing_nonfinite_or_short_samples(self):
        summary, csv, scenario = fixture()
        for changed in (
            csv.replace(",10,", ",25,"),
            csv.replace(",8\n", ",0\n"),
            csv.replace(",8\n", ",nan\n"),
            csv.replace(",8\n", ",inf\n"),
            "\n".join(csv.splitlines()[:50]),
            csv.replace("forest,", "unknown,"),
        ):
            with self.subTest(sample=changed[:80]), self.assertRaises(ValueError):
                gate.validate_evidence(
                    summary, changed, scenario, "stage3g-environment", HEAD
                )
        bad = copy.deepcopy(summary)
        bad["Sectors"][0]["FrameP95Ms"] = 2
        with self.assertRaises(ValueError):
            gate.validate_evidence(bad, csv, scenario, "stage3g-environment", HEAD)

    def test_sacalobra_requires_map_terrain_identity_and_render_settings(self):
        for field, value in (
            ("MapPackage", "/Game/Prototype/Maps/L_CyclingTest"),
            ("ComponentCount", 256),
            ("TerrainSha256", ""),
            ("SettingsSha256", ""),
            ("ScreenPercentage", 50),
            ("DynamicResolution", True),
            ("ScenarioId", "stage3g-environment"),
        ):
            summary, csv, scenario = fixture("sa-calobra-terrain")
            summary[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                gate.validate_evidence(
                    summary, csv, scenario, "sa-calobra-terrain", HEAD
                )

    def test_unregistered_producer_and_missing_artifact_never_pass(self):
        scenario = POLICY["scenarios"]["sa-calobra-terrain"]
        with self.assertRaisesRegex(ValueError, "not registered"):
            gate.evaluate_remote(
                "owner/repo",
                "unused",
                HEAD,
                "sa-calobra-terrain",
                scenario,
                {"proofs": {}},
            )
        broker = {
            "proofs": {
                "environment-performance": {
                    "enabled": True,
                    "workflow": "perf.yml",
                    "artifact_name": "proof-$proof-$sha",
                }
            }
        }
        with (
            patch.object(gate.proof_broker, "find_artifact", return_value=None),
            self.assertRaisesRegex(ValueError, "missing/expired"),
        ):
            gate.evaluate_remote(
                "owner/repo",
                "unused",
                HEAD,
                "stage3g-environment",
                POLICY["scenarios"]["stage3g-environment"],
                broker,
            )

    def test_failed_wrong_workflow_or_untrusted_branch_artifact_rejected(self):
        broker = {
            "proofs": {
                "environment-performance": {
                    "enabled": True,
                    "workflow": "perf.yml",
                    "artifact_name": "proof-$proof-$sha",
                }
            }
        }
        run = {
            "status": "completed",
            "conclusion": "success",
            "path": ".github/workflows/perf.yml",
            "event": "workflow_dispatch",
            "head_repository": {"full_name": "owner/repo"},
            "head_branch": "main",
        }
        for key, value in (
            ("conclusion", "failure"),
            ("status", "in_progress"),
            ("path", ".github/workflows/other.yml"),
            ("head_branch", "untrusted"),
            ("event", "pull_request"),
        ):
            with (
                patch.object(
                    gate.proof_broker,
                    "find_artifact",
                    return_value={"id": 5, "workflow_run": {"id": 10}},
                ),
                patch.object(gate.proof_broker, "default_branch", return_value="main"),
                patch.object(
                    gate.github_ops, "request", return_value={**run, key: value}
                ),
                self.subTest(key=key),
                self.assertRaises(ValueError),
            ):
                gate.evaluate_remote(
                    "owner/repo",
                    "unused",
                    HEAD,
                    "stage3g-environment",
                    POLICY["scenarios"]["stage3g-environment"],
                    broker,
                )

    def test_duplicate_receipt_names_are_rejected_without_extracting(self):
        data = io.BytesIO()
        with zipfile.ZipFile(data, "w") as archive:
            archive.writestr("first/summary.json", "{}")
            archive.writestr("second/summary.json", "{}")
        with self.assertRaisesRegex(ValueError, "exactly one"):
            gate.archive_text(data.getvalue(), "summary.json")


class OwnerDeferralTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.git("init", "--quiet")
        self.git("config", "user.name", "World proof test")
        self.git("config", "user.email", "test@example.invalid")
        self.write("Content/Worlds/SaCalobra/mask.txt", "frozen mask")
        self.baseline = self.commit()
        self.policy = copy.deepcopy(POLICY)
        self.policy["owner_deferred_2a_performance"]["baseline_sha"] = self.baseline

    def git(self, *args):
        return subprocess.check_output(
            ["git", *args], cwd=self.root, text=True, stderr=subprocess.PIPE
        ).strip()

    def write(self, path, content):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    def commit(self):
        self.git("add", ".")
        self.git("commit", "--quiet", "-m", "test fixture")
        return self.git("rev-parse", "HEAD")

    def deferred(self, head, needed=None):
        return gate.deferred_2a_performance(
            head, needed or ["sa-calobra-terrain"], self.policy, self.root
        )

    def test_frozen_world_with_documented_closeout_is_explicitly_deferred(self):
        self.write("docs/CI_VALIDATION_TIERS.md", "Owner decision: due in 2B")
        self.write("scripts/ci/world_proof_gate.py", "closeout control")
        result = self.deferred(self.commit())
        self.assertEqual(result["status"], "DEFERRED_TO_2B")
        self.assertEqual(result["due_issue"], 363)
        self.assertFalse(result["performance_pass"])

    def test_material_geometry_configuration_and_new_producers_end_deferral(self):
        for path in (
            "Content/Worlds/SaCalobra/mask.txt",
            "Content/Materials/M_Ground.uasset",
            "Config/DefaultEngine.ini",
            "scripts/ue/sa_calobra_material.py",
            "Source/YACS/MaterialConsumer.cpp",
        ):
            with self.subTest(path=path):
                target = self.root / path
                previous = target.read_bytes() if target.exists() else None
                self.write(path, "2B world change")
                self.assertIsNone(self.deferred(self.commit()))
                if previous is None:
                    target.unlink()
                else:
                    target.write_bytes(previous)
                self.assertIsNotNone(self.deferred(self.commit()))

    def test_other_scenarios_and_invalid_or_unrelated_baselines_cannot_defer(self):
        self.assertIsNone(self.deferred(self.baseline, ["UNMAPPED_WORLD"]))
        self.assertIsNone(
            self.deferred(self.baseline, ["sa-calobra-terrain", "stage3g-environment"])
        )
        self.policy["owner_deferred_2a_performance"]["baseline_sha"] = "invalid"
        with self.assertRaisesRegex(ValueError, "invalid owner-approved"):
            self.deferred(self.baseline)
        self.policy["owner_deferred_2a_performance"]["baseline_sha"] = "b" * 40
        with self.assertRaisesRegex(ValueError, "cannot verify"):
            self.deferred(self.baseline)
        self.policy["owner_deferred_2a_performance"]["baseline_sha"] = self.baseline
        self.git("checkout", "--quiet", "--orphan", "unrelated")
        self.write("docs/other.md", "unrelated world")
        self.assertIsNone(self.deferred(self.commit()))

    def m3_deferred(self, head, needed=None):
        self.policy["owner_deferred_m3_performance"]["baseline_sha"] = self.baseline
        return gate.deferred_m3_performance(
            head, needed or ["sa-calobra-material"], self.policy, self.root
        )

    def test_m3_assembly_changes_are_explicitly_deferred_without_performance_pass(self):
        self.write("Content/Worlds/SaCalobra/mask.txt", "assembled material checkpoint")
        result = self.m3_deferred(
            self.commit(), ["sa-calobra-material", "stage3g-environment"]
        )
        self.assertEqual(result["status"], "DEFERRED_AFTER_M3")
        self.assertEqual(result["due"], "after_m3_assembly")
        self.assertFalse(result["performance_pass"])
        self.assertEqual(result["baseline_sha"], self.baseline)

    def test_completed_assembly_unknown_world_and_unrelated_head_cannot_defer(self):
        self.assertIsNone(self.m3_deferred(self.baseline, ["UNMAPPED_WORLD"]))
        self.policy["owner_deferred_m3_performance"]["assembly_status"] = "COMPLETE"
        self.assertIsNone(self.m3_deferred(self.baseline))
        self.policy["owner_deferred_m3_performance"]["assembly_status"] = "IN_PROGRESS"
        self.git("checkout", "--quiet", "--orphan", "unrelated-m3")
        self.write("docs/other.md", "another world")
        self.assertIsNone(self.m3_deferred(self.commit()))

    def test_invalid_owner_decision_or_unregistered_scenario_cannot_defer(self):
        decision = self.policy["owner_deferred_m3_performance"]
        decision["baseline_sha"] = self.baseline
        for key, value in (
            ("stage", "M4"),
            ("owner_decision_date", "2026-10-08"),
            ("assembly_status", "DONE"),
            ("due", "never"),
            ("baseline_sha", "invalid"),
        ):
            previous = decision[key]
            decision[key] = value
            with (
                self.subTest(key=key),
                self.assertRaisesRegex(ValueError, "invalid owner-approved M3"),
            ):
                gate.deferred_m3_performance(
                    self.baseline, ["sa-calobra-material"], self.policy, self.root
                )
            decision[key] = previous
        self.policy["scenarios"].pop("sa-calobra-material")
        with self.assertRaisesRegex(ValueError, "unregistered M3 scenario"):
            self.m3_deferred(self.baseline)


if __name__ == "__main__":
    unittest.main()
