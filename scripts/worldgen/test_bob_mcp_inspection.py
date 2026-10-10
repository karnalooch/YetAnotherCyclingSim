"""Synthetic unit fixtures verify domain delegation, never native/MCP admission."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import stat
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

from scripts.worldgen import bob_mcp_inspection as adapter
from scripts.worldgen import bob_terrain_fit_inspector as inspector


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


class BobMcpInspectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # The executing candidate is uncommitted in the development checkout.
        # Isolate source-SHA tests in a real temporary Git repository, including
        # the adapter; this makes no commit or index change in the user's repo.
        cls.repository_directory = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.repository_directory.cleanup)
        cls.repository_root = Path(cls.repository_directory.name)
        for relative in adapter.SOURCE_PATHS:
            destination = cls.repository_root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes((adapter.ROOT / relative).read_bytes())
        for arguments in (
            ["init", "--quiet"], ["add", "--", *adapter.SOURCE_PATHS],
            ["-c", "user.name=BOB unit fixture", "-c", "user.email=bob-unit@example.invalid",
             "commit", "--quiet", "-m", "Synthetic domain source fixture"],
        ):
            subprocess.run(["git", "-C", str(cls.repository_root), *arguments],
                           check=True, capture_output=True)
        cls.exact_sha = subprocess.run(
            ["git", "-C", str(cls.repository_root), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
        cls.source_hashes = {
            path: digest((cls.repository_root / path).read_bytes())
            for path in adapter.SOURCE_PATHS
        }

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        # These are deliberately synthetic test rows, not admitted UE evidence.
        self.samples = [
            {"station_m": float(index), "lateral_m": 0.0,
             "local_xy_m": [float(index), 0.0], "road_surface_z_m": 100.0,
             "landscape_z_m": ground}
            for index, ground in enumerate([99.96, 100.5, 99.0, 95.0])
        ]
        self.envelope = {
            "schema_version": 1, "exact_sha": self.exact_sha,
            "region_id": "sa_calobra", "producer": adapter.NATIVE_PRODUCER,
            "sample_source": adapter.NATIVE_SAMPLE_SOURCE,
            "geometry_inspection_view": "road-geometry-inspection-before",
            "source_sha256": dict(self.source_hashes), "samples": self.samples,
        }
        self.request = {
            "exact_sha": self.exact_sha, "native_samples_path": "native-samples.json",
            "native_samples_sha256": "", "source_sha256": dict(self.source_hashes),
        }
        self.write_envelope()

    def write_raw(self, raw):
        self.path = self.root / "native-samples.json"
        self.path.write_bytes(raw)
        self.request["native_samples_sha256"] = digest(raw)

    def write_envelope(self):
        self.write_raw((json.dumps(self.envelope, indent=2) + "\n").encode())

    def inspect(self, request=None):
        with mock.patch.object(adapter, "ROOT", self.repository_root):
            return adapter.inspect_bob_request(
                self.request if request is None else request, evidence_root=self.root,
                repository_root=self.repository_root,
            )

    def test_delegates_to_real_inspector_and_binds_actual_result_and_input_bytes(self):
        before = self.path.read_bytes()
        with mock.patch.object(adapter, "inspect_terrain_fit", wraps=inspector.inspect_terrain_fit) as delegate:
            bundle = self.inspect()
        delegate.assert_called_once()
        result = bundle["result"]
        self.assertEqual(result, inspector.inspect_terrain_fit(
            self.samples, exact_sha=self.exact_sha, contact_band_max_m=0.08,
            structure_review_threshold_m=4.0,
            geometry_inspection_view="road-geometry-inspection-before",
        ))
        self.assertEqual(result["class_counts"], {
            "CONTACT_OK": 1, "CUT_REQUIRED": 1,
            "FILL_REQUIRED": 1, "STRUCTURE_REVIEW": 1,
        })
        self.assertEqual(result["status"], "REVIEW_REQUIRED")
        proof, receipt = bundle["proof"], bundle["receipt"]
        self.assertEqual(proof["input"]["sha256"], digest(before))
        self.assertEqual(proof["input"]["path"], str(self.path))
        self.assertEqual(proof["source_sha256"], self.source_hashes)
        self.assertEqual(proof["output"]["sha256"], digest(adapter.canonical_json_bytes(result)))
        self.assertEqual(proof["direct_invocation_sha256"], proof["output"]["sha256"])
        self.assertEqual(receipt["proof"]["sha256"], digest(adapter.canonical_json_bytes(proof)))
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(set(self.root.iterdir()), {self.path})
        for flag in adapter.FALSE_FLAGS:
            self.assertIs(result[flag], False)
            self.assertIs(receipt[flag], False)
        self.assertEqual(receipt["evidence_scope"], "DOMAIN_DELEGATION_ONLY")
        for claim in ("native_capture_verified", "official_mcp_verified", "persistent_content_verified"):
            self.assertIs(receipt[claim], False)

    def test_trace_misses_retain_incomplete_domain_result(self):
        self.envelope["samples"][0]["landscape_z_m"] = None
        self.write_envelope()
        bundle = self.inspect()
        self.assertEqual(bundle["result"]["trace_miss_count"], 1)
        self.assertEqual(bundle["result"]["status"], "INSPECTION_INCOMPLETE")
        self.assertEqual(bundle["receipt"]["domain_status"], "INSPECTION_INCOMPLETE")
        self.assertIs(bundle["result"]["inspection_complete"], False)

    def test_rejects_request_engineering_overrides_and_arbitrary_execution(self):
        for name, value in {
            "contact_band_max_m": 20.0, "structure_review_threshold_m": 100.0,
            "python": "print('not admitted')", "save_map": True,
            "evidence_root": str(self.root),
        }.items():
            with self.subTest(name=name):
                request = {**self.request, name: value}
                with mock.patch.object(adapter, "inspect_terrain_fit") as delegate:
                    with self.assertRaisesRegex(ValueError, "exactly"):
                        self.inspect(request)
                    delegate.assert_not_called()

    def test_rejects_stale_repository_sample_and_fixed_source_hashes(self):
        requests = [
            {**self.request, "exact_sha": "0" * 40},
            {**self.request, "native_samples_sha256": "0" * 64},
            {**self.request, "source_sha256": {**self.source_hashes, adapter.POLICY: "0" * 64}},
            {**self.request, "source_sha256": {**self.source_hashes, "arbitrary.py": "0" * 64}},
            {**self.request, "source_sha256": {}},
        ]
        for request in requests:
            with self.subTest(request=request):
                with mock.patch.object(adapter, "inspect_terrain_fit") as delegate:
                    with self.assertRaises(ValueError):
                        self.inspect(request)
                    delegate.assert_not_called()

    def test_rejects_source_hashes_that_match_dirty_bytes_but_not_the_pinned_commit(self):
        real_git = adapter._git

        def changed_committed_source(root, *arguments):
            raw = real_git(root, *arguments)
            return raw + b"\n" if arguments[0] == "show" else raw

        with mock.patch.object(adapter, "_git", side_effect=changed_committed_source):
            with self.assertRaisesRegex(ValueError, "differs from exact_sha"):
                self.inspect()

    def test_rejects_dirty_or_uncommitted_executing_adapter(self):
        path = self.repository_root / adapter.ADAPTER
        original = path.read_bytes()
        self.addCleanup(path.write_bytes, original)
        path.write_bytes(original + b"\n# uncommitted adapter change\n")
        request = deepcopy(self.request)
        request["source_sha256"][adapter.ADAPTER] = digest(path.read_bytes())
        with self.assertRaisesRegex(ValueError, "executing domain source hash mismatch"):
            self.inspect(request)

    def test_rejects_windows_junction_reparse_metadata(self):
        real_lstat = Path.lstat

        def junction_metadata(path):
            metadata = real_lstat(path)
            if path == self.path:
                return SimpleNamespace(st_mode=metadata.st_mode,
                    st_file_attributes=getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
            return metadata

        with mock.patch.object(Path, "lstat", junction_metadata):
            with self.assertRaisesRegex(ValueError, "reparse"):
                self.inspect()

    def test_rejects_file_drift_during_bounded_read(self):
        real_stat = Path.stat
        calls = 0

        def changed_metadata(path, *arguments, **keywords):
            nonlocal calls
            metadata = real_stat(path, *arguments, **keywords)
            if path == self.path and keywords.get("follow_symlinks") is not False:
                calls += 1
                return SimpleNamespace(st_mode=metadata.st_mode, st_dev=metadata.st_dev,
                    st_ino=metadata.st_ino, st_size=metadata.st_size,
                    st_mtime_ns=metadata.st_mtime_ns + calls,
                    st_ctime_ns=metadata.st_ctime_ns)
            return metadata

        with mock.patch.object(Path, "stat", changed_metadata):
            with self.assertRaisesRegex(ValueError, "changed while being read"):
                self.inspect()

    def test_rejects_empty_or_aggregate_data_and_unknown_sample_fields(self):
        for samples in ([], {}, [{**self.samples[0], "class_counts": {}}],
                        [{key: value for key, value in self.samples[0].items() if key != "station_m"}]):
            with self.subTest(samples=samples):
                self.envelope["samples"] = samples
                self.write_envelope()
                with self.assertRaises(ValueError):
                    self.inspect()

    def test_rejects_unbound_native_identity_and_envelope_overrides(self):
        cases = [
            ("exact_sha", "1" * 40), ("region_id", "italy"),
            ("producer", "synthetic_generator"), ("sample_source", "r16_interpolation"),
            ("source_sha256", {}), ("geometry_inspection_view", "unreviewed"),
            ("geometry_inspection_view", []),
            ("schema_version", True), ("contact_band_max_m", 20.0),
        ]
        original = deepcopy(self.envelope)
        for name, value in cases:
            with self.subTest(name=name):
                self.envelope = {**original, name: value}
                self.write_envelope()
                with self.assertRaises(ValueError):
                    self.inspect()

    def test_rejects_invalid_numbers(self):
        for value in (True, "100", float("inf"), float("nan")):
            with self.subTest(value=value):
                self.envelope["samples"][0]["road_surface_z_m"] = value
                self.write_envelope()
                with self.assertRaises(ValueError):
                    self.inspect()

    def test_rejects_duplicate_json_keys(self):
        raw = json.dumps(self.envelope).replace('"schema_version": 1',
                                              '"schema_version": 1, "schema_version": 1')
        self.write_raw(raw.encode())
        with self.assertRaisesRegex(ValueError, "duplicate JSON"):
            self.inspect()

    def test_rejects_lfs_pointer_even_when_its_hash_matches(self):
        self.write_raw(b"version https://git-lfs.github.com/spec/v1\noid sha256:" + b"a" * 64 + b"\nsize 99\n")
        with self.assertRaisesRegex(ValueError, "Git LFS pointer"):
            self.inspect()

    def test_rejects_absolute_traversing_and_symlink_paths(self):
        for relative in (str(self.path), "../native-samples.json", "./native-samples.json",
                         "nested/../../native-samples.json", "nested\\native-samples.json",
                         "native-samples.json:alternate", "C:native-samples.json", "bad\x00.json"):
            with self.subTest(relative=relative):
                with self.assertRaises(ValueError):
                    self.inspect({**self.request, "native_samples_path": relative})
        link = self.root / "link.json"
        link.symlink_to(self.path)
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.inspect({**self.request, "native_samples_path": "link.json"})
        directory = self.root / "nested"
        directory.symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.inspect({**self.request, "native_samples_path": "nested/native-samples.json"})

    def test_rejects_input_drift_during_execution(self):
        real_inspect = inspector.inspect_terrain_fit

        def drift(samples, **arguments):
            result = real_inspect(samples, **arguments)
            self.path.write_bytes(self.path.read_bytes() + b"\n")
            return result

        with mock.patch.object(adapter, "inspect_terrain_fit", side_effect=drift):
            with self.assertRaisesRegex(ValueError, "stale SHA256"):
                self.inspect()

    def test_rejects_delegation_that_changes_domain_result(self):
        real_inspect = inspector.inspect_terrain_fit

        def fake_result(samples, **arguments):
            result = real_inspect(samples, **arguments)
            result["status"] = "PASS"
            return result

        with mock.patch.object(adapter, "inspect_terrain_fit", side_effect=fake_result):
            with self.assertRaisesRegex(ValueError, "differs from direct"):
                self.inspect()

    def test_rejects_authoring_admission_even_if_both_invocations_match(self):
        real_inspect = inspector.inspect_terrain_fit

        def bad_contract(samples, **arguments):
            result = real_inspect(samples, **arguments)
            result["eligible_for_learning"] = True
            return result

        with mock.patch.object(adapter, "inspect_terrain_fit", side_effect=bad_contract):
            with mock.patch.object(inspector, "inspect_terrain_fit", side_effect=bad_contract):
                with self.assertRaisesRegex(ValueError, "read-only domain contract"):
                    self.inspect()


if __name__ == "__main__":
    unittest.main()
