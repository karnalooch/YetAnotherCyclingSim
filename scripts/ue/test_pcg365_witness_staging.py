"""Portable contract checks for the read-only/isolated PCG365 witness stager.

These offline checks intentionally do not run PowerShell, Unreal, MCP or UBT.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/ue/Prepare-YacsPcgWitnessStage.ps1"
DOCS = ROOT / "docs/tooling/PCG365_NATIVE_WITNESS_DEPLOYMENT.md"


class NativeWitnessStageContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = SCRIPT.read_text(encoding="utf-8")
        cls.docs = DOCS.read_text(encoding="utf-8")

    def test_inspect_is_the_default_and_buildstage_is_explicit(self):
        self.assertIn("[ValidateSet('Inspect', 'BuildStage')]", self.script)
        self.assertIn("$Action = 'Inspect'", self.script)
        self.assertIn("if ($Action -ceq 'Inspect')", self.script)

    def test_exact_source_and_worktree_guards(self):
        self.assertIn("git -C $ProjectRoot rev-parse HEAD", self.script)
        self.assertIn("git -C $ProjectRoot status --porcelain --untracked-files=no", self.script)
        self.assertIn("Assert-YacsBuildIsolation -ProjectPath $ProjectFile", self.script)
        self.assertIn("The build candidate DLL is already loaded", self.script)

    def test_accepted_world_hash_is_checked_on_both_sides(self):
        self.assertIn("CANONICAL_CHECKPOINT_MUTATED", self.script)
        self.assertIn("CANONICAL_CHECKPOINT_MISSING", self.docs)
        self.assertIn("$checkpoint = @(Check-CanonicalCheckpoint)", self.script)
        self.assertIn("$checkpointAfter = @(Check-CanonicalCheckpoint)", self.script)

    def test_no_mutation_of_owner_live_release(self):
        self.assertIn("STAGED_NOT_DEPLOYED", self.script)
        self.assertIn("owner_restart_approved = $false", self.script)
        self.assertIn("native_reader_loaded = $false", self.script)
        self.assertNotIn("Stop-Process", self.script)
        self.assertNotIn("git reset --hard", self.script)
        self.assertNotIn("git clean", self.script)
        self.assertNotIn("Restart-Computer", self.script)
        self.assertNotIn("Live Host executable replacement", self.script)

    def test_compilation_and_staging_require_fresh_verified_artifacts(self):
        self.assertIn("No freshly linked DLL for requested exact HEAD", self.script)
        self.assertIn("Editor and engine BuildId mismatch", self.script)
        self.assertIn("Staged byte identity drift", self.script)
        self.assertIn("never overwrite it", self.script)
        self.assertIn("'-NoHotReloadFromIDE'", self.script)

    def test_docs_keep_external_witness_and_generation_gates_blocked(self):
        self.assertIn("process-local", self.docs)
        self.assertIn("newly generated UUID", self.docs)
        self.assertIn("SAFE_MCP_BLOCKED", self.docs)
        self.assertIn("WHOLE_AREA_BLOCKED", self.docs)


if __name__ == "__main__":
    unittest.main()
