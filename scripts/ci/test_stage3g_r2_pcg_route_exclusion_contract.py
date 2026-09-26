from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "YetAnotherCyclingSim.uproject"
TARGET = ROOT / "Source" / "YetAnotherCyclingSimEditor.Target.cs"
BUILD = ROOT / "Source" / "YetAnotherCyclingSimEditor" / "YetAnotherCyclingSimEditor.Build.cs"
HEADER = ROOT / "Source" / "YetAnotherCyclingSimEditor" / "Public" / "PCG" / "Stage3GRouteExclusionSettings.h"
CPP = ROOT / "Source" / "YetAnotherCyclingSimEditor" / "Private" / "PCG" / "Stage3GRouteExclusionSettings.cpp"
AUTHOR = ROOT / "scripts" / "ue" / "stage3g_author_pcg_route_exclusion.py"
WRAPPER = ROOT / "scripts" / "ue" / "Invoke-YacsStage3GR2PCGRouteExclusion.ps1"


class Stage3GR2PCGRouteExclusionContractTests(unittest.TestCase):
    def test_pcg_bridge_is_editor_only(self):
        project = json.loads(PROJECT.read_text(encoding="utf-8"))
        modules = {row["Name"]: row for row in project["Modules"]}
        self.assertEqual(modules["YetAnotherCyclingSim"]["Type"], "Runtime")
        self.assertEqual(modules["YetAnotherCyclingSimEditor"]["Type"], "Editor")

        target = TARGET.read_text(encoding="utf-8")
        build = BUILD.read_text(encoding="utf-8")
        self.assertIn('ExtraModuleNames.Add("YetAnotherCyclingSimEditor")', target)
        self.assertIn('"PCG"', build)
        self.assertIn('"YetAnotherCyclingSim"', build)

    def test_node_consumes_canonical_route_contract(self):
        header = HEADER.read_text(encoding="utf-8")
        cpp = CPP.read_text(encoding="utf-8")
        self.assertIn("ProtectedHalfWidthM = 4.0", header)
        self.assertIn("TryBuildAlpineJourneyRouteGeometry", cpp)
        self.assertIn("TryEvaluateRouteExclusion", cpp)
        self.assertIn("InPoint.Transform.GetLocation() / 100.0", cpp)
        for forbidden in ("RoadTiles", "Landscape", "ActorLocation", "GetActorTransform"):
            self.assertNotIn(forbidden, cpp)

    def test_authoring_asset_path_and_proof_are_fixed(self):
        author = AUTHOR.read_text(encoding="utf-8")
        wrapper = WRAPPER.read_text(encoding="utf-8")
        self.assertIn("/Game/YACS/WorldGen/PCG", author)
        self.assertIn('ASSET_NAME = "PCG_RouteExclusion"', author)
        self.assertIn("PROTECTED_HALF_WIDTH_M = 4.0", author)
        self.assertIn("PCG_RouteExclusion.uasset", wrapper)
        self.assertIn("FRouteGeometryProfile", wrapper)


if __name__ == "__main__":
    unittest.main()
