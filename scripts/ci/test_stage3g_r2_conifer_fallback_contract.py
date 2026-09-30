from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "scripts" / "assets" / "stage3g_polyhaven.json"
PROFILE = ROOT / "scripts" / "ue" / "stage3g_profile_fir_tree.py"
WRAPPER = ROOT / "scripts" / "ue" / "Invoke-YacsStage3GR2FirProfile.ps1"
RETIRED_WORKFLOW = ROOT / ".github" / "workflows" / "stage3g-r2-fir-profile.yml"


class Stage3GR2ConiferFallbackContractTests(unittest.TestCase):
    def test_fir_sapling_is_curated_but_not_preapproved(self):
        payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
        small = next(item for item in payload["assets"] if item["id"] == "fir_sapling")
        medium = next(
            item for item in payload["assets"] if item["id"] == "fir_sapling_medium"
        )
        self.assertEqual(small["stage"], "3G")
        self.assertEqual(medium["stage"], "3G")
        self.assertTrue(small["enabled"])
        self.assertTrue(medium["enabled"])
        self.assertIn("mass-scatter", medium["role"].lower())
        self.assertIn("profil", medium["notes"].lower())

    def test_profiler_is_asset_parameterized(self):
        profile = PROFILE.read_text(encoding="utf-8")
        wrapper = WRAPPER.read_text(encoding="utf-8")
        self.assertIn("YACS_STAGE3G_PROFILE_ASSET_ID", profile)
        self.assertIn("$AssetId = 'fir_tree_01'", wrapper)
        self.assertIn("YACS_STAGE3G_PROFILE_ASSET_ID", wrapper)
        self.assertIn("$Profile.asset_id -ne $AssetId", wrapper)

    def test_historical_profile_workflow_stays_retired(self):
        self.assertFalse(RETIRED_WORKFLOW.exists())


if __name__ == "__main__":
    unittest.main()
