"""Synthetic stdlib checks for the #364 read-only baseline boundary, not UE proof."""

import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from scripts.ci import official_mcp_bob_session as session
from scripts.ue import read_road_material_baseline as reader

EXACT_SHA = "a" * 40


def preparation():
    assets = [{"path": session.operation.MAP_FILE, "sha256": "b" * 64, "size_bytes": 10}]
    assets.extend({"path": f"Content/Generated/YACS/Test/M_{index}.uasset",
                   "sha256": "c" * 64, "size_bytes": 10} for index in range(13))
    return {
        "schema_version": 1, "status": "ACCEPTED_CONSUMER_BYTES_STAGED", "exact_sha": EXACT_SHA,
        "consumer_source_sha": session.SOURCE_SHA, "consumer_source_run": session.SOURCE_RUN,
        "consumer_source_attempt": session.SOURCE_ATTEMPT,
        "profile_sha256": session.operation.PROFILE_SHA256,
        "metadata_anchors": {name: {"sha256": pin[0], "size_bytes": pin[1]}
                             for name, pin in session.PINNED_METADATA.items()},
        "consumer_assets": assets, "native_runtime_verified": False,
        "official_mcp_admitted": False, "persistent_world_mutation": False,
        "performance_pass": False, "context_written": False,
        "performance_status": "DEFERRED_AFTER_M3",
    }


def actor(label):
    return SimpleNamespace(get_actor_label=lambda: label)


class BaselineBoundaryTests(unittest.TestCase):
    def test_fixed_output_rejects_escape_and_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run = root / reader.OUTPUT_BASE / "run-364"
            target = reader.output_path(root, str(run), session._safe_path)
            self.assertEqual(target.name, reader.OUTPUT_NAME)
            for value in (str(root / "Saved/other/run"), str(run / "child"),
                          str(root / reader.OUTPUT_BASE / ".." / "outside"), "relative"):
                with self.subTest(value=value), self.assertRaises(ValueError):
                    reader.output_path(root, value, session._safe_path)
            target.parent.mkdir(parents=True)
            target.write_bytes(b"retain")
            with self.assertRaisesRegex(ValueError, "overwrite"):
                reader.output_path(root, str(run), session._safe_path)
            self.assertEqual(target.read_bytes(), b"retain")

    def test_linked_output_ancestor_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            destination = root / "elsewhere"
            destination.mkdir()
            link = root / "Saved"
            try:
                link.symlink_to(destination, target_is_directory=True)
            except OSError as exc:
                self.skipTest(str(exc))
            with self.assertRaisesRegex(ValueError, "symlink/reparse"):
                reader.output_path(root, str(root / reader.OUTPUT_BASE / "run-364"), session._safe_path)

    def test_frozen_receipt_contract_rejects_changed_anchor_and_admission(self):
        value = preparation()
        self.assertEqual(reader.validate_preparation(value, EXACT_SHA, session)["path"],
                         session.operation.MAP_FILE)
        for key, bad in (("exact_sha", "d" * 40), ("consumer_source_sha", EXACT_SHA),
                         ("status", "PREPARATION_PENDING"), ("metadata_anchors", {}),
                         ("official_mcp_admitted", True), ("performance_pass", True),
                         ("performance_status", "PASS")):
            changed = deepcopy(value)
            changed[key] = bad
            with self.subTest(key=key), self.assertRaises(ValueError):
                reader.validate_preparation(changed, EXACT_SHA, session)

    def test_asset_map_missing_duplicate_or_unbounded_is_refused(self):
        value = preparation()
        for mutation in ("duplicate", "map_missing", "unbounded", "boolean_size"):
            changed = deepcopy(value)
            if mutation == "duplicate":
                changed["consumer_assets"][1] = changed["consumer_assets"][0]
            elif mutation == "map_missing":
                changed["consumer_assets"][0]["path"] = "Content/Wrong.umap"
            else:
                changed["consumer_assets"][0]["size_bytes"] = (
                    session.FILE_LIMIT + 1 if mutation == "unbounded" else True)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                reader.validate_preparation(changed, EXACT_SHA, session)

    def test_wrong_raw_receipt_hash_never_reaches_parser(self):
        fake = SimpleNamespace(SESSION_DIR=session.SESSION_DIR, _safe_path=lambda root, path: root / path,
                               _identity=Mock(return_value={"sha256": "b" * 64, "size_bytes": 10}),
                               _read_json=Mock(side_effect=AssertionError("must not parse")))
        with self.assertRaisesRegex(ValueError, "untrusted"):
            reader.authenticated_preparation(fake, EXACT_SHA, "c" * 64)
        fake._read_json.assert_not_called()

    def test_authentication_passes_actual_raw_size_to_reader(self):
        fake = SimpleNamespace(**{key: getattr(session, key) for key in
                                  ("SESSION_DIR", "SOURCE_SHA", "SOURCE_RUN", "SOURCE_ATTEMPT",
                                   "operation", "PINNED_METADATA", "FILE_LIMIT")})
        fake._safe_path = lambda root, path: root / path
        fake._identity = Mock(return_value={"sha256": "b" * 64, "size_bytes": 10})
        fake._read_json = Mock(return_value=preparation())
        path, identity, _value, _map = reader.authenticated_preparation(fake, EXACT_SHA, "b" * 64)
        fake._read_json.assert_called_once_with(path, ("b" * 64, 10))
        self.assertEqual(identity["size_bytes"], 10)

    def test_duplicate_actor_labels_do_not_disappear_in_dictionary(self):
        actors = [actor("YACS_PERSIST_ROAD")]
        actors.extend(actor(f"YACS_PERSIST_SUPPORT_{index:03}") for index in range(1, 187))
        self.assertEqual(len(reader.road_support_actors(actors)), 187)
        with self.assertRaisesRegex(ValueError, "duplicate"):
            reader.road_support_actors(actors + [actor("YACS_PERSIST_SUPPORT_001")])
        with self.assertRaisesRegex(ValueError, "186"):
            reader.road_support_actors(actors[:-1])
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            reader.road_support_actors(actors + [actor("YACS_PERSIST_ROAD_COPY")])

    def test_numeric_snapshot_refuses_non_finite_values(self):
        transform = SimpleNamespace(to_tuple=lambda: (1, SimpleNamespace(to_tuple=lambda: (2, 3))))
        self.assertEqual(reader.numeric_tuple(transform), [1.0, [2.0, 3.0]])
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.assertRaisesRegex(ValueError, "non-finite"):
                reader.numeric_tuple(value)

    def test_reflection_retains_actual_docs_and_never_invokes_query(self):
        def unproved_query():
            """Actual fixture-only query signature; must never execute."""
            raise AssertionError("reflection invoked an unproved method")

        api = SimpleNamespace(GeometryScript_UVs=SimpleNamespace(get_triangle_uvs=unproved_query),
                              MaterialEditingLibrary=SimpleNamespace())
        mesh = SimpleNamespace(get_vertex_count=unproved_query)
        result = reader.query_reflection(api, mesh)
        self.assertIn("DynamicMesh.get_vertex_count", result["query_docs"])
        self.assertIn("GeometryScript_UVs.get_triangle_uvs", result["query_docs"])
        self.assertFalse(result["new_geometry_query_behavior_verified"])
        self.assertFalse(result["query_docs"]["GeometryScript_UVs.get_triangle_uvs"]
                         ["invoked_by_reflection"])
        self.assertFalse(result["material_read_docs"]["get_material_function_expressions"]["callable"])

    def test_reflection_explicitly_marks_missing_and_truncated_docs(self):
        def method():
            raise AssertionError("must not run")

        method.__doc__ = "d" * (reader.DOC_LIMIT + 1)
        mesh = SimpleNamespace(get_vertex_positions=method, get_triangle_count=Mock())
        mesh.get_triangle_count.__doc__ = None
        result = reader.query_reflection(SimpleNamespace(MaterialEditingLibrary=SimpleNamespace()), mesh)
        docs = result["query_docs"]
        self.assertTrue(docs["DynamicMesh.get_vertex_positions"]["doc_truncated"])
        self.assertEqual(len(docs["DynamicMesh.get_vertex_positions"]["doc"]), reader.DOC_LIMIT)
        self.assertFalse(docs["DynamicMesh.get_triangle_count"]["doc_available"])

    def test_unreal_cache_input_checkout_matches_committed_raw_bytes(self):
        """Compile/proof cache inputs must be byte-identical on Windows and Linux.

        This is a source checkout guard, not cache/proof admission or a native run.
        """
        import hashlib
        import subprocess

        from scripts.ci.classify_changes import (
            UNREAL_COMPILE_TOOLING_EXACT, UNREAL_PROOF_EXACT,
        )

        repo = reader.ROOT
        critical_ps1 = {path for path in
                        UNREAL_COMPILE_TOOLING_EXACT | UNREAL_PROOF_EXACT
                        if path.endswith(".ps1")}
        listing = subprocess.run(
            ["git", "-C", str(repo), "ls-tree", "-r", "-z", "HEAD", "--",
             "Source", "Plugins", *sorted(critical_ps1)],
            check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        ).stdout
        committed = {}
        for row in listing.split(b"\\0"):
            if not row:
                continue
            header, marker, name = row.partition(b"\\t")
            self.assertEqual(marker, b"\\t")
            mode, obj_type, sha = header.split(b" ")
            self.assertEqual(obj_type, b"blob")
            path = name.decode("utf-8")
            if path.endswith(".cs") or path in critical_ps1:
                self.assertEqual(mode, b"100644")
                committed[path] = sha.decode("ascii")
        self.assertTrue(critical_ps1.issubset(committed))
        self.assertTrue(any(path.endswith(".cs") for path in committed))

        paths = sorted(committed)
        attributes = subprocess.run(
            ["git", "-C", str(repo), "check-attr", "eol", "--", *paths],
            check=True, capture_output=True, text=True,
        ).stdout.splitlines()
        self.assertEqual(len(attributes), len(paths))
        self.assertEqual({line.rpartition(": eol: ")[0]: line.rpartition(": eol: ")[2]
                          for line in attributes},
                         {path: "lf" for path in paths})

        for path, expected in committed.items():
            with self.subTest(path=path):
                raw = (repo / path).read_bytes()
                self.assertNotIn(b"\\r", raw, "fingerprint input has physical CR bytes")
                git_blob = b"blob " + str(len(raw)).encode("ascii") + b"\\0" + raw
                self.assertEqual(hashlib.sha1(git_blob).hexdigest(), expected,
                                 "physical fingerprint input differs from Git HEAD")

    def test_native_dirty_package_boundary_fails_closed(self):
        api = SimpleNamespace(EditorLoadingAndSavingUtils=SimpleNamespace(
            get_dirty_map_packages=list, get_dirty_content_packages=list))
        reader.dirty_packages(api)
        api.EditorLoadingAndSavingUtils.get_dirty_content_packages = lambda: ["dirty"]
        with self.assertRaisesRegex(ValueError, "dirty"):
            reader.dirty_packages(api)
        api.EditorLoadingAndSavingUtils = SimpleNamespace()
        with self.assertRaises(ValueError):
            reader.dirty_packages(api)


if __name__ == "__main__":
    unittest.main()
