"""Offline synthetic proof for recoloring only existing red-review actors."""
from __future__ import annotations

import unittest

from scripts.live_host.recipes import marker_preview_palette as recipe

MAP = "/Game/Generated/YACS/SaCalobra/WholeMapPreparation/L_SaCalobraMaterialReview"


class Color:
    def __init__(self, r, g, b, a):
        self.r, self.g, self.b, self.a = r, g, b, a


class Component:
    def __init__(self, *, bad_text=False, fail_once=False):
        self.text_render_color = Color(255, 32, 32, 255)
        self.text = "P3  REJECTED  /  REVIEW" if not bad_text else "APPROVED"
        self.fail_once = fail_once

    def get_editor_property(self, name):
        return getattr(self, name)

    def set_text_render_color(self, color):
        if self.fail_once:
            self.fail_once = False
            raise RuntimeError("native UE preview failure")
        self.text_render_color = color


class Actor:
    def __init__(self, site, **kwargs):
        self.site = site
        self.component = Component(**kwargs)

    def get_path_name(self):
        return f"{MAP}:PersistentLevel.Marker_{self.site}"

    def get_actor_label(self):
        return f"PCG365_REVIEW_RED_{self.site}"

    def get_component_by_class(self, kind):
        assert kind is Component
        return self.component


class Unreal:
    TextRenderComponent = Component
    Color = Color


class World:
    def get_path_name(self):
        return MAP + ".L_SaCalobraMaterialReview"


class Live:
    map_package = MAP

    def __init__(self):
        self.world = World()
        self.owned = [Actor(site) for site in recipe.IDS]
        self.report = {
            "markers": [
                {
                    "id": site,
                    "label": "REJECTED / REVIEW",
                    "production_placement": False,
                    "marker_actor": actor.get_path_name(),
                }
                for site, actor in zip(recipe.IDS, self.owned, strict=True)
            ]
        }


def context():
    return {"intent": "preview", "asset_scope": (), "live": Live()}


class MarkerPaletteTests(unittest.TestCase):
    def test_green_recolors_five_owned_actors_without_approving_contact(self):
        ctx = context()
        result = recipe.run(Unreal, ctx, {"palette": "green"})
        self.assertEqual(result["native_rgba"], [32, 232, 88, 255])
        self.assertEqual(result["native_readback_count"], 5)
        self.assertEqual(result["source_status"], "REJECTED")
        self.assertEqual(result["contact_qualification"], "NOT_ADMITTED")
        self.assertEqual(result["qualified_assets"], [])
        self.assertFalse(result["placement"])
        self.assertFalse(result["map_saved"])
        self.assertFalse(result["terrain_modified"])
        self.assertTrue(all(
            component.component.text_render_color.g == 232
            for component in ctx["live"].owned
        ))

    def test_red_can_restore_original_palette_in_same_editor(self):
        ctx = context()
        recipe.run(Unreal, ctx, {"palette": "green"})
        result = recipe.run(Unreal, ctx, {"palette": "red"})
        self.assertEqual(result["native_rgba"], [255, 32, 32, 255])
        self.assertTrue(all(
            actor.component.text_render_color.r == 255
            for actor in ctx["live"].owned
        ))

    def test_reject_any_nonpreview_and_unknown_palette_without_mutation(self):
        for change, params in [
            ({"intent": "author"}, {"palette": "green"}),
            ({"asset_scope": ("Content/World.umap",)}, {"palette": "green"}),
            ({}, {"palette": "blue"}),
            ({}, {"palette": "Green"}),
            ({}, {"palette": "green", "script": "quit"}),
            ({}, {}),
        ]:
            ctx = {**context(), **change}
            with self.subTest(change=change, params=params):
                with self.assertRaises(ValueError):
                    recipe.run(Unreal, ctx, params)
                self.assertTrue(all(
                    actor.component.text_render_color.r == 255
                    for actor in ctx["live"].owned
                ))

    def test_marker_identity_and_rejection_label_are_immutable(self):
        cases = [
            ("marker_actor", "OTHER"),
            ("label", "APPROVED"),
            ("production_placement", True),
            ("id", "P42"),
        ]
        for field, value in cases:
            ctx = context()
            ctx["live"].report["markers"][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                recipe.run(Unreal, ctx, {"palette": "green"})
            self.assertTrue(all(
                actor.component.text_render_color.r == 255
                for actor in ctx["live"].owned
            ))
        ctx = context()
        ctx["live"].owned[0].component.text = "ACCEPTED"
        with self.assertRaises(ValueError):
            recipe.run(Unreal, ctx, {"palette": "green"})

    def test_failed_color_write_restores_previous_markers(self):
        ctx = context()
        ctx["live"].owned[2].component.fail_once = True
        with self.assertRaises(RuntimeError):
            recipe.run(Unreal, ctx, {"palette": "green"})
        self.assertTrue(all(
            actor.component.text_render_color.r == 255
            for actor in ctx["live"].owned
        ))

    def test_reviewed_catalog_keeps_empty_authoring_scope(self):
        import json
        from pathlib import Path

        catalog = json.loads(
            (Path(__file__).resolve().parent / "recipes/catalog.json").read_text()
        )
        entries = [item for item in catalog["recipes"]
                   if item["id"] == "marker_preview_palette"]
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["asset_scope"], [])
        self.assertEqual(entries[0]["intents"], ["preview"])
        self.assertEqual(
            entries[0]["parameters"]["palette"]["enum"], ["green", "red"]
        )


if __name__ == "__main__":
    unittest.main()
