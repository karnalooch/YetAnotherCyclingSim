"""Producer-to-admission regression; no Unreal or GPU impersonation."""

import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from scripts.ci.sa_calobra_performance import evaluate


class SaCalobraPerformanceTests(unittest.TestCase):
    def fixture(self, root, gpu=7.0):
        (root / "Prepared").mkdir()
        (root / "Prepared/terrain-import.json").write_text(
            json.dumps({"heightmap_sha256": "b" * 64})
        )
        (root / "sa-calobra-settings.json").write_text("{}")
        csv = root / "sa-calobra-terrain-performance.csv"
        csv.write_text(
            "sector,rel_s,frame_ms,game_ms,draw_ms,rhi_ms,gpu_ms\n"
            + "".join(
                f"{sector},{i / 60},10,3,2,1,{gpu}\n"
                for sector in ["overview", "rider", "slope"]
                for i in range(120)
            )
        )
        Path(str(csv) + ".identity.json").write_text(
            json.dumps(
                {
                    "MapPackage": "/Game/Worlds/SaCalobra/L_SaCalobraTerrainBaseline",
                    "ComponentCount": 1024,
                    "ActiveGpu": "NVIDIA GeForce RTX 2070 SUPER",
                    "Resolution": "1920x1080",
                }
            )
        )

    def test_producer_summary_passes_shared_raw_sample_admission(self):
        with (
            tempfile.TemporaryDirectory() as folder,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            root = Path(folder)
            self.fixture(root)
            result = evaluate(root, "a" * 40, 0)
            self.assertEqual(result["Result"], "PASS")
            self.assertEqual(len(result["Sectors"]), 3)

    def test_missing_gpu_fails_and_retains_failure_receipt(self):
        with (
            tempfile.TemporaryDirectory() as folder,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            root = Path(folder)
            self.fixture(root, 0)
            with self.assertRaises(ValueError):
                evaluate(root, "a" * 40, 0)
            self.assertEqual(
                json.loads(
                    (root / "sa-calobra-terrain-performance-summary.json").read_text()
                )["Result"],
                "FAIL",
            )

    def test_editor_failure_cannot_publish_pass(self):
        with (
            tempfile.TemporaryDirectory() as folder,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            root = Path(folder)
            self.fixture(root)
            with self.assertRaises(ValueError):
                evaluate(root, "a" * 40, 1)
