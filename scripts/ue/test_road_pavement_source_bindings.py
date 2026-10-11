"""Address/owner regression tests; no archived code execution or native claim."""

from copy import deepcopy
import hashlib
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from scripts.ue import road_pavement_source_bindings as bindings

INERT_PRODUCER = b"not Python: source evidence must never execute\r\n"
INERT_IDENTITY = {"size_bytes": len(INERT_PRODUCER),
                  "sha256": hashlib.sha256(INERT_PRODUCER).hexdigest()}


def plan_fixture():
    # Full accepted owner/row/buffer counts, with a support-only parapet inside
    # the list. Geometry clipping itself has separate surface/continuity tests.
    owners = []
    for index in range(185):
        if index == 7:
            owners.append({"support_label": "YACS_PERSIST_SUPPORT_007", "window_id": "fixture-7",
                           "kind": "parapet", "material_target": False})
        hairpin = index == 184
        owners.append({"support_label": f"YACS_PERSIST_SUPPORT_{len(owners):03d}",
                       "window_id": "accepted-hairpin" if hairpin else f"fixture-{index}",
                       "material_target": True, "kind": "hairpin" if hairpin else "ordinary",
                       "section_count": 2401 if hairpin else 84 if index == 0 else 80})
    identity = {"support_source_schema_version": 1, "geometry_consumers_executed": False,
                "geometry_authored": False, "support_count": 186, "material_target_count": 185,
                "excluded_parapet_count": 1,
                "producer_files": {bindings.PRODUCER_PATH: dict(INERT_IDENTITY)}}
    return {"source_identity": identity, "owners": owners}


def fake_build(*keys):
    return SimpleNamespace(meshes=tuple(SimpleNamespace(owner_label=key[0],
        fragments=(SimpleNamespace(source_triangle=key[1:]),)) for key in keys))


class PavementSourceBindingTests(unittest.TestCase):
    def setUp(self):
        self.plan = plan_fixture()
        self.pin = patch.object(bindings, "PRODUCER_IDENTITY", dict(INERT_IDENTITY))
        self.pin.start()
        self.addCleanup(self.pin.stop)

    def prepare(self, *keys, plan=None):
        with patch.object(bindings.geometry, "build_markings", return_value=fake_build(*keys)) as build:
            result = bindings.prepare_bindings(self.plan if plan is None else plan,
                                               producer_bytes=INERT_PRODUCER)
            build.assert_called_once_with(self.plan if plan is None else plan,
                                          quad_triangles=((0, 1, 2), (1, 3, 2)))
        return result

    def test_actual_cell_slots_skip_interleaved_bottoms_and_retain_ordered_vertices(self):
        label = "YACS_PERSIST_SUPPORT_000"
        result = self.prepare((label, 0, 0, 0), (label, 0, 0, 1), (label, 0, 1, 0),
                              (label, 0, 23, 1), (label, 1, 0, 0))
        self.assertEqual(set(result), {"quad_triangles", "triangle_bindings"})
        self.assertEqual(result["quad_triangles"], ((0, 1, 2), (1, 3, 2)))
        self.assertEqual(result["triangle_bindings"], (
            (label, 0, 0, 0, 0, 0, 1, 25),
            (label, 0, 0, 1, 1, 1, 26, 25),
            (label, 0, 1, 0, 4, 1, 2, 26),
            (label, 0, 23, 1, 93, 24, 49, 48),
            (label, 1, 0, 0, 96, 25, 26, 50)))

    def test_prefix_counts_include_bottom_and_perimeter_but_exclude_parapet(self):
        labels = ("YACS_PERSIST_SUPPORT_001", "YACS_PERSIST_SUPPORT_008", "YACS_PERSIST_SUPPORT_185")
        rows = self.prepare(*( (label, 0, 0, 0) for label in labels))["triangle_bindings"]
        # First source slab has 84 rows: 4200 vertices and 8396 total faces.
        self.assertEqual(rows[0], (labels[0], 0, 0, 0, 8396, 4200, 4201, 4225))
        # After one 84-row and six 80-row slabs, skip the Nudo parapet entirely.
        self.assertEqual(rows[1], (labels[1], 0, 0, 0, 56372, 28200, 28201, 28225))
        # 14724 network rows / 184 complete slabs precede the 2401-row hairpin.
        self.assertEqual(rows[2], (labels[2], 0, 0, 0, 1471664, 736200, 736201, 736225))

    def test_same_source_face_used_by_both_bands_is_deduplicated_deterministically(self):
        first = ("YACS_PERSIST_SUPPORT_000", 0, 1, 1)
        last = ("YACS_PERSIST_SUPPORT_185", 2399, 23, 1)
        forward = self.prepare(last, first, first)
        reverse = self.prepare(first, last, last)
        self.assertEqual(forward, reverse)
        self.assertEqual(len(forward["triangle_bindings"]), 2)
        self.assertEqual(forward["triangle_bindings"][-1],
                         (*last, 1702061, 796199, 796224, 796223))

    def test_coincident_owner_seams_keep_distinct_explicit_native_addresses(self):
        before = ("YACS_PERSIST_SUPPORT_000", 82, 0, 1)
        after = ("YACS_PERSIST_SUPPORT_001", 0, 0, 0)
        rows = self.prepare(before, after)["triangle_bindings"]
        self.assertNotEqual(rows[0][4], rows[1][4])
        self.assertTrue(set(rows[0][5:]).isdisjoint(rows[1][5:]))
        self.assertEqual(rows[0][5:], (2051, 2076, 2075))
        self.assertEqual(rows[1][5:], (4200, 4201, 4225))

    def test_changed_bytes_or_source_pin_fail_before_clipping_or_execution(self):
        with patch.object(bindings.geometry, "build_markings") as build:
            for raw in (INERT_PRODUCER + b"\n", INERT_PRODUCER.replace(b"\r\n", b"\n"),
                        b"raise RuntimeError('executed')", bytearray(INERT_PRODUCER)):
                with self.subTest(raw=raw), self.assertRaisesRegex(ValueError, "exact retained"):
                    bindings.prepare_bindings(self.plan, producer_bytes=raw)
            changed = deepcopy(self.plan)
            changed["source_identity"]["producer_files"][bindings.PRODUCER_PATH]["sha256"] = "0" * 64
            with self.assertRaisesRegex(ValueError, "source identity"):
                bindings.prepare_bindings(changed, producer_bytes=INERT_PRODUCER)
            build.assert_not_called()

    def test_full_inventory_order_and_accepted_road_counts_are_required(self):
        mutations = []
        reordered = deepcopy(self.plan)
        reordered["owners"][0], reordered["owners"][1] = reordered["owners"][1], reordered["owners"][0]
        mutations.append(reordered)
        for mutate in (lambda p: p["owners"][0].update(section_count=85),
                       lambda p: p["owners"][7].update(material_target=True),
                       lambda p: p["owners"][-1].update(window_id="invented-hairpin"),
                       lambda p: p["source_identity"].update(geometry_authored=True),
                       lambda p: p["source_identity"].update(excluded_parapet_count=0)):
            changed = deepcopy(self.plan)
            mutate(changed)
            mutations.append(changed)
        for changed in mutations:
            with self.subTest(changed=mutations.index(changed)), patch.object(bindings.geometry, "build_markings") as build:
                with self.assertRaises(ValueError):
                    bindings.prepare_bindings(changed, producer_bytes=INERT_PRODUCER)
                build.assert_not_called()

    def test_clipped_addresses_cannot_reach_parapets_bottoms_or_other_owners(self):
        for key in (("YACS_PERSIST_SUPPORT_007", 0, 0, 0),
                    ("YACS_PERSIST_SUPPORT_000", 83, 0, 0),
                    ("YACS_PERSIST_SUPPORT_000", 0, 24, 0),
                    ("YACS_PERSIST_SUPPORT_000", 0, 0, 2),
                    ("YACS_PERSIST_SUPPORT_000", -1, 0, 0),
                    ("YACS_PERSIST_SUPPORT_000", False, 0, 0)):
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.prepare(key)
        with self.assertRaisesRegex(ValueError, "empty or unbounded"):
            self.prepare()

    def test_explicit_interior_faces_reuse_the_same_derivation_without_building_white_paint(self):
        first = ("YACS_PERSIST_SUPPORT_000", 4, 12, 0)
        last = ("YACS_PERSIST_SUPPORT_185", 2399, 11, 1)
        expected = self.prepare(first, last)
        with patch.object(bindings.geometry, "build_markings") as build:
            actual = bindings.prepare_bindings(self.plan, producer_bytes=INERT_PRODUCER,
                                               needed_faces=[last, list(first), first])
            build.assert_not_called()
        self.assertEqual(actual, expected)

    def test_explicit_face_contract_rejects_empty_unbounded_and_malformed_requests(self):
        key = ("YACS_PERSIST_SUPPORT_000", 1, 12, 0)
        for values in ([], iter([key]), [key] * (bindings.MAX_BINDINGS + 1),
                       [(key[0], True, 12, 0)], [(key[0], 1, 12)],
                       [("YACS_PERSIST_SUPPORT_007", 1, 12, 0)],
                       [(key[0], 83, 12, 0)], [(key[0], 1, 24, 0)],
                       [(key[0], 1, 12, 2)], [None]):
            with self.subTest(kind=type(values).__name__), patch.object(bindings.geometry, "build_markings") as build:
                with self.assertRaises(ValueError):
                    bindings.prepare_bindings(self.plan, producer_bytes=INERT_PRODUCER, needed_faces=values)
                build.assert_not_called()
        with patch.object(bindings.geometry, "build_markings") as build:
            with self.assertRaisesRegex(ValueError, "exact retained"):
                bindings.prepare_bindings(self.plan, producer_bytes=INERT_PRODUCER + b"\n", needed_faces=[key])
            build.assert_not_called()


if __name__ == "__main__":
    unittest.main()
