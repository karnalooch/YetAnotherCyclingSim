"""Hosted tests for Blender Material Forge reference admission."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from scripts.blender import material_forge_reference_contract as contract


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class MaterialForgeReferenceContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.rock = self._variant("regional_limestone", "base", 4.0)
        self.soil = self._variant("mediterranean_soil", "fine", 4.0)

    def _variant(self, family: str, variant: str, tile: float) -> Path:
        root = self.root / family / variant
        export = root / "export"
        export.mkdir(parents=True)
        maps = {}
        for channel in contract.REQUIRED_CHANNELS:
            path = export / f"YACS_Material_{channel}.png"
            payload = f"{family}:{variant}:{channel}".encode()
            path.write_bytes(payload)
            maps[channel] = {
                "path": f"export/{path.name}",
                "sha256": _sha(payload),
            }

        (root / "validation.json").write_text(
            json.dumps(
                {
                    "status": contract.EXPECTED_STATUS,
                    "family": family,
                    "variant": variant,
                    "normal_convention": contract.EXPECTED_NORMAL,
                    "semantic_owner": contract.EXPECTED_SEMANTIC_OWNER,
                    "world_semantics_generated": False,
                    "maps": maps,
                }
            ),
            encoding="utf-8",
        )
        (root / "provenance.json").write_text(
            json.dumps(
                {
                    "family": family,
                    "variant": variant,
                    "tile_metres": tile,
                    "normal_convention": contract.EXPECTED_NORMAL,
                    "semantic_owner": contract.EXPECTED_SEMANTIC_OWNER,
                    "world_semantics_generated": False,
                }
            ),
            encoding="utf-8",
        )
        return root

    def test_admits_exact_cpu_validated_pair(self):
        plan = contract.build_reference_plan(self.rock, self.soil)
        self.assertEqual(plan["status"], "REFERENCE_PLAN_READY")
        self.assertEqual(plan["tile_metres"], 4.0)
        self.assertEqual(len(plan["views"]), 4)
        self.assertFalse(plan["height_displacement_used"])
        self.assertFalse(plan["world_semantics_changed"])
        self.assertEqual(len(plan["input_fingerprint"]), 64)

    def test_rejects_map_hash_drift(self):
        path = self.rock / "export" / "YACS_Material_BaseColor.png"
        path.write_bytes(b"drift")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            contract.build_reference_plan(self.rock, self.soil)

    def test_rejects_unadmitted_validation_status(self):
        path = self.soil / "validation.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["status"] = "GRAPH_READY_RENDER_PENDING"
        path.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "not CPU-admitted"):
            contract.build_reference_plan(self.rock, self.soil)

    def test_rejects_semantic_ownership_drift(self):
        path = self.rock / "validation.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["semantic_owner"] = "Material Forge"
        path.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "semantic owner"):
            contract.build_reference_plan(self.rock, self.soil)

    def test_rejects_mismatched_physical_tile_scale(self):
        path = self.soil / "provenance.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["tile_metres"] = 2.0
        path.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "same physical tile scale"):
            contract.build_reference_plan(self.rock, self.soil)


if __name__ == "__main__":
    unittest.main()
