from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


class PassoGiauLandscapeAuthorContractTest(unittest.TestCase):
    def test_cpp_import_contract_is_isolated_and_exact(self) -> None:
        cpp = read(
            "Source/YetAnotherCyclingSim/Private/Editor/"
            "CyclingPassoGiauLandscapeSpikeCommandlet.cpp"
        )
        self.assertIn(
            "/Game/Prototype/Maps/L_PassoGiauTerrainSpike",
            cpp,
        )
        self.assertNotIn("/Game/Prototype/Maps/L_CyclingTest", cpp)
        self.assertIn("LandscapeVertices = 1009", cpp)
        self.assertIn("NumSubsections = 2", cpp)
        self.assertIn("SubsectionSizeQuads = 63", cpp)
        self.assertIn(
            "ExpectedComponentCount = ExpectedComponentGrid * ExpectedComponentGrid",
            cpp,
        )
        self.assertIn("ExpectedComponentGrid = 8", cpp)
        self.assertIn("XYScaleCmPerVertex = 793.650794", cpp)
        self.assertIn("ZScale = 301.26543", cpp)
        self.assertIn("LocationZCm = 194259.253", cpp)
        self.assertIn(
            "encoded height-domain proof",
            read("scripts/ue/Invoke-YacsPassoGiauLandscapeSpike.ps1"),
        )

    def test_map_prep_creates_blank_isolated_spike_without_canonical_load(self) -> None:
        script = read("scripts/ue/stage3g_prepare_passo_giau_landscape_map.py")
        self.assertIn(
            'SPIKE_MAP = "/Game/Prototype/Maps/L_PassoGiauTerrainSpike"',
            script,
        )
        self.assertIn(
            "level_subsystem.new_level(SPIKE_MAP, is_partitioned_world=False)",
            script,
        )
        self.assertNotIn("duplicate_asset", script)
        self.assertNotIn("/Game/Prototype/Maps/L_CyclingTest", script)
        self.assertIn('"canonical_map_loaded": False', script)
        self.assertIn('"canonical_map_mutated": False', script)

    def test_wrapper_fails_closed_on_canonical_map_and_mutations(self) -> None:
        wrapper = read("scripts/ue/Invoke-YacsPassoGiauLandscapeSpike.ps1")
        self.assertIn("$CanonicalHashBefore", wrapper)
        self.assertIn("$CanonicalHashAfter", wrapper)
        self.assertIn(
            "L_CyclingTest changed during isolated Passo Giau authoring",
            wrapper,
        )
        self.assertIn(
            "$Unexpected = @($TrackedChanges | Where-Object { $_ -ne $SpikeMapRelative })",
            wrapper,
        )
        self.assertIn("visual_acceptance = 'PENDING_HUMAN_REVIEW'", wrapper)
        self.assertIn("authoritative_route_geometry = $false", wrapper)
        self.assertIn("authoritative_physics = $false", wrapper)

    def test_capture_requires_real_png_and_human_review(self) -> None:
        capture = read("scripts/ue/stage3g_capture_passo_giau_landscape.py")
        self.assertIn("take_high_res_screenshot", capture)
        self.assertIn("res_x=1920", capture)
        self.assertIn("res_y=1080", capture)
        self.assertIn("is_task_done()", capture)
        self.assertIn("set_keep_python_script_alive(True)", capture)
        self.assertIn('"visual_acceptance": "PENDING_HUMAN_REVIEW"', capture)

    def test_workflow_runs_only_on_ue58_and_commits_only_spike_map(self) -> None:
        workflow = read(".github/workflows/passo-giau-r4-1-landscape-author.yml")
        self.assertIn("runs-on: [self-hosted, yacs-ue58]", workflow)
        self.assertIn("lfs: false", workflow)
        self.assertNotIn("git lfs checkout", workflow)
        self.assertNotIn("git lfs fsck", workflow)
        self.assertIn("permissions:\n  contents: write", workflow)
        self.assertIn(
            "$asset = 'Content/Prototype/Maps/L_PassoGiauTerrainSpike.umap'",
            workflow,
        )
        self.assertIn("git diff --cached --name-only", workflow)
        self.assertNotIn("git add -A", workflow)

    def test_editor_build_links_landscape_module(self) -> None:
        build = read("Source/YetAnotherCyclingSim/YetAnotherCyclingSim.Build.cs")
        self.assertIn('"Landscape"', build)


if __name__ == "__main__":
    unittest.main()
