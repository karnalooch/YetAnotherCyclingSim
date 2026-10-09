"""Generate one explicit quality-library role at a time, preserving the scene."""

import json
import runpy
from pathlib import Path

import unreal

ROOT = Path(__file__).resolve().parents[2]
BASE = runpy.run_path(
    str(ROOT / "scripts/assets/generate_sa_calobra_texture_library_ue.py")
)
MEMORY = runpy.run_path(str(ROOT / "scripts/ue/sa_calobra_material_waves.py"))[
    "available_memory"
]


def headroom():
    memory = MEMORY()
    if memory["free_physical"] < 8 * 1024**3 or memory["free_commit"] < 12 * 1024**3:
        raise RuntimeError("Pause: insufficient memory headroom")


class QualityBatch(BASE["Batch"]):
    def begin_item(self):
        headroom()
        super().begin_item()

    def material(self, result):
        item = self.items[self.index]
        outputs = {
            channel: {**result["outputs"][channel], "origin": "UE TextureGraph"}
            for channel in ("BaseColor", "MacroMask")
        }
        for channel in ("Normal", "Roughness", "Height"):
            task = unreal.AssetImportTask()
            for prop, value in {
                "filename": item["pbr_maps"][channel]["path"],
                "destination_path": self.folder + "/ProviderData/" + item["role"],
                "destination_name": "T_" + channel,
                "automated": True,
                "replace_existing": False,
                "save": False,
            }.items():
                task.set_editor_property(prop, value)
            unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
            paths = task.get_editor_property("imported_object_paths")
            if len(paths) != 1:
                raise RuntimeError("Provider import failed: " + channel)
            texture = unreal.load_asset(paths[0])
            texture.set_editor_property("srgb", False)
            texture.set_editor_property(
                "compression_settings",
                unreal.TextureCompressionSettings.TC_NORMALMAP
                if channel == "Normal"
                else unreal.TextureCompressionSettings.TC_MASKS,
            )
            texture.set_editor_property("address_x", unreal.TextureAddress.TA_WRAP)
            texture.set_editor_property("address_y", unreal.TextureAddress.TA_WRAP)
            if channel == "Normal":
                texture.set_editor_property("flip_green_channel", False)
            if not unreal.EditorAssetLibrary.save_loaded_asset(
                texture, only_if_is_dirty=False
            ):
                raise RuntimeError("Provider asset save failed")
            outputs[channel] = {
                "asset": texture.get_path_name(),
                "origin": "provider PBR unchanged",
                "source": item["pbr_maps"][channel],
                "srgb": False,
            }
        material = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            "M_SC_" + item["role"],
            self.folder + "/Materials",
            unreal.Material,
            unreal.MaterialFactoryNew(),
        )
        if material is None:
            raise RuntimeError("Material creation failed")
        lib = unreal.MaterialEditingLibrary
        for index, (channel, pin, prop, sampler) in enumerate(
            (
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
        ):
            node = lib.create_material_expression(
                material, unreal.MaterialExpressionTextureSample, -450, index * 220
            )
            node.set_editor_property(
                "texture", unreal.load_asset(outputs[channel]["asset"])
            )
            node.set_editor_property("sampler_type", sampler)
            if not lib.connect_material_property(node, pin, prop):
                raise RuntimeError("Material connection failed")
        if lib.recompile_material(material):
            raise RuntimeError("Material compile failed")
        if not unreal.EditorAssetLibrary.save_loaded_asset(
            material, only_if_is_dirty=False
        ):
            raise RuntimeError("Material save failed")
        result["final_pbr_outputs"] = outputs
        result["data_map_authority"] = "provider maps; not inferred from BaseColor"
        result["height_connected_to_geometry"] = False
        return material.get_path_name()

    def tick(self, dt):
        if self.phase == "awaiting_next_role":
            return
        previous = self.index
        super().tick(dt)
        if self.phase == "next" and self.index > previous:
            if self.index == len(self.items):
                self.finish()
            else:
                self.phase = "awaiting_next_role"
            self.progress()

    def progress(self):
        report = {
            "phase": self.phase,
            "completed_roles": [r["role"] for r in self.results],
            "library": self.folder,
            "result_directory": str(self.out),
            "automatic_next_role": False,
            "visual_acceptance": "pending",
            "target_score": 9,
            "achieved_score": None,
            "map_saved": False,
        }
        (ROOT / "Saved/RuntimeProof/quality-library-progress.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8"
        )
        unreal.log("YACS_QUALITY_LIBRARY " + json.dumps(report))


def main():
    state = getattr(unreal, "_yacs_quality_library", None)
    if state and state.phase == "finished" and not state.results:
        failure = json.loads((state.out / "result.json").read_text())
        manifest = (
            ROOT / "worldgen/materials/sa_calobra_texture_library_v2_20261005.json"
        )
        updated = json.loads(manifest.read_text())
        if (
            failure["status"] == "failed"
            and "Source alpha must be opaque" in str(failure["error"])
            and updated["items"][0]["source_sha256"]
            != state.manifest["items"][0]["source_sha256"]
        ):
            # Only the rejected, zero-output alpha attempt may be replaced.
            # Preserve its receipt; all other failures still require diagnosis.
            unreal.log("YACS_QUALITY_ALPHA_SOURCE_REPLACED " + str(state.out))
            state = None
    if state:
        if state.phase != "awaiting_next_role":
            raise RuntimeError(
                "Wait for the current role; finished/failed batches do not restart"
            )
        headroom()
        if (
            BASE["scene"]() != state.before
            or BASE["digest"](state.map_file) != state.map_hash
        ):
            raise RuntimeError("Scene changed during the quality-library run")
        state.phase = "next"
        state.progress()
        return
    headroom()
    manifest = ROOT / "worldgen/materials/sa_calobra_texture_library_v2_20261005.json"
    recipe = json.loads(manifest.read_text())
    if BASE["digest"](ROOT / recipe["map_file"]) != recipe["map_sha256"]:
        raise RuntimeError("Accepted map identity changed")
    for item in recipe["items"]:
        for entry in item["pbr_maps"].values():
            if BASE["digest"](entry["path"]) != entry["sha256"]:
                raise RuntimeError("PBR source hash mismatch")
    previous = getattr(unreal, "_yacs_surface_library_batch", None)
    if previous and previous.phase != "finished":
        raise RuntimeError("Another library batch is active")
    state = QualityBatch(manifest)
    unreal._yacs_quality_library = state
    unreal._yacs_surface_library_batch = state
    state.progress()


if __name__ == "__main__":
    main()
