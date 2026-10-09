"""Synthetic offline boundaries; these fixtures never prove native/MCP admission."""

from copy import deepcopy
import hashlib
import importlib
import importlib.util
import json
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

from scripts.worldgen import bob_mcp_inspection as adapter
from scripts.worldgen import bob_terrain_fit_inspector as inspector


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
OPERATION_PATH = "scripts/ue/official_mcp_bob_operation.py"
GEOMETRY_SOURCES = (
    "smooth_road_ribbon", "curved_road_plan", "road_cut_limits", "road_single_bend",
    "road_surface_profile", "road_edge_roles", "road_width_profile", "road_transition",
)
MAP_PACKAGE = "/Game/Generated/YACS/SaCalobra/WholeMapPreparation/L_SaCalobraMaterialReview"
CANONICAL_MAP = "Content/Worlds/SaCalobra/L_SaCalobraAccepted_20261004.umap"
CONSUMER_FILES = (
    "Content/Generated/YACS/SaCalobra/WholeMapPreparation/L_SaCalobraMaterialReview.umap",
    "Content/Generated/YACS/SaCalobra/WholeMapPreparation/M_SaCalobraWholeMapPreparation.uasset",
    "Content/Generated/YACS/SaCalobra/WholeMapPreparation/MI_SaCalobraWholeMapPreparation.uasset",
)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def reflected(**fields):
    return SimpleNamespace(get_editor_property=lambda name: fields.get(name))


def synthetic_profile():
    """An explicitly synthetic, non-authoritative plane accepted by the real builder."""
    offsets = [-2.5 + index * 5.0 / 24.0 for index in range(25)]
    return {
        "region_id": "sa_calobra", "status": "REVIEW_REQUIRED",
        "source_xy_preserved": True, "terrain_modified": False,
        "road_earthworks_modified": False, "earthworks_authoring_permitted": False,
        "authoritative_physics": False, "geographic_width_admitted": False,
        "road_admitted": False,
        "stations": [
            {"station_m": float(index), "lateral_m": list(offsets),
             "xy_local_m": [[float(index), offset] for offset in offsets],
             "candidate_ground_m": [100.0] * 25}
            for index in range(21)
        ],
    }


class OfficialMcpBobOperationTests(unittest.TestCase):
    def setUp(self):
        # Real Git and original source bytes bind the fixture. Only the trusted
        # accepted-profile/map pins are changed to SYNTHETIC_TEST_ONLY bytes.
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        source_paths = set(adapter.SOURCE_PATHS) | {OPERATION_PATH}
        source_paths.update(f"scripts/geometry/{name}.py" for name in GEOMETRY_SOURCES)
        plugin_paths = subprocess.run(
            ["git", "-C", str(REPOSITORY_ROOT), "ls-files", "--cached", "--others",
             "--exclude-standard", "--", "Plugins/YacsBobInspection"],
            check=True, capture_output=True, text=True,
        ).stdout.splitlines()
        source_paths.update(plugin_paths)
        for relative in source_paths:
            destination = self.root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes((REPOSITORY_ROOT / relative).read_bytes())
        (self.root / ".gitignore").write_text("Saved/\n", encoding="utf-8")
        self.project_path = self.root / "YetAnotherCyclingSim.uproject"
        self.project_path.write_bytes((REPOSITORY_ROOT / self.project_path.name).read_bytes())
        (self.root / "Config").mkdir()
        (self.root / "Config/SyntheticFixture.ini").write_text("; SYNTHETIC_TEST_ONLY\n")
        for arguments in (
            ["init", "--quiet"], ["add", "."],
            ["-c", "user.name=BOB operation unit fixture",
             "-c", "user.email=bob-operation@example.invalid", "commit", "--quiet",
             "-m", "Synthetic operation source fixture"],
        ):
            self.git(*arguments)
        self.exact_sha = self.git("rev-parse", "HEAD").decode().strip()
        self.source_hashes = {relative: digest((self.root / relative).read_bytes())
                              for relative in source_paths}
        self.session = self.root / "Saved/RuntimeProof/OfficialMcpBob"
        self.session.mkdir(parents=True)
        self.profile = synthetic_profile()
        self.profile["exact_sha"] = "c5573b3cf545c51ce83ad1fb0a5ca3111f5ad7f6"
        self.profile_path = self.session / "profile.json"
        self.profile_path.write_bytes(adapter.canonical_json_bytes(self.profile))
        self.profile_hash = digest(self.profile_path.read_bytes())
        self.canonical_path = self.root / CANONICAL_MAP
        self.canonical_path.parent.mkdir(parents=True, exist_ok=True)
        self.canonical_path.write_bytes(b"SYNTHETIC_TEST_ONLY canonical map bytes")
        self.asset_rows = []
        for relative in CONSUMER_FILES:
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            raw = ("SYNTHETIC_TEST_ONLY consumer asset " + relative).encode()
            path.write_bytes(raw)
            self.asset_rows.append({"path": relative, "sha256": digest(raw), "size_bytes": len(raw)})
        self.actor_path = MAP_PACKAGE + ".L_SaCalobraMaterialReview:PersistentLevel.Landscape_0"
        self.context = {
            "schema_version": 1, "exact_sha": self.exact_sha,
            "source_sha256": self.source_hashes, "profile_sha256": self.profile_hash,
            "profile_source_sha": "c5573b3cf545c51ce83ad1fb0a5ca3111f5ad7f6",
            "consumer_source_sha": "94827365ef8e83e52717bb21f9d6efa921aa2d1e",
            "consumer_assets": deepcopy(self.asset_rows),
            "landscape": {"path": self.actor_path, "class_path": "/Script/Landscape.Landscape"},
        }
        self.context_path = self.session / "session-context.json"
        self.write_context()
        self.configure_synthetic_api()
        specification = importlib.util.spec_from_file_location(
            "_synthetic_official_mcp_bob_operation", self.root / OPERATION_PATH)
        self.operation = importlib.util.module_from_spec(specification)
        with mock.patch.dict(sys.modules, {"unreal": self.api}):
            specification.loader.exec_module(self.operation)
            self.producer = importlib.import_module("scripts.ue.bob_road_earthworks_cut")
        for name, value in (
            ("ROOT", self.root), ("PROFILE_SHA256", self.profile_hash),
            ("CANONICAL_MAP_SHA256", digest(self.canonical_path.read_bytes())),
        ):
            patcher = mock.patch.object(self.operation, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = mock.patch.object(adapter, "ROOT", self.root)
        patcher.start()
        self.addCleanup(patcher.stop)
        for name, value in (("ROOT", self.root), ("unreal", self.api)):
            patcher = mock.patch.object(self.producer, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def git(self, *arguments):
        return subprocess.run(["git", "-C", str(self.root), *arguments],
                              check=True, capture_output=True).stdout

    def write_context(self):
        self.context_path.write_bytes(adapter.canonical_json_bytes(self.context))

    def configure_synthetic_api(self):
        self.transform = [0.0, 0.0, 0.0]
        self.component = SimpleNamespace(
            get_path_name=lambda: self.actor_path + ".LandscapeHeightfieldCollisionComponent_0",
            get_class=lambda: SimpleNamespace(get_path_name=lambda:
                "/Script/Landscape.LandscapeHeightfieldCollisionComponent"),
        )
        self.landscape = SimpleNamespace(
            get_path_name=lambda: self.actor_path,
            get_class=lambda: SimpleNamespace(get_path_name=lambda: "/Script/Landscape.Landscape"),
            get_components_by_class=mock.Mock(return_value=[self.component]),
            get_actor_transform=lambda: SimpleNamespace(to_tuple=lambda: tuple(self.transform)),
        )
        self.road = SimpleNamespace(
            get_path_name=lambda: MAP_PACKAGE +
                ".L_SaCalobraMaterialReview:PersistentLevel.YACS_PERSIST_ROAD",
            get_actor_transform=lambda: SimpleNamespace(to_tuple=lambda: (1.0, 2.0, 3.0)),
        )
        self.world = SimpleNamespace(
            get_path_name=lambda: MAP_PACKAGE + ".L_SaCalobraMaterialReview",
            get_outermost=lambda: SimpleNamespace(get_name=lambda: MAP_PACKAGE),
        )
        self.editor = SimpleNamespace(get_editor_world=mock.Mock(return_value=self.world))
        self.actors = SimpleNamespace(get_all_level_actors=mock.Mock(
            return_value=[self.landscape, self.road]))
        self.identity_fields = {
            "accepted": True, "status": "CHECKPOINT_IDENTITY", "error": "",
            "map_package": MAP_PACKAGE, "actor_path": self.actor_path,
            "actor_class_path": "/Script/Landscape.Landscape", "hit_actor": self.landscape,
            "blocking_hit": False, "impact_point": SimpleNamespace(x=0.0, y=0.0, z=0.0),
            "hit_component": None, "component_path": "", "component_class_path": "",
        }
        self.identity = mock.Mock(side_effect=lambda: reflected(**self.identity_fields))
        self.bridge = mock.Mock(side_effect=lambda hit: reflected(**hit.fixture_fields))
        self.trace_count = 0
        self.trace_mutation = None
        self.missing_indices = set()

        def trace(world, start, end, channel, complex_trace, ignored, debug, ignore_self):
            self.assertIs(world, self.world)
            self.assertTrue(complex_trace)
            self.assertTrue(ignore_self)
            self.assertEqual(ignored, [self.road])
            index = self.trace_count
            self.trace_count += 1
            if index == 0 and self.trace_mutation is not None:
                self.trace_mutation()
            if index in self.missing_indices:
                return None
            fields = {
                "accepted": True, "status": "OWNED_LANDSCAPE_HIT", "error": "",
                "blocking_hit": True, "map_package": MAP_PACKAGE,
                "impact_point": SimpleNamespace(x=start.x, y=start.y, z=start.z - 9800.0),
                "hit_actor": self.landscape, "hit_component": self.component,
                "actor_path": self.actor_path, "actor_class_path": "/Script/Landscape.Landscape",
                "component_path": self.component.get_path_name(),
                "component_class_path": "/Script/Landscape.LandscapeHeightfieldCollisionComponent",
            }
            return SimpleNamespace(fixture_fields=fields)

        self.trace = mock.Mock(side_effect=trace)
        self.api = SimpleNamespace(
            Paths=SimpleNamespace(
                project_dir=mock.Mock(return_value=str(self.root)),
                project_file_path=mock.Mock(return_value=str(self.project_path)),
                convert_relative_path_to_full=lambda path: str(Path(path).absolute()),
            ),
            UnrealEditorSubsystem=object(), EditorActorSubsystem=object(), Landscape=object(),
            PrimitiveComponent=object(),
            GameplayStatics=SimpleNamespace(get_all_actors_of_class=mock.Mock(return_value=[self.landscape])),
            EditorLoadingAndSavingUtils=SimpleNamespace(
                get_dirty_map_packages=mock.Mock(return_value=[]),
                get_dirty_content_packages=mock.Mock(return_value=[]),
            ),
            YacsBobLandscapeHitLibrary=SimpleNamespace(
                inspect_accepted_checkpoint_identity=self.identity,
                inspect_accepted_landscape_hit=self.bridge,
            ),
            Vector=lambda x, y, z: SimpleNamespace(x=x, y=y, z=z),
            TraceTypeQuery=SimpleNamespace(ECC_VISIBILITY=object()),
            DrawDebugTrace=SimpleNamespace(NONE=object()),
            SystemLibrary=SimpleNamespace(line_trace_single=self.trace),
        )
        self.api.get_editor_subsystem = mock.Mock(side_effect=lambda kind:
            self.editor if kind is self.api.UnrealEditorSubsystem else self.actors)

    def capture(self):
        with mock.patch.dict(sys.modules, {
            "unreal": self.api, "scripts.ue.bob_road_earthworks_cut": self.producer,
        }):
            return self.operation.capture_and_inspect()

    def assert_pre_capture_rejection(self, regex=None):
        with self.assertRaisesRegex((ValueError, RuntimeError, OSError), regex or ".*"):
            self.capture()
        self.trace.assert_not_called()
        self.assertFalse((self.session / "bundle").exists())

    def assert_capture_rejection_without_receipt(self, regex=None):
        with self.assertRaisesRegex((ValueError, RuntimeError, OSError), regex or ".*"):
            self.capture()
        self.assertGreater(self.trace.call_count, 0)
        self.assertFalse((self.session / "bundle/receipt.json").exists())

    def persistent_bytes(self):
        return {path.relative_to(self.root).as_posix(): path.read_bytes()
                for folder in ("Content", "Config") for path in (self.root / folder).rglob("*")
                if path.is_file()} | {self.project_path.name: self.project_path.read_bytes()}

    def test_captures_complete_rows_and_real_domain_results_without_admission_claims(self):
        before = self.persistent_bytes()
        context_before = self.context_path.read_bytes()
        profile_before = self.profile_path.read_bytes()
        with mock.patch.object(self.producer, "measure_smooth_terrain_fit",
                               wraps=self.producer.measure_smooth_terrain_fit) as measure:
            actual = self.capture()
        measure.assert_called_once()
        bundle = self.session / "bundle"
        self.assertEqual({path.name for path in bundle.iterdir()}, {
            "native-samples.json", "direct-inspection.json", "result.json", "proof.json",
            "capture-proof.json", "receipt.json",
        })
        rows = json.loads((bundle / "native-samples.json").read_bytes())["samples"]
        self.assertEqual(len(rows), 21 * 25)
        self.assertEqual(set(rows[0]), adapter.SAMPLE_FIELDS)
        self.assertEqual(self.trace.call_count, len(rows))
        self.assertEqual(self.bridge.call_count, len(rows))
        expected = inspector.inspect_terrain_fit(rows, exact_sha=self.exact_sha,
            contact_band_max_m=0.08, structure_review_threshold_m=4.0,
            geometry_inspection_view="road-geometry-inspection-before")
        self.assertEqual(actual["result"], expected)
        self.assertEqual(expected["status"], "REVIEW_REQUIRED")
        self.assertEqual(expected["class_counts"]["CUT_REQUIRED"], len(rows))
        for name in ("result", "proof", "receipt"):
            self.assertEqual(json.loads((bundle / (name + ".json")).read_bytes()), actual[name])
        self.assertEqual(json.loads((bundle / "direct-inspection.json").read_bytes()), expected)
        self.assertEqual(actual["proof"]["output"]["sha256"],
                         digest((bundle / "result.json").read_bytes()))
        self.assertEqual(actual["receipt"]["proof"]["sha256"],
                         digest((bundle / "proof.json").read_bytes()))
        capture = actual["capture"]
        self.assertEqual(capture["source_sha256"], self.source_hashes)
        self.assertEqual(capture["native_sample_sha256"],
                         digest((bundle / "native-samples.json").read_bytes()))
        self.assertEqual(capture["context_sha256"], digest(context_before))
        self.assertEqual(capture["profile"], {"sha256": self.profile_hash,
                         "source_exact_sha": self.context["profile_source_sha"]})
        self.assertTrue(capture["direct_invocation_matches"])
        self.assertTrue(capture["persistent_files_unchanged"])
        self.assertTrue(capture["scene_snapshot_unchanged"])
        for report in (actual["result"], actual["receipt"], capture):
            for flag in adapter.FALSE_FLAGS:
                self.assertIs(report[flag], False)
        for report in (actual["receipt"], capture):
            for claim in ("native_capture_verified", "official_mcp_verified",
                          "persistent_content_verified"):
                self.assertIs(report[claim], False)
        self.assertEqual(self.persistent_bytes(), before)
        self.assertEqual(self.context_path.read_bytes(), context_before)
        self.assertEqual(self.profile_path.read_bytes(), profile_before)
        self.assertEqual(self.git("status", "--porcelain", "--untracked-files=no"), b"")

    def test_actual_trace_misses_remain_incomplete_in_full_bundle(self):
        self.missing_indices = {0, 524}
        actual = self.capture()
        self.assertEqual(actual["result"]["status"], "INSPECTION_INCOMPLETE")
        self.assertEqual(actual["result"]["trace_miss_count"], 2)
        rows = json.loads((self.session / "bundle/native-samples.json").read_bytes())["samples"]
        self.assertEqual(len(rows), 525)
        self.assertIsNone(rows[0]["landscape_z_m"])
        self.assertIsNone(rows[-1]["landscape_z_m"])
        self.assertIs(actual["receipt"]["native_capture_verified"], False)

    def test_sink_must_be_invoked_by_actual_producer(self):
        real_measure = self.producer.measure_smooth_terrain_fit

        def omit_sink(*arguments, **keywords):
            keywords["sample_sink"] = None
            return real_measure(*arguments, **keywords)

        with mock.patch.object(self.producer, "measure_smooth_terrain_fit", side_effect=omit_sink):
            self.assert_capture_rejection_without_receipt("exactly one real direct inspection")

    def test_sink_cannot_be_invoked_twice(self):
        real_measure = self.producer.measure_smooth_terrain_fit

        def duplicate_sink(*arguments, **keywords):
            sink = keywords["sample_sink"]

            def duplicate(**captured):
                sink(**captured)
                sink(**captured)

            keywords["sample_sink"] = duplicate
            return real_measure(*arguments, **keywords)

        with mock.patch.object(self.producer, "measure_smooth_terrain_fit", side_effect=duplicate_sink):
            self.assert_capture_rejection_without_receipt("more than once")

    def test_sink_inspection_must_match_real_producer_return(self):
        real_measure = self.producer.measure_smooth_terrain_fit

        def corrupt_return(*arguments, **keywords):
            result = real_measure(*arguments, **keywords)
            return {**result, "sample_count": result["sample_count"] + 1}

        with mock.patch.object(self.producer, "measure_smooth_terrain_fit", side_effect=corrupt_return):
            self.assert_capture_rejection_without_receipt("exactly one real direct inspection")

    def test_sink_rows_must_reproduce_real_direct_inspection(self):
        real_measure = self.producer.measure_smooth_terrain_fit

        def corrupt_row(*arguments, **keywords):
            sink = keywords["sample_sink"]

            def corrupted(*, samples, inspection):
                samples[0]["landscape_z_m"] = samples[0]["road_surface_z_m"] - 0.04
                sink(samples=samples, inspection=inspection)

            keywords["sample_sink"] = corrupted
            return real_measure(*arguments, **keywords)

        with mock.patch.object(self.producer, "measure_smooth_terrain_fit", side_effect=corrupt_row):
            self.assert_capture_rejection_without_receipt("differs from delegated")

    def test_source_drift_during_measurement_prevents_receipt(self):
        path = self.root / "scripts/geometry/smooth_road_ribbon.py"
        self.trace_mutation = lambda: path.write_bytes(path.read_bytes() + b"\n# drift\n")
        self.assert_capture_rejection_without_receipt()

    def test_context_drift_during_measurement_prevents_receipt(self):
        self.trace_mutation = lambda: self.context_path.write_bytes(
            self.context_path.read_bytes() + b" ")
        self.assert_capture_rejection_without_receipt("stale SHA256")

    def test_profile_drift_during_measurement_prevents_receipt(self):
        self.trace_mutation = lambda: self.profile_path.write_bytes(self.profile_path.read_bytes() + b" ")
        self.assert_capture_rejection_without_receipt("stale SHA256")

    def test_consumer_asset_drift_during_measurement_prevents_receipt(self):
        path = self.root / CONSUMER_FILES[0]
        self.trace_mutation = lambda: path.write_bytes(path.read_bytes() + b"changed")
        self.assert_capture_rejection_without_receipt("consumer asset bytes differ")

    def test_unlisted_persistent_config_drift_prevents_receipt(self):
        path = self.root / "Config/SyntheticFixture.ini"
        self.trace_mutation = lambda: path.write_text("; Changed while measuring\n")
        self.assert_capture_rejection_without_receipt()

    def test_new_unlisted_content_file_prevents_receipt(self):
        self.trace_mutation = lambda: (self.root / "Content/unexpected.bin").write_bytes(b"new content")
        self.assert_capture_rejection_without_receipt("persistent project or native scene changed")

    def test_native_actor_transform_drift_prevents_receipt(self):
        self.trace_mutation = lambda: self.transform.__setitem__(0, 10.0)
        self.assert_capture_rejection_without_receipt("native scene changed")

    def test_dirty_content_during_measurement_prevents_receipt(self):
        self.trace_mutation = lambda: setattr(
            self.api.EditorLoadingAndSavingUtils.get_dirty_content_packages, "return_value", [object()])
        self.assert_capture_rejection_without_receipt("non-dirty map and content")

    def test_context_byte_bound_rejects_before_native_identity(self):
        with mock.patch.object(adapter, "MAX_INPUT_BYTES", len(self.context_path.read_bytes()) - 1):
            self.assert_pre_capture_rejection("bounded input size")
        self.identity.assert_not_called()
        self.assertFalse((self.session / "bundle/receipt.json").exists())

    def test_total_persistent_byte_bound_rejects_before_native_measurement(self):
        with mock.patch.object(self.operation, "MAX_PERSISTENT_BYTES", 1):
            self.assert_pre_capture_rejection()
        self.assertFalse((self.session / "bundle/receipt.json").exists())

    def test_persistent_entry_bound_counts_directories_before_native_measurement(self):
        # The files alone fit this limit; traversed directories must also consume
        # the bound so an arbitrarily broad empty tree cannot evade it.
        with mock.patch.object(self.operation, "MAX_PERSISTENT_FILES", len(self.persistent_bytes())):
            self.assert_pre_capture_rejection("inventory exceeds its entry bound")
        self.assertFalse((self.session / "bundle/receipt.json").exists())

    def test_rejects_caller_arguments(self):
        for arguments in (({"map": MAP_PACKAGE},), ("execute_python",)):
            with self.subTest(arguments=arguments):
                with self.assertRaises(TypeError):
                    self.operation.capture_and_inspect(*arguments)
        with self.assertRaises(TypeError):
            self.operation.capture_and_inspect(evidence_root=str(self.session))
        self.identity.assert_not_called()
        self.trace.assert_not_called()

    def test_rejects_context_shape_unknown_fields_and_noninteger_schema(self):
        original = deepcopy(self.context)
        cases = [[], {**original, "save_map": True}, {**original, "schema_version": True},
                 {key: value for key, value in original.items() if key != "landscape"}]
        for context in cases:
            with self.subTest(context=context):
                self.context = context
                self.write_context()
                self.assert_pre_capture_rejection()
        self.identity.assert_not_called()

    def test_rejects_stale_head_and_checkpoint_provenance(self):
        original = deepcopy(self.context)
        for name in ("exact_sha", "profile_source_sha", "consumer_source_sha"):
            with self.subTest(name=name):
                self.context = {**original, name: "1" * 40}
                self.write_context()
                self.assert_pre_capture_rejection()
        self.identity.assert_not_called()

    def test_rejects_source_hash_omission_or_source_inventory_extension(self):
        original = deepcopy(self.context)
        for hashes in ({}, {**original["source_sha256"], "scripts/arbitrary.py": "a" * 64}):
            with self.subTest(hashes=hashes):
                self.context = {**original, "source_sha256": hashes}
                self.write_context()
                self.assert_pre_capture_rejection()
        self.identity.assert_not_called()

    def test_rejects_uncommitted_source_even_when_context_matches_dirty_bytes(self):
        relative = "scripts/geometry/smooth_road_ribbon.py"
        path = self.root / relative
        path.write_bytes(path.read_bytes() + b"\n# SYNTHETIC dirty source\n")
        self.context["source_sha256"][relative] = digest(path.read_bytes())
        self.write_context()
        self.assert_pre_capture_rejection()
        self.identity.assert_not_called()

    def test_rejects_profile_hash_override_and_tampered_profile(self):
        self.context["profile_sha256"] = "1" * 64
        self.write_context()
        self.assert_pre_capture_rejection()
        self.context["profile_sha256"] = self.profile_hash
        self.write_context()
        self.profile_path.write_bytes(self.profile_path.read_bytes() + b" ")
        self.assert_pre_capture_rejection()
        self.identity.assert_not_called()

    def test_rejects_profile_bound_to_another_producer_sha(self):
        self.profile["exact_sha"] = "1" * 40
        self.profile_path.write_bytes(adapter.canonical_json_bytes(self.profile))
        actual_hash = digest(self.profile_path.read_bytes())
        self.context["profile_sha256"] = actual_hash
        self.write_context()
        with mock.patch.object(self.operation, "PROFILE_SHA256", actual_hash):
            self.assert_pre_capture_rejection()
        self.trace.assert_not_called()

    def test_rejects_missing_or_changed_consumer_and_canonical_assets(self):
        for path in (self.root / CONSUMER_FILES[0], self.canonical_path):
            with self.subTest(path=path):
                raw = path.read_bytes()
                path.write_bytes(raw + b"changed")
                self.assert_pre_capture_rejection()
                path.write_bytes(raw)
        (self.root / CONSUMER_FILES[1]).unlink()
        self.assert_pre_capture_rejection()

    def test_rejects_missing_duplicate_and_unknown_consumer_rows(self):
        original = deepcopy(self.context)
        cases = [self.asset_rows[:-1], self.asset_rows + [self.asset_rows[0]],
                 [{**self.asset_rows[0], "save": True}, *self.asset_rows[1:]]]
        for rows in cases:
            with self.subTest(rows=rows):
                self.context = {**original, "consumer_assets": rows}
                self.write_context()
                self.assert_pre_capture_rejection()

    def test_rejects_absolute_traversing_windows_and_nul_asset_paths(self):
        original = deepcopy(self.context)
        for path in (str(self.root / CONSUMER_FILES[0]), "../foreign.umap",
                     "Content/../foreign.umap", "C:/foreign.umap", "Content\\foreign.umap",
                     "Content/foreign\x00.umap"):
            with self.subTest(path=path):
                self.context = deepcopy(original)
                self.context["consumer_assets"][0]["path"] = path
                self.write_context()
                self.assert_pre_capture_rejection()

    def test_rejects_context_or_profile_symlinks(self):
        for path in (self.context_path, self.profile_path):
            with self.subTest(path=path):
                raw = path.read_bytes()
                target = self.root / (path.name + ".outside")
                target.write_bytes(raw)
                path.unlink()
                path.symlink_to(target)
                self.assert_pre_capture_rejection()
                path.unlink()
                path.write_bytes(raw)

    def test_rejects_windows_reparse_metadata(self):
        real_lstat = Path.lstat

        def metadata(path):
            value = real_lstat(path)
            if path == self.profile_path:
                return SimpleNamespace(st_mode=value.st_mode,
                    st_file_attributes=getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
            return value

        with mock.patch.object(Path, "lstat", metadata):
            self.assert_pre_capture_rejection()

    def test_rejects_duplicate_context_json_fields(self):
        raw = self.context_path.read_text().replace('"schema_version":1',
            '"schema_version":1,"schema_version":1')
        self.assertNotEqual(raw, self.context_path.read_text())
        self.context_path.write_text(raw)
        self.assert_pre_capture_rejection()

    def test_rejects_dirty_maps_or_content_before_measurement(self):
        for name in ("get_dirty_map_packages", "get_dirty_content_packages"):
            with self.subTest(name=name):
                function = getattr(self.api.EditorLoadingAndSavingUtils, name)
                function.return_value = [object()]
                self.assert_pre_capture_rejection()
                function.return_value = []

    def test_rejects_foreign_project(self):
        self.api.Paths.project_dir.return_value = str(self.root / "ForeignProject")
        self.assert_pre_capture_rejection()
        self.trace.assert_not_called()

    def test_rejects_foreign_current_map_even_when_native_identity_claims_expected_map(self):
        self.world.get_path_name = lambda: "/Game/Worlds/Foreign.Foreign"
        self.assert_pre_capture_rejection("wrong current map")

    def test_rejects_foreign_world_and_landscape_identity(self):
        original = dict(self.identity_fields)
        for name, value in (
            ("accepted", False), ("status", "UNKNOWN"), ("error", "unexpected"),
            ("map_package", "/Game/Worlds/Foreign"), ("actor_path", "/World/Foreign"),
            ("actor_class_path", "/Script/Engine.Actor"), ("hit_actor", object()),
        ):
            with self.subTest(name=name):
                self.identity_fields = {**original, name: value}
                self.assert_pre_capture_rejection()

    def test_rejects_missing_checkpoint_identity_bridge(self):
        self.api.YacsBobLandscapeHitLibrary = SimpleNamespace()
        self.assert_pre_capture_rejection()

    def test_rejects_ambiguous_native_landscape_inventory(self):
        self.api.GameplayStatics.get_all_actors_of_class.return_value = [self.landscape, object()]
        self.assert_pre_capture_rejection()

    def test_refuses_to_replace_existing_bundle(self):
        bundle = self.session / "bundle"
        bundle.mkdir()
        retained = bundle / "retained.txt"
        retained.write_bytes(b"existing owner evidence")
        with self.assertRaises((ValueError, RuntimeError, FileExistsError)):
            self.capture()
        self.assertEqual(retained.read_bytes(), b"existing owner evidence")
        self.assertEqual(list(bundle.iterdir()), [retained])
        self.trace.assert_not_called()


if __name__ == "__main__":
    unittest.main()
