"""Live-only viewer of the pinned saved #364 Sa Calobra road v0.3.1.

This is NOT a renderer/asset authoring tool. No spawning, saving, material or
landscape mutation. It reads the existing saved road/shoulder material bindings
and reports the actual global-light actors so their state cannot be invented.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def need(condition, message):
    if not condition:
        raise ValueError(message)


def sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_world_pins(registry, project, expected_profile):
    need(registry.get("policy") == "LATEST_VERIFIED_FAIL_CLOSED",
         "Live profile does not use fail-closed world selection")
    need(registry.get("selected_world_id") == expected_profile,
         "Native selected world is not the installer profile")
    choices = [row for row in registry.get("worlds", [])
               if row.get("id") == expected_profile]
    need(len(choices) == 1, "Selected saved road profile is not unique")
    profile = choices[0]
    need(profile.get("version") == "0.3.1"
         and profile.get("evidence_status") == "SAVED_CHECKPOINT_REOPENED_RENDERED",
         "Road checkpoint is not the retained accepted v0.3.1")
    need(Path(profile["project_root"]).resolve() == Path(project).resolve(),
         "Native UE is not using the latest source-backed project")
    from scripts.ue import read_live_road_checkpoint as reader

    need(profile["map_package"] == reader.MAP,
         "Native map package differs from v0.3.1 technical readback")
    need({row["path"]: (row["bytes"], row["sha256"])
          for row in profile["files"]} ==
         {"Content/" + reader.PACKAGE.removeprefix("/Game/") + "/" + name: size_hash
          for name, size_hash in reader.EXPECTED_FILES.items()},
         "Retained v0.3.1 packages disagree with reader source")
    saved = reader.validate_saved_receipt(
        json.loads((Path(project) / profile["receipt_relative"]).read_text(
            encoding="utf-8"
        ))
    )
    return profile, saved


def lighting_readback(unreal, world):
    """Observe, not fabricate, the ambient/global lighting configuration."""
    counts = {}
    for cls_name, key in (
        ("DirectionalLight", "directional_lights"),
        ("SkyLight", "sky_lights"),
        ("SkyAtmosphere", "sky_atmospheres"),
        ("ExponentialHeightFog", "height_fog_actors"),
        ("VolumetricCloud", "volumetric_clouds"),
    ):
        cls = getattr(unreal, cls_name, None)
        if cls is None:
            counts[key] = None
            continue
        try:
            counts[key] = len(
                unreal.GameplayStatics.get_all_actors_of_class(world, cls)
            )
        except Exception:
            counts[key] = None
    cvars = {}
    for name in (
        "r.DynamicGlobalIlluminationMethod",
        "r.ReflectionMethod",
    ):
        try:
            cvars[name] = unreal.SystemLibrary.get_console_variable_int_value(
                name
            )
        except Exception:
            cvars[name] = None
    return {
        "status": "READ_ONLY_NATIVE_OBSERVATION_NOT_VISUAL_ACCEPTANCE",
        "actor_counts": counts,
        "cvars": cvars,
        "global_lighting_visual_pass": False,
    }


class VerifiedRoadWorld:
    """Existing UE world, with command bridge but without P0-P4 camera semantics."""

    def __init__(self, project, session, registry, profile_id, release):
        self.project = Path(project)
        self.session = Path(session)
        self.release = Path(release)
        self.registry = registry
        self.profile_id = profile_id
        self.world = None
        self.owned = []
        self.camera_cm = None
        self.target_cm = None
        self.map_package = ""
        self.report = {"markers": [], "placement": False}

    def start(self, unreal):
        profile, saved = read_world_pins(
            self.registry, self.project, self.profile_id
        )
        self.map_package = profile["map_package"]
        self.camera_cm = profile["camera_cm"]
        self.target_cm = profile["target_cm"]
        need(
            unreal.EditorLoadingAndSavingUtils.load_map(self.map_package),
            "Saved road map v0.3.1 could not be opened in native UE"
        )
        editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        self.world = editor.get_editor_world()
        need(self.world is not None and
             self.world.get_path_name() == self.map_package + ".L_RoadSurface",
             "Latest v0.3.1 saved road is not the loaded editor world")

        road_actors = list(unreal.GameplayStatics.get_all_actors_of_class(
            self.world, unreal.DynamicMeshActor
        ))
        need(len(road_actors) == 559,
             "Latest road is missing one or more of 559 saved mesh actors")
        by_label = {}
        for actor in road_actors:
            label = actor.get_actor_label()
            need(label not in by_label,
                 "Duplicate saved road/shoulder native actor label")
            by_label[label] = actor
        for binding in saved["bindings"]:
            actor = by_label.get(binding["label"])
            need(actor is not None,
                 "Current road/shoulder actor is missing: " + binding["label"])
            material = actor.get_dynamic_mesh_component().get_material(
                binding["slot"]
            )
            need(material is not None
                 and material.get_path_name() == binding["material"],
                 "Saved road/shoulder material readback mismatch: "
                 + binding["label"])
        need(by_label.get("YACS_PERSIST_ROAD") is not None,
             "No pinned road actor in the latest scene")

        eye = unreal.Vector(*self.camera_cm)
        destination = unreal.Vector(*self.target_cm)
        rotation = unreal.MathLibrary.find_look_at_rotation(eye, destination)
        editor.set_level_viewport_camera_info(eye, rotation)
        observed = editor.get_level_viewport_camera_info()
        need(observed is not None and
             (observed[0] - eye).length() <= 1.0,
             "Native road-view camera readback failed")

        # Load does not imply that global illumination was configured by #474.
        # Report actual light actors and reflected GI CVars as observations.
        self.lighting = lighting_readback(unreal, self.world)
        map_file = self.project / profile["map_relative"]
        need(
            map_file.stat().st_size == profile["files"][0]["bytes"]
            and sha256(map_file) == profile["files"][0]["sha256"],
            "Latest map bytes changed while viewing road/lighting"
        )
        self.report = {
            "status": "LATEST_VERIFIED_WORLD_NATIVE_ROAD_READY",
            "map_package": self.map_package,
            "world_profile_id": self.profile_id,
            "version": profile["version"],
            "markers": [],
            "road_native_actor_count": len(road_actors),
            "material_bindings_verified": len(saved["bindings"]),
            "lighting": self.lighting,
            "map_saved": False,
            "terrain_modified": False,
            "placement": False,
            "qualified_assets": [],
            "global_lighting_visual_pass": False,
        }
        return self.report
