from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "reusable-unreal.yml"
CACHE = ROOT / "scripts" / "ci" / "Resolve-YacsUnrealCiCache.ps1"


class UnrealCiCacheContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")
        cls.cache = CACHE.read_text(encoding="utf-8")

    def test_workflow_uses_serialized_warm_worktree_without_destructive_clean(self):
        for token in (
            "group: yacs-unreal-ci-${{ github.repository }}",
            "YACS_UNREAL_WORKTREE: _unreal-ci-warm",
            "clean: false",
            "git clean -ffd",
            "Resolve verified Unreal execution mode",
        ):
            self.assertIn(token, self.workflow)
        self.assertNotIn("git clean -ffdx", self.workflow)

    def test_workflow_has_static_runtime_compile_paths(self):
        for token in (
            "compile_fingerprint:",
            "proof_fingerprint:",
            "steps.cache.outputs.mode != 'static'",
            "YACS_UNREAL_EXECUTION_MODE -eq 'compile'",
            "YACS_UNREAL_EXECUTION_MODE -eq 'runtime'",
            "-SkipBuild",
            "STATIC Unreal equivalence proof",
        ):
            self.assertIn(token, self.workflow)

    def test_cache_requires_engine_binary_and_fingerprint_evidence(self):
        for token in (
            "UnrealEditor-YetAnotherCyclingSim.dll",
            "UnrealEditor-YetAnotherCyclingSimEditor.dll",
            "Engine/Build/Build.version",
            "compile-fingerprint-mismatch",
            "proof-fingerprint-mismatch",
            "expected-binary-missing",
            "engine-identity-mismatch",
            "invalid-cache-state-shape",
            "verified-equivalent-proof",
        ):
            self.assertIn(token, self.cache)

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
