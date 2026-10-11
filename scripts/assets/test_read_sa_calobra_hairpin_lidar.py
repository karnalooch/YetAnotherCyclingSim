"""Exercise source identity, LAS ownership and bounded observation export."""

import csv
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from scripts.assets import read_sa_calobra_hairpin_lidar as reader


def identity(raw):
    return {"size_bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def profile_fixture():
    rows = []
    for i in range(2401):
        station = i * 0.125
        lateral = [(c - 12) * 0.2 for c in range(25)]
        rows.append(
            {
                "station_m": station,
                "xy_local_m": [[1000 + station, 500 + u] for u in lateral],
                "candidate_ground_m": [
                    601 + station * 0.02 + u * 0.02 for u in lateral
                ],
                "native_ground_m": [600 + station * 0.01 + u * 0.002 for u in lateral],
            }
        )
    return {
        "origin_epsg_m": list(reader.ORIGIN_M),
        "metric_crs": "EPSG:25831",
        "stations": rows,
    }


class Chunk:
    def __init__(self, records):
        self.x, self.y, self.z = (np.array([r[k] for r in records]) for k in range(3))
        self.X, self.Y, self.Z = (
            np.rint(v * 100).astype(np.int64) for v in (self.x, self.y, self.z)
        )
        for offset, key in enumerate(reader.CSV_FIELDS[10:21], start=3):
            setattr(self, key, np.array([r[offset] for r in records], dtype=np.uint16))

    def __len__(self):
        return len(self.x)


class HairpinLidarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.profile = profile_fixture()
        cls.profile_raw = json.dumps(cls.profile, separators=(",", ":")).encode()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.cache, self.output = self.root / "cache", self.root / "evidence"
        self.cache.mkdir()
        e95, e110, north = (
            reader.ORIGIN_M[0] + 1095,
            reader.ORIGIN_M[0] + 1110,
            reader.ORIGIN_M[1] - 500,
        )

        def point(e, n, z, cls=2, withheld=0, synthetic=0, overlap=0):
            return (e, n, z, cls, withheld, synthetic, overlap, 1, 1, 2, 318, 2, 1, 0)

        # The first point is outside; original point indices must not be compacted.
        self.records = [
            point(e95 + 2, north, 602),
            point(e95, north, 602.01),
            point(e95 + 0.5, north - 0.5, 602.02, 65, withheld=1),
            point(e95 + 0.25, north + 0.25, 602.03, 17),
            point(e110, north, 602.04, 7),
            point(e95 - 0.5, north, 602.05, 2, overlap=1),
        ]
        self.inputs, self.headers, self.paths = [], [], []
        self.selected_name = "PNOA_999_9999.laz"  # Deliberately misleading filename.
        for i in range(9):
            name = self.selected_name if i == 4 else f"PNOA_484_440{i}.laz"
            raw = ("original retained source " + name).encode()
            path = self.cache / "manual-cnig" / name
            path.parent.mkdir(exist_ok=True)
            path.write_bytes(raw)
            self.paths.append(path)
            self.inputs.append(
                {"path": "sa-calobra-working-v1/manual-cnig/" + name, **identity(raw)}
            )
            lower = (
                [484000, 4409000, 500] if i == 4 else [486000 + i * 1000, 4409000, 500]
            )
            upper = [lower[0] + 999, lower[1] + 999, 700]
            self.headers.append(
                {
                    "file": name,
                    "points": len(self.records) if i == 4 else 1,
                    "crs": "EPSG:25831",
                    "version": "1.4",
                    "point_format": 8,
                    "bounds": [lower, upper],
                    "scales": [0.01, 0.01, 0.01],
                    "offsets": [0.0, 0.0, 0.0],
                }
            )
        self.manifest = {
            "status": "LIDAR_EVIDENCE_CANDIDATE",
            "geometry_mutation": False,
            "inputs": self.inputs,
            "headers": self.headers,
            "counts": {"decoded_all_tiles": sum(h["points"] for h in self.headers)},
        }
        self.manifest_raw = json.dumps(self.manifest).encode()
        self.manifest_path = self.cache / reader.LIDAR_RELATIVE
        self.manifest_path.parent.mkdir()
        self.manifest_path.write_bytes(self.manifest_raw)
        self.profile_path = self.cache / reader.PROFILE_RELATIVE
        self.profile_path.parent.mkdir()
        self.profile_path.write_bytes(self.profile_raw)
        self.addCleanup(patch.stopall)
        patch.object(reader, "LIDAR_IDENTITY", identity(self.manifest_raw)).start()
        patch.object(reader, "PROFILE_IDENTITY", identity(self.profile_raw)).start()
        patch.object(reader, "CHUNK_SIZE", 2).start()
        self.chunk_calls, self.after_decode = [], None
        self.bad_header = False
        fixture = self

        class LasReader:
            def __init__(self, path):
                self.path = Path(path)
                retained = next(
                    h for h in fixture.headers if h["file"] == self.path.name
                )
                bounds = np.array(retained["bounds"], dtype=float)
                if fixture.bad_header:
                    bounds[1, 0] += 0.01
                self.header = SimpleNamespace(
                    point_count=retained["points"],
                    version="1.4",
                    point_format=SimpleNamespace(id=8),
                    mins=bounds[0],
                    maxs=bounds[1],
                    scales=np.array(retained["scales"]),
                    offsets=np.array(retained["offsets"]),
                    parse_crs=lambda: SimpleNamespace(to_string=lambda: "EPSG:25831"),
                )

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def chunk_iterator(self, size):
                fixture.chunk_calls.append(self.path.name)
                for i in range(0, len(fixture.records), size):
                    yield Chunk(fixture.records[i : i + size])
                if fixture.after_decode:
                    fixture.after_decode()

        self.real_decoder = reader._decoder
        self.decoder = patch.object(
            reader, "_decoder", return_value=(SimpleNamespace(open=LasReader), np)
        ).start()

    def run_reader(self):
        return reader.read(self.cache, self.output)

    def test_exact_byte_mismatch_stops_before_decoder(self):
        self.manifest_path.write_bytes(self.manifest_raw + b"\n")
        report = self.run_reader()
        self.assertEqual(report["status"], "FAILED")
        self.assertIn("source bytes differ", report["error"])
        self.decoder.assert_not_called()
        self.assertFalse((self.output / "hairpin-lidar-points.csv").exists())

    def test_missing_manifest_is_unavailable_without_observations(self):
        self.manifest_path.unlink()
        report = self.run_reader()
        self.assertEqual(report["status"], "UNAVAILABLE")
        self.assertFalse(report["observations_available"])
        self.assertEqual(report["retained_header_status"], "NOT_RUN")
        self.decoder.assert_not_called()

    def test_missing_decoder_retains_exact_header_evidence_only(self):
        self.decoder.side_effect = reader.Unavailable("Existing decoder is absent")
        report = self.run_reader()
        self.assertEqual(report["status"], "UNAVAILABLE")
        self.assertEqual(report["retained_header_status"], "PASS")
        self.assertEqual(report["current_header_status"], "NOT_RUN")
        self.assertEqual(len(report["transects"]), 8)
        self.assertEqual(
            (self.output / "source-lidar-manifest.json").read_bytes(), self.manifest_raw
        )
        self.assertEqual(report["csv_rows"], 0)
        self.assertFalse(list(self.output.glob("*.csv")))

    def test_header_bounds_own_selection_and_source_indices_and_flags_survive(self):
        report = self.run_reader()
        self.assertEqual(report["status"], "OBSERVATIONS_EXPORTED")
        self.assertEqual(report["selected_tiles"], [self.selected_name])
        self.assertEqual(self.chunk_calls, [self.selected_name])
        self.assertEqual(report["post_read_source_status"], "PASS")
        with (self.output / "hairpin-lidar-points.csv").open(newline="") as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual([int(r["point_index"]) for r in rows], [1, 2, 3, 4, 5])
        self.assertEqual([int(r["classification"]) for r in rows], [2, 65, 17, 7, 2])
        self.assertEqual(
            [int(r["accepted_by_existing_reader"]) for r in rows], [1, 0, 1, 0, 0]
        )
        self.assertEqual([int(r["withheld"]) for r in rows], [0, 1, 0, 0, 0])
        self.assertEqual([int(r["overlap"]) for r in rows], [0, 0, 0, 0, 1])
        self.assertTrue(all(r["tile"] == self.selected_name for r in rows))
        self.assertEqual(int(rows[0]["raw_x"]), round(self.records[1][0] * 100))
        self.assertEqual(float(rows[0]["z_m"]), self.records[1][2])
        self.assertEqual(float(rows[1]["lateral_m"]), 0.5)
        self.assertFalse(report["geometry_mutation"] or report["profile_fit"])

    def test_source_frames_preserve_actual_key_and_ground_to_pavement_offset(self):
        frames = reader.transects(self.profile)
        self.assertEqual(
            [f["source_station_m"] for f in frames], list(reader.STATIONS_M)
        )
        frame = next(f for f in frames if f["source_station_m"] == 150)
        self.assertEqual(frame["profile_section_index"], 1200)
        sample = frame["source_samples"][1]
        self.assertAlmostEqual(
            sample["frozen_pavement_m"] - sample["candidate_ground_m"], 0.04
        )
        self.assertAlmostEqual(sample["candidate_minus_native_ground_m"], 2.5)
        self.assertEqual(frame["along_unit"], [1.0, 0.0])
        self.assertEqual(frame["lateral_unit"], [0.0, -1.0])
        changed = {**self.profile, "origin_epsg_m": [483000, 4409516.5]}
        with self.assertRaisesRegex(ValueError, "CRS/origin"):
            reader.transects(changed)

    def test_csv_bytes_do_not_depend_on_decoder_chunk_boundaries(self):
        first = self.run_reader()
        with patch.object(reader, "CHUNK_SIZE", 3):
            second = reader.read(self.cache, self.root / "second-evidence")
        self.assertEqual(second["status"], "OBSERVATIONS_EXPORTED")
        self.assertEqual(first["csv"], second["csv"])

    def test_wrong_decoder_version_is_reported_without_import_or_install(self):
        versions = {**reader.DECODER_VERSIONS, "laspy": "0.0.0"}
        report = {}
        with (
            patch.object(
                reader.importlib.metadata, "version", side_effect=versions.__getitem__
            ),
            self.assertRaisesRegex(reader.Unavailable, "pinned versions"),
        ):
            self.real_decoder(report)
        self.assertEqual(report["decoder_versions"], versions)

    def test_current_header_mismatch_blocks_point_decoding(self):
        self.bad_header = True
        report = self.run_reader()
        self.assertEqual(report["status"], "FAILED")
        self.assertIn("Current LAS header differs", report["error"])
        self.assertEqual(self.chunk_calls, [])
        self.assertFalse(list(self.output.glob("*.csv")))

    def test_raw_source_tamper_is_rejected_before_any_decoder_call(self):
        self.paths[4].write_bytes(b"tampered")
        report = self.run_reader()
        self.assertEqual(report["status"], "FAILED")
        self.decoder.assert_not_called()

    def test_changed_source_after_decode_never_promotes_partial_csv(self):
        self.after_decode = lambda: self.paths[4].write_bytes(b"changed after decode")
        report = self.run_reader()
        self.assertEqual(report["status"], "FAILED")
        self.assertFalse(report["observations_available"])
        self.assertEqual(report["post_read_source_status"], "NOT_RUN")
        self.assertTrue((self.output / "hairpin-lidar-points.partial.csv").exists())
        self.assertFalse((self.output / "hairpin-lidar-points.csv").exists())

    def test_csv_limit_fails_without_truncating_to_a_success(self):
        with patch.object(reader, "MAX_CSV_ROWS", 2):
            report = self.run_reader()
        self.assertEqual(report["status"], "FAILED")
        self.assertIn("bound exceeded", report["error"])
        self.assertFalse(report["observations_available"])
        self.assertFalse((self.output / "hairpin-lidar-points.csv").exists())

    def test_existing_output_and_source_cache_output_are_never_modified(self):
        self.output.mkdir()
        sentinel = self.output / "keep.txt"
        sentinel.write_text("retain me")
        with self.assertRaises(FileExistsError):
            self.run_reader()
        self.assertEqual(sentinel.read_text(), "retain me")
        with self.assertRaisesRegex(ValueError, "source cache"):
            reader.read(self.cache, self.cache / "new-evidence")
        self.assertFalse((self.cache / "new-evidence").exists())

    def test_original_source_paths_cannot_escape_cache(self):
        with self.assertRaisesRegex(ValueError, "escapes"):
            reader._safe(self.cache, "../outside.laz")

    def test_cli_returns_explicit_unavailable_exit_and_new_receipt(self):
        config_path = self.root / "workspace.json"
        config_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    **{
                        name: name
                        for name in ("project", "data", "cache", "checkpoints", "work")
                    },
                }
            )
        )
        with (
            patch.object(
                reader.sys,
                "argv",
                [
                    "read",
                    "--workspace-config",
                    str(config_path),
                    "--output-name",
                    "hairpin-test",
                ],
            ),
            patch.object(reader.sys, "stdout", io.StringIO()),
        ):
            self.assertEqual(reader.main(), 2)
        out = self.root / "work/hairpin-test"
        report = json.loads((out / "hairpin-lidar.json").read_text())
        self.assertEqual(report["status"], "UNAVAILABLE")
        self.assertFalse(list(out.glob("*.csv")))


class ExistingDecoderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.executable = self.root / "existing-python.exe"
        self.executable.write_bytes(b"existing executable fixture")
        self.workspace = {"project": str(self.root / "project")}
        self.addCleanup(patch.stopall)
        patch.object(reader.sys, "executable", str(self.executable)).start()
        patch.object(reader.shutil, "which", return_value=None).start()

    def qualified(self):
        return {
            "status": "EXISTING_DECODER_READY",
            "executable": str(self.executable),
            "executable_identity": identity(self.executable.read_bytes()),
            "python_version": [3, 12, 10],
            "implementation": "cpython", "pointer_bits": 64,
            "imports_verified": True,
            "decoder_versions": dict(reader.DECODER_VERSIONS),
        }

    def child(self, probe, code=0):
        return SimpleNamespace(
            returncode=code, stdout=json.dumps(probe).encode(), stderr=b""
        )

    def test_missing_old_venv_uses_only_successfully_qualified_known_executable(self):
        with patch.object(
            reader.subprocess, "run", return_value=self.child(self.qualified())
        ) as run:
            report = reader.resolve_existing_decoder(self.workspace)
        self.assertEqual(report["status"], "EXISTING_DECODER_SELECTED")
        self.assertEqual(report["candidates"][0]["status"], "MISSING")
        self.assertEqual(report["selected"]["path"], str(self.executable))
        self.assertFalse(report["installation_performed"])
        self.assertFalse(report["source_read"])
        self.assertEqual(run.call_count, 1)
        self.assertEqual(run.call_args.kwargs["timeout"], 15)
        self.assertEqual(run.call_args.args[0][1:3], ["-I", "-B"])
        self.assertEqual(run.call_args.args[0][-1], "--probe-decoder")

    def test_exit_zero_cannot_qualify_wrong_packages_abi_or_unverified_imports(self):
        for change in (
            {"decoder_versions": {**reader.DECODER_VERSIONS, "lazrs": "0.0.0"}},
            {"python_version": [3, 14, 8]}, {"imports_verified": False},
            {"pointer_bits": 32}, {"executable_identity": identity(b"different")},
        ):
            with self.subTest(change=change), patch.object(
                reader.subprocess, "run",
                return_value=self.child({**self.qualified(), **change}),
            ):
                report = reader.resolve_existing_decoder(self.workspace)
                self.assertIsNone(report["selected"])
                self.assertEqual(report["status"], "GIS_ENVIRONMENT_UNAVAILABLE")

    def test_actual_import_failure_is_not_a_qualified_environment(self):
        with (
            patch.object(reader.sys, "version_info", (3, 12, 10)),
            patch.object(reader, "_decoder", side_effect=ImportError("native DLL absent")),
        ):
            report = reader.decoder_environment()
        self.assertFalse(report["imports_verified"])
        self.assertEqual(report["status"], "UNAVAILABLE")
        self.assertIn("native DLL absent", report["error"])

    def test_changed_executable_is_rejected_after_real_probe_result(self):
        result = self.child(self.qualified())

        def mutate(*args, **kwargs):
            self.executable.write_bytes(b"changed executable")
            return result

        with patch.object(reader.subprocess, "run", side_effect=mutate):
            report = reader.resolve_existing_decoder(self.workspace)
        self.assertIsNone(report["selected"])
        self.assertIn("changed during", report["candidates"][-1]["error"])

    def test_timeout_and_missing_candidates_never_select_an_interpreter(self):
        with patch.object(
            reader.subprocess, "run",
            side_effect=reader.subprocess.TimeoutExpired("owned probe", 15),
        ):
            report = reader.resolve_existing_decoder(self.workspace)
        self.assertIsNone(report["selected"])
        self.assertEqual(report["candidates"][-1]["status"], "TIMED_OUT")
        self.executable.unlink()
        with patch.object(reader.subprocess, "run") as run:
            report = reader.resolve_existing_decoder(self.workspace)
        run.assert_not_called()
        self.assertTrue(all(row["status"] == "MISSING" for row in report["candidates"]))

    def test_only_absolute_named_pyvenv_metadata_is_inspected_and_deduplicated(self):
        config = self.root / "project/.venv/pyvenv.cfg"
        config.parent.mkdir(parents=True)
        config.write_text(f"executable = {self.executable}\nhome = relative/path\n")
        with patch.object(
            reader.subprocess, "run", return_value=self.child({"status": "UNAVAILABLE"}, 2)
        ) as run:
            report = reader.resolve_existing_decoder(self.workspace)
        self.assertEqual(run.call_count, 1)
        self.assertEqual(len(report["candidates"]), 2)
        self.assertIsNone(report["selected"])
        self.assertEqual(report["project_pyvenv_config"], identity(config.read_bytes()))


if __name__ == "__main__":
    unittest.main()
