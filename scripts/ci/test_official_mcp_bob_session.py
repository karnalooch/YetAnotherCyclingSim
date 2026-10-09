"""Synthetic offline session boundaries, never accepted native/MCP evidence.

The fixture binds real repository source in a temporary Git checkout and uses
real local Git LFS objects/checkout. Its maps, receipts and reflected Editor API
are explicitly synthetic; no Editor, network fetch or MCP server is launched.
"""

from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

from scripts.ci import official_mcp_bob_session as production
from scripts.ue import official_mcp_bob_operation as operation


REPOSITORY = Path(__file__).resolve().parents[2]
UTILITY = "scripts/ci/official_mcp_bob_session.py"
CUT = "Content/Worlds/SaCalobra/CheckpointEarthworks/T_SYNTHETIC_CUT.uasset"
FLAGS = (
    "native_runtime_verified",
    "official_mcp_admitted",
    "persistent_world_mutation",
    "performance_pass",
)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


class OfficialMcpBobSessionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        process = subprocess.run(
            ["git", "lfs", "version"], capture_output=True, check=False
        )
        if process.returncode:
            raise unittest.SkipTest(
                "synthetic hydration fixtures require local git-lfs"
            )

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.base = Path(self.directory.name)
        self.root = self.base / "isolated-project"
        self.root.mkdir()
        self.config = {key: self.base / key for key in ("work", "data", "cache")}
        self.config["root"] = self.base
        for path in self.config.values():
            path.mkdir(exist_ok=True)
        self.cache = self.config["cache"] / "git-lfs/YetAnotherCyclingSim"
        self.cache.mkdir(parents=True)
        source_paths = set(operation.BASE_SOURCE_PATHS) | set(
            production.UTILITY_SOURCE_PATHS
        )
        source_paths.update(
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(REPOSITORY),
                    "ls-files",
                    "--",
                    "Plugins/YacsBobInspection",
                ],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.splitlines()
        )
        for relative in source_paths:
            self.write(self.root, relative, (REPOSITORY / relative).read_bytes())
        self.write(
            self.root, "YetAnotherCyclingSim.uproject", b'{"synthetic_test_only":true}'
        )
        self.write(self.root, ".gitignore", b"Saved/\n")
        self.write(
            self.root,
            ".gitattributes",
            b"*.uasset filter=lfs diff=lfs merge=lfs -text\n*.umap filter=lfs diff=lfs merge=lfs -text\n*.uexp filter=lfs diff=lfs merge=lfs -text\n",
        )
        specification = importlib.util.spec_from_file_location(
            "_synthetic_bob_session", self.root / UTILITY
        )
        self.session = importlib.util.module_from_spec(specification)
        specification.loader.exec_module(self.session)
        self.workspace_resolver = self.session._workspace
        # A synthetic host predicate lets Linux exercise the actual trusted
        # root/source guard; it makes no claim about this host being Windows.
        self.patch(self.session, "WINDOWS_HOST", True)
        self.patch(operation, "ROOT", self.root)
        self.patch(operation.adapter, "ROOT", self.root)
        self.patch(self.session, "_workspace", lambda: self.config)

        self.dependency_payloads = {
            relative: ("SYNTHETIC_TEST_ONLY LFS dependency " + relative).encode()
            for relative in sorted(
                production.TEXTURE_PRIMARIES | {operation.CANONICAL_MAP_FILE, CUT}
            )
        }
        texture = sorted(production.TEXTURE_PRIMARIES)[0]
        self.dependency_payloads[texture.rsplit(".", 1)[0] + ".uexp"] = (
            b"SYNTHETIC_TEST_ONLY texture sidecar"
        )
        self.generated_payloads = {
            relative: ("SYNTHETIC_TEST_ONLY generated package " + relative).encode()
            for relative in sorted(production.GENERATED_PRIMARIES)
        }
        generated = sorted(production.GENERATED_PRIMARIES)[0]
        self.generated_payloads[generated.rsplit(".", 1)[0] + ".uexp"] = (
            b"SYNTHETIC_TEST_ONLY generated sidecar"
        )
        for relative, raw in self.dependency_payloads.items():
            self.write(self.root, relative, raw)
        self.git("init", "--quiet")
        self.git("config", "lfs.storage", str(self.cache))
        self.git("lfs", "install", "--local", "--skip-smudge")
        self.commit("Synthetic source and local LFS fixture")
        self.exact_sha = self.git("rev-parse", "HEAD").decode().strip()
        self.rows = [
            dict(path=path, sha256=digest(raw), size_bytes=len(raw))
            for path, raw in sorted(self.dependency_payloads.items())
        ]
        self.patch(self.session, "FROZEN_DEPENDENCY_COUNT", len(self.rows))
        self.patch(
            self.session,
            "FROZEN_DEPENDENCY_BYTES",
            sum(row["size_bytes"] for row in self.rows),
        )
        self.patch(
            self.session,
            "FROZEN_DEPENDENCY_SHA256",
            digest(
                b"\n".join(
                    row["path"].encode() + b" " + row["sha256"].encode()
                    for row in self.rows
                )
            ),
        )
        self.patch(
            operation,
            "CANONICAL_MAP_SHA256",
            digest(self.dependency_payloads[operation.CANONICAL_MAP_FILE]),
        )
        self.pointers = {
            row["path"]: self.git("show", "HEAD:" + row["path"]) for row in self.rows
        }
        for relative, raw in self.pointers.items():
            self.write(self.root, relative, raw)
        # Refresh the index's fixture pointer stat data, as a fresh skip-smudge
        # checkout would. This changes neither its pointer bytes nor HEAD.
        self.git("add", "--", *self.pointers)

        self.actor_path = (
            operation.MAP_PACKAGE
            + ".L_SaCalobraMaterialReview:PersistentLevel.Landscape_SYNTHETIC"
        )
        self.road_path = (
            operation.MAP_PACKAGE
            + ".L_SaCalobraMaterialReview:PersistentLevel.YACS_SYNTHETIC_ROAD"
        )
        self.geometry = {
            "actors": [
                [
                    "<scene>.<world>:PersistentLevel.Landscape_SYNTHETIC",
                    [0.0, 0.0, 0.0],
                ],
                [
                    "<scene>.<world>:PersistentLevel.YACS_SYNTHETIC_ROAD",
                    [1.0, 2.0, 3.0],
                ],
            ],
            "synthetic_test_only": True,
        }
        self.proof_root = self.config["work"] / self.session.PROOF_RELATIVE
        self.consumer_root = self.proof_root / "saved-material-consumer"
        for relative, raw in self.generated_payloads.items():
            self.write(self.consumer_root, "packages/" + Path(relative).name, raw)
        self.documents = self.metadata()
        self.pins = self.write_documents(self.documents)
        self.patch(self.session, "PINNED_METADATA", self.pins)
        self.profile = {
            "exact_sha": operation.PROFILE_SOURCE_SHA,
            "synthetic_test_only": True,
        }
        self.profile_path = self.write(
            self.config["data"], self.session.PROFILE_RELATIVE, canonical(self.profile)
        )
        self.patch(operation, "PROFILE_SHA256", digest(self.profile_path.read_bytes()))
        self.evidence = self.root / self.session.SESSION_DIR
        self.context_path = self.evidence / "session-context.json"
        self.configure_api()

    def patch(self, target, name, value):
        patcher = mock.patch.object(target, name, value)
        patcher.start()
        self.addCleanup(patcher.stop)

    def write(self, root, relative, raw):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        return path

    def git(self, *arguments):
        return subprocess.run(
            ["git", "-C", str(self.root), *arguments],
            check=True,
            capture_output=True,
            timeout=30,
        ).stdout

    def commit(self, message):
        self.git("add", ".")
        self.git(
            "-c",
            "user.name=Synthetic BOB fixture",
            "-c",
            "user.email=bob@example.invalid",
            "commit",
            "--quiet",
            "-m",
            message,
        )

    def metadata(self):
        canonical_map = operation.CANONICAL_MAP_SHA256
        parent = (
            "/Game/"
            + self.session.GENERATED_PREFIX.removeprefix("Content/")
            + "M_SaCalobraWholeMapPreparation"
        )
        initial = {
            "schema_version": 1,
            "exact_sha": self.session.SOURCE_SHA,
            "status": "PASS",
            "audit_phase": "initial",
            "map_sha256": canonical_map,
            "errors": [],
            "tracked_checkout_unchanged": True,
            "retained_source_unchanged": True,
            "prepared_bundle_unchanged": True,
        }
        post = dict(
            initial,
            audit_phase="post-material",
            initial_receipt_sha256=digest(canonical(initial)),
        )
        saved = {
            "exact_sha": self.session.SOURCE_SHA,
            "map_package": operation.MAP_PACKAGE,
            "map_sha256": digest(self.generated_payloads[operation.MAP_FILE]),
            "expected_material_parent": parent,
            "component_count": 1024,
            "fresh_process": True,
            "material_reapplied": False,
            "geometry_mutation": False,
        }
        reload = dict(saved, status="SAVED_MATERIAL_CONSUMER_RELOADED")
        fresh = dict(
            saved,
            status="SAVED_MATERIAL_CONSUMER_RENDERED",
            saved_assets_unchanged=True,
            capture_settings_restored=True,
        )
        assets = []
        for path, raw in sorted(
            {
                **self.generated_payloads,
                **{
                    path: raw
                    for path, raw in self.dependency_payloads.items()
                    if path.startswith(self.session.LIBRARY)
                },
            }.items()
        ):
            row = dict(path=path, sha256=digest(raw), size_bytes=len(raw))
            if path in self.generated_payloads:
                row["storage"] = {
                    "asset": "packages/" + Path(path).name,
                    "release": "isolated saved material consumer",
                }
            assets.append(row)
        generated = [row for row in assets if "storage" in row]
        source = {
            "exact_sha": self.session.SOURCE_SHA,
            **{
                name: digest(("SYNTHETIC_TEST_ONLY " + name).encode())
                for name in self.session.SOURCE_PROOF_HASHES
            },
        }
        source["checkout_restoration_sha256"] = digest(canonical(initial))
        consumer = dict(
            saved,
            schema_version=1,
            status="SAVED_MATERIAL_CONSUMER_PREPARED",
            canonical_map_package="/Game/Worlds/SaCalobra/L_SaCalobraAccepted_20261004",
            canonical_map_sha256=canonical_map,
            terrain_sha256=canonical_map,
            terrain_identity_kind="immutable_canonical_accepted_map",
            canonical_map_saved=False,
            expected_material_instance=parent.replace("/M_SaCalobra", "/MI_SaCalobra"),
            producer_sha256_lf="1" * 64,
            material_recipe_sha256="2" * 64,
            geometry_snapshot=deepcopy(self.geometry),
            geometry_snapshot_sha256=digest(canonical(self.geometry)),
            source_proof=source,
            fresh_render_receipt={
                "path": "fresh-render-receipt.json",
                "sha256": digest(canonical(fresh)),
            },
            assets=assets,
        )
        return {
            self.session.CONSUMER_NAME: consumer,
            self.session.DELIVERY_NAME: {"schema_version": 1, "files": generated},
            self.session.RELOAD_NAME: reload,
            self.session.FRESH_NAME: fresh,
            self.session.INITIAL_NAME: initial,
            self.session.POST_NAME: post,
        }

    def write_documents(self, documents):
        pins = {}
        for name in production.PINNED_METADATA:
            raw = canonical(documents[name])
            self.write(self.proof_root, name, raw)
            pins[name] = (digest(raw), len(raw))
        return pins

    def cache_object(self, row):
        oid = row["sha256"]
        return self.cache / f"objects/{oid[:2]}/{oid[2:4]}/{oid}"

    def stage(self):
        return self.session.stage_accepted_consumer(exact_sha=self.exact_sha)

    def context(self):
        with mock.patch.dict(sys.modules, {"unreal": self.api}):
            return self.session.prepare_native_session_context()

    def assert_no_context(self):
        self.assertFalse(self.context_path.exists())
        self.assertFalse((self.evidence / "bundle").exists())

    def assert_false_flags(self, receipt):
        for name in FLAGS:
            self.assertIs(receipt[name], False)
        self.assertIs(receipt["context_written"], False)

    def configure_api(self):
        self.landscape_transform = [0.0, 0.0, 0.0]
        self.landscape = SimpleNamespace(
            get_path_name=lambda: self.actor_path,
            get_class=lambda: SimpleNamespace(
                get_path_name=lambda: operation.LANDSCAPE_CLASS
            ),
            get_actor_transform=lambda: SimpleNamespace(
                to_tuple=lambda: tuple(self.landscape_transform)
            ),
            get_components_by_class=mock.Mock(return_value=[object()] * 1024),
        )
        self.road = SimpleNamespace(
            get_path_name=lambda: self.road_path,
            get_actor_transform=lambda: SimpleNamespace(
                to_tuple=lambda: (1.0, 2.0, 3.0)
            ),
        )
        self.world = SimpleNamespace(
            get_path_name=lambda: operation.MAP_PACKAGE + ".L_SaCalobraMaterialReview"
        )
        self.editor = SimpleNamespace(
            get_editor_world=mock.Mock(return_value=self.world)
        )
        self.actors = SimpleNamespace(
            get_all_level_actors=mock.Mock(return_value=[self.landscape, self.road])
        )
        self.identity_fields = {
            "accepted": True,
            "status": "CHECKPOINT_IDENTITY",
            "error": "",
            "map_package": operation.MAP_PACKAGE,
            "actor_path": self.actor_path,
            "actor_class_path": operation.LANDSCAPE_CLASS,
            "hit_actor": self.landscape,
        }
        self.identity = mock.Mock(
            side_effect=lambda: SimpleNamespace(
                get_editor_property=lambda name: self.identity_fields.get(name)
            )
        )
        self.api = SimpleNamespace(
            synthetic_test_only=True,
            Paths=SimpleNamespace(
                project_dir=lambda: str(self.root),
                convert_relative_path_to_full=lambda path: path,
            ),
            YacsBobLandscapeHitLibrary=SimpleNamespace(
                inspect_accepted_checkpoint_identity=self.identity
            ),
            UnrealEditorSubsystem=object(),
            EditorActorSubsystem=object(),
            Landscape=object(),
            LandscapeComponent=object(),
            GameplayStatics=SimpleNamespace(
                get_all_actors_of_class=mock.Mock(return_value=[self.landscape])
            ),
            EditorLoadingAndSavingUtils=SimpleNamespace(
                get_dirty_map_packages=mock.Mock(return_value=[]),
                get_dirty_content_packages=mock.Mock(return_value=[]),
            ),
        )
        self.api.get_editor_subsystem = lambda kind: (
            self.editor if kind is self.api.UnrealEditorSubsystem else self.actors
        )

    def test_metadata_preserves_closed_asset_inventory_and_receipt_graph(self):
        documents = self.session._read_metadata(self.proof_root)
        consumer, generated, assets = self.session._validate_metadata(documents)
        self.assertEqual(consumer, self.documents[self.session.CONSUMER_NAME])
        self.assertEqual(len(generated), 5)
        self.assertEqual(len(assets), 16)
        self.assertTrue(
            all(set(row) == {"path", "sha256", "size_bytes"} for row in assets)
        )
        self.assertEqual(
            {row["path"] for row in generated}, set(self.generated_payloads)
        )

    def test_all_raw_metadata_hashes_are_checked_before_any_json_parse(self):
        first, last = list(self.pins)[0], list(self.pins)[-1]
        raw = b"SYNTHETIC invalid JSON intentionally authenticated"
        self.write(self.proof_root, first, raw)
        self.pins[first] = (digest(raw), len(raw))
        self.write(self.proof_root, last, canonical({"tampered": True}))
        with self.assertRaisesRegex(ValueError, "immutable artifact anchor"):
            self.session._read_metadata(self.proof_root)

    def test_metadata_rejects_semantic_receipt_graph_and_geometry_mismatches(self):
        consumer_name = self.session.CONSUMER_NAME
        cases = (
            (consumer_name, ("exact_sha",), "0" * 40),
            (consumer_name, ("geometry_mutation",), True),
            (consumer_name, ("canonical_map_saved",), True),
            (consumer_name, ("source_proof", "exact_sha"), "0" * 40),
            (consumer_name, ("source_proof", "checkout_restoration_sha256"), "0" * 64),
            (consumer_name, ("fresh_render_receipt", "sha256"), "0" * 64),
            (consumer_name, ("geometry_snapshot", "actors"), []),
            (self.session.POST_NAME, ("initial_receipt_sha256",), "0" * 64),
            (self.session.INITIAL_NAME, ("errors",), ["changed owner bytes"]),
            (self.session.RELOAD_NAME, ("material_reapplied",), True),
            (self.session.FRESH_NAME, ("capture_settings_restored",), False),
            (self.session.FRESH_NAME, ("saved_assets_unchanged",), False),
        )
        for name, keys, replacement in cases:
            with self.subTest(name=name, keys=keys):
                documents = deepcopy(self.documents)
                parent = documents[name]
                for key in keys[:-1]:
                    parent = parent[key]
                parent[keys[-1]] = replacement
                with self.assertRaises(ValueError):
                    self.session._validate_metadata(documents)

    def test_consumer_scope_storage_sidecars_and_delivery_subset_are_fixed(self):
        for mutation in (
            "foreign_path",
            "extra_sidecar",
            "foreign_storage",
            "duplicate",
            "missing_primary",
            "delivery",
        ):
            with self.subTest(mutation=mutation):
                documents = deepcopy(self.documents)
                assets = documents[self.session.CONSUMER_NAME]["assets"]
                generated = next(row for row in assets if "storage" in row)
                if mutation == "foreign_path":
                    generated["path"] = "Content/Foreign.uasset"
                elif mutation == "extra_sidecar":
                    generated["path"] = generated["path"].rsplit(".", 1)[0] + ".other"
                elif mutation == "foreign_storage":
                    generated["storage"]["asset"] = "../owner.umap"
                elif mutation == "duplicate":
                    assets.append(deepcopy(assets[0]))
                elif mutation == "missing_primary":
                    assets.remove(
                        next(row for row in assets if row["path"] == operation.MAP_FILE)
                    )
                else:
                    documents[self.session.DELIVERY_NAME]["files"] = []
                with self.assertRaises(ValueError):
                    self.session._validate_metadata(documents)

    def test_input_and_asset_budget_refusals(self):
        with mock.patch.object(self.session, "JSON_LIMIT", 8):
            with self.assertRaisesRegex(ValueError, "bounded regular file"):
                self.session._read_metadata(self.proof_root)
        with mock.patch.object(self.session, "TOTAL_LIMIT", 8):
            with self.assertRaisesRegex(ValueError, "byte bound"):
                self.session._validate_metadata(self.documents)
        with self.assertRaisesRegex(ValueError, "bounded regular file"):
            self.session._identity(self.profile_path, limit=8)

    def test_execution_sha_and_tracked_sources_must_match_real_git_head(self):
        for exact in ("bad", "0" * 40):
            with (
                self.subTest(exact=exact),
                self.assertRaisesRegex(ValueError, "execution SHA"),
            ):
                self.session.stage_accepted_consumer(exact_sha=exact)
        path = self.root / UTILITY
        path.write_bytes(path.read_bytes() + b"\n# SYNTHETIC tracked source drift\n")
        with self.assertRaisesRegex(ValueError, "unchanged tracked files"):
            self.stage()
        self.assertFalse(self.evidence.exists())
        self.identity.assert_not_called()

    def test_source_pointer_set_is_bound_to_actual_head_and_frozen_anchors(self):
        self.assertEqual(
            self.session._source_dependency_inventory(self.exact_sha), self.rows
        )
        self.write(self.root, CUT, b"SYNTHETIC changed committed dependency")
        self.commit("Synthetic pointer drift")
        with self.assertRaisesRegex(ValueError, "frozen source dependency set"):
            self.session._source_dependency_inventory(
                self.git("rev-parse", "HEAD").decode().strip()
            )

    def test_real_lfs_checkout_hydrates_only_exact_pointers_or_missing_targets(self):
        existing, missing = self.rows[:2]
        existing_path = self.write(
            self.root, existing["path"], self.dependency_payloads[existing["path"]]
        )
        before = existing_path.stat()
        (self.root / missing["path"]).unlink()
        cache_before = {
            row["path"]: (
                self.cache_object(row).read_bytes(),
                self.cache_object(row).stat().st_ino,
            )
            for row in self.rows
        }
        self.session._hydrate_dependencies(self.rows, self.cache)
        self.assertEqual(existing_path.stat().st_ino, before.st_ino)
        self.assertEqual(existing_path.stat().st_mtime_ns, before.st_mtime_ns)
        for row in self.rows:
            self.assertEqual(
                (self.root / row["path"]).read_bytes(),
                self.dependency_payloads[row["path"]],
            )
            self.assertEqual(
                (
                    self.cache_object(row).read_bytes(),
                    self.cache_object(row).stat().st_ino,
                ),
                cache_before[row["path"]],
            )
        # Compare actual clean-filter content, including the manually installed
        # matching owner file whose cached pointer stat intentionally survives.
        self.git("diff", "--exit-code", "--", *self.dependency_payloads)

    def test_owner_asset_mismatch_is_rejected_before_any_pointer_is_replaced(self):
        owner = self.rows[-1]
        wrong = b"SYNTHETIC owner changes must survive"
        self.write(self.root, owner["path"], wrong)
        with self.assertRaisesRegex(ValueError, "never overwrite owner bytes"):
            self.session._hydrate_dependencies(self.rows, self.cache)
        self.assertEqual((self.root / owner["path"]).read_bytes(), wrong)
        for row in self.rows[:-1]:
            self.assertEqual(
                (self.root / row["path"]).read_bytes(), self.pointers[row["path"]]
            )

    def test_every_cache_object_is_preflighted_before_lfs_checkout_can_write(self):
        broken = self.cache_object(self.rows[-1])
        wrong = b"SYNTHETIC corrupt cache object"
        broken.write_bytes(wrong)
        with self.assertRaisesRegex(ValueError, "missing or corrupt"):
            self.session._hydrate_dependencies(self.rows, self.cache)
        for row in self.rows:
            self.assertEqual(
                (self.root / row["path"]).read_bytes(), self.pointers[row["path"]]
            )
        self.assertEqual(broken.read_bytes(), wrong)

    def test_path_aliases_and_synthetic_windows_reparse_metadata_are_denied(self):
        for relative in (
            "../outside",
            "Content//owner",
            "Content/./owner",
            "D:/owner",
            "Content\\owner",
        ):
            with self.subTest(relative=relative), self.assertRaises(ValueError):
                self.session._safe_path(self.root, relative)
        target = self.root / self.rows[0]["path"]
        original = target.read_bytes()
        outside = self.base / "outside.uasset"
        outside.write_bytes(b"SYNTHETIC outside bytes")
        target.unlink()
        target.symlink_to(outside)
        with self.assertRaisesRegex(ValueError, "symlink/reparse"):
            self.session._hydrate_dependencies(self.rows, self.cache)
        target.unlink()
        target.write_bytes(original)
        real_lstat = Path.lstat

        def reparse(path):
            observed = real_lstat(path)
            if path == target:
                return SimpleNamespace(
                    st_mode=observed.st_mode, st_file_attributes=0x400
                )
            return observed

        with (
            mock.patch.object(Path, "lstat", reparse),
            self.assertRaisesRegex(ValueError, "symlink/reparse"),
        ):
            self.session._identity(target)
        for row in self.rows:
            self.assertEqual(
                (self.root / row["path"]).read_bytes(), self.pointers[row["path"]]
            )

    def test_raw_workspace_link_is_denied_before_resolver_can_erase_alias(self):
        workspace = self.base / "synthetic-canonical-workspace"
        workspace.mkdir()
        for key in ("work", "data", "cache"):
            (workspace / key).mkdir()
        self.write(
            workspace,
            "workspace.json",
            canonical(
                {
                    "schema_version": 1,
                    "project": "project",
                    "checkpoints": "checkpoints",
                    "work": "work",
                    "data": "data",
                    "cache": "cache",
                }
            ),
        )
        real_path = Path

        def synthetic_canonical_path(value):
            return workspace if value == "D:/yacs" else real_path(value)

        with mock.patch.object(self.session, "Path", synthetic_canonical_path):
            config = self.workspace_resolver()
            self.assertEqual(Path(config["work"]), workspace / "work")
            (workspace / "work").rmdir()
            (workspace / "work").symlink_to(
                self.config["work"], target_is_directory=True
            )
            with self.assertRaisesRegex(ValueError, "symlink/reparse"):
                self.workspace_resolver()

    def test_full_stage_restores_accepted_bytes_but_never_publishes_native_context(
        self,
    ):
        receipt = self.stage()
        self.assertEqual(receipt["status"], "ACCEPTED_CONSUMER_BYTES_STAGED")
        self.assert_false_flags(receipt)
        self.assertEqual(
            receipt["restoration"]["restored"], len(self.generated_payloads)
        )
        self.assertEqual(
            (self.evidence / "profile.json").read_bytes(),
            self.profile_path.read_bytes(),
        )
        self.assertEqual(
            json.loads((self.evidence / "session-preparation.json").read_bytes()),
            receipt,
        )
        self.assert_no_context()
        self.identity.assert_not_called()
        for path, raw in {
            **self.dependency_payloads,
            **self.generated_payloads,
        }.items():
            self.assertEqual((self.root / path).read_bytes(), raw)

    def test_generated_owner_mismatch_or_unrecorded_sidecar_never_hydrates_sources(
        self,
    ):
        primary = sorted(self.generated_payloads)[0]
        owner = self.write(self.root, primary, b"SYNTHETIC owner generated package")
        with self.assertRaisesRegex(ValueError, "Checkpoint content mismatch"):
            self.stage()
        self.assertFalse(self.evidence.exists())
        self.assertEqual(owner.read_bytes(), b"SYNTHETIC owner generated package")
        owner.unlink()
        sidecar = self.write(
            self.root,
            primary.rsplit(".", 1)[0] + ".unknown",
            b"SYNTHETIC owner sidecar",
        )
        with self.assertRaisesRegex(ValueError, "unrecorded package family"):
            self.stage()
        self.assertTrue(sidecar.exists())
        for row in self.rows:
            self.assertEqual(
                (self.root / row["path"]).read_bytes(), self.pointers[row["path"]]
            )
        self.identity.assert_not_called()

    def test_partial_atomic_restoration_failure_leaves_blocked_receipt_and_no_context(
        self,
    ):
        real_link, published = Path.hardlink_to, []

        def fail_second(path, source):
            if len(published) == 1:
                raise OSError("SYNTHETIC injected second package publication failure")
            result = real_link(path, source)
            published.append(path)
            return result

        with (
            mock.patch.object(Path, "hardlink_to", fail_second),
            self.assertRaisesRegex(OSError, "publication failure"),
        ):
            self.stage()
        self.assertEqual(len(published), 1)
        self.assertTrue(published[0].is_file())
        receipt = json.loads((self.evidence / "session-preparation.json").read_bytes())
        self.assertEqual(receipt["status"], "PREPARATION_BLOCKED")
        self.assert_false_flags(receipt)
        self.assertFalse((self.evidence / "profile.json").exists())
        self.assert_no_context()
        self.identity.assert_not_called()

    def test_source_drift_during_restoration_blocks_receipt_before_profile_or_context(
        self,
    ):
        real_link, changed = Path.hardlink_to, False

        def change_source(path, source):
            nonlocal changed
            result = real_link(path, source)
            if not changed:
                utility = self.root / UTILITY
                utility.write_bytes(
                    utility.read_bytes() + b"\n# SYNTHETIC concurrent source drift\n"
                )
                changed = True
            return result

        with (
            mock.patch.object(Path, "hardlink_to", change_source),
            self.assertRaisesRegex(ValueError, "unchanged tracked files"),
        ):
            self.stage()
        receipt = json.loads((self.evidence / "session-preparation.json").read_bytes())
        self.assertEqual(receipt["status"], "PREPARATION_BLOCKED")
        self.assert_false_flags(receipt)
        self.assertFalse((self.evidence / "profile.json").exists())
        self.assert_no_context()

    def test_texture_inventory_must_equal_frozen_committed_dependency_before_hydration(
        self,
    ):
        documents = deepcopy(self.documents)
        texture = next(
            row
            for row in documents[self.session.CONSUMER_NAME]["assets"]
            if "storage" not in row
        )
        texture["sha256"] = "0" * 64
        self.session.PINNED_METADATA = self.write_documents(documents)
        with self.assertRaisesRegex(ValueError, "texture differs from frozen"):
            self.stage()
        self.assertFalse(self.evidence.exists())
        for row in self.rows:
            self.assertEqual(
                (self.root / row["path"]).read_bytes(), self.pointers[row["path"]]
            )

    def test_stage_refuses_wrong_profile_and_existing_evidence_without_overwrite(self):
        raw = self.profile_path.read_bytes()
        self.profile_path.write_bytes(canonical(dict(self.profile, exact_sha="0" * 40)))
        with mock.patch.object(
            operation, "PROFILE_SHA256", digest(self.profile_path.read_bytes())
        ):
            with self.assertRaisesRegex(ValueError, "profile identity"):
                self.stage()
        self.profile_path.write_bytes(raw)
        self.evidence.mkdir(parents=True)
        sentinel = self.write(
            self.evidence, "session-preparation.json", b"SYNTHETIC prior evidence"
        )
        with self.assertRaisesRegex(ValueError, "evidence already exists"):
            self.stage()
        self.assertEqual(sentinel.read_bytes(), b"SYNTHETIC prior evidence")
        self.assert_no_context()

    def test_context_has_exact_eight_fields_and_uses_actual_reflected_actor(self):
        receipt = self.stage()
        context = self.context()
        self.assertEqual(set(context), operation.CONTEXT_FIELDS)
        self.assertEqual(
            context["landscape"],
            {
                "path": self.landscape.get_path_name(),
                "class_path": operation.LANDSCAPE_CLASS,
            },
        )
        self.assertEqual(context["consumer_assets"], receipt["consumer_assets"])
        self.assertEqual(context["exact_sha"], self.exact_sha)
        self.assertEqual(json.loads(self.context_path.read_bytes()), context)
        self.assertGreaterEqual(self.identity.call_count, 3)
        self.assert_false_flags(
            json.loads((self.evidence / "session-preparation.json").read_bytes())
        )
        before = self.context_path.read_bytes()
        with self.assertRaisesRegex(ValueError, "context/output already exists"):
            self.context()
        self.assertEqual(self.context_path.read_bytes(), before)

    def test_context_never_invents_actor_when_native_helper_is_missing_or_unbound(self):
        self.stage()
        for fields in (
            {"accepted": False},
            {"hit_actor": None},
            {"actor_path": self.road_path},
        ):
            with self.subTest(fields=fields):
                original = dict(self.identity_fields)
                self.identity_fields.update(fields)
                with self.assertRaises(ValueError):
                    self.context()
                self.identity_fields = original
                self.assert_no_context()
        with mock.patch.object(
            self.api.YacsBobLandscapeHitLibrary,
            "inspect_accepted_checkpoint_identity",
            None,
        ):
            with self.assertRaisesRegex(ValueError, "helper is unavailable"):
                self.context()
        self.assert_no_context()

    def test_context_requires_clean_fixed_scene_geometry_and_component_count(self):
        self.stage()
        cases = (
            (self.api.Paths, "project_dir", lambda: str(self.base)),
            (
                self.api.EditorLoadingAndSavingUtils,
                "get_dirty_map_packages",
                lambda: [object()],
            ),
            (
                self.api.EditorLoadingAndSavingUtils,
                "get_dirty_content_packages",
                lambda: [object()],
            ),
            (
                self.editor,
                "get_editor_world",
                lambda: SimpleNamespace(get_path_name=lambda: "/Game/Foreign.Map"),
            ),
            (
                self.api.GameplayStatics,
                "get_all_actors_of_class",
                lambda *_: [self.landscape, self.road],
            ),
            (self.landscape, "get_components_by_class", lambda *_: [object()] * 1023),
            (
                self.landscape,
                "get_actor_transform",
                lambda: SimpleNamespace(to_tuple=lambda: (1.0, 0.0, 0.0)),
            ),
        )
        for target, name, replacement in cases:
            with self.subTest(name=name), mock.patch.object(target, name, replacement):
                with self.assertRaises(ValueError):
                    self.context()
                self.assert_no_context()

    def test_context_scene_change_at_final_native_boundary_prevents_publication(self):
        self.stage()
        observed = self.identity.side_effect

        def change_final_scene():
            if self.identity.call_count == 3:
                self.landscape_transform[0] = 1.0
            return observed()

        self.identity.side_effect = change_final_scene
        with self.assertRaisesRegex(ValueError, "boundary changed"):
            self.context()
        self.assert_no_context()

    def test_host_and_imported_domain_checkout_guards_are_not_bypassed(self):
        with mock.patch.object(self.session, "WINDOWS_HOST", False):
            with self.assertRaisesRegex(ValueError, "trusted Windows host"):
                self.stage()
        with mock.patch.object(operation, "ROOT", self.base):
            with self.assertRaisesRegex(
                ValueError, "domain modules belong to another checkout"
            ):
                self.stage()
        self.assertFalse(self.evidence.exists())
        self.identity.assert_not_called()

    def test_poststage_asset_or_profile_drift_rejects_before_native_identity(self):
        self.stage()
        paths = [self.root / operation.MAP_FILE, self.evidence / "profile.json"]
        for path in paths:
            with self.subTest(path=path):
                original = path.read_bytes()
                path.write_bytes(original + b"SYNTHETIC drift")
                with self.assertRaises(ValueError):
                    self.context()
                path.write_bytes(original)
                self.identity.assert_not_called()
                self.assert_no_context()


if __name__ == "__main__":
    unittest.main()
