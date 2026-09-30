from __future__ import annotations

from pathlib import Path
import unittest


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
        ):
            self.assertIn(token, self.workflow)

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
            "Resolve-YacsUnrealEngine.ps1",
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
        self.assertIn("Resolve-YacsUnrealEngine -ProjectPath", self.cache)
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
