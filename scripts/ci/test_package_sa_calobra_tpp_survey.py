"""Primary-evidence admission and durable navigation, without Unreal or codecs."""

from __future__ import annotations

import copy
import csv
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from scripts.proof.package_sa_calobra_tpp_survey import digest, package, validate
from scripts.proof.sa_calobra_tpp_survey import (
    FROZEN_SHA,
    REPOSITORY_RECIPE,
    SurveyConfig,
    build_survey_plan,
)

SHA = "a" * 40


def section(x, z=0):
    return [[x, -2, z], [x, 2, z]]


class SurveyPackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "Survey"
        (self.root / "frames").mkdir(parents=True)
        recipe = json.loads(REPOSITORY_RECIPE.read_text(encoding="utf-8-sig"))
        source_identity = {
            "accepted_road_sha": FROZEN_SHA,
            "recipe_sha256": digest(REPOSITORY_RECIPE),
            "source_run_id": recipe["source_run_id"],
            "verified_input_count": len(recipe["inputs"]),
            "network_window_count": 1,
            "checkpoint_hairpin_count": 1,
            "geometry_consumers_executed": False,
        }
        self.report = build_survey_plan(
            [
                {"id": "first", "sections": [section(0), section(25, 2)]},
                {"id": "second", "sections": [section(200), section(220)]},
            ],
            SurveyConfig(SHA),
            source_identity=source_identity,
        )
        self.report["planned_frames"] = copy.deepcopy(self.report["frames"])
        self.report.update(
            status="CAPTURED",
            error=None,
            saved_to_map=False,
            physical_simulation=False,
            performance_acceptance="NOT_MEASURED",
            visual_acceptance="PENDING_REVIEW",
            cleanup={"status": "RESTORED"},
            source_scene={
                "map": "/Game/Generated/SaCalobra/L_Test",
                "map_sha256": "b" * 64,
                "accepted_cliff_implementation_sha": "4f2cba560d54931dc8ba080370d96a7aad24f15b",
                "cliff_recipe": "limestone-local-reshape-v8",
                "component": "Component_230",
                "scope": "Synthetic test scene",
                "material_path": "/Game/Generated/SaCalobra/M_Limestone",
            },
        )
        for frame in self.report["frames"]:
            path = self.root / frame["file"]
            Image.new("RGB", (160, 90), (frame["index"] * 16, 64, 96)).save(path)
            readiness_file = f"readiness/{frame['frame_id']}/capture-readiness.json"
            readiness_path = self.root / readiness_file
            readiness_path.parent.mkdir(parents=True)
            readiness_path.write_text(
                json.dumps(
                    {
                        "status": "NATIVE_LOADING_AND_MIPS_READY",
                        "height_mip_lease_requested": True,
                        "native_loading_barrier_completed": True,
                        "saved_to_map": False,
                        "height_edits_applied": False,
                        "textures_after": [
                            {
                                "is_default_texture": False,
                                "is_compiling": False,
                                "mips": 4,
                                "resident_mips": 4,
                            }
                        ],
                    }
                )
            )
            frame.update(
                sha256=digest(path),
                size_bytes=path.stat().st_size,
                width_px=160,
                height_px=90,
                native_readiness={
                    "status": "NATIVE_LOADING_AND_MIPS_READY",
                    "full_height_mips_requested": True,
                    "height_texture_count": 1,
                    "receipt": readiness_file,
                    "sha256": digest(readiness_path),
                },
            )
        self.save()

    def save(self):
        (self.root / "survey.json").write_text(
            json.dumps(self.report), encoding="utf-8"
        )

    def both(self, index, key, value):
        self.report["frames"][index][key] = value
        self.report["planned_frames"][index][key] = value
        self.save()

    def test_complete_evidence_preserves_primary_bytes_and_pairs_directions(self):
        primary = {
            path: digest(path) for path in self.root.rglob("*") if path.is_file()
        }
        report, pairs = validate(self.root, SHA)
        self.assertEqual(len(pairs) * 2, report["frame_count"])
        for _, station, pair in pairs:
            self.assertEqual(pair["forward"]["station_m"], station)
            self.assertEqual(pair["reverse"]["station_m"], station)
            self.assertNotEqual(
                pair["forward"]["camera_location_cm"],
                pair["reverse"]["camera_location_cm"],
            )
        receipt = package(self.root, SHA)
        self.assertEqual(receipt["technical_status"], "VALIDATED")
        self.assertEqual(receipt["performance_acceptance"], "NOT_MEASURED")
        self.assertEqual(receipt["pair_count"], len(pairs))
        self.assertEqual({path: digest(path) for path in primary}, primary)
        output = self.root / "review"
        document = (output / "index.html").read_text()
        self.assertIn("750 ms", document)
        for frame in report["frames"]:
            self.assertIn(f'href="../{frame["file"]}"', document)
            self.assertIn('coords="', document)
        with (output / "surface-review-template.csv").open(newline="") as source:
            rows = list(csv.DictReader(source))
        self.assertEqual(len(rows), len(pairs))
        self.assertEqual({row["review_status"] for row in rows}, {"UNREVIEWED"})
        self.assertEqual({row["surface_priority"] for row in rows}, {"UNASSIGNED"})
        self.assertTrue(all(row["visible_duration_s"] == "" for row in rows))
        svg = (output / "route.svg").read_text()
        self.assertIn("stroke-dasharray", svg)
        self.assertIn("no connecting road proved", svg)
        self.assertIn("#39a5ff", svg)
        self.assertIn("#ffb454", svg)
        self.assertIn(
            "source_scene",
            json.loads((output / "package-verification.json").read_text()),
        )
        with (output / "frames.csv").open(newline="") as source:
            rows = list(csv.DictReader(source))
        self.assertEqual(len(rows), report["frame_count"])
        self.assertEqual(
            {row["native_readiness_status"] for row in rows},
            {"NATIVE_LOADING_AND_MIPS_READY"},
        )

    def test_short_expected_sha_and_mismatched_capture_sha_fail(self):
        for expected in ("main", SHA[:8], "A" * 40, "b" * 40):
            with (
                self.subTest(expected=expected),
                self.assertRaisesRegex(ValueError, "SHA"),
            ):
                validate(self.root, expected)

    def test_surface_tags_have_visible_legend_and_evidence_backed_multi_tag_template(
        self,
    ):
        package(self.root, SHA)
        output = self.root / "review"
        document = (output / "index.html").read_text()
        guide = (output / "review-guide.txt").read_text()
        for tag in (
            "GEO_FIX",
            "SILHOUETTE_CRITICAL",
            "HERO_DETAIL",
            "BACKGROUND_LOW_PRIORITY",
            "MATERIAL_TEST_CANDIDATE",
        ):
            with self.subTest(tag=tag):
                self.assertIn(f"<dt><code>{tag}</code></dt><dd>", document)
                self.assertIn(tag + ": ", guide)
        for text in (document, guide):
            self.assertIn("GEO_FIX;SILHOUETTE_CRITICAL", text)
            self.assertIn("surface_id", text)
            self.assertIn("evidence_reason", text)
            self.assertIn("evidence_frame", text)
            self.assertIn("oryginalnego PNG", text)
        self.assertIn("nie wykluczają się", document)
        self.assertIn("nie uruchamiają automatycznych zmian", document)
        with (output / "surface-review-template.csv").open(newline="") as source:
            rows = list(csv.DictReader(source))
        self.assertTrue(rows)
        for row in rows:
            self.assertEqual(row["review_tags"], "")
            self.assertEqual(row["evidence_reason"], "")
            self.assertEqual(row["evidence_frame"], "")
            self.assertEqual(row["review_status"], "UNREVIEWED")

    def test_status_cleanup_and_acceptance_fail_closed(self):
        original = copy.deepcopy(self.report)
        for update in (
            {"status": "RUNNING"},
            {"status": "FAILED"},
            {"error": "capture timeout"},
            {"cleanup": {"status": "PENDING"}},
            {"performance_acceptance": "PASSED"},
            {"visual_acceptance": "ACCEPTED"},
            {"saved_to_map": True},
            {"physical_simulation": True},
            {"continuous_route": True},
        ):
            with self.subTest(update=update):
                self.report = copy.deepcopy(original)
                self.report.update(update)
                self.save()
                with self.assertRaises(ValueError):
                    validate(self.root, SHA)
        self.assertFalse((self.root / "review").exists())

    def test_missing_or_mismatched_provenance_fails(self):
        self.report["source_scene"]["map_sha256"] = "pending"
        self.save()
        with self.assertRaisesRegex(ValueError, "map SHA256"):
            validate(self.root, SHA)
        self.report["source_scene"]["map_sha256"] = "b" * 64
        self.report["source_identity"]["recipe_sha256"] = "c" * 64
        self.save()
        with self.assertRaisesRegex(ValueError, "source identity"):
            validate(self.root, SHA)

    def test_tampered_hash_dimensions_and_byte_count_fail(self):
        original = copy.deepcopy(self.report)
        for key, value, message in (
            ("sha256", "b" * 64, "SHA256"),
            ("size_bytes", 1, "byte count"),
            ("width_px", 161, "dimensions"),
        ):
            with self.subTest(key=key):
                self.report = copy.deepcopy(original)
                self.report["frames"][0][key] = value
                self.save()
                with self.assertRaisesRegex(ValueError, message):
                    validate(self.root, SHA)

    def test_hash_receipt_does_not_make_non_png_valid(self):
        frame = self.report["frames"][0]
        path = self.root / frame["file"]
        path.write_bytes(b"not a native PNG")
        frame.update(sha256=digest(path), size_bytes=path.stat().st_size)
        self.save()
        with self.assertRaisesRegex(ValueError, "PNG decode"):
            validate(self.root, SHA)

    def test_missing_captured_frame_and_missing_file_fail(self):
        frame = self.report["frames"].pop()
        self.save()
        with self.assertRaisesRegex(ValueError, "missing or excess"):
            validate(self.root, SHA)
        self.report["frames"].append(frame)
        self.save()
        (self.root / frame["file"]).unlink()
        with self.assertRaisesRegex(ValueError, "missing or path"):
            validate(self.root, SHA)

    def test_escape_absolute_path_and_symlinks_fail(self):
        original = self.report["frames"][0]["file"]
        for path in (
            "../outside.png",
            "frames/../outside.png",
            "/tmp/outside.png",
            "frames\\outside.png",
        ):
            with self.subTest(path=path):
                self.both(0, "file", path)
                with self.assertRaisesRegex(ValueError, "unsafe frame path"):
                    validate(self.root, SHA)
        self.both(0, "file", original)
        source = self.root / original
        outside = Path(self.temp.name) / "outside.png"
        source.replace(outside)
        source.symlink_to(outside)
        with self.assertRaisesRegex(ValueError, "symlink"):
            validate(self.root, SHA)

    def test_untracked_extra_screenshot_fails(self):
        Image.new("RGB", (1, 1)).save(self.root / "frames/stale.PNG")
        with self.assertRaisesRegex(ValueError, "stale or untracked"):
            validate(self.root, SHA)

    def test_plan_mismatch_and_geometry_recomputation_detect_cam_drift(self):
        self.report["frames"][0]["camera_location_cm"][0] += 1
        self.save()
        with self.assertRaisesRegex(ValueError, "plan mismatch"):
            validate(self.root, SHA)
        self.report["planned_frames"][0]["camera_location_cm"][0] += 1
        self.save()
        with self.assertRaisesRegex(ValueError, "TPP rig mismatch"):
            validate(self.root, SHA)

    def test_spacing_schedule_detects_changed_station_even_in_plan(self):
        self.both(1, "station_m", 7.0)
        with self.assertRaisesRegex(ValueError, "schedule mismatch"):
            validate(self.root, SHA)

    def test_readiness_missing_full_mips_fails(self):
        self.report["frames"][0]["native_readiness"]["full_height_mips_requested"] = (
            False
        )
        self.save()
        with self.assertRaisesRegex(ValueError, "native mip readiness"):
            validate(self.root, SHA)

    def test_full_readiness_hash_and_residency_are_checked(self):
        readiness = self.report["frames"][0]["native_readiness"]
        path = self.root / readiness["receipt"]
        full = json.loads(path.read_text())
        full["textures_after"][0]["resident_mips"] = 2
        path.write_text(json.dumps(full))
        with self.assertRaisesRegex(ValueError, "readiness receipt SHA256"):
            validate(self.root, SHA)
        readiness["sha256"] = digest(path)
        self.save()
        with self.assertRaisesRegex(ValueError, "not fully resident"):
            validate(self.root, SHA)

    def test_readiness_receipt_escape_and_missing_file_fail(self):
        readiness = self.report["frames"][0]["native_readiness"]
        original = readiness["receipt"]
        readiness["receipt"] = "../capture-readiness.json"
        self.save()
        with self.assertRaisesRegex(ValueError, "unsafe native readiness"):
            validate(self.root, SHA)
        readiness["receipt"] = original
        self.save()
        (self.root / original).unlink()
        with self.assertRaisesRegex(ValueError, "missing or path-escaping native"):
            validate(self.root, SHA)

    def test_packager_retains_previous_human_review_notes(self):
        package(self.root, SHA)
        notes = self.root / "review/surface-review-template.csv"
        notes.write_text("owner decisions retained\n")
        with self.assertRaisesRegex(ValueError, "already exists"):
            package(self.root, SHA)
        self.assertEqual(notes.read_text(), "owner decisions retained\n")


if __name__ == "__main__":
    unittest.main()
