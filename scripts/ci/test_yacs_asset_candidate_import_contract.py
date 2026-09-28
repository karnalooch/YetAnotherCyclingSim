"""Static contract tests for the sandboxed World Authoring candidate importer."""

from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
IMPORTER = ROOT / "scripts" / "ue" / "yacs_asset_candidate_import.py"


class YacsAssetCandidateImportContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = IMPORTER.read_text(encoding="utf-8")

    def test_generated_content_root_is_fixed(self) -> None:
        self.assertIn(
            'DESTINATION_ROOT = "/Game/Generated/YACS/Library/Candidates/PolyHaven"',
            self.text,
        )
        self.assertIn('path.startswith("/Game/Generated/YACS/")', self.text)

    def test_only_discovery_candidates_are_auto_imported(self) -> None:
        self.assertIn(
            'source_mode != "discovery" or lifecycle != "acquired_candidate"',
            self.text,
        )
        self.assertIn('"auto_approved": False', self.text)
        self.assertIn('"automatic_acceptance": False', self.text)

    def test_approved_catalog_assets_are_not_reimported(self) -> None:
        self.assertIn(
            'source_mode == "catalog" and lifecycle == "approved"',
            self.text,
        )
        self.assertIn('"reason": "already_qualified"', self.text)

    def test_source_path_is_confined_to_cache(self) -> None:
        self.assertIn("target.relative_to(cache_root.resolve())", self.text)
        self.assertIn("selection-plan source path escapes cache", self.text)

    def test_provider_is_fail_closed(self) -> None:
        self.assertIn('provider != "polyhaven"', self.text)
        self.assertIn("SAFE_ID.fullmatch(asset_id)", self.text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
