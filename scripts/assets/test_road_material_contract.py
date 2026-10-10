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
from types import SimpleNamespace
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

    def test_windows_distinct_path_creation_and_handle_change_times_are_supported(self):
        original = contract.os.fstat

        def windows_handle(fd):
            info = original(fd)
            return SimpleNamespace(
                **{name: getattr(info, name) for name in contract.IDENTITY_FIELDS},
                st_mode=info.st_mode,
            )

        def distinct_change_time(fd):
            info = windows_handle(fd)
            info.st_ctime_ns += 100
            return info

        # Synthetic CPython Windows API semantics, not actual Windows/native proof.
        with (
            patch.object(contract, "_WINDOWS", True),
            patch.object(contract.os, "fstat", side_effect=distinct_change_time),
        ):
            self.assertEqual(self.check()["tile_size_cm"], 400)

    def test_windows_handle_change_time_drift_during_read_still_rejects(self):
        original = contract.os.fstat
        calls = 0

        def changing_handle(fd):
            nonlocal calls
            calls += 1
            info = original(fd)
            values = {name: getattr(info, name) for name in contract.IDENTITY_FIELDS}
            values["st_ctime_ns"] += calls
            return SimpleNamespace(**values, st_mode=info.st_mode)

        with (
            patch.object(contract, "_WINDOWS", True),
            patch.object(contract.os, "fstat", side_effect=changing_handle),
            self.assertRaisesRegex(
                ValueError, "Source changed during read.*st_ctime_ns"
            ),
        ):
            self.check()

    def test_windows_cross_view_identity_size_and_mtime_drift_still_reject(self):
        original = contract.os.fstat
        for changed_field in ("st_dev", "st_ino", "st_size", "st_mtime_ns"):
            with self.subTest(field=changed_field):

                def different_handle(fd, field=changed_field):
                    info = original(fd)
                    values = {
                        name: getattr(info, name) for name in contract.IDENTITY_FIELDS
                    }
                    values[field] += 1
                    return SimpleNamespace(**values, st_mode=info.st_mode)

                with (
                    patch.object(contract, "_WINDOWS", True),
                    patch.object(contract.os, "fstat", side_effect=different_handle),
                    self.assertRaisesRegex(
                        ValueError, "Source changed before read.*" + changed_field
                    ) as error,
                ):
                    self.check()
                self.assertLess(len(str(error.exception).encode("utf-8")), 2048)
                self.assertNotIn(str(self.root), str(error.exception))
                self.assertIn('"expected":', str(error.exception))
                self.assertIn('"observed":', str(error.exception))

    def test_non_windows_cross_view_ctime_remains_exact(self):
        original = contract.os.fstat

        def different_ctime(fd):
            info = original(fd)
            values = {name: getattr(info, name) for name in contract.IDENTITY_FIELDS}
            values["st_ctime_ns"] += 1
            return SimpleNamespace(**values, st_mode=info.st_mode)

        with (
            patch.object(contract, "_WINDOWS", False),
            patch.object(contract.os, "fstat", side_effect=different_ctime),
            self.assertRaisesRegex(
                ValueError, "Source changed before read.*st_ctime_ns"
            ),
        ):
            self.check()

    def test_opened_nonregular_handle_is_rejected(self):
        original = contract.os.fstat

        def nonregular_handle(fd):
            info = original(fd)
            values = {name: getattr(info, name) for name in contract.IDENTITY_FIELDS}
            return SimpleNamespace(**values, st_mode=0)

        with (
            patch.object(contract.os, "fstat", side_effect=nonregular_handle),
            self.assertRaisesRegex(ValueError, "Opened source is not a regular file"),
        ):
            self.check()

    def test_windows_path_ctime_drift_remains_rejected_independently(self):
        original = contract._safe_path
        catalog_observations = 0

        def changed_path(path, *, directory=False):
            nonlocal catalog_observations
            info = original(path, directory=directory)
            if path.name == "catalog.json":
                catalog_observations += 1
                if catalog_observations == 2:
                    values = {
                        name: getattr(info, name) for name in contract.IDENTITY_FIELDS
                    }
                    values["st_ctime_ns"] += 1
                    return SimpleNamespace(**values, st_mode=info.st_mode)
            return info

        with (
            patch.object(contract, "_WINDOWS", True),
            patch.object(contract, "_safe_path", side_effect=changed_path),
            self.assertRaisesRegex(
                ValueError, "Source changed after read.*st_ctime_ns"
            ),
        ):
            self.check()


class RoadAsphaltReplayContractTests(unittest.TestCase):
    """Synthetic authenticated receipt fixtures, not two native render executions."""

    SOURCE_HEAD = "1" * 40
    SOURCE_FINGERPRINT = "2" * 64

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
        self.root = Path(self.directory.name)
        runs = []
        for label in ("run-a", "run-b"):
            directory = self.root / label / contract.FAMILY / contract.VARIANT
            shutil.copytree(self.template.name, directory)
            source = contract.check_asphalt_source(directory)
            runs.append(
                {
                    "run": label,
                    "directory": label + "\\aged_mountain_asphalt\\base",
                    "fingerprint": "d" * 64,
                    "source": source,
                    "graph_sha256": source["retained_receipts"]["Material.ptex"][
                        "sha256"
                    ],
                    "map_sha256": {
                        name: row["sha256"] for name, row in source["maps"].items()
                    },
                }
            )
        self.receipt = {
            "schema_version": 1,
            "issue": 364,
            "exact_sha": self.SOURCE_HEAD,
            "run": "123",
            "attempt": "1",
            "status": "ROAD_ASPHALT_SOURCE_DETERMINISM_PASS",
            "source_fingerprint": self.SOURCE_FINGERPRINT,
            "runs": runs,
            "godot_sha256": "b" * 64,
            "material_maker_sha256": "c" * 64,
            "tool_archive_hashes_verified": True,
            "source_commit": contract.MM_SOURCE,
            "primed_source_identity": {
                "source_commit": contract.MM_SOURCE,
                "program_inputs_unchanged": True,
                "primed_icon_imports": {
                    "fixture.svg.import": {
                        "source_blob_id": "3" * 40,
                        "sha256": "4" * 64,
                    }
                },
            },
            "two_run_graph_and_map_bytes_equal": True,
            "rendered_variant_count": 2,
            "unreal_consumption_verified": False,
            "world_mutation": False,
            "human_visual_status": "PENDING_FINAL_M3",
            "performance_status": "DEFERRED_AFTER_M3",
            "performance_pass": False,
        }
        self.save()

    def save(self) -> None:
        _write(self.root / "source-proof.json", self.receipt)

    def check(self, *, digest=None, source_head=None, fingerprint=None) -> dict:
        return contract.check_asphalt_replay(
            self.root,
            digest if digest is not None else _sha(self.root / "source-proof.json"),
            source_head if source_head is not None else self.SOURCE_HEAD,
            fingerprint if fingerprint is not None else self.SOURCE_FINGERPRINT,
        )

    def test_replay_binds_retained_bytes_and_keeps_native_and_tool_admission_false(
        self,
    ):
        before = {
            p.relative_to(self.root).as_posix(): _sha(p)
            for p in self.root.rglob("*")
            if p.is_file()
        }
        result = self.check()
        self.assertEqual(result["source_head"], self.SOURCE_HEAD)
        self.assertEqual(
            result["authenticated_source_receipt"]["sha256"],
            _sha(self.root / "source-proof.json"),
        )
        self.assertEqual([row["run"] for row in result["runs"]], ["run-a", "run-b"])
        self.assertIs(result["producer_attestation_authenticated"], True)
        self.assertIs(result["retained_two_run_graph_and_map_bytes_equal"], True)
        self.assertIs(result["producer_reported_tool_archive_hashes_verified"], True)
        for key in (
            "producer_binary_independently_verified",
            "unreal_verified",
            "renders_executed_by_reader",
            "world_mutation",
            "geometry_changed",
            "height_displacement_used",
            "performance_pass",
        ):
            self.assertIs(result[key], False)
        self.assertEqual(result["human_visual_status"], "PENDING_FINAL_M3")
        self.assertNotIn("execution_head", result)
        self.assertLess(len(json.dumps(result)), 32 * 1024)
        self.assertEqual(result, self.check())
        self.assertEqual(
            before,
            {
                p.relative_to(self.root).as_posix(): _sha(p)
                for p in self.root.rglob("*")
                if p.is_file()
            },
        )

    def test_raw_receipt_is_authenticated_before_json_parse(self):
        with (
            patch.object(
                contract, "_json", side_effect=AssertionError("must not parse")
            ),
            self.assertRaisesRegex(ValueError, "authentication failed"),
        ):
            self.check(digest="0" * 64)

    def test_source_head_and_current_fingerprint_gate_are_exact(self):
        with self.assertRaisesRegex(ValueError, "source HEAD mismatch"):
            self.check(source_head="0" * 40)
        with self.assertRaisesRegex(ValueError, "source fingerprint mismatch"):
            self.check(fingerprint="0" * 64)

    def test_top_admission_claims_must_preserve_real_boolean_scope(self):
        for key, value in (
            ("tool_archive_hashes_verified", 1),
            ("two_run_graph_and_map_bytes_equal", False),
            ("unreal_consumption_verified", True),
            ("world_mutation", True),
            ("performance_pass", 0),
            ("human_visual_status", "ACCEPTED"),
            ("performance_status", "PASS"),
            ("rendered_variant_count", True),
        ):
            with self.subTest(key=key):
                original = self.receipt[key]
                self.receipt[key] = value
                self.save()
                with self.assertRaises(ValueError):
                    self.check()
                self.receipt[key] = original

    def test_only_two_literal_directories_in_fixed_order_are_allowed(self):
        original = self.receipt["runs"][0]["directory"]
        for directory in (
            "../run-a/aged_mountain_asphalt/base",
            "D:/outside/base",
            "run-b/aged_mountain_asphalt/base",
            "run-a/aged_mountain_asphalt/worn",
        ):
            with self.subTest(directory=directory):
                self.receipt["runs"][0]["directory"] = directory
                self.save()
                with self.assertRaisesRegex(ValueError, "directory/order"):
                    self.check()
        self.receipt["runs"][0]["directory"] = original
        self.receipt["runs"].reverse()
        self.save()
        with self.assertRaisesRegex(ValueError, "directory/order"):
            self.check()

    def test_posix_literal_directories_are_supported_without_changing_receipt_bytes(
        self,
    ):
        for row in self.receipt["runs"]:
            row["directory"] = row["directory"].replace("\\", "/")
        self.save()
        self.assertEqual(
            self.check()["runs"][0]["directory"], "run-a/aged_mountain_asphalt/base"
        )

    def test_height_tamper_in_one_run_is_rejected(self):
        path = (
            self.root
            / "run-b/aged_mountain_asphalt/base/export/YACS_Material_Height.exr"
        )
        path.write_bytes(path.read_bytes() + b"changed")
        with self.assertRaisesRegex(ValueError, "Map changed.*Height"):
            self.check()

    def test_self_consistent_but_different_run_bytes_cannot_pass_outer_true_flag(self):
        root = self.root / "run-b/aged_mountain_asphalt/base"
        height = root / "export/YACS_Material_Height.exr"
        height.write_bytes(height.read_bytes() + b"different")
        for name, change in (
            (
                "validation.json",
                lambda data: data["maps"]["Height"].update(sha256=_sha(height)),
            ),
            (
                "export/YACS_Material_native-check.json",
                lambda data: data["images"]["Height.exr"].update(sha256=_sha(height)),
            ),
            (
                "render-receipt.json",
                lambda data: data.update(
                    validation_sha256=_sha(root / "validation.json")
                ),
            ),
        ):
            document = json.loads((root / name).read_bytes())
            change(document)
            _write(root / name, document)
        source = contract.check_asphalt_source(root)
        self.receipt["runs"][1]["source"] = source
        self.receipt["runs"][1]["map_sha256"] = {
            name: row["sha256"] for name, row in source["maps"].items()
        }
        self.save()
        with self.assertRaisesRegex(ValueError, "two-run graph/map bytes differ"):
            self.check()

    def test_outer_graph_and_map_bindings_are_checked_against_actual_files(self):
        self.receipt["runs"][0]["map_sha256"]["Height"] = "0" * 64
        self.save()
        with self.assertRaisesRegex(ValueError, "graph/map bindings"):
            self.check()

    def test_embedded_receipts_cannot_gain_independent_native_authority(self):
        self.receipt["runs"][0]["source"]["producer_binary_independently_verified"] = (
            True
        )
        self.save()
        with self.assertRaisesRegex(ValueError, "source receipt differs"):
            self.check()

    def test_missing_unchanged_source_attestation_rejects(self):
        self.receipt["primed_source_identity"]["program_inputs_unchanged"] = False
        self.save()
        with self.assertRaisesRegex(ValueError, "source was not unchanged"):
            self.check()

    def test_joint_byte_cap_is_checked_before_any_variant_read(self):
        limit = self.check()["total_read_bytes"] - 1
        with (
            patch.object(contract, "MAX_TOTAL_BYTES", limit),
            patch.object(
                contract,
                "check_asphalt_source",
                side_effect=AssertionError("must preflight first"),
            ),
            self.assertRaisesRegex(ValueError, "source byte budget"),
        ):
            self.check()

    def test_first_run_changes_during_second_run_are_rejected(self):
        original = contract.check_asphalt_source

        def mutate_first_run(directory):
            source = original(directory)
            if "run-b" in directory.parts:
                path = (
                    self.root
                    / "run-a/aged_mountain_asphalt/base/MATERIAL_MAKER_LICENSE.txt"
                )
                path.write_bytes(path.read_bytes() + b"changed later")
            return source

        with (
            patch.object(
                contract, "check_asphalt_source", side_effect=mutate_first_run
            ),
            self.assertRaisesRegex(
                ValueError, "Replay source changed before completion"
            ),
        ):
            self.check()

    def test_authenticated_top_receipt_changes_during_run_reads_are_rejected(self):
        original = contract.check_asphalt_source

        def mutate_top(directory):
            source = original(directory)
            if "run-b" in directory.parts:
                path = self.root / "source-proof.json"
                path.write_bytes(path.read_bytes() + b" ")
            return source

        with (
            patch.object(contract, "check_asphalt_source", side_effect=mutate_top),
            self.assertRaisesRegex(
                ValueError, "Replay source changed before completion"
            ),
        ):
            self.check()

    def test_current_catalog_raw_identity_must_match_original_embedded_receipts(self):
        catalog = self.root / "changed-catalog.json"
        data = json.loads(contract.DEFAULT_CATALOG.read_bytes())
        data["families"][1]["label"] = "Changed documentary catalog byte"
        _write(catalog, data)
        original = contract.check_asphalt_source

        def different_catalog(directory):
            return original(directory, catalog)

        with (
            patch.object(contract, "DEFAULT_CATALOG", catalog),
            patch.object(
                contract, "check_asphalt_source", side_effect=different_catalog
            ),
            self.assertRaisesRegex(ValueError, "source receipt differs"),
        ):
            self.check()


if __name__ == "__main__":
    unittest.main()
