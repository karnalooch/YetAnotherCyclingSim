"""Offline tests for bounded immutable-evidence replay; no live network."""

import copy
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_sa_calobra_detail_pilot as replay  # noqa: E402


class FakeResponse(io.BytesIO):
    def __init__(self, data, status=206, content_range=None):
        super().__init__(data)
        self.status = status
        self.headers = {"Content-Range": content_range}


def archive():
    return replay.RemoteArchive(
        {"href": "https://github-cloud.githubusercontent.com/fixture"}
    )


def native_fixture():
    # Exact relevant fields copied from the original receipt with SHA256
    # 35c76796924681c4d836388761bcc3ee83dd6e9fa544c3adb109e004e1c58225.
    return {
        "exact_sha": "b1ea05b33b9f3208e7aeb6884f1a67792d9c6121",
        "status": "COMPONENT230_CLIFF_VISUAL_PASS",
        "map_saved": False,
        "assets_saved": False,
        "canonical_landscape_mutation": False,
        "selector_policy_mutation": False,
        "mesh": {"generator": "native-source-rock-reshape"},
        "terrain_erosion_trial": {
            "restored": True,
            "source_heightfield_unchanged": True,
            "terrain_import_performed": False,
            "derived_heightfield_modified": False,
            "mesh_export": {
                "shape_profile": "rounded-limestone-reshape-v8",
                "displacement_limit_cm": 50,
            },
            "combined_audit": {"status": "PASS"},
        },
    }


class BoundedRangeContracts(unittest.TestCase):
    def test_matching_partial_response_advances_only_verified_bytes(self):
        reader = archive()
        reader.seek(7)
        response = FakeResponse(b"abcd", content_range=f"bytes 7-10/{replay.SIZE}")
        with patch.object(
            replay.urllib.request, "urlopen", return_value=response
        ) as request:
            self.assertEqual(reader.read(4), b"abcd")
        self.assertEqual(reader.tell(), 11)
        self.assertEqual(reader.bytes_read, 4)
        self.assertEqual(reader.requests, 1)
        sent = request.call_args.args[0]
        self.assertEqual(sent.get_header("Range"), "bytes=7-10")
        self.assertEqual(sent.get_header("Accept-encoding"), "identity")

    def test_wrong_status_range_or_truncated_bytes_leave_position_unchanged(self):
        variants = [
            (200, f"bytes 7-10/{replay.SIZE}", b"abcd"),
            (206, f"bytes 7-10/{replay.SIZE + 1}", b"abcd"),
            (206, f"bytes 8-11/{replay.SIZE}", b"abcd"),
            (206, f"bytes 7-10/{replay.SIZE}", b"abc"),
            (206, f"bytes 7-10/{replay.SIZE}", b"abcde"),
        ]
        for status, content_range, data in variants:
            with self.subTest(
                status=status, content_range=content_range, length=len(data)
            ):
                reader = archive()
                reader.seek(7)
                with patch.object(
                    replay.urllib.request,
                    "urlopen",
                    return_value=FakeResponse(data, status, content_range),
                ):
                    with self.assertRaises(ValueError):
                        reader.read(4)
                self.assertEqual(reader.tell(), 7)
                self.assertEqual(reader.bytes_read, 0)
                self.assertEqual(reader.requests, 0)

    def test_seek_bounds_and_exact_eof_do_not_request_network(self):
        reader = archive()
        self.assertEqual(reader.seek(-3, 2), replay.SIZE - 3)
        self.assertEqual(reader.seek(2, 1), replay.SIZE - 1)
        self.assertEqual(reader.seek(1, 1), replay.SIZE)
        for offset, whence in [(-1, 0), (1, 2), (0, 3)]:
            with (
                self.subTest(offset=offset, whence=whence),
                self.assertRaises(ValueError),
            ):
                reader.seek(offset, whence)
            self.assertEqual(reader.tell(), replay.SIZE)
        with patch.object(replay.urllib.request, "urlopen") as network:
            self.assertEqual(reader.read(5), b"")
            network.assert_not_called()

    def test_per_request_and_aggregate_budgets_rejected_before_network(self):
        with patch.object(replay, "LIMIT", 10):
            reader = archive()
            with patch.object(replay.urllib.request, "urlopen") as network:
                with self.assertRaises(ValueError):
                    reader.read(10)
                reader.bytes_read = 39
                with self.assertRaises(ValueError):
                    reader.read(2)
                network.assert_not_called()
            self.assertEqual(reader.tell(), 0)
            self.assertEqual(reader.requests, 0)


class ImmutableReplayContracts(unittest.TestCase):
    def test_native_receipt_requires_identity_and_source_restoration(self):
        valid = native_fixture()
        replay.verify_native(valid)
        for path, bad in [
            (("exact_sha",), "0" * 40),
            (("mesh", "generator"), "unreviewed-generator"),
            (
                ("terrain_erosion_trial", "mesh_export", "shape_profile"),
                "unreviewed-profile",
            ),
            (("terrain_erosion_trial", "restored"), False),
            (("terrain_erosion_trial", "source_heightfield_unchanged"), False),
            (("canonical_landscape_mutation",), True),
        ]:
            with self.subTest(path=path):
                altered = copy.deepcopy(valid)
                parent = altered
                for key in path[:-1]:
                    parent = parent[key]
                parent[path[-1]] = bad
                with self.assertRaises(ValueError):
                    replay.verify_native(altered)

    def test_altered_camera_csv_rejected_before_download_or_output_creation(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            frames = root / "frames.csv"
            frames.write_bytes(b'frame_id,camera_location_cm\nforged-frame,"[0,0,0]"\n')
            annotations = root / "annotations.json"
            annotations.write_text("{}")
            output = root / "output"
            arguments = [
                "replay",
                "--frames",
                str(frames),
                "--annotations",
                str(annotations),
                "--output",
                str(output),
            ]
            with (
                patch.object(replay.sys, "argv", arguments),
                patch.object(replay, "download_action") as network,
            ):
                with self.assertRaisesRegex(
                    ValueError, "(?i)(csv|frames|camera|source).*?(hash|sha|identity)"
                ):
                    replay.main()
                network.assert_not_called()
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
