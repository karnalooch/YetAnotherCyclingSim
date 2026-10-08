"""Shared, replayable contract for the complete Sa Calobra preparation preview.

The registered material amplitudes and the physical A/B/C/D/U demand atlas are
different inputs. This module never converts one into the other and never edits
ground, road, or cliff geometry. Unreal is injected so the contract and rollback
can be tested without importing the editor.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAP = "/Game/Worlds/SaCalobra/L_SaCalobraAccepted_20261004"
MASTER_PACKAGE = "/Game/Generated/YACS/SaCalobra/WholeMapPreparation"
MASTER_NAME = "M_SaCalobraWholeMapPreparation"
MASTER_PATH = f"{MASTER_PACKAGE}/{MASTER_NAME}"
INSTANCE_NAME = "MI_SaCalobraWholeMapPreparation"
INSTANCE_PATH = f"{MASTER_PACKAGE}/{INSTANCE_NAME}"
LIBRARY = "/Game/Generated/YACS/TextureMaterialPrep/Libraries/3d53743e48394f31beb35e4030dc8a87"
ROLES = ("DryGrass", "ForestLitter", "ExposedRock", "DryMineral", "Scree")
WEIGHTS_SHA = "af16fc7c43ec8a3a3b2e000fe716232a3229fe0ac6b4e9708baae5842ef99f6c"
AVAILABILITY_SHA = "9c9906268977a8f49ba20c194cecb101e8bb8c25c44b51ee30f66e7e88a7522a"
INFERENCE_SHA = "cc3bc3490878c5a96c20586cd28b0cd3cc812c5506ae97a7110c59e6ed3a3176"
EXCLUSIONS_SHA = "c74bde6ae8589304fe3d52f4e1e20801b0fe5647de6ffbc268c9b2ca65eaa941"
FORMULA = "[R,G,B,max(0,1-R-G-B)]*(1-A), then dry-channel A; channels divided by255"
GRID = {
    "crs": "EPSG:25831",
    "height": 4033,
    "width": 4033,
    "pixel_size_m": 0.5,
    "transform": [0.5, 0.0, 483000.0, 0.0, -0.5, 4409516.5],
}
WORLD_MAPPING = {
    "origin_epsg_m": [483000.25, 4409516.25],
    "world_unit": "centimetres",
    "axis": "X east;Y south",
    "uv": "(UE_XY_cm/50+0.5)/4033",
    "footprint_world_bounds_cm": [-25, -25, 201625, 201625],
}
# Initial rendering settings, independent of physical atlas bands. Distances do
# not infer that a distant wall has low visual demand, and do not move geometry.
SCALARS = {
    "NearDetailStartCm": 2500.0,
    "FarDetailEndCm": 25000.0,
    "MicroNormalStrength": 0.75,
    "ForceDetailMix": 0.0,
    "ForcedDetailFactor": 1.0,
    "DomainMix": 0.0,
    "CheckerMix": 0.0,
    "CheckerCellSizeCm": 100.0,
}
ROUGHNESS = {
    "DryGrass": 0.88,
    "ForestLitter": 0.9,
    "ExposedRock": 0.78,
    "DryMineral": 0.85,
    "Scree": 0.86,
}
DOMAIN_COLORS = {
    "DryGrass": [0.18, 0.55, 0.10],
    "ForestLitter": [0.015, 0.15, 0.045],
    "ExposedRock": [0.55, 0.20, 0.90],
    "DryMineral": [0.42, 0.25, 0.09],
    "Scree": [0.04, 0.35, 0.65],
}
RESOLUTION = (1920, 1080)
CONSOLE_NAMES = (
    "r.ForceLOD",
    "r.ScreenPercentage",
    "r.PostProcessAAQuality",
    "showflag.DynamicShadows",
    "r.Streaming.FullyLoadUsedTextures",
    "r.HighResScreenshotDelay",
    "r.Test.FreezeTemporalSequences",
)


def canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(value, indent=2, allow_nan=False) + "\n").encode("utf-8")
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(data)
    temporary.replace(path)


def checked_bytes(path, limit=40 * 1024 * 1024):
    path = Path(path)
    if path.stat().st_size > limit:
        raise ValueError("Oversized preparation input: " + path.name)
    with path.open("rb") as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError("Oversized preparation input: " + path.name)
    return data


def load_inputs(root):
    root = Path(root).resolve()
    payload = checked_bytes(root / "surface-prep-manifest.json", 2 * 1024 * 1024)
    manifest = json.loads(payload)
    content = {key: value for key, value in manifest.items() if key != "fingerprint"}
    if (
        manifest.get("fingerprint") != hashlib.sha256(canonical(content)).hexdigest()
        or manifest.get("status") != "WHOLE_MAP_MATERIAL_PREPARATION_CANDIDATE"
        or manifest.get("geometry_mutation") is not False
        or manifest.get("current_cover_admitted") is not False
        or manifest.get("expected_landscape_component_count") != 1024
        or any(
            manifest.get("grid", {}).get(key) != value for key, value in GRID.items()
        )
        or manifest.get("world_mapping") != WORLD_MAPPING
        or manifest.get("recipe", {}).get("material_formula") != FORMULA
        or manifest.get("recipe_sha256")
        != hashlib.sha256(canonical(manifest["recipe"])).hexdigest()
        or manifest.get("coverage", {}).get("cells") != 4033 * 4033
    ):
        raise ValueError(
            "Unsupported, incomplete or stale whole-map preparation contract"
        )
    producer = ROOT / "scripts/assets/prepare_sa_calobra_whole_map_surface_prep.py"
    if manifest.get("producer_file") != producer.relative_to(
        ROOT
    ).as_posix() or hashlib.sha256(
        producer.read_bytes().replace(b"\r\n", b"\n")
    ).hexdigest() != manifest.get("producer_sha256_lf"):
        raise ValueError("Whole-map preparation producer changed")
    outputs = manifest.get("outputs", [])
    names = [row.get("path") for row in outputs]
    if len(names) != len(set(names)) or len(names) != 9:
        raise ValueError("Unexpected whole-map input inventory")
    hashes = {}
    for row in outputs:
        name = row["path"]
        if not isinstance(name, str) or Path(name).name != name or name in (".", ".."):
            raise ValueError("Unsafe preparation input path")
        path = (root / name).resolve()
        if path.parent != root:
            raise ValueError("Preparation input leaves bundle")
        data = checked_bytes(path)
        actual = hashlib.sha256(data).hexdigest()
        if actual != row.get("sha256") or len(data) != row.get("size_bytes"):
            raise ValueError("Preparation input changed: " + name)
        hashes[name] = actual
    pins = {
        "material-weights.png": WEIGHTS_SHA,
        "sample-availability.png": AVAILABILITY_SHA,
        "inference-kind.png": INFERENCE_SHA,
        "exclusion-reasons.tif": EXCLUSIONS_SHA,
    }
    if any(hashes.get(name) != value for name, value in pins.items()):
        raise ValueError("Whole-map input differs from the fixed source products")
    for row in manifest.get("sources", {}).values():
        if hashes.get(row.get("path")) != row.get("sha256"):
            raise ValueError("Whole-map source inventory mismatch")
    return {
        "root": root,
        "manifest": manifest,
        "hashes": hashes,
        "manifest_sha256": hashlib.sha256(payload).hexdigest(),
    }


def asset_file(asset_path):
    if not asset_path.startswith("/Game/") or "." in asset_path:
        raise ValueError("Expected a package asset path")
    return ROOT / "Content" / (asset_path.removeprefix("/Game/") + ".uasset")


def package_files(asset_path):
    primary = asset_file(asset_path)
    rows = []
    for path in sorted(primary.parent.glob(primary.stem + ".*")):
        ending = path.name.removeprefix(primary.stem)
        if (
            ending not in (".uasset", ".uexp", ".ubulk", ".uptnl", ".m.ubulk")
            or not path.is_file()
        ):
            raise ValueError("Unsupported generated package sidecar: " + path.name)
        rows.append(
            {
                "file": path.relative_to(ROOT).as_posix(),
                "sha256": digest(path),
                "size_bytes": path.stat().st_size,
            }
        )
    if not any(row["file"] == primary.relative_to(ROOT).as_posix() for row in rows):
        raise ValueError("Generated package primary file is missing")
    return rows


def verify_instance(api, master, instance, receipt):
    """Verify in-memory bindings too; a file hash cannot detect unsaved edits."""
    if (
        master is None
        or instance is None
        or master.get_editor_property("tangent_space_normal") is not True
    ):
        raise RuntimeError(
            "Prepared master/instance or tangent normal-space setting is unavailable"
        )
    association = api.MaterialParameterAssociation.GLOBAL_PARAMETER
    lib = api.MaterialEditingLibrary
    scalars = dict(SCALARS)
    for role, settings in receipt["rendering_recipe"]["roles"].items():
        scalars[role + "TileSizeCm"] = settings["tile_cm"]
        scalars[role + "Roughness"] = settings["roughness"]
    if {str(name) for name in lib.get_scalar_parameter_names(instance)} != set(scalars):
        raise RuntimeError("Prepared scalar parameter inventory differs")
    for name, expected in scalars.items():
        actual = float(
            lib.get_material_instance_scalar_parameter_value(
                instance, name, association
            )
        )
        if not math.isfinite(actual) or abs(actual - expected) > 1e-5:
            raise RuntimeError("Prepared in-memory scalar differs: " + name)
    textures = {"WeightTex": MASTER_PACKAGE + "/T_WholeMapWeights"}
    textures.update(
        {
            role + channel + "Tex": row["asset"]
            for role, values in receipt["source_assets"].items()
            for channel, row in values.items()
        }
    )
    if {str(name) for name in lib.get_texture_parameter_names(instance)} != set(
        textures
    ):
        raise RuntimeError("Prepared texture parameter inventory differs")
    readbacks = []
    for name, expected in textures.items():
        texture = lib.get_material_instance_texture_parameter_value(
            instance, name, association
        )
        if texture is None or texture.get_path_name().split(".")[0] != expected:
            raise RuntimeError("Prepared in-memory texture binding differs: " + name)
        row = json.loads(api.YacsTextureAuditLibrary.describe_texture(texture))
        if row.get("is_default_texture", True) or row.get("is_compiling", True):
            raise RuntimeError("Prepared native texture fallback: " + name)
        if name == "WeightTex" and (
            row.get("size_x"),
            row.get("size_y"),
            row.get("srgb"),
        ) != (4033, 4033, False):
            raise RuntimeError(
                "Prepared weight texture dimensions/linear registration differ"
            )
        readbacks.append(dict(row, parameter=name))
    return {"scalars": scalars, "texture_readbacks": readbacks}


def source_assets():
    """Verify loaded packages against their committed Git LFS object identity."""
    result = {}
    for role in ROLES:
        result[role] = {}
        for channel, suffix in (
            ("BaseColor", "Sources/T_Source_" + role),
            ("Normal", "ProviderData/" + role + "/T_Normal"),
        ):
            package = LIBRARY + "/" + suffix
            path = asset_file(package)
            relative = path.relative_to(ROOT).as_posix()
            pointer = subprocess.check_output(
                ["git", "show", "HEAD:" + relative], cwd=ROOT
            )
            match = re.fullmatch(
                rb"version https://git-lfs.github.com/spec/v1\r?\n"
                rb"oid sha256:([0-9a-f]{64})\r?\nsize ([0-9]+)\r?\n?",
                pointer,
            )
            if (
                not match
                or path.stat().st_size != int(match[2])
                or digest(path) != match[1].decode()
            ):
                raise ValueError(
                    "Unmaterialized or changed source texture: " + relative
                )
            result[role][channel] = {
                "asset": package,
                "file": relative,
                "sha256": match[1].decode(),
                "size_bytes": int(match[2]),
            }
    return result


def rendering_recipe():
    catalogue_path = (
        ROOT / "worldgen/materials/sa_calobra_texture_library_v2_20261005.json"
    )
    catalogue_bytes = checked_bytes(catalogue_path, 1024 * 1024)
    catalogue = json.loads(catalogue_bytes)
    selected = {
        item["role"]: item for item in catalogue["items"] if item["role"] in ROLES
    }
    if set(selected) != set(ROLES):
        raise ValueError("Preparation role catalogue is incomplete")
    role_rows = {}
    for role in ROLES:
        source = selected[role]
        size = source["world_size_m"]
        if len(size) != 2 or size[0] != size[1] or not 0.5 <= float(size[0]) <= 10:
            raise ValueError("Unsupported material source scale")
        role_rows[role] = {
            "tile_cm": 100.0 * float(size[0]),
            "source_id": source["source_id"],
            "source_url": source["source_url"],
            "license": source["license"],
            "scale_authority": source["scale_authority"],
            "roughness": ROUGHNESS[role],
            "domain_color_linear": DOMAIN_COLORS[role],
        }
    normal_evidence = (
        ROOT
        / "docs/experiments/sa-calobra-material-repair-20261006/evidence/native-projection.json"
    )
    return {
        "schema_version": 1,
        "roles": role_rows,
        "scalar_defaults": dict(SCALARS),
        "source_catalogue_sha256": hashlib.sha256(catalogue_bytes).hexdigest(),
        "source_catalogue": catalogue_path.relative_to(ROOT).as_posix(),
        "material_formula": FORMULA,
        "world_mapping": WORLD_MAPPING,
        "projection": "Epic WorldAlignedTexture + WorldAlignedNormal",
        "normal_space": {
            "world_aligned_normal_world_space": False,
            "material_tangent_space_normal": True,
            "neutral_normal": [0, 0, 1],
            "evidence_file": normal_evidence.relative_to(ROOT).as_posix(),
            "evidence_sha256": digest(normal_evidence),
        },
        "roughness_authority": "Explicit preparation constants; final per-role PBR review pending",
        "distance_detail": "Micro normal amplitude only; macro albedo and physical atlas unchanged",
        "shader_cost_reduction_claimed": False,
        "geometry_detail": "Native adaptive Landscape LOD; accepted v8 mesh remains unchanged",
        "texture_parameter_count": 11,
        "final_material_acceptance": "PENDING_OWNER",
    }


def near_detail_factor(
    distance_cm, start_cm=SCALARS["NearDetailStartCm"], end_cm=SCALARS["FarDetailEndCm"]
):
    if (
        not all(math.isfinite(value) for value in (distance_cm, start_cm, end_cm))
        or not 0 <= start_cm < end_cm
    ):
        raise ValueError("Invalid independent material-distance settings")
    return 1.0 - max(0.0, min(1.0, (distance_cm - start_cm) / (end_cm - start_cm)))


def console_value(api, name):
    value = api.SystemLibrary.get_console_variable_string_value(name)
    if value == "" or not math.isfinite(float(value)):
        raise RuntimeError("Unverified capture console variable: " + name)
    return value


def memory_checkpoint(stage, physical_gib, commit_gib, *, memory=None):
    if memory is None:
        from scripts.ue.sa_calobra_material_waves import available_memory

        memory = available_memory
    values = memory()
    report = {
        "stage": stage,
        "minimum_free_physical_gib": physical_gib,
        "minimum_free_commit_gib": commit_gib,
        "memory": values,
    }
    if (
        values["free_physical"] < physical_gib * 1024**3
        or values["free_commit"] < commit_gib * 1024**3
    ):
        raise RuntimeError("Whole-map memory gate failed: " + json.dumps(report))
    report["status"] = "PASS"
    return report


class CaptureEnvironment:
    """Snapshot before the owning cliff harness changes any capture setting."""

    def __init__(self, api, world, landscape):
        self.api, self.world = api, world
        self.values = {name: console_value(api, name) for name in CONSOLE_NAMES}
        self.viewport = api.get_editor_subsystem(api.UnrealEditorSubsystem)
        self.camera = self.viewport.get_level_viewport_camera_info()
        if self.camera is None:
            raise RuntimeError("Preparation requires an active native viewport")
        self.components = list(
            landscape.get_components_by_class(api.LandscapeComponent)
        )
        if len(self.components) != 1024:
            raise RuntimeError("Preparation needs the entire accepted Landscape")
        self.lods = {
            component.get_path_name(): int(component.get_editor_property("forced_lod"))
            for component in self.components
        }
        self.report = {
            "console_before": dict(self.values),
            "component_forced_lod_before": self.lods,
            "adaptive_during_capture": False,
            "restored": False,
        }

    def enable_adaptive(self):
        self.api.SystemLibrary.execute_console_command(self.world, "r.ForceLOD -1")
        if int(float(console_value(self.api, "r.ForceLOD"))) != -1:
            raise RuntimeError("Native global automatic LOD did not apply")
        for component in self.components:
            component.set_editor_property("forced_lod", -1)
        if any(
            int(component.get_editor_property("forced_lod")) != -1
            for component in self.components
        ):
            raise RuntimeError("Native component automatic LOD did not apply")
        self.report.update(
            adaptive_during_capture=True,
            global_force_lod_during_capture=-1,
            component_auto_lod_count=1024,
            geometry_lod_cost_measured=False,
        )

    def assert_adaptive(self):
        if int(float(console_value(self.api, "r.ForceLOD"))) != -1 or any(
            int(component.get_editor_property("forced_lod")) != -1
            for component in self.components
        ):
            raise RuntimeError("Whole-map capture lost native adaptive LOD")

    def restore(self):
        errors = []
        for component in self.components:
            try:
                previous = self.lods[component.get_path_name()]
                component.set_editor_property("forced_lod", previous)
                if int(component.get_editor_property("forced_lod")) != previous:
                    raise RuntimeError("component LOD did not restore")
            except Exception as exc:  # noqa: BLE001 - continue every native rollback after wrapper errors
                errors.append(component.get_path_name() + ": " + str(exc))
        for name, previous in self.values.items():
            try:
                self.api.SystemLibrary.execute_console_command(
                    self.world, name + " " + previous
                )
                if abs(float(console_value(self.api, name)) - float(previous)) > 1e-6:
                    raise RuntimeError("console value did not restore")
            except Exception as exc:  # noqa: BLE001 - continue every native rollback after wrapper errors
                errors.append(name + ": " + str(exc))
        try:
            self.viewport.set_level_viewport_camera_info(*self.camera)
            actual = self.viewport.get_level_viewport_camera_info()
            if (
                actual is None
                or any(
                    abs(
                        float(getattr(actual[0], axis))
                        - float(getattr(self.camera[0], axis))
                    )
                    > 0.001
                    for axis in ("x", "y", "z")
                )
                or any(
                    abs(
                        (
                            float(getattr(actual[1], axis))
                            - float(getattr(self.camera[1], axis))
                            + 180
                        )
                        % 360
                        - 180
                    )
                    > 0.01
                    for axis in ("pitch", "yaw", "roll")
                )
            ):
                raise RuntimeError("Original viewport camera did not restore")
        except Exception as exc:  # noqa: BLE001 - continue every native rollback after wrapper errors
            errors.append("viewport: " + str(exc))
        self.report.update(restored=not errors, restore_errors=errors)
        return errors


def mesh_material_snapshot(api):
    """Read separate road/BOB/cliff materials; Landscape is not a MeshComponent."""
    rows = []
    actors = api.get_editor_subsystem(api.EditorActorSubsystem).get_all_level_actors()
    for actor in actors:
        for component in actor.get_components_by_class(api.MeshComponent):
            rows.append(
                {
                    "component": component.get_path_name(),
                    "materials": [
                        None
                        if component.get_material(i) is None
                        else component.get_material(i).get_path_name()
                        for i in range(component.get_num_materials())
                    ],
                    "collision": str(component.get_collision_enabled()),
                }
            )
    return sorted(rows, key=lambda row: row["component"])


def assert_isolated_bootstrap(api):
    """Refuse graph creation if project startup loaded the working Landscape."""
    world = api.get_editor_subsystem(api.UnrealEditorSubsystem).get_editor_world()
    path = world.get_path_name()
    actors = api.get_editor_subsystem(api.EditorActorSubsystem).get_all_level_actors()
    landscape_count = len(
        api.GameplayStatics.get_all_actors_of_class(world, api.Landscape)
    )
    component_count = sum(
        len(actor.get_components_by_class(api.LandscapeComponent)) for actor in actors
    )
    if path.split(".")[0] != "/Engine/Maps/Entry" or landscape_count or component_count:
        raise RuntimeError(
            "Whole-map master requires isolated /Engine/Maps/Entry with no Landscape"
        )
    return {
        "world": path,
        "package": path.split(".")[0],
        "landscape_actor_count": landscape_count,
        "landscape_component_count": component_count,
        "isolated": True,
    }


def drain_compilation(api):
    result = json.loads(
        api.YacsTextureAuditLibrary.drain_asset_compilation_and_collect_garbage()
    )
    if (
        not result.get("ok")
        or result.get("remaining_after") != 0
        or result.get("shader_jobs_after") != 0
    ):
        raise RuntimeError("Whole-map native asset compilation did not drain")
    return result


class LandscapeBinding:
    def __init__(self, api, landscape, master, instance):
        self.api, self.landscape, self.master, self.instance = (
            api,
            landscape,
            master,
            instance,
        )
        self.components = sorted(
            landscape.get_components_by_class(api.LandscapeComponent),
            key=lambda component: component.get_path_name(),
        )
        if len(self.components) != 1024:
            raise RuntimeError("Preparation must bind all 1024 components")
        self.original = landscape.get_editor_property("landscape_material")
        self.overrides = {
            component.get_path_name(): component.get_editor_property(
                "override_material"
            )
            for component in self.components
        }
        self.other_materials = mesh_material_snapshot(api)
        self.applied = False

    def assert_other_materials(self):
        if mesh_material_snapshot(self.api) != self.other_materials:
            raise RuntimeError(
                "A separate road/BOB/cliff material or collision mode changed"
            )

    def apply(self):
        self.applied = True  # Restore even when a setter partially fails.
        self.landscape.set_editor_property("landscape_material", self.instance)
        for component in self.components:
            component.set_editor_property("override_material", None)
        drain_compilation(self.api)
        self.assert_other_materials()
        return self.audit()

    def audit(self):
        rows = []
        for component in self.components:
            if (
                component.get_material(0) != self.instance
                or component.get_editor_property("override_material") is not None
            ):
                raise RuntimeError(
                    "Landscape assignment differs: " + component.get_name()
                )
            # The existing reflected audit walks to terminal UMaterial. It must
            # receive the master, not its MaterialInstanceConstant child.
            row = json.loads(
                self.api.YacsTextureAuditLibrary.describe_landscape_material_instances(
                    component, self.master
                )
            )
            if (
                not row.get("all_instances_match")
                or row.get("render_instance_count", 0) <= 0
            ):
                raise RuntimeError(
                    "Native Landscape render root differs: " + component.get_name()
                )
            row.update(
                assigned_instance=self.instance.get_path_name(), override_is_none=True
            )
            rows.append(row)
        return rows

    def restore(self):
        errors = []
        try:
            self.landscape.set_editor_property("landscape_material", self.original)
        except Exception as exc:  # noqa: BLE001 - continue every native rollback after wrapper errors
            errors.append("global material: " + str(exc))
        for component in self.components:
            try:
                previous = self.overrides[component.get_path_name()]
                component.set_editor_property("override_material", previous)
                if component.get_editor_property("override_material") != previous:
                    raise RuntimeError("override did not restore")
            except Exception as exc:  # noqa: BLE001 - continue every native rollback after wrapper errors
                errors.append(component.get_path_name() + ": " + str(exc))
        try:
            if (
                self.landscape.get_editor_property("landscape_material")
                != self.original
            ):
                raise RuntimeError("global material did not restore")
            self.assert_other_materials()
        except Exception as exc:  # noqa: BLE001 - continue every native rollback after wrapper errors
            errors.append(str(exc))
        self.applied = False if not errors else self.applied
        return errors


def preview(action="apply", *, bundle=None, master_receipt=None):
    """Explicit reversible owner replay of the retained candidate packages.

    Run inside the already-open accepted map. Existing road and native v8 mesh
    materials remain owned by their actors. This does not load or save a map.
    """
    import builtins

    import unreal

    state_name = "_yacs_whole_map_preparation_preview"
    state = getattr(builtins, state_name, None)
    if action == "restore":
        if state is None:
            raise RuntimeError("No whole-map preview is active")
        errors = state["binding"].restore() + state["environment"].restore()
        if errors:
            raise RuntimeError(
                "Whole-map preview rollback failed: " + "; ".join(errors)
            )
        delattr(builtins, state_name)
        return {"status": "RESTORED", "map_saved": False}
    if (
        action != "apply"
        or state is not None
        or bundle is None
        or master_receipt is None
    ):
        raise ValueError("Use apply with bundle/master_receipt once, then restore")
    if not unreal.SystemLibrary.get_engine_version().startswith("5.8.2-56702186"):
        raise RuntimeError("Whole-map preview requires the verified engine version")
    inputs = load_inputs(bundle)
    receipt = json.loads(checked_bytes(master_receipt, 2 * 1024 * 1024))
    if (
        receipt.get("status") != "WHOLE_MAP_FIXED_MASTER_SAVED"
        or receipt.get("prep_manifest_sha256") != inputs["manifest_sha256"]
        or receipt.get("source_assets") != source_assets()
        or receipt.get("rendering_recipe") != rendering_recipe()
    ):
        raise ValueError("Retained preparation packages and source contract differ")
    generated = receipt.get("generated_assets", [])
    if {row.get("asset") for row in generated} != {
        MASTER_PATH,
        INSTANCE_PATH,
        MASTER_PACKAGE + "/T_WholeMapWeights",
    }:
        raise ValueError("Unexpected retained preparation package inventory")
    for row in generated:
        if digest(asset_file(row["asset"])) != row.get("sha256") or package_files(
            row["asset"]
        ) != row.get("package_files"):
            raise ValueError("Retained preparation package changed")
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    if world.get_path_name().split(".")[0] != MAP:
        raise RuntimeError("Open the accepted map before applying the preview")
    landscapes = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Landscape)
    if len(landscapes) != 1:
        raise RuntimeError("Expected one accepted Landscape")
    memory = memory_checkpoint("before_owner_preview", 8, 12)
    master, instance = unreal.load_asset(MASTER_PATH), unreal.load_asset(INSTANCE_PATH)
    if master is None or instance is None:
        raise RuntimeError("Restore the retained generated packages before preview")
    verify_instance(unreal, master, instance, receipt)
    binding = LandscapeBinding(unreal, landscapes[0], master, instance)
    environment = CaptureEnvironment(unreal, world, landscapes[0])
    # Persist rollback handles before the first setter, including partial failure.
    setattr(builtins, state_name, {"binding": binding, "environment": environment})
    try:
        environment.enable_adaptive()
        rows = binding.apply()
    except Exception as exc:
        errors = binding.restore() + environment.restore()
        if not errors:
            delattr(builtins, state_name)
        raise RuntimeError(
            "Whole-map preview apply failed: "
            + str(exc)
            + (
                "; rollback incomplete: " + "; ".join(errors)
                if errors
                else "; original bindings restored"
            )
        ) from exc
    return {
        "status": "WHOLE_MAP_PREVIEW_APPLIED",
        "component_count": len(rows),
        "memory": memory,
        "prep_manifest_sha256": inputs["manifest_sha256"],
        "map_saved": False,
        "visual_acceptance": "PENDING_OWNER",
        "restore": "preview('restore')",
    }
