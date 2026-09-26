from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "ue" / "Invoke-YacsStage3GAuthoring.ps1"


class Stage3GAuthoringOutputContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = SCRIPT.read_text(encoding="utf-8")

    def test_material_phase_validates_authored_files_not_stdout_marker(self):
        self.assertIn("$ExpectedMaterialAssets = @(", self.script)
        self.assertIn("M_Stage3G_Grass.uasset", self.script)
        self.assertIn("MI_Stage3G_Water.uasset", self.script)
        self.assertIn("Stage 3G material authoring outputs: PASS", self.script)
        self.assertNotIn("Stage 3G material success marker missing.", self.script)

    def test_world_phase_uses_explicit_proof_file(self):
        self.assertIn("YACS_STAGE3G_WORLD_PROOF", self.script)
        self.assertIn("stage3g_world_authoring_proof.txt", self.script)
        self.assertIn("Stage 3G world authoring proof: PASS.", self.script)
        self.assertNotIn(
            "Stage 3G world-authoring success marker missing.", self.script
        )

    def test_artifact_root_is_canonicalized_before_world_proof(self):
        repo_anchor = "$ArtifactRoot = Join-Path -Path $RepoRoot -ChildPath $ArtifactRoot"
        canonicalize = "$ArtifactRoot = (Resolve-Path -LiteralPath $ArtifactRoot).Path"
        world_proof = "$WorldProof = Join-Path -Path $ArtifactRoot"
        self.assertIn(repo_anchor, self.script)
        self.assertIn(canonicalize, self.script)
        self.assertIn(world_proof, self.script)
        self.assertLess(self.script.index(repo_anchor), self.script.index(canonicalize))
        self.assertLess(self.script.index(canonicalize), self.script.index(world_proof))

    def test_unreal_process_still_fails_closed_on_nonzero_exit(self):
        self.assertIn("if ($ExitCode -ne 0)", self.script)
        self.assertIn("Unreal process failed with exit code $ExitCode", self.script)


if __name__ == "__main__":
    unittest.main()
