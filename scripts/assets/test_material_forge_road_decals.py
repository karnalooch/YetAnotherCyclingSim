"""CPU contracts and synthetic decoder-boundary tests; no native render claims."""

from __future__ import annotations

import copy
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter


ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / "scripts/assets/material_forge_road_decals.py"
spec = importlib.util.spec_from_file_location("tested_road_decals", PATH)
decals = importlib.util.module_from_spec(spec)
spec.loader.exec_module(decals)


def _install_fixture(root: Path) -> Path:
    """A minimal PBR definition for authoring tests, not an installed renderer."""
    install = root / "mm-fixture"
    (install / "nodes").mkdir(parents=True)
    (install / "material_maker.exe").write_bytes(b"synthetic authoring tool identity")
    ports = ("albedo_tex", "roughness_tex", "ao_tex", "depth_tex", "normal_tex", "emission_tex")
    decals.forge._write_json(install / "nodes/material.mmg", {
        "parameters": {}, "shader_model": {"inputs": [{"name": port} for port in ports]},
    })
    return install


def _outline(motif: dict, size: int = 160) -> np.ndarray:
    """Independent coarse silhouette diagnostic, ignoring widths and tiny chips."""
    paths = [np.asarray(stroke["points"])[:, :2] for stroke in motif["strokes"]]
    points = np.concatenate(paths)
    centre = (points.max(axis=0) + points.min(axis=0)) * 0.5
    span = np.ptp(points, axis=0).max()
    image = Image.new("L", (size, size))
    draw = ImageDraw.Draw(image)
    for path in paths:
        normalized = (path - centre) / span * (size - 24) + size / 2
        draw.line([tuple(point) for point in normalized], fill=255, width=3)
    return np.asarray(image) > 0


def _native_boundary_fixture(directory: Path, index: int, size: int) -> None:
    """Stub the existing GDScript JSON boundary. EXR bytes are deliberately fake.

    The independent line images exercise validation failures; they do not render
    the authored shader or establish tool provenance, exit 0 or source fidelity.
    """
    export = directory / "export"
    line = Image.new("L", (size, size))
    draw = ImageDraw.Draw(line)
    draw.line([(int(size * (0.20 + 0.037 * index)), int(size * 0.20)),
               (int(size * 0.73), int(size * (0.79 - 0.033 * index)))],
              fill=190, width=max(2, size // 300))
    core = np.asarray(line, dtype=np.float32) / 255
    halo = np.asarray(line.filter(ImageFilter.MaxFilter(3)), dtype=np.float32) / 255 * 0.15
    detail = np.stack([core, core * 0.2, halo], axis=2)
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32) / size
    tone = np.where(core > 0, 0.13 + 0.10 * yy + 0.03 * xx, 0.26)
    color = np.stack([tone + 0.01, tone, tone - 0.01], axis=2)
    nx = np.where(core > 0, 0.06 * np.cos(xx * 14), 0)
    normal = (np.stack([nx, np.zeros_like(nx), np.sqrt(1 - nx * nx)], axis=2) + 1) * 0.5
    orm = np.stack([1 - 0.10 * core, 0.91 + 0.03 * core, np.zeros_like(core)], axis=2)
    for name, array in (("BaseColor", color), ("Normal_DX", normal), ("ORM", orm), ("DetailMasks", detail)):
        Image.fromarray(np.uint8(np.clip(array * 255, 0, 255))).save(export / f"YACS_Material_{name}.png")
    (export / "YACS_Material_Height.exr").write_bytes(b"\x76\x2f\x31\x01synthetic-decoder-boundary")
    _refresh_native_boundary(directory, size)


def _refresh_native_boundary(directory: Path, size: int) -> None:
    export = directory / "export"
    decals.forge._write_json(export / "YACS_Material_native-check.json", {
        "valid": True,
        "engine": {"hash": decals.forge.load_upstreams()["godot"]["commit"]},
        "images": {suffix: {"width": size, "height": size,
                            "sha256": decals.forge.sha256_path(export / ("YACS_Material_" + suffix))}
                   for suffix in decals.MAP_SUFFIXES},
    })


class AuthoredDecalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.recipe = decals.load_recipe()

    def _recipe_path(self, recipe):
        path = self.root / "recipe.json"
        decals.forge._write_json(path, recipe)
        return path

    def test_metric_bounds_and_instruction_determinism(self):
        hashes = set()
        for motif in self.recipe["motifs"]:
            with self.subTest(motif=motif["id"]):
                first = decals.drawing_instructions(motif, 2048, 0.06)
                second = decals.drawing_instructions(copy.deepcopy(motif), 2048, 0.06)
                self.assertEqual(first, second)
                self.assertGreater(first["minimum_primitive_clearance_metres"], 0.12)
                self.assertLessEqual(len(first["segments"]), 56)
                self.assertLessEqual(len(first["chips"]), 7)
                self.assertEqual(first["coordinate_unit"], "metre")
                self.assertGreaterEqual(first["extent_metres"], 1.0)
                self.assertLessEqual(first["extent_metres"], 2.0)
                hashes.add(decals.forge.canonical_hash(first))
        self.assertEqual(len(hashes), 8)
        first = decals.drawing_instructions(self.recipe["motifs"][0], 2048, 0.06)
        self.assertEqual(decals.forge.canonical_hash(first),
                         "a791886eb8f08a4dbf903c34d1a2afc2d264e1e562d0edf126a7fb9fbce633e0")

    def test_seed_changes_only_bounded_internal_edges(self):
        motif = copy.deepcopy(self.recipe["motifs"][0])
        original = decals.drawing_instructions(motif, 2048, 0.06)
        motif["seed"] += 1
        altered = decals.drawing_instructions(motif, 2048, 0.06)
        self.assertNotEqual(original, altered)
        self.assertEqual(original["segments"][0]["start_m"], altered["segments"][0]["start_m"])
        self.assertEqual(original["segments"][-1]["end_m"], altered["segments"][-1]["end_m"])
        self.assertEqual(decals.outline_fingerprint(motif), decals.outline_fingerprint(self.recipe["motifs"][0]))
        for index, (a, b) in enumerate(zip(original["segments"][::4], altered["segments"][::4])):
            self.assertLess(np.linalg.norm(np.asarray(a["end_m"]) - b["end_m"]), 0.055)
            line = np.asarray(original["segments"][4 * index + 3]["end_m"]) - a["start_m"]
            for internal in original["segments"][4 * index:4 * index + 3]:
                offset = np.asarray(internal["end_m"]) - a["start_m"]
                distance = abs(line[0] * offset[1] - line[1] * offset[0]) / np.linalg.norm(line)
                self.assertLessEqual(distance, decals.MAX_KNOT_DEVIATION_METRES + 0.000000002)

    def test_rejects_intrusion_nan_unknown_world_fields_and_primitive_explosion(self):
        changes = [
            lambda r: r["motifs"][0]["strokes"][0]["points"][0].__setitem__(0, 0.025),
            lambda r: r["motifs"][0]["chips"][0].__setitem__("centre", [0.02, 0.5]),
            lambda r: r["motifs"][0]["strokes"][0]["points"][2].__setitem__(2, float("nan")),
            lambda r: r.__setitem__("placement", {"road_window": "0112"}),
            lambda r: r.__setitem__("sampler_address", "wrap"),
            lambda r: r["motifs"][0].__setitem__("strokes", [r["motifs"][0]["strokes"][0]] * 8),
            lambda r: r["motifs"][0].__setitem__("chips", r["motifs"][0]["chips"] * 5),
        ]
        for change in changes:
            recipe = copy.deepcopy(self.recipe)
            change(recipe)
            with self.subTest(change=change), self.assertRaises(ValueError):
                decals.load_recipe(self._recipe_path(recipe))

    def test_rejects_rotated_recoloured_or_reseeded_source_duplicates(self):
        recipe = copy.deepcopy(self.recipe)
        replacement = recipe["motifs"][1]
        replacement["strokes"] = copy.deepcopy(recipe["motifs"][0]["strokes"])
        replacement["strokes"].reverse()
        for stroke in replacement["strokes"]:
            stroke["points"].reverse()
            for point in stroke["points"]:
                point[0], point[1] = point[1], 1.0 - point[0]
                point[2] *= 0.8
        with self.assertRaisesRegex(ValueError, "transformed copies"):
            decals.load_recipe(self._recipe_path(recipe))

    def test_all_neighbor_outlines_remain_distinct_under_rotation_and_mirror(self):
        outlines = [_outline(motif) for motif in self.recipe["motifs"]]
        worst = 0.0
        for i, left in enumerate(outlines):
            for right in outlines[i + 1:]:
                for flip in (False, True):
                    for turn in range(4):
                        transformed = np.rot90(np.fliplr(right) if flip else right, turn)
                        intersection = np.count_nonzero(left & transformed)
                        union = np.count_nonzero(left | transformed)
                        worst = max(worst, intersection / union)
        # This is a coarse source silhouette regression, not a promise about
        # road placement. It catches nearby families becoming one thick stamp.
        self.assertLess(worst, 0.65)

    def test_two_authors_produce_same_graphs_without_touching_base(self):
        install = _install_fixture(self.root)
        base_identity = decals.forge.source_fingerprint()
        first = decals.author(install, self.root / "run-a")
        second = decals.author(install, self.root / "run-b")
        self.assertEqual(first, second)
        self.assertEqual(base_identity, decals.forge.source_fingerprint())
        for entry in first["variants"]:
            graph = decals.forge._json(self.root / "run-a" / entry["directory"] / "Material.ptex")
            self.assertEqual(len(graph["nodes"]), 6)
            self.assertLess(len(json.dumps(graph)), 30000)
            pbr = next(node for node in graph["nodes"] if node["name"] == "PBR_Output")
            exports = pbr["shader_model"]["exports"]["YACS/Textures"]["files"]
            self.assertEqual({e["file_name"].split("$(path_prefix)_")[1] for e in exports}, set(decals.MAP_SUFFIXES))
            self.assertFalse(pbr["parameters"]["flags_transparent"])
            self.assertEqual(pbr["parameters"]["depth_scale"], 0)
        with self.assertRaises(FileExistsError):
            decals.author(install, self.root / "run-a")

    def test_render_argv_reuses_existing_adapter_and_refuses_existing_maps(self):
        install = _install_fixture(self.root)
        run = self.root / "run"
        decals.author(install, run)
        godot = self.root / "Godot fixture.exe"
        godot.write_bytes(b"not executed")
        source = self.root / "primed source fixture"
        (source / ".godot/imported").mkdir(parents=True)
        (source / "project.godot").write_text("fixture")
        (source / ".godot/global_script_class_cache.cfg").write_text("fixture")
        result = decals.render_commands(run, godot, source)
        self.assertEqual(len(result["commands"]), 8)
        self.assertFalse(result["native_process_exit_verified"])
        for command in result["commands"]:
            self.assertEqual(command["argv"][4], str(ROOT / "scripts/assets/render_material_forge.gd"))
            self.assertEqual(command["argv"][-1], "2048")
            self.assertEqual(command["required_process_exit"], 0)
        directory = run / self.recipe["motifs"][0]["id"]
        (directory / "export/unexpected.png").write_bytes(b"already rendered")
        with self.assertRaises(FileExistsError):
            decals.render_commands(run, godot, source)

    def test_cli_author_stdout_is_one_json_document(self):
        install = _install_fixture(self.root)
        result = subprocess.run([sys.executable, str(PATH), "author", "--material-maker", str(install),
                                 "--output", str(self.root / "cli-run")],
                                check=True, capture_output=True, text=True)
        self.assertEqual(len(json.loads(result.stdout)["variants"]), 8)


class NativeDecoderBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        cls.recipe = decals.load_recipe()
        cls.recipe["resolution"] = 1024
        cls.recipe_path = cls.root / "fixture-recipe.json"
        decals.forge._write_json(cls.recipe_path, cls.recipe)
        install = _install_fixture(cls.root)
        cls.runs = [cls.root / "run-a", cls.root / "run-b"]
        for run in cls.runs:
            decals.author(install, run, cls.recipe_path)
        for index, motif in enumerate(cls.recipe["motifs"]):
            _native_boundary_fixture(cls.runs[0] / motif["id"], index, 1024)
            shutil.copytree(cls.runs[0] / motif["id"] / "export", cls.runs[1] / motif["id"] / "export", dirs_exist_ok=True)
        for run in cls.runs:
            decals.validate(run, cls.recipe_path)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        self.work = tempfile.TemporaryDirectory()
        self.addCleanup(self.work.cleanup)
        self.run = Path(self.work.name) / "run-a"
        shutil.copytree(self.runs[0], self.run)
        self.directory = self.run / self.recipe["motifs"][0]["id"]
        self.provenance = decals.forge._json(self.directory / "provenance.json")

    def _edit_png(self, name, edit, refresh_native=True):
        path = self.directory / "export" / ("YACS_Material_" + name + ".png")
        with Image.open(path) as image:
            array = np.asarray(image).copy()
        edit(array)
        Image.fromarray(array).save(path)
        if refresh_native:
            _refresh_native_boundary(self.directory, 1024)

    def test_two_complete_runs_compare_without_claiming_process_exit_or_ue(self):
        result = decals.compare(self.run, self.runs[1], self.recipe_path)
        self.assertTrue(result["deterministic"])
        self.assertEqual(result["motif_count"], 8)
        self.assertEqual(result["maps_per_motif"], 5)
        self.assertFalse(result["native_process_exit_verified"])
        self.assertFalse(result["ue_verified"])
        self.assertFalse(result["visual_accepted"])
        with self.assertRaisesRegex(ValueError, "distinct"):
            decals.compare(self.run, self.run, self.recipe_path)

    def test_refuses_native_hash_or_engine_mismatch(self):
        self._edit_png("DetailMasks", lambda a: a.__setitem__((500, 500, 0), 170), refresh_native=False)
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            decals.check_variant(self.directory, self.provenance)
        native = self.directory / "export/YACS_Material_native-check.json"
        receipt = decals.forge._json(native)
        receipt["engine"]["hash"] = "wrong engine"
        decals.forge._write_json(native, receipt)
        with self.assertRaisesRegex(ValueError, "pinned Godot"):
            decals.check_variant(self.directory, self.provenance)

    def test_rejects_bleed_in_each_mask_channel(self):
        path = self.directory / "export/YACS_Material_DetailMasks.png"
        original = path.read_bytes()
        for channel in range(3):
            path.write_bytes(original)
            self._edit_png("DetailMasks", lambda a: a.__setitem__((4, 50, channel), 1))
            with self.subTest(channel=channel), self.assertRaisesRegex(ValueError, "empty border"):
                decals.check_variant(self.directory, self.provenance)

    def test_rejects_empty_and_overfilled_masks(self):
        path = self.directory / "export/YACS_Material_DetailMasks.png"
        original = path.read_bytes()
        for filled in (False, True):
            path.write_bytes(original)
            def edit(array):
                array[:] = 0
                if filled:
                    array[160:864, 160:864, 0] = 180
            self._edit_png("DetailMasks", edit)
            with self.subTest(filled=filled), self.assertRaisesRegex(ValueError, "sparse readable cracks"):
                decals.check_variant(self.directory, self.provenance)

    def test_rejects_one_bad_normal_even_when_global_p99_would_hide_it(self):
        self._edit_png("Normal_DX", lambda a: a.__setitem__((500, 500), [255, 255, 255]))
        with self.assertRaisesRegex(ValueError, "normal vectors"):
            decals.check_variant(self.directory, self.provenance)

    def test_rejects_non_neutral_border_and_flat_relief(self):
        path = self.directory / "export/YACS_Material_Normal_DX.png"
        original = path.read_bytes()
        self._edit_png("Normal_DX", lambda a: a.__setitem__((0, 2), [140, 128, 254]))
        with self.assertRaisesRegex(ValueError, "border normal"):
            decals.check_variant(self.directory, self.provenance)
        path.write_bytes(original)
        self._edit_png("Normal_DX", lambda a: a.__setitem__(slice(None), [128, 128, 255]))
        with self.assertRaisesRegex(ValueError, "relief is missing"):
            decals.check_variant(self.directory, self.provenance)

    def test_rejects_wet_or_metallic_response(self):
        path = self.directory / "export/YACS_Material_ORM.png"
        original = path.read_bytes()
        for channel, value in ((1, 180), (2, 12)):
            path.write_bytes(original)
            self._edit_png("ORM", lambda a: a.__setitem__((500, 500, channel), value))
            with self.subTest(channel=channel), self.assertRaisesRegex(ValueError, "dry and non-metallic"):
                decals.check_variant(self.directory, self.provenance)

    def test_native_decode_and_comparison_cannot_omit_height(self):
        path = self.directory / "export/YACS_Material_native-check.json"
        native = decals.forge._json(path)
        del native["images"]["Height.exr"]
        decals.forge._write_json(path, native)
        with self.assertRaisesRegex(ValueError, "all five maps"):
            decals.check_variant(self.directory, self.provenance)
        validation_path = self.directory / "validation.json"
        validation = decals.forge._json(validation_path)
        del validation["maps"]["Height"]
        decals.forge._write_json(validation_path, validation)
        manifest_path = self.run / "run-manifest.json"
        manifest = decals.forge._json(manifest_path)
        entry = next(v for v in manifest["validations"] if v["motif"] == self.provenance["motif"])
        entry["validation_sha256"] = decals.forge.sha256_path(validation_path)
        decals.forge._write_json(manifest_path, manifest)
        with self.assertRaisesRegex(ValueError, "cannot omit"):
            decals.compare(self.run, self.runs[1], self.recipe_path)

    def test_graph_bytes_are_bound_to_source_provenance(self):
        graph = self.directory / "Material.ptex"
        graph.write_bytes(graph.read_bytes() + b" ")
        with self.assertRaisesRegex(ValueError, "source hash mismatch"):
            decals.validate(self.run, self.recipe_path)

    def test_rejects_duplicate_rendered_outlines(self):
        duplicate = self.run / self.recipe["motifs"][1]["id"]
        shutil.copyfile(self.directory / "export/YACS_Material_DetailMasks.png", duplicate / "export/YACS_Material_DetailMasks.png")
        # All maps are copied to keep the independent albedo/normal fixture
        # coherent with its opacity; native outline uniqueness must still fail.
        shutil.copytree(self.directory / "export", duplicate / "export", dirs_exist_ok=True)
        with self.assertRaisesRegex(ValueError, "same crack outline"):
            decals.validate(self.run, self.recipe_path)

    def test_comparison_cannot_pass_missing_variant_or_stale_output(self):
        self._edit_png("DetailMasks", lambda a: a.__setitem__((500, 500, 0), 160))
        with self.assertRaisesRegex(ValueError, "changed after validation"):
            decals.compare(self.run, self.runs[1], self.recipe_path)
        manifest_path = self.run / "run-manifest.json"
        manifest = decals.forge._json(manifest_path)
        manifest["variants"].pop()
        decals.forge._write_json(manifest_path, manifest)
        with self.assertRaisesRegex(ValueError, "all eight"):
            decals.compare(self.run, self.runs[1], self.recipe_path)


if __name__ == "__main__":
    unittest.main()
