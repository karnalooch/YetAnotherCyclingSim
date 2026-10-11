"""Disposable contract/texture fixtures; none is a Godot or Unreal proof."""

from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zlib

from scripts.ue import road_crack_sources as sources


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def png(width, color):
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff)
    header = struct.pack(">IIBBBBB", width, width, 8, 6, 0, 0, 0)
    data = zlib.compress((b"\0" + bytes(color) * width) * width)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", data) + chunk(b"IEND", b"")


COLORS = {"BaseColor": (68, 66, 61, 255), "Normal_DX": (127, 127, 255, 255),
          "ORM": (255, 229, 0, 255), "DetailMasks": (0, 0, 0, 255)}


def decoded_border(width=32):
    return {channel: (width, width, 4, bytearray(color * (width * width))) for channel, color in COLORS.items()}


def neutral_fixture():
    return sources.neutral_border(decoded_border(), 180.0, 6.0)


class ProofFixture:
    """Synthetic linked metadata for adversarial contract tests, not evidence."""
    def __init__(self, root):
        self.root, self.repo = root / "proof", root / "source-fixture"
        self.root.mkdir()
        self.repo.mkdir()
        self.recipe = json.loads((sources.ROOT / sources.SOURCE_FILES["recipe_sha256"]).read_text())
        self.upstreams = {"godot": {"commit": "d" * 40}, "fixture_only": True}
        self.identity = {"generator": sources.GENERATOR, "version": 1}
        for key, relative in sources.SOURCE_FILES.items():
            raw = json.dumps(self.recipe if key == "recipe_sha256" else self.upstreams).encode() if key in (
                "recipe_sha256", "upstreams_sha256") else b"# disposable source fixture\n"
            path = self.repo / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
            self.identity[key] = sha(raw)
        maps = {channel: png(2048, color) for channel, color in COLORS.items()}
        # Height is authoring-only and authenticated as opaque EXR bytes here.
        # The production decoder is Godot, whose original proof must be pinned.
        maps["Height"] = b"\x76\x2f\x31\x01disposable-exr-header-fixture"
        self.manifests, processes = {}, []
        for repeat in ("run-a", "run-b"):
            variants, validations = [], []
            for index, motif in enumerate(self.recipe["motifs"]):
                name, extent = motif["id"], motif["extent_metres"]
                folder = self.root / repeat / name
                shader = "disposable shader fixture " + name
                graph = {"nodes": [{"name": "Road_Crack_Form", "shader_model": {"global": shader}}, *({"name": str(i)} for i in range(5))]}
                graph_sha = self.write(folder / "Material.ptex", graph)
                draw_sha = self.write(folder / "draw-instructions.json", {"extent_metres": extent})
                provenance = {"motif": name, "generator": sources.GENERATOR, "generator_version": 1,
                              "source_identity": self.identity, "graph_sha256": graph_sha, "draw_instructions_sha256": draw_sha,
                              "surface_shader_sha256": sha(shader.encode()), "physical_extent_metres": extent,
                              "resolution": 2048, "empty_border_metres": 0.06, "sampler_address": "clamp", "tileable": False,
                              "semantic_owner": "PCG/PCGEx", "local_mask_channels": sources.MASK_CHANNELS,
                              "normal_convention": "DirectX", "normal_strength": 0.16, "height_is_authoring_only": True,
                              "displacement_enabled": False, "asset_kind": "local_surface_decal", "upstreams": self.upstreams,
                              "node_count": 6, **{key: False for key in sources.PENDING_FLAGS}}
                prov_sha = self.write(folder / "provenance.json", provenance)
                images, rows = {}, {}
                for channel, raw in maps.items():
                    suffix = sources.SUFFIXES[channel]
                    relative = "export/" + sources.EXPORT_PREFIX + "_" + suffix
                    self.write(folder / relative, raw)
                    images[suffix] = {"width": 2048, "height": 2048, "sha256": sha(raw)}
                    rows[channel] = {"path": relative, "size": [2048, 2048], "sha256": sha(raw)}
                native_sha = self.write(folder / "export/YACS_Material_native-check.json", {
                    "valid": True, "engine": {"hash": self.upstreams["godot"]["commit"]}, "images": images})
                stats = {"core_coverage_fraction": 0.002, "total_footprint_fraction": 0.004,
                         "normal_length_error_max": 0.01, "normal_xy_peak": 0.2, "weathering_max": 0.1,
                         "roughness_min": 0.89, "border_mask_max": 0.0,
                         "border_pixels_checked": math.floor(0.06 / extent * 2048) - 2}
                validation = {"status": sources.SOURCE_STATUS, "motif": name, "graph_sha256": graph_sha,
                              "normal_convention": "DirectX", "sampler_address": "clamp", "native_decode_verified": True,
                              "mask_statistics": stats, "decoded_core_outline_sha256": sha(name.encode()),
                              "native_check_sha256": native_sha, "maps": rows, **{key: False for key in sources.PENDING_FLAGS}}
                val_sha = self.write(folder / "validation.json", validation)
                log = b"synthetic fixture log; no native process was run\n"
                self.write(folder / "source-runner.log", log)
                processes.append({"repeat": repeat, "motif": name, "pid": 1000 + len(processes), "exit_observed": True,
                                  "exit_code": 0, "stopped_on_failure": False, "elapsed_seconds": 1.0,
                                  "deadline_seconds": 180, "log_sha256": sha(log)})
                variants.append({"motif": name, "directory": name, "graph_sha256": graph_sha,
                                 "draw_instructions_sha256": draw_sha, "provenance_sha256": prov_sha})
                validations.append({"motif": name, "validation_sha256": val_sha})
            self.manifests[repeat] = {"schema_version": 1, "generator": sources.GENERATOR, "source_identity": self.identity,
                                      "status": sources.SOURCE_STATUS, "variants": variants, "validations": validations,
                                      **{key: False for key in sources.PENDING_FLAGS}}
        self.host = {"schema_version": 1, "issue": 364, "status": "ROAD_DECALS_SOURCE_DETERMINISM_PASS",
                     "exact_sha": "a" * 40, "run": "1", "attempt": "1", "source_identity": self.identity,
                     "tool_archive_hashes_verified": True, "native_process_exit_verified": True,
                     "two_run_graph_and_map_bytes_equal": True, "error": None,
                     "human_visual_status": "PENDING_FINAL_M3", "performance_status": "DEFERRED_AFTER_M3",
                     "unreal_consumption_verified": False, "world_mutation": False, "performance_pass": False,
                     "processes": processes, "comparison": {
                         "status": "DECAL_TWO_RUN_MAP_BYTES_MATCH_HOST_RECEIPT_PENDING", "deterministic": True,
                         "native_decode_verified": True, "requires_existing_host_pin_and_exit_verification": True,
                         "motif_count": 8, "maps_per_motif": 5, "mismatches": [], "source_identity": self.identity,
                         **{key: False for key in sources.PENDING_FLAGS}}}
        self.repin()

    @staticmethod
    def write(path, value):
        raw = value if isinstance(value, bytes) else json.dumps(value, sort_keys=True).encode()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        return sha(raw)

    def repin(self):
        manifest_pins = {}
        for repeat, manifest in self.manifests.items():
            name = repeat + "/run-manifest.json"
            self.write(self.root / name, manifest)
            raw = (self.root / name).read_bytes()
            manifest_pins[repeat] = {"file": name, "sha256": sha(raw), "size_bytes": len(raw)}
        self.host["runs"] = [{"repeat": r, "directory": r, "manifest_sha256": manifest_pins[r]["sha256"]} for r in manifest_pins]
        self.host["comparison"].update(left_manifest_sha256=manifest_pins["run-a"]["sha256"],
                                       right_manifest_sha256=manifest_pins["run-b"]["sha256"])
        name = "receipt/source-proof.json"
        self.write(self.root / name, self.host)
        raw = (self.root / name).read_bytes()
        self.pins = {"schema_version": 1, "exact_sha": "a" * 40, "run": "1", "attempt": "1",
                     "source_proof": {"file": name, "sha256": sha(raw), "size_bytes": len(raw)}, "run_manifests": manifest_pins}

    def edit_validation(self, repeat, motif, edit):
        path = self.root / repeat / motif / "validation.json"
        value = json.loads(path.read_bytes())
        edit(value)
        identity = self.write(path, value)
        next(v for v in self.manifests[repeat]["validations"] if v["motif"] == motif)["validation_sha256"] = identity
        self.repin()

    def load(self, **kwargs):
        return sources.load_sources(self.root, self.pins, source_repo_root=self.repo, **kwargs)


class Texture:
    def __init__(self, path):
        self.path, self.properties, self.size = path, {}, 2048

    def get_path_name(self):
        return self.path

    def set_editor_property(self, name, value):
        self.properties[name] = value

    def get_editor_property(self, name):
        return self.properties[name]

    def blueprint_get_size_x(self):
        """Disposable fixture size query, not engine reflection."""
        return self.size

    def blueprint_get_size_y(self):
        """Disposable fixture size query, not engine reflection."""
        return self.size


class ImportTask(Texture):
    def __init__(self):
        super().__init__("fixture-task")


class ImportEngine:
    def __init__(self):
        self.assets, self.tasks = {}, []
        self.fail_import = False
        self.api = SimpleNamespace(
            Texture2D=Texture, AssetImportTask=ImportTask,
            TextureCompressionSettings=SimpleNamespace(TC_DEFAULT="color", TC_NORMALMAP="normal", TC_MASKS="masks"),
            TextureAddress=SimpleNamespace(TA_WRAP="wrap", TA_CLAMP="clamp"),
            AssetToolsHelpers=SimpleNamespace(get_asset_tools=lambda: SimpleNamespace(import_asset_tasks=self.import_tasks)),
            EditorAssetLibrary=SimpleNamespace(does_asset_exist=lambda name: name in self.assets),
            load_asset=lambda name: self.assets.get(name))

    def import_tasks(self, tasks):
        """Disposable import recorder, not native asset proof."""
        for task in tasks:
            self.tasks.append(task)
            name = task.properties["destination_path"] + "/" + task.properties["destination_name"] + "." + task.properties["destination_name"]
            if not self.fail_import:
                self.assets[name] = Texture(name)
            task.properties["imported_object_paths"] = [] if self.fail_import else [name]


class SourceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="crack-source-fixture-")
        self.addCleanup(self.directory.cleanup)
        self.fixture = ProofFixture(Path(self.directory.name))

    def test_complete_linked_contract_is_read_only_and_selection_uses_recipe_order(self):
        value = self.fixture.load(motif_ids=list(reversed(sources.CANARY_MOTIFS)))
        self.assertEqual(value["selected_motifs"], list(sources.CANARY_MOTIFS))
        self.assertEqual((value["verified_map_count"], value["verified_process_count"], len(value["files"])), (80, 16, 179))
        self.assertEqual(value["motifs"]["short_oblique"]["extent_cm"], 140.0)
        self.assertTrue(value["read_only"])
        self.assertFalse(value["normal_space_verified"])
        self.assertFalse(value["owner_visual_pass"])
        self.assertEqual(value, self.fixture.load())
        paths = sources.asset_paths(value)
        self.assertEqual(len(paths["textures"]), 2)
        self.assertNotEqual(paths["root"], sources.asset_paths(self.fixture.load(motif_ids=["short_oblique"]))["root"])

    def test_pin_changes_traversal_missing_trust_and_unknown_selection_fail(self):
        original = deepcopy(self.fixture.pins)
        for mutation in (
            lambda p: p["source_proof"].update(sha256="b" * 64),
            lambda p: p["source_proof"].update(file="../source-proof.json"),
            lambda p: p.pop("source_proof"),
            lambda p: p.update(run="2"),
        ):
            self.fixture.pins = deepcopy(original)
            mutation(self.fixture.pins)
            with self.assertRaises(ValueError):
                self.fixture.load()
        self.fixture.pins = original
        for selected in (("missing",), ("short_oblique", "short_oblique"), ()):
            with self.assertRaises(ValueError):
                self.fixture.load(motif_ids=selected)

    def test_failed_missing_or_unobserved_native_exit_and_overclaim_are_rejected(self):
        original = deepcopy(self.fixture.host)
        for change in (lambda h: h["processes"][0].update(exit_code=1),
                       lambda h: h["processes"].pop(),
                       lambda h: h["processes"][0].update(exit_observed=False),
                       lambda h: h.update(unreal_consumption_verified=True)):
            self.fixture.host = deepcopy(original)
            change(self.fixture.host)
            self.fixture.repin()
            with self.assertRaises(ValueError):
                self.fixture.load()

    def test_any_repeat_map_log_raw_source_or_native_stat_drift_fails(self):
        for relative in ("run-b/short_oblique/export/YACS_Material_ORM.png", "run-b/short_oblique/source-runner.log"):
            path = self.fixture.root / relative
            original = path.read_bytes()
            path.write_bytes(original + b"changed")
            with self.assertRaises(ValueError):
                self.fixture.load()
            path.write_bytes(original)
        source = self.fixture.repo / sources.SOURCE_FILES["recipe_sha256"]
        original = source.read_bytes()
        source.write_bytes(original + b"\r\n")
        with self.assertRaisesRegex(ValueError, "source bytes differ"):
            self.fixture.load()
        source.write_bytes(original)
        self.fixture.edit_validation("run-b", "short_oblique", lambda v: v["mask_statistics"].update(core_coverage_fraction=0.003))
        with self.assertRaisesRegex(ValueError, "statistics differ"):
            self.fixture.load()

    def test_symlink_map_and_repeated_outline_or_nonempty_border_are_rejected(self):
        path = self.fixture.root / "run-a/short_oblique/export/YACS_Material_ORM.png"
        raw = path.read_bytes()
        target = self.fixture.root / "detached-map.png"
        target.write_bytes(raw)
        path.unlink()
        path.symlink_to(target)
        with self.assertRaises(ValueError):
            self.fixture.load()
        path.unlink()
        path.write_bytes(raw)
        self.fixture.edit_validation("run-a", "short_oblique", lambda v: v.update(decoded_core_outline_sha256=sha(b"drifting_interrupted")))
        with self.assertRaisesRegex(ValueError, "repeat one decoded outline"):
            self.fixture.load()

    def test_source_root_has_one_pinned_location_without_a_fallback(self):
        work = Path(self.directory.name) / "work"
        work.mkdir()
        with patch.object(sources, "load_workspace", return_value={"work": str(work)}):
            with self.assertRaises((ValueError, FileNotFoundError)):
                sources.source_root()
            expected = work / "material-forge/road-decals" / sources.VERIFIED_PINS["exact_sha"] / (
                sources.VERIFIED_PINS["run"] + "-" + sources.VERIFIED_PINS["attempt"])
            expected.mkdir(parents=True)
            self.assertEqual(sources.source_root(), expected)
        self.assertEqual(sources.VERIFIED_PINS["source_proof"]["file"], "source-proof.json")

    def test_border_statistics_reject_both_flat_and_excessive_coverage(self):
        path = self.fixture.root / "run-a/short_oblique/validation.json"
        original = json.loads(path.read_bytes())["mask_statistics"]
        for key, value in (("core_coverage_fraction", 0), ("core_coverage_fraction", 0.03),
                           ("total_footprint_fraction", 0.1), ("border_mask_max", 1 / 255),
                           ("roughness_min", 0.5), ("normal_xy_peak", 0.0), ("normal_length_error_max", float("nan"))):
            stats = {**original, key: value}
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                sources._statistics(stats, 1.4)

    def test_small_neutral_cache_never_replaces_full_map_authentication(self):
        sources._decode_neutral_maps.cache_clear()
        self.addCleanup(sources._decode_neutral_maps.cache_clear)
        source = self.fixture.load()

        def decode(path, expected):
            self.assertEqual(expected, (2048, 2048))
            channel = next(c for c in sources.CHANNELS if Path(path).name == "YACS_Material_" + c + ".png")
            return decoded_border()[channel]

        with patch.object(sources, "decode_png", side_effect=decode) as decoder:
            measured = sources._neutral_sources(self.fixture.root, source)
            measured["short_oblique"]["encoded_rgb8"]["Normal_DX"][0] = 0
            again = sources._neutral_sources(self.fixture.root, self.fixture.load())
            self.assertEqual(decoder.call_count, 8)
            self.assertEqual(again["short_oblique"]["encoded_rgb8"]["Normal_DX"][0], 127)
            path = self.fixture.root / "run-b/short_oblique/export/YACS_Material_ORM.png"
            path.write_bytes(path.read_bytes() + b"tampered-after-cache")
            with self.assertRaises(ValueError):
                sources._neutral_sources(self.fixture.root, self.fixture.load())
            self.assertEqual(decoder.call_count, 8)

    def test_border_measurement_decodes_true_png_and_rejects_hidden_edge_leaks(self):
        decoded = {}
        for channel, color in COLORS.items():
            path = self.fixture.root / (channel + ".png")
            path.write_bytes(png(32, color))
            decoded[channel] = sources.decode_png(path, (32, 32))
        measured = sources.neutral_border(decoded, 180.0, 6.0)
        self.assertEqual(measured["encoded_rgb8"]["Normal_DX"], [127, 127, 255])
        self.assertAlmostEqual(measured["normal_xy_bias"][0], -1 / 255)
        self.assertAlmostEqual(measured["orm_linear"][1], 229 / 255)
        for channel, byte, bad in (("DetailMasks", 31 * 4, 1), ("Normal_DX", (32 * 31 + 18) * 4, 120),
                                   ("ORM", (32 * 10 + 31) * 4 + 1, 200), ("BaseColor", 3, 0)):
            data = deepcopy(decoded)
            data[channel][3][byte] = bad
            with self.subTest(channel=channel), self.assertRaises(ValueError):
                sources.neutral_border(data, 180.0, 6.0)

    def test_new_import_is_clamped_unsaved_exact_and_fresh_verification_rejects_drift(self):
        engine = ImportEngine()
        neutral = neutral_fixture()
        with patch.object(sources, "_context"), patch.object(sources, "_decode_neutral_maps", return_value=neutral):
            textures, receipt = sources.import_textures(engine.api, self.fixture.root, self.fixture.pins, source_repo_root=self.fixture.repo)
            self.assertEqual(len(engine.tasks), 8)
            self.assertTrue(all(task.properties["save"] is False and task.properties["replace_existing"] is False for task in engine.tasks))
            self.assertTrue(all(t.properties["address_x"] == t.properties["address_y"] == "clamp" for row in textures.values() for t in row.values()))
            self.assertTrue(all(receipt[key] is False for key in sources.FALSE_FLAGS))
            self.assertEqual(sources.verify_import(engine.api, self.fixture.root, self.fixture.pins, receipt,
                                                   source_repo_root=self.fixture.repo), textures)
            self.assertEqual(len(engine.tasks), 8)
            for prop, value in (("address_x", "wrap"), ("srgb", True), ("flip_green_channel", True)):
                texture = textures["short_oblique"]["Normal_DX"]
                old = texture.properties[prop]
                texture.properties[prop] = value
                with self.assertRaises(ValueError):
                    sources.verify_import(engine.api, self.fixture.root, self.fixture.pins, receipt, source_repo_root=self.fixture.repo)
                texture.properties[prop] = old
            textures["short_oblique"]["Normal_DX"].size = 1024
            with self.assertRaises(ValueError):
                sources.verify_import(engine.api, self.fixture.root, self.fixture.pins, receipt, source_repo_root=self.fixture.repo)
            with self.assertRaisesRegex(ValueError, "refuse overwrite"):
                sources.import_textures(engine.api, self.fixture.root, self.fixture.pins, source_repo_root=self.fixture.repo)
            self.assertEqual(len(engine.tasks), 8)

    def test_failed_native_import_and_source_change_during_import_never_return_receipt(self):
        for failure in ("native", "source"):
            engine = ImportEngine()
            engine.fail_import = failure == "native"
            original = engine.import_tasks
            if failure == "source":
                def changed(tasks):
                    original(tasks)
                    path = self.fixture.root / "run-b/short_oblique/source-runner.log"
                    path.write_bytes(path.read_bytes() + b"changed")
                engine.import_tasks = changed
                changed.__doc__ = "Disposable mutation fixture."
            with self.subTest(failure=failure), patch.object(sources, "_context"), \
                    patch.object(sources, "_decode_neutral_maps", return_value=neutral_fixture()), self.assertRaises(ValueError):
                sources.import_textures(engine.api, self.fixture.root, self.fixture.pins, source_repo_root=self.fixture.repo)


if __name__ == "__main__":
    unittest.main()
