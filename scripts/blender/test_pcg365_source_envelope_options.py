"""Bounded coarse-source options; no Blender import or asset execution."""

import contextlib
import io
from pathlib import Path
import unittest

from scripts.blender.build_pcg365_source_envelope import parse_arguments


class EnvelopeOptions(unittest.TestCase):
    def arguments(self, *extra):
        return parse_arguments(
            [
                "--catalog",
                "parent.json",
                "--expected-catalog-sha256",
                "a" * 64,
                "--output-directory",
                "fresh",
                "--asset",
                "namaqualand_boulder_06_01",
                *extra,
            ]
        )

    def test_existing_default_and_source_provenance_preserved(self):
        args = self.arguments()
        self.assertEqual(args.grid, 129)
        self.assertEqual(args.catalog, Path("parent.json"))
        self.assertEqual(args.expected_catalog_sha256, "a" * 64)
        self.assertEqual(args.asset, ["namaqualand_boulder_06_01"])
        self.assertEqual(args.output_directory, Path("fresh"))

    def test_supported_coarse_grids(self):
        for grid in (33, 49, 129):
            with self.subTest(grid=grid):
                self.assertEqual(self.arguments("--grid", str(grid)).grid, grid)

    def test_unbounded_grids_refused(self):
        for grid in ("0", "1", "32", "65", "100000", "33.0", "invalid"):
            with self.subTest(grid=grid), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    self.arguments("--grid", grid)

    def test_parent_proof_still_required(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            parse_arguments(
                [
                    "--catalog",
                    "parent.json",
                    "--output-directory",
                    "fresh",
                    "--grid",
                    "33",
                ]
            )


if __name__ == "__main__":
    unittest.main()
