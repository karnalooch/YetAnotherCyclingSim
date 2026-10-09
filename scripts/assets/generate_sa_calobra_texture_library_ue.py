"""Generate an isolated seven-role library through native YacsTextureTools.

Call start(manifest_path) in the existing editor. Never assigns world materials,
saves a level, overwrites an asset, or starts another editor. Inputs are pinned
local images; all image processing belongs to the existing Texture Graph plugin.
"""

import hashlib
import json
import re
import time
import uuid
from pathlib import Path

import unreal

_active = None


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def scene():
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    actors = sorted(
        (
            a.get_name(),
            a.get_class().get_name(),
            a.get_actor_label(),
            re.sub(r" \(0x[0-9a-fA-F]+\)", "", str(a.get_actor_transform())),
        )
        for a in subsystem.get_all_level_actors()
    )
    return {"world": world.get_path_name(), "actors": actors}


class Batch:
    def __init__(self, manifest_path):
        self.manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8-sig"))
        self.project = Path(unreal.Paths.project_dir()).resolve()
        if self.project != Path(self.manifest["project"]).resolve():
            raise RuntimeError("Wrong project")
        self.items = self.manifest["items"]
        if len(self.items) != 7 or len({i["role"] for i in self.items}) != 7:
            raise RuntimeError("Expected seven unique surface roles")
        for item in self.items:
            if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]+", item["role"]):
                raise RuntimeError("Unsafe role")
            if digest(item["source_file"]) != item["source_sha256"]:
                raise RuntimeError("Source identity mismatch: " + item["role"])
        self.map_file = self.project / self.manifest["map_file"]
        self.map_hash = digest(self.map_file)
        self.before = scene()
        if self.before["world"].split(".")[0] != self.manifest["map_asset"]:
            raise RuntimeError("Open the recorded texture checkpoint first")
        capabilities = json.loads(unreal.YacsTextureTools.inspect_capabilities())
        if capabilities["status"] != "available_opt_in":
            raise RuntimeError(str(capabilities))
        self.id = uuid.uuid4().hex
        self.folder = "/Game/Generated/YACS/TextureMaterialPrep/Libraries/" + self.id
        self.out = self.project / "Saved/RuntimeProof/TextureLibraries" / self.id
        self.out.mkdir(parents=True, exist_ok=False)
        self.write("manifest.json", self.manifest)
        self.results = []
        self.index = 0
        self.phase = "next"
        self.in_tick = False
        self.handle = unreal.register_slate_post_tick_callback(self.tick)
        unreal.log("YACS_TEXTURE_LIBRARY_STARTED " + str(self.out))

    def write(self, name, value):
        with (self.out / name).open("x", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2)

    def begin_item(self):
        # Interchange pumps Slate while importing. A nested tick must not import
        # this same source or start a second native job.
        self.phase = "importing"
        item = self.items[self.index]
        task = unreal.AssetImportTask()
        task.filename = item["source_file"]
        task.destination_path = self.folder + "/Sources"
        task.destination_name = "T_Source_" + item["role"]
        task.automated = True
        task.replace_existing = False
        task.save = True
        unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
        if len(task.imported_object_paths) != 1:
            raise RuntimeError("Source import failed")
        recipe = unreal.YacsTextureRecipe()
        recipe.resolution = 1024
        recipe.world_size_meters = unreal.Vector2D(*item["world_size_m"])
        recipe.seam_blend_width = item.get("seam_blend_width", 0.0)
        recipe.de_light_strength = item.get("de_light_strength", 0.0)
        recipe.color_gain = unreal.LinearColor(*item.get("color_gain", [1, 1, 1]), 1)
        recipe.height_strength = item.get("height_strength", 0.5)
        recipe.normal_strength = item.get("normal_strength", 1.0)
        recipe.roughness_min = item.get("roughness_min", 0.6)
        recipe.roughness_max = item.get("roughness_max", 0.9)
        recipe.macro_variation = item.get("macro_variation", 0.5)
        result = json.loads(
            unreal.YacsTextureTools.prepare_texture(
                task.imported_object_paths[0], recipe
            )
        )
        self.write(item["role"] + "-prepared.json", result)
        if result["status"] != "prepared":
            raise RuntimeError(str(result))
        self.job = result["job_id"]
        result = json.loads(unreal.YacsTextureTools.render_preview(self.job))
        if result["status"] in ("failed", "rejected"):
            raise RuntimeError(str(result))
        self.started = time.monotonic()
        self.phase = "rendering"

    def material(self, result):
        item = self.items[self.index]
        name = "M_SC_" + item["role"]
        package = self.folder + "/Materials"
        if unreal.EditorAssetLibrary.does_asset_exist(package + "/" + name):
            raise RuntimeError("Material collision")
        material = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            name, package, unreal.Material, unreal.MaterialFactoryNew()
        )
        if material is None:
            raise RuntimeError("Material creation failed")
        lib = unreal.MaterialEditingLibrary
        channels = (
            (
                "BaseColor",
                "RGB",
                unreal.MaterialProperty.MP_BASE_COLOR,
                unreal.MaterialSamplerType.SAMPLERTYPE_COLOR,
            ),
            (
                "Normal",
                "RGB",
                unreal.MaterialProperty.MP_NORMAL,
                unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL,
            ),
            (
                "Roughness",
                "R",
                unreal.MaterialProperty.MP_ROUGHNESS,
                unreal.MaterialSamplerType.SAMPLERTYPE_MASKS,
            ),
        )
        for index, (role, pin, prop, sampler) in enumerate(channels):
            texture = unreal.load_asset(result["output_folder"] + "/" + role)
            if not isinstance(texture, unreal.Texture2D):
                raise RuntimeError("Missing generated map: " + role)
            node = lib.create_material_expression(
                material, unreal.MaterialExpressionTextureSample, -450, index * 220
            )
            node.set_editor_property("texture", texture)
            node.set_editor_property("sampler_type", sampler)
            if not lib.connect_material_property(node, pin, prop):
                raise RuntimeError("Material connection failed: " + role)
        errors = lib.recompile_material(material)
        if errors:
            raise RuntimeError("Material compile errors: " + str(errors))
        if not unreal.EditorAssetLibrary.save_loaded_asset(
            material, only_if_is_dirty=False
        ):
            raise RuntimeError("Material save failed")
        return material.get_path_name()

    def finish(self, error=None):
        if self.phase == "finished":
            return
        self.phase = "finished"
        unreal.unregister_slate_post_tick_callback(self.handle)
        unchanged = scene() == self.before and digest(self.map_file) == self.map_hash
        self.write(
            "result.json",
            {
                "status": "generated_review_required"
                if not error and unchanged and len(self.results) == 7
                else "failed",
                "error": error,
                "library": self.folder,
                "items": self.results,
                "world_unchanged": unchanged,
                "map_sha256": self.map_hash,
                "world_assignment": False,
                "visual_acceptance": "pending",
                "height_normal_roughness": "image-derived artistic estimates; not measured PBR",
                "physical_scale": "provider dimensions; not independent survey",
            },
        )
        unreal.log("YACS_TEXTURE_LIBRARY_FINISHED " + str(self.out))

    def tick(self, _dt):
        if self.in_tick or self.phase == "finished":
            return
        self.in_tick = True
        try:
            if self.phase == "next":
                if self.index == len(self.items):
                    self.finish()
                else:
                    self.begin_item()
                return
            result = json.loads(unreal.YacsTextureTools.get_job_status(self.job))
            if (
                result["status"] in ("failed", "rejected", "timeout_draining")
                or time.monotonic() - self.started > 240
            ):
                raise RuntimeError(str(result))
            if self.phase == "rendering" and result["status"] == "rendered":
                self.phase = "exporting"
                exported = json.loads(unreal.YacsTextureTools.export_pbr_set(self.job))
                if exported["status"] in ("failed", "rejected"):
                    raise RuntimeError(str(exported))
            elif (
                self.phase == "exporting"
                and result["status"] == "export_completed_unverified"
            ):
                self.phase = "validating"
                result = json.loads(unreal.YacsTextureTools.validate_texture(self.job))
                if result["status"] != "exported_review_required":
                    raise RuntimeError(str(result))
                result["material"] = self.material(result)
                result["role"] = self.items[self.index]["role"]
                self.results.append(result)
                self.write(result["role"] + "-result.json", result)
                self.index += 1
                self.phase = "next"
        except Exception as exc:
            self.finish(str(exc))
            unreal.log_error("YACS_TEXTURE_LIBRARY_FAILED " + str(exc))
        finally:
            self.in_tick = False


def start(manifest_path):
    global _active
    previous = getattr(unreal, "_yacs_surface_library_batch", None)
    if previous is not None and previous.phase != "finished":
        raise RuntimeError("Batch still active; inspect its receipt before retrying")
    _active = Batch(manifest_path)
    unreal._yacs_surface_library_batch = _active
    return str(_active.out)


if __name__ == "__main__":
    # Explicit startup option for a freshly launched editor, never a live-session
    # map switch. The normal menu entry still requires the checkpoint already open.
    if "-YacsTextureLibraryStartup" in unreal.SystemLibrary.get_command_line():
        unreal.EditorPythonScripting.set_keep_python_script_alive(True)
        checkpoint = "/Game/Worlds/SaCalobra/L_SaCalobraTextureCheckpoint_20261005"
        if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level(
            checkpoint
        ):
            raise RuntimeError("Texture checkpoint load failed")
    start(
        Path(__file__).resolve().parents[2]
        / "worldgen/materials/sa_calobra_texture_library_20261005.json"
    )
