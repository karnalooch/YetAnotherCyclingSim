from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


class AlternativeQueryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location(
            "alternative_test",
            Path(__file__).with_name("acquire_sa_calobra_context_alternatives.py"),
        )
        cls.module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"requests": SimpleNamespace()}):
            spec.loader.exec_module(cls.module)

    def data(self):
        return {
            "spatialReference": {"wkid": 25831},
            "features": [{"attributes": {"OBJECTID": 1}}],
        }

    def test_complete_object_ids_pass(self):
        self.assertEqual(
            self.module.validate_query(
                {"objectIds": [1], "objectIdFieldName": "OBJECTID"}, self.data()
            ),
            1,
        )

    def test_truncated_ids_fail(self):
        with self.assertRaisesRegex(ValueError, "identities"):
            self.module.validate_query(
                {"objectIds": [1, 2], "objectIdFieldName": "OBJECTID"}, self.data()
            )

    def test_transfer_limit_fails(self):
        data = self.data()
        data["exceededTransferLimit"] = True
        with self.assertRaisesRegex(ValueError, "partial"):
            self.module.validate_query(
                {"objectIds": [1], "objectIdFieldName": "OBJECTID"}, data
            )

    def test_unverified_crs_fails(self):
        data = self.data()
        data["spatialReference"]["wkid"] = 4326
        with self.assertRaisesRegex(ValueError, "CRS"):
            self.module.validate_query(
                {"objectIds": [1], "objectIdFieldName": "OBJECTID"}, data
            )


if __name__ == "__main__":
    unittest.main()
