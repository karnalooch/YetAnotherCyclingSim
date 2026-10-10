"""Synthetic source-receipt tests; these establish no render or native proof."""

from __future__ import annotations

import hashlib
import json
import shutil
import struct
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest.mock import patch

from scripts.assets import road_material_contract as contract


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def _png() -> bytes:
    def chunk(name: bytes, body: bytes) -> bytes:
        return (
            struct.pack(">I", len(body))
            + name
            + body
            + struct.pack(">I", zlib.crc32(name + body))
        )

    ihdr = struct.pack(">IIBBBBB", 2048, 2048, 8, 2, 0, 0, 0)
    pixels = (b"\x00" + b"\x78\x80\xff" * 2048) * 2048
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(pixels))
        + chunk(b"IEND", b"")
    )


def _synthetic_bundle(root: Path) -> None:
    """Mock retained CPU/Godot assertions; Height is deliberately not real EXR."""
    (root / "export").mkdir(parents=True)
    shutil.copyfile(contract.DEFAULT_CATALOG, root / "catalog.json")
    graph = {
        "seed_int": 101,
        "nodes": [
            {
                "name": "Limestone_Form",
                "parameters": {"seed": 101, "fractures": 0.62, "pores": 0.22},
            },
            {"name": "Limestone_Color", "parameters": {"brightness": 0.3}},
            {"name": "Height_Normal", "parameters": {"strength": 0.48}},
            {
                "name": "Limestone_Response",
                "shader_model": {
                    "outputs": [
                        {
                            "f": "clamp(0.820000+0.070000*$variation($uv)+0.030000*$crack($uv)-0.060000*$pore($uv),0.0,1.0)"
                        }
                    ]
                },
            },
        ],
    }
    _write(root / "Material.ptex", graph)
    (root / "MATERIAL_MAKER_LICENSE.txt").write_text(
        "Synthetic MIT notice fixture", encoding="utf-8"
    )
    engine = {
        "major": 4,
        "minor": 7,
        "patch": 2,
        "hash": contract.GODOT_SOURCE,
        "build": "official",
        "status": "stable",
    }
    provenance = {
        "status": contract.STATUS,
        "family": contract.FAMILY,
        "variant": "base",
        "seed": 101,
        "tile_metres": 4,
        "parameters": {**contract.PARAMETERS, "refinement": {}, "landscape": {}},
        "semantic_owner": "PCG/PCGEx",
        "world_semantics_generated": False,
        "normal_convention": "DirectX",
        "local_mask_channels": contract.MASKS,
        "generator": "yacs-material-forge",
        "generator_version": 4,
        "graph": "Material.ptex",
        "graph_sha256": _sha(root / "Material.ptex"),
        "recipe": "scripts/assets/material_forge.py",
        "expected_maps": list(contract.SUFFIXES.values()),
        "render_receipt": "render-receipt.json",
        "upstreams": {
            "material_maker": {"validated_source_commit": contract.MM_SOURCE},
            "godot": {"commit": contract.GODOT_SOURCE},
        },
        "license": "MIT",
        "notice": "MATERIAL_MAKER_LICENSE.txt",
    }
    validation = {
        "status": contract.STATUS,
        "family": contract.FAMILY,
        "variant": "base",
        "semantic_owner": "PCG/PCGEx",
        "world_semantics_generated": False,
        "normal_convention": "DirectX",
        "local_mask_channels": contract.MASKS,
        "geometry_changed": False,
        "visual_accepted": False,
        "performance_accepted": False,
        "normal_length_error_p99": 0.008,
        "maps": {},
    }
    native = {"valid": True, "engine": engine, "images": {}}
    png = _png()
    for channel, suffix in contract.SUFFIXES.items():
        relative = "export/YACS_Material_" + suffix
        (root / relative).write_bytes(
            b"\x76\x2f\x31\x01synthetic_height" if channel == "Height" else png
        )
        digest = _sha(root / relative)
        row = {"path": relative, "sha256": digest}
        if channel != "Height":
            row.update(
                size=[2048, 2048],
                wrap_step_x=0.002,
                wrap_step_y=0.002,
                interior_step_x=0.002,
                interior_step_y=0.002,
            )
        validation["maps"][channel] = row
        native["images"][suffix] = {
            "width": 2048,
            "height": 2048,
            "sha256": digest,
            "format": 5,
        }
    _write(root / "provenance.json", provenance)
    _write(root / "validation.json", validation)
    _write(root / "export/YACS_Material_native-check.json", native)
    _write(
        root / "render-receipt.json",
        {
            "producer": "Material Maker source runtime under pinned Godot",
            "source_commit": contract.MM_SOURCE,
            "source_class_cache_sha256": "a" * 64,
            "source_imported_file_count": 249,
            "godot_sha256": "b" * 64,
            "graph_sha256": _sha(root / "Material.ptex"),
            "engine": engine,
            "command": [
                "D:/tools/Godot.exe",
                "--path",
                "D:/tools/material-maker",
                "--script",
                "D:/project/scripts/assets/render_material_forge.gd",
                "--",
                "D:/proof/Material.ptex",
                "D:/proof/export/YACS_Material",
                "2048",
            ],
            "exit_code": 0,
            "upstream_diagnostics": [],
            "validation_sha256": _sha(root / "validation.json"),
            "status": contract.STATUS,
        },
    )


class RoadAsphaltSourceContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.template = tempfile.TemporaryDirectory()
        _synthetic_bundle(Path(cls.template.name))

    @classmethod
    def tearDownClass(cls) -> None:
        cls.template.cleanup()

    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name) / "base"
        shutil.copytree(self.template.name, self.root)

    def check(self) -> dict:
        return contract.check_asphalt_source(self.root, self.root / "catalog.json")

    def edit(self, name: str, change) -> None:
        path = self.root / name
        data = json.loads(path.read_bytes())
        change(data)
        _write(path, data)

    def refresh_render_validation(self) -> None:
        self.edit(
            "render-receipt.json",
            lambda data: data.update(
                validation_sha256=_sha(self.root / "validation.json")
            ),
        )

    def test_synthetic_receipt_is_bounded_read_only_and_never_native_admission(self):
        before = {
            p.relative_to(self.root).as_posix(): _sha(p)
            for p in self.root.rglob("*")
            if p.is_file()
        }
        result = self.check()
        self.assertEqual(set(result["maps"]), set(contract.SUFFIXES))
        self.assertEqual(result["tile_size_cm"], 400)
        self.assertEqual(result["visual_status"], "PENDING_FINAL_M3")
        for key in (
            "unreal_verified",
            "two_run_replay_verified",
            "visual_accepted",
            "performance_pass",
            "geometry_changed",
            "height_displacement_used",
            "producer_binary_independently_verified",
        ):
            self.assertIs(result[key], False)
        self.assertEqual(result, self.check())
        self.assertLess(len(json.dumps(result)), 16 * 1024)
        self.assertEqual(
            before,
            {
                p.relative_to(self.root).as_posix(): _sha(p)
                for p in self.root.rglob("*")
                if p.is_file()
            },
        )

    def test_legacy_two_metre_recipe_cannot_be_relabelled_as_current(self):
        self.edit("provenance.json", lambda data: data.update(tile_metres=2.0))
        with self.assertRaisesRegex(ValueError, "source tile_metres"):
            self.check()

    def test_validation_variant_must_match_provenance(self):
        self.edit("validation.json", lambda data: data.update(variant="worn"))
        self.refresh_render_validation()
        with self.assertRaisesRegex(ValueError, "family/variant"):
            self.check()

    def test_height_tamper_after_cpu_validation_is_rejected(self):
        with (self.root / "export/YACS_Material_Height.exr").open("ab") as stream:
            stream.write(b"changed")
        with self.assertRaisesRegex(ValueError, "Map changed.*Height"):
            self.check()

    def test_missing_fifth_map_is_rejected(self):
        (self.root / "export/YACS_Material_Height.exr").unlink()
        with self.assertRaises(ValueError):
            self.check()

    def test_native_dimensions_must_be_measured_2048(self):
        self.edit(
            "export/YACS_Material_native-check.json",
            lambda data: data["images"]["Height.exr"].update(width=1024),
        )
        with self.assertRaisesRegex(ValueError, "Native resolution"):
            self.check()

    def test_actual_png_dimensions_must_match_receipts(self):
        path = self.root / "export/YACS_Material_BaseColor.png"
        raw = path.read_bytes()
        path.write_bytes(raw[:16] + struct.pack(">II", 1024, 2048) + raw[24:])
        digest = _sha(path)
        self.edit(
            "validation.json",
            lambda data: data["maps"]["BaseColor"].update(sha256=digest),
        )
        self.edit(
            "export/YACS_Material_native-check.json",
            lambda data: data["images"]["BaseColor.png"].update(sha256=digest),
        )
        self.refresh_render_validation()
        with self.assertRaisesRegex(ValueError, "PNG resolution"):
            self.check()

    def test_nonfinite_values_and_wrong_current_recipe_are_rejected(self):
        for value in (float("nan"), float("inf"), 0, 2, True, "4"):
            with self.subTest(value=value):
                self.edit(
                    "provenance.json",
                    lambda data, value=value: data.update(tile_metres=value),
                )
                with self.assertRaises(ValueError):
                    self.check()

    def test_current_catalog_cannot_authorize_a_different_recipe(self):
        self.edit(
            "catalog.json",
            lambda data: data["families"][0]["variants"][0].update(roughness=0.8),
        )
        self.edit(
            "provenance.json", lambda data: data["parameters"].update(roughness=0.8)
        )
        with self.assertRaisesRegex(ValueError, "catalog roughness"):
            self.check()

    def test_graph_metadata_cannot_hide_a_different_actual_normal_strength(self):
        self.edit(
            "Material.ptex",
            lambda data: data["nodes"][2]["parameters"].update(strength=0.52),
        )
        digest = _sha(self.root / "Material.ptex")
        self.edit("provenance.json", lambda data: data.update(graph_sha256=digest))
        self.edit("render-receipt.json", lambda data: data.update(graph_sha256=digest))
        with self.assertRaisesRegex(ValueError, "graph strength"):
            self.check()

    def test_graph_drift_is_rejected(self):
        self.edit("Material.ptex", lambda data: data.update(seed_int=999))
        with self.assertRaisesRegex(ValueError, "graph hash mismatch"):
            self.check()

    def test_directx_and_geometry_semantics_flags_are_required(self):
        for key, value in (
            ("normal_convention", "OpenGL"),
            ("geometry_changed", True),
            ("world_semantics_generated", True),
            ("visual_accepted", True),
        ):
            with self.subTest(key=key):
                shutil.copyfile(
                    Path(self.template.name) / "validation.json",
                    self.root / "validation.json",
                )
                self.edit(
                    "validation.json",
                    lambda data, key=key, value=value: data.update({key: value}),
                )
                self.refresh_render_validation()
                with self.assertRaises(ValueError):
                    self.check()

    def test_fixed_relative_map_path_rejects_traversal(self):
        self.edit(
            "validation.json",
            lambda data: data["maps"]["BaseColor"].update(path="../outside.png"),
        )
        self.refresh_render_validation()
        with self.assertRaisesRegex(ValueError, "Unexpected map path"):
            self.check()

    def test_symlinked_map_is_rejected(self):
        path = self.root / "export/YACS_Material_BaseColor.png"
        path.unlink()
        try:
            path.symlink_to(self.root / "export/YACS_Material_ORM.png")
        except OSError:
            self.skipTest("Symlink creation unavailable")
        with self.assertRaisesRegex(ValueError, "symlink or reparse"):
            self.check()

    def test_symlinked_source_root_is_rejected(self):
        alias = Path(self.directory.name) / "alias"
        try:
            alias.symlink_to(self.root, target_is_directory=True)
        except OSError:
            self.skipTest("Symlink creation unavailable")
        with self.assertRaisesRegex(ValueError, "symlink or reparse"):
            contract.check_asphalt_source(alias, self.root / "catalog.json")

    def test_duplicate_json_fields_are_rejected(self):
        path = self.root / "provenance.json"
        path.write_text(path.read_text()[:-1] + ',"tile_metres":4}', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Duplicate source JSON"):
            self.check()

    def test_render_validation_link_must_match_actual_bytes(self):
        self.edit(
            "validation.json", lambda data: data.update(normal_length_error_p99=0.009)
        )
        with self.assertRaisesRegex(ValueError, "Render receipt content mismatch"):
            self.check()

    def test_render_must_use_the_actual_pinned_source_and_engine(self):
        self.edit(
            "render-receipt.json", lambda data: data.update(source_commit="0" * 40)
        )
        with self.assertRaisesRegex(ValueError, "Render producer pin"):
            self.check()

    def test_malformed_nested_receipts_return_value_error(self):
        for name, change in (
            ("catalog.json", lambda data: data.update(families=["bad"])),
            ("provenance.json", lambda data: data.update(upstreams=[])),
            ("Material.ptex", lambda data: data["nodes"][0].update(parameters=[])),
        ):
            with self.subTest(name=name):
                shutil.copyfile(Path(self.template.name) / name, self.root / name)
                self.edit(name, change)
                if name == "Material.ptex":
                    self.edit(
                        "provenance.json",
                        lambda data: data.update(
                            upstreams={
                                "material_maker": {
                                    "validated_source_commit": contract.MM_SOURCE
                                },
                                "godot": {"commit": contract.GODOT_SOURCE},
                            },
                            graph_sha256=_sha(self.root / "Material.ptex"),
                        ),
                    )
                with self.assertRaises(ValueError):
                    self.check()
                shutil.copyfile(Path(self.template.name) / name, self.root / name)

    def test_decoder_version_and_failed_render_cannot_be_admitted(self):
        self.edit(
            "export/YACS_Material_native-check.json",
            lambda data: data["engine"].update(patch=1),
        )
        with self.assertRaisesRegex(ValueError, "Godot version"):
            self.check()
        shutil.copyfile(
            Path(self.template.name) / "export/YACS_Material_native-check.json",
            self.root / "export/YACS_Material_native-check.json",
        )
        self.edit("render-receipt.json", lambda data: data.update(exit_code=1))
        with self.assertRaisesRegex(ValueError, "Render receipt did not succeed"):
            self.check()

    def test_native_hash_link_must_match_exact_height(self):
        self.edit(
            "export/YACS_Material_native-check.json",
            lambda data: data["images"]["Height.exr"].update(sha256="0" * 64),
        )
        with self.assertRaisesRegex(ValueError, "Native map hash mismatch"):
            self.check()

    def test_cpu_tiling_failure_is_rejected(self):
        self.edit(
            "validation.json",
            lambda data: data["maps"]["BaseColor"].update(wrap_step_x=0.5),
        )
        self.refresh_render_validation()
        with self.assertRaisesRegex(ValueError, "tiling check failed"):
            self.check()

    def test_aggregate_and_member_byte_bounds_fail_closed(self):
        total = self.check()["total_read_bytes"]
        with (
            patch.object(contract, "MAX_TOTAL_BYTES", total - 1),
            self.assertRaisesRegex(ValueError, "Source byte budget"),
        ):
            self.check()
        with (
            patch.object(contract, "MAX_MAP_BYTES", 8),
            self.assertRaisesRegex(ValueError, "byte bound"),
        ):
            self.check()

    def test_prior_map_changed_during_later_reads_is_rejected(self):
        original = contract._read

        def change_prior_map(path, limit, budget):
            result = original(path, limit, budget)
            if path.name == "YACS_Material_DetailMasks.png":
                with (self.root / "export/YACS_Material_BaseColor.png").open(
                    "ab"
                ) as stream:
                    stream.write(b"changed later")
            return result

        with (
            patch.object(contract, "_read", side_effect=change_prior_map),
            self.assertRaisesRegex(ValueError, "before contract completion"),
        ):
            self.check()


if __name__ == "__main__":
    unittest.main()
