from __future__ import annotations

import unittest

import validate_changed_assets as va


class AssetValidationTests(unittest.TestCase):
    def test_required_lfs_asset_accepts_pointer(self):
        problems = va.validate_asset_blob(
            path="Content/Prototype/Maps/L_CyclingTest.umap",
            filter_name="lfs",
            content=(
                b"version https://git-lfs.github.com/spec/v1\n"
                b"oid sha256:abc\n"
                b"size 123\n"
            ),
        )
        self.assertEqual(problems, [])

    def test_required_lfs_asset_rejects_missing_lfs_filter(self):
        problems = va.validate_asset_blob(
            path="Content/Prototype/Maps/L_CyclingTest.umap",
            filter_name="unspecified",
            content=b"binary",
        )
        self.assertEqual(len(problems), 1)
        self.assertIn("required Git LFS extension", problems[0])

    def test_lfs_asset_rejects_materialized_payload(self):
        problems = va.validate_asset_blob(
            path="Content/Prototype/Routes/BP_StraightTestRoute.uasset",
            filter_name="lfs",
            content=b"real binary payload",
        )
        self.assertEqual(len(problems), 1)
        self.assertIn("materialized", problems[0])

    def test_non_lfs_raster_is_allowed_in_lightweight_lane(self):
        problems = va.validate_asset_blob(
            path="Content/Prototype/UI/icon.png",
            filter_name="unspecified",
            content=b"small png bytes",
        )
        self.assertEqual(problems, [])


if __name__ == "__main__":
    unittest.main()
