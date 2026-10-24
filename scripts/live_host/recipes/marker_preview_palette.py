"""Change only five transient P0–P4 TextRender colors in the open UE viewport.

These diagnostic sites remain REJECTED: green is an owner-requested UI
presentation color and is NOT a terrain-contact qualification or placement.
No save, spawning, landscape/road/physics edits, or second Unreal process.
"""
from __future__ import annotations

IDS = ("P0", "P1", "P2", "P3", "P4")
PALETTES = {
    "green": (32, 232, 88, 255),
    "red": (255, 32, 32, 255),
}


def _rgba(color):
    return tuple(int(getattr(color, key)) for key in ("r", "g", "b", "a"))


def run(unreal, context, parameters):
    if context.get("intent") != "preview":
        raise ValueError("Marker colors can only be previewed")
    if context.get("asset_scope") != ():
        raise ValueError("Marker preview cannot author or save assets")
    if type(parameters) is not dict or set(parameters) != {"palette"}:
        raise ValueError("Exact single palette argument required")
    palette = parameters["palette"]
    if type(palette) is not str or palette not in PALETTES:
        raise ValueError("Only reviewed green/red presentation colors are allowed")
    live = context["live"]
    if live.world.get_path_name().split(".")[0] != live.map_package:
        raise ValueError("Wrong UE world for red-review marker preview")

    records = live.report.get("markers")
    sites = live.report.get("markers")
    if (
        type(records) is not list or len(records) != 5
        or len(live.owned) != 5
        or tuple(record.get("id") for record in records) != IDS
        or tuple(site.get("id") for site in sites) != IDS
    ):
        raise ValueError("Original five marker identities are not intact")
    components = []
    before = []
    for site, actor in zip(records, live.owned, strict=True):
        if (
            site.get("label") != "REJECTED / REVIEW"
            or site.get("production_placement") is not False
            or site.get("marker_actor") != actor.get_path_name()
            or actor.get_actor_label() != "PCG365_REVIEW_RED_" + site["id"]
        ):
            raise ValueError("Unexpected original rejected marker actor identity")
        comp = actor.get_component_by_class(unreal.TextRenderComponent)
        if comp is None:
            raise ValueError("Text marker component not available")
        if "REJECTED" not in str(comp.get_editor_property("text")):
            raise ValueError("Source rejection label must remain visible")
        components.append(comp)
        before.append(comp.get_editor_property("text_render_color"))
    target = PALETTES[palette]
    color = unreal.Color(*target)
    try:
        for component in components:
            component.set_text_render_color(color)
        observed = [
            _rgba(component.get_editor_property("text_render_color"))
            for component in components
        ]
        if observed != [target] * 5:
            raise ValueError("Native TextRender marker color readback differs")
    except Exception:
        # Restore all five originals even if one setter or readback fails.
        for component, previous in zip(components, before, strict=True):
            try:
                component.set_text_render_color(previous)
            except Exception:
                pass
        raise

    return {
        "status": "APPLIED_PREVIEW",
        "action": "RECOLOR_FIVE_REJECTED_SITE_MARKERS_ONLY",
        "sites": list(IDS),
        "palette": palette,
        "native_rgba": list(target),
        "previous_rgba": [list(_rgba(value)) for value in before],
        "native_readback_count": len(observed),
        "source_status": "REJECTED",
        "contact_qualification": "NOT_ADMITTED",
        "qualified_assets": [],
        "placement": False,
        "map_saved": False,
        "terrain_modified": False,
    }
