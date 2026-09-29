"""Unit tests for the YACS semantic asset library."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
ASSET_DIR = ROOT / "scripts" / "assets"
MODULE_PATH = ASSET_DIR / "yacs_asset_library.py"

if str(ASSET_DIR) not in sys.path:
    sys.path.insert(0, str(ASSET_DIR))

SPEC = importlib.util.spec_from_file_location("yacs_asset_library", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("could not load yacs_asset_library")
LIB = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = LIB
SPEC.loader.exec_module(LIB)


def base_catalog() -> dict:
    return {
        "schema_version": 1,
        "generated_content_root": "/Game/Generated/YACS",
        "providers": {
            "polyhaven": {
                "name": "Poly Haven",
                "api_base": "https://api.polyhaven.com",
                "asset_license": "CC0-1.0",
                "allowed_download_hosts": ["dl.polyhaven.org"],
                "credit": "Source assets are provided by Poly Haven.",
            }
        },
        "assets": [
            {
                "id": "approved_fir",
                "semantic_roles": ["mass_conifer", "alpine_conifer"],
                "lifecycle_status": "approved",
                "source": {
                    "provider": "polyhaven",
                    "asset_id": "fir_sapling_medium",
                },
                "ue_asset_path": "/Game/Prototype/Fir",
                "capabilities": {
                    "pcg_mass_scatter": True,
                    "hero_near_camera": False,
                    "has_lods": True,
                },
                "cost": {"profile": "mass_forest", "notes": "test"},
            }
        ],
    }


def base_preset() -> dict:
    return {
        "schema_version": 1,
        "id": "test_grove",
        "seed": 42,
        "generated_root": "/Game/Generated/YACS/Test",
        "composition": {
            "type": "forest_patch",
            "size_m": [10.0, 10.0],
        },
        "asset_policy": {
            "preferred_lifecycle_status": ["approved"],
            "auto_acquire_missing": True,
            "allowed_providers": ["polyhaven"],
            "allowed_licenses": ["CC0-1.0"],
            "max_download_mib": 512,
            "resolution": "2k",
        },
        "asset_slots": [
            {
                "slot": "mass_conifer",
                "kind": "model",
                "semantic_roles": ["mass_conifer", "alpine_conifer"],
                "search_terms": ["fir", "spruce", "conifer", "tree"],
                "preferred_source_ids": [
                    "fir_sapling_medium",
                    "fir_sapling",
                ],
                "excluded_source_ids": ["fir_tree_01"],
                "prefer_lods": True,
                "max_polycount": 180000,
                "required_maps": ["diffuse", "normal_dx", "roughness"],
            }
        ],
        "pcg": {
            "graph": "/Game/YACS/WorldGen/PCG/PCG_Forest",
            "route_exclusion_graph": "/Game/YACS/WorldGen/PCG/PCG_RouteExclusion",
            "generation_mode": "transient_proof",
        },
    }


class YacsAssetLibraryTests(unittest.TestCase):
    def test_approved_catalog_asset_wins_without_live_discovery(self) -> None:
        catalog = base_catalog()
        preset = base_preset()

        LIB.validate_catalog(catalog)
        LIB.validate_preset(preset, catalog)
        selections, discovery = LIB.select_slots(catalog, preset, None)

        self.assertEqual(len(selections), 1)
        self.assertEqual(selections[0].source, "catalog")
        self.assertEqual(selections[0].provider_asset_id, "fir_sapling_medium")
        self.assertEqual(discovery, {})

    def test_live_ranking_is_deterministic_and_prefers_known_light_fir(self) -> None:
        slot = base_preset()["asset_slots"][0]
        payload = {
            "spruce_generic": {
                "type": 2,
                "name": "Spruce Tree",
                "description": "A conifer forest tree.",
                "category": "Nature/Trees",
                "tags": ["spruce", "tree", "conifer"],
                "polycount": 42000,
                "lods": True,
            },
            "fir_sapling_medium": {
                "type": 2,
                "name": "Fir Sapling Medium",
                "description": "Medium fir tree for forests.",
                "category": "Nature/Trees",
                "tags": ["fir", "tree"],
                "polycount": 90000,
                "lods": True,
            },
        }

        first = LIB.rank_polyhaven_assets(payload, slot)
        second = LIB.rank_polyhaven_assets(dict(reversed(list(payload.items()))), slot)

        self.assertEqual(
            [item.asset_id for item in first],
            [item.asset_id for item in second],
        )
        self.assertEqual(first[0].asset_id, "fir_sapling_medium")
        self.assertIn("preferred_source_id", first[0].reasons)

    def test_excluded_heavy_tree_is_never_ranked_for_mass_scatter(self) -> None:
        slot = base_preset()["asset_slots"][0]
        payload = {
            "fir_tree_01": {
                "type": 2,
                "name": "Fir Tree 01",
                "description": "Hero fir tree.",
                "category": "Nature/Trees",
                "tags": ["fir", "tree", "conifer"],
                "polycount": 10000,
                "lods": True,
            }
        }

        self.assertEqual(LIB.rank_polyhaven_assets(payload, slot), [])

    def test_polycount_cap_rejects_oversized_candidate(self) -> None:
        slot = base_preset()["asset_slots"][0]
        payload = {
            "mega_fir": {
                "type": 2,
                "name": "Mega Fir Tree",
                "description": "A fir tree.",
                "category": "Nature/Trees",
                "tags": ["fir", "tree"],
                "polycount": 180001,
                "lods": True,
            }
        }

        self.assertEqual(LIB.rank_polyhaven_assets(payload, slot), [])

    def test_generated_root_must_stay_inside_yacs_sandbox(self) -> None:
        with self.assertRaisesRegex(ValueError, "generated_root"):
            LIB.validate_generated_root("/Game/Prototype/Maps")

    def test_license_gate_is_fail_closed(self) -> None:
        catalog = base_catalog()
        preset = base_preset()
        preset["asset_policy"]["allowed_licenses"] = ["MIT"]

        with self.assertRaisesRegex(ValueError, "is not allowed"):
            LIB.validate_preset(preset, catalog)

    def test_download_host_is_allowlisted(self) -> None:
        LIB.validate_download_url(
            "https://dl.polyhaven.org/file/tree.fbx",
            {"dl.polyhaven.org"},
        )
        with self.assertRaisesRegex(ValueError, "not allowlisted"):
            LIB.validate_download_url(
                "https://example.invalid/tree.fbx",
                {"dl.polyhaven.org"},
            )

    def test_invalid_provider_asset_id_is_ignored(self) -> None:
        slot = base_preset()["asset_slots"][0]
        payload = {
            "../escape": {
                "type": 2,
                "name": "Fir Tree",
                "category": "Trees",
                "tags": ["fir"],
                "polycount": 1000,
                "lods": True,
            }
        }
        self.assertEqual(LIB.rank_polyhaven_assets(payload, slot), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
