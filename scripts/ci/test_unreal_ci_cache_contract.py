from __future__ import annotations

import shlex
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "reusable-unreal.yml"
CACHE = ROOT / "scripts" / "ci" / "Resolve-YacsUnrealCiCache.ps1"
ENGINE = ROOT / "scripts" / "ci" / "Resolve-YacsUnrealEngine.ps1"
ENVIRONMENT = ROOT / "scripts" / "ci" / "Resolve-YacsUnrealBuildEnvironment.ps1"
PREFLIGHT = ROOT / "scripts" / "ue" / "Preflight-YacsProof.ps1"


class UnrealCiCacheContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")
        cls.cache = CACHE.read_text(encoding="utf-8")
        cls.engine = ENGINE.read_text(encoding="utf-8")
        cls.environment = ENVIRONMENT.read_text(encoding="utf-8")
        cls.preflight = PREFLIGHT.read_text(encoding="utf-8")

    def test_workflow_preserves_only_allow_listed_warm_build_state(self):
        # Keep this list intentionally identical to the workflow's persistent
        # build surfaces; every other ignored path must be disposable.
        for token in (
            "group: yacs-unreal-ci-${{ github.repository }}",
            "YACS_UNREAL_WORKTREE: _unreal-ci-warm",
            "clean: false",
            "git clean -ffdx",
            "-e '/Binaries/'",
            "-e '/Intermediate/'",
            "-e '/Plugins/**/Binaries/'",
            "-e '/Plugins/**/Intermediate/'",
            "-e '/Saved/BuildCache/UnrealCi/'",
            "Resolve verified Unreal execution mode",
            "Retain previous owner-handoff LFS payloads before sanitization",
            "_yacs-retained-lfs/handoff-${{ github.run_id }}-${{ github.run_attempt }}",
            "retain_unreal_assets.py",
        ):
            self.assertIn(token, self.workflow)

    def test_handoff_lfs_retention_precedes_code_only_sanitization(self):
        retain_index = self.workflow.index(
            "Retain previous owner-handoff LFS payloads before sanitization"
        )
        sanitize_index = self.workflow.index(
            "Sanitize tracked workspace while preserving verified build outputs"
        )
        code_only_index = self.workflow.index("Enforce code-only checkout")
        self.assertLess(retain_index, sanitize_index)
        self.assertLess(sanitize_index, code_only_index)

    def test_cleanup_retains_only_diagnostic_logs_and_admitted_build_surfaces(self):
        commands = [
            line.strip()
            for line in self.workflow.splitlines()
            if line.strip().startswith("git clean -ffdx")
        ]
        self.assertEqual(len(commands), 2)
        self.assertEqual(commands[0], commands[1])
        keep = [
            "Saved/Logs/YetAnotherCyclingSim.log",
            "Saved/RuntimeProof/CI/RegionTerrain/123-1/map-preparation.stdout.log",
            "Saved/RuntimeProof/CI/Unreal/Proof/automation_editor.log",
            "Saved/RuntimeProof/CI/Unreal/Proof/automation_run.log",
            "Saved/RuntimeProof/CI/Unreal/Proof-123-1/automation_editor.log",
            "Binaries/build.dll",
            "Saved/BuildCache/UnrealCi/state.json",
        ]
        remove = [
            "Saved/Logs/unrelated.log",
            "Saved/RuntimeProof/CI/RegionTerrain/123-1/profile.json",
            "Saved/RuntimeProof/CI/Unreal/Proof-123-1/summary.json",
            "Saved/RuntimeProof/CI/Unreal/Proof/summary.json",
            "Saved/RuntimeProof/CI/RegionTerrain/123-1/render.png",
            "Saved/RuntimeProof/CI/RegionTerrain/123-1/Prepared/terrain.r16",
            "Saved/unrelated.tmp",
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "--quiet", str(root)], check=True)
            for name in keep + remove:
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("fixture", encoding="utf-8")
            subprocess.run(
                shlex.split(commands[0]),
                cwd=root,
                check=True,
                capture_output=True,
                text=True,
            )
            for name in keep:
                self.assertTrue((root / name).exists(), name)
            for name in remove:
                self.assertFalse((root / name).exists(), name)

    def test_region_artifact_upload_is_current_attempt_only(self):
        block = self.workflow.split(
            "- name: Upload native Sa Calobra import diagnostic", 1
        )[1]
        block = block.split("- name: Upload concise Unreal proof", 1)[0]
        paths = [
            line.strip() for line in block.splitlines() if "/RegionTerrain/" in line
        ]
        self.assertEqual(len(paths), 5)
        self.assertNotIn("Upload bounded BOB construction lesson", block)
        self.assertNotIn("bob-build-lesson", block)
        self.assertNotIn("bob-lesson-", block)
        for path in paths:
            self.assertIn(
                "/RegionTerrain/${{ github.run_id }}-${{ github.run_attempt }}/",
                path,
            )

        capture = self.workflow.split(
            "- name: Capture isolated native Sa Calobra terrain", 1
        )[1].split("- name: Retire owner-approved obsolete Italy payloads", 1)[0]
        self.assertIn("$proof.captures.Count -ne 10", capture)
        self.assertIn("road-geometry-inspection-before", capture)
        self.assertIn("road-geometry-inspection-after", capture)
        self.assertIn("geometry-inspection-clay-wireframe", capture)
        self.assertIn(
            "Mandatory road Geometry Inspection before/after proof failed.",
            capture,
        )
        self.assertIn(
            "$proof.bob_mode -ne 'INSPECTOR_PLUS_TRANSIENT_CUT_AND_VERTICAL_SUPPORT'",
            capture,
        )
        self.assertIn("bob-road-earthworks-cut-proof.json", capture)
        self.assertIn("BOB direct Road_Earthworks CUT proof failed.", capture)
        self.assertIn("bob-vertical-support-proof.json", capture)
        self.assertIn("$cut.geometry_repair_executed -ne $true", capture)
        self.assertIn("$cut.transient_road_earthworks_modified -ne $true", capture)
        self.assertIn("$support.wall_segment_count -le 0", capture)
        self.assertIn("[int]$cut.after.class_counts.CUT_REQUIRED -ne 0", capture)
        self.assertIn("$inspection.actual_viewmode -ne 'VMI_CLAY'", capture)
        self.assertIn("Final road rider capture did not return to Lit mode.", capture)
        self.assertIn("WaitForExit(300000)", capture)
        self.assertNotIn("YACS_KEEP_EDITOR_OPEN", capture)
        self.assertNotIn("RUNNER_TRACKING_ID", capture)

        handoff = self.workflow.split(
            "- name: Launch interactive Sa Calobra owner handoff", 1
        )[1].split(
            "- name: Clean current-run evidence and non-allow-listed residue", 1
        )[0]
        self.assertIn("$env:YACS_OWNER_HANDOFF = '1'", handoff)
        self.assertIn("$env:RUNNER_TRACKING_ID = ''", handoff)
        self.assertNotIn("Set-Content", handoff)
        self.assertNotIn("-ExecutePythonScript", handoff)
        self.assertIn("owner-handoff-proof.json", handoff)
        self.assertIn("road-contact-rider", handoff)
        self.assertIn("$proof.viewmode -ne 'VMI_LIT'", handoff)
        self.assertIn("$proof.lighting_status -ne 'PASS'", handoff)
        self.assertIn("[double]$proof.directional_light_intensity -le 0.0", handoff)
        self.assertIn("[double]$proof.skylight_intensity -le 0.0", handoff)
        self.assertIn(
            "$proof.bob_mode -ne 'INSPECTOR_PLUS_TRANSIENT_CUT_AND_VERTICAL_SUPPORT'",
            handoff,
        )
        self.assertIn("$proof.cut_patch_applied -ne $true", handoff)
        self.assertIn("$proof.cut_patch_layer -ne 'Road_Earthworks'", handoff)
        self.assertIn("OWNER HANDOFF PASS", handoff)

        bootstrap = (ROOT / "Content/Python/init_unreal.py").read_text(encoding="utf-8")
        self.assertIn('YACS_OWNER_HANDOFF") == "1"', bootstrap)
        self.assertIn("scripts.ue.owner_handoff_startup", bootstrap)
        startup = (ROOT / "scripts/ue/owner_handoff_startup.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("unreal.ViewModeIndex.VMI_LIT", startup)
        self.assertIn("unreal.DirectionalLight", startup)
        self.assertIn("unreal.SkyLight", startup)
        self.assertIn('"lighting_status"', startup)
        self.assertIn('"INSPECTOR_PLUS_TRANSIENT_CUT_AND_VERTICAL_SUPPORT"', startup)
        self.assertIn('"cut_patch_applied"', startup)
        self.assertIn("apply_cut_patch", startup)

        self.assertIn(
            "if: ${{ always() && !inputs.region_terrain_import }}",
            self.workflow,
        )
        importer = (ROOT / "scripts/ue/Invoke-YacsRegionTerrainImport.ps1").read_text()
        self.assertIn("-AbsLog=", importer)
        self.assertIn("$LogName + '.engine.log'", importer)
        self.assertIn("Evidence directory already exists", importer)
        self.assertIn("capture.engine.log", self.workflow)

    def test_workflow_has_static_runtime_compile_paths(self):
        for token in (
            "compile_fingerprint:",
            "proof_fingerprint:",
            "steps.cache.outputs.mode != 'static'",
            "YACS_UNREAL_EXECUTION_MODE -eq 'compile'",
            "YACS_UNREAL_EXECUTION_MODE -eq 'runtime'",
            "YACS_UNREAL_COMPILE_KIND",
            "steps.cache.outputs.compile_kind",
            "-SkipBuild",
            "STATIC Unreal equivalence proof",
        ):
            self.assertIn(token, self.workflow)

    def test_cache_requires_engine_binary_and_fingerprint_evidence(self):
        for token in (
            "UnrealEditor-YetAnotherCyclingSim.dll",
            "UnrealEditor-YetAnotherCyclingSimEditor.dll",
            "Resolve-YacsUnrealBuildEnvironment.ps1",
            "compile-fingerprint-mismatch",
            "proof-fingerprint-mismatch",
            "expected-binary-missing",
            "environment-identity-mismatch",
            "environment-identity-unresolved",
            "invalid-cache-state-shape",
            "verified-equivalent-proof",
            "PreviousStateInvalidated",
            "$State.CompilePassed = $false",
            "$State.ProofPassed = $false",
            "compile_kind=$CompileKind",
        ):
            self.assertIn(token, self.cache)

    def test_compile_cache_distinguishes_warm_from_cold(self):
        for token in (
            "$CompileKind = 'cold'",
            "$CompileKind = 'warm'",
            "compile-fingerprint-mismatch",
            "expected-binary-missing",
            "$Purge = $false",
            "cache-schema-mismatch",
            "environment-identity-mismatch",
            "$Purge = $true",
            "ToolchainIdentity",
            "EnvironmentIdentity",
            "CompletedCompileKind",
        ):
            self.assertIn(token, self.cache)

        # Source/graph changes must stay incremental; only environment/cache
        # trust failures may request destructive cleanup.
        mismatch = self.cache.index("compile-fingerprint-mismatch")
        warm = self.cache.rfind("$CompileKind = 'warm'", 0, mismatch)
        purge_false = self.cache.find("$Purge = $false", mismatch)
        self.assertGreaterEqual(warm, 0)
        self.assertGreater(purge_false, mismatch)

    def test_engine_identity_has_one_project_association_authority(self):
        for token in (
            "EngineAssociation",
            "Build.version",
            "Build.bat",
            "UnrealEditor-Cmd.exe",
            "BuildVersionSha256",
            "BuildBatSha256",
            "UnrealEditorCmdSha256",
            "Identity = $Identity",
        ):
            self.assertIn(token, self.engine)
        self.assertIn("Resolve-YacsUnrealBuildEnvironment -ProjectPath", self.cache)
        self.assertIn("Resolve-YacsUnrealEngine.ps1", self.environment)
        self.assertIn("Resolve-YacsUnrealEngine -ProjectPath", self.environment)
        self.assertIn("Resolve-YacsUnrealEngine.ps1", self.preflight)
        self.assertIn("Resolve-YacsUnrealEngine -ProjectPath", self.preflight)
        self.assertNotIn("$SearchDirs = @(", self.preflight)
        self.assertNotIn("function Read-EngineVersion", self.preflight)

    def test_environment_identity_is_shared_and_toolchain_aware(self):
        for token in (
            "Resolve-YacsUnrealEngine.ps1",
            "Resolve-YacsUnrealToolchain",
            "clSha256",
            "linkSha256",
            "rcSha256",
            "Resolve-YacsUnrealBuildEnvironment",
            "Identity = $Identity",
        ):
            self.assertIn(token, self.environment)
        self.assertIn("Resolve-YacsUnrealBuildEnvironment.ps1", self.cache)
        self.assertNotIn("function Resolve-YacsToolchainIdentity", self.cache)

    def test_workspace_lock_cleanup_knows_warm_worktree(self):
        cleanup = (
            ROOT / "scripts" / "ci" / "Release-YacsUnrealWorkspaceLocks.ps1"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "_unreal-ci-warm/Saved/Logs/YetAnotherCyclingSim.log",
            cleanup,
        )

    def test_cache_records_exact_head_equivalence_evidence(self):
        for token in (
            "Head = $ExpectedHead",
            "CompileFingerprint = $ExpectedCompileFingerprint",
            "ProofFingerprint = $ExpectedProofFingerprint",
            "PreviousProofHead = $PreviousProofHead",
            "ProofHead = $ExpectedHead",
        ):
            self.assertIn(token, self.cache)


if __name__ == "__main__":
    unittest.main()
