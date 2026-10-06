"""Read live texture residency and runtime quality settings without mutation."""

import json
import runpy
from pathlib import Path
import unreal

ROOT = Path(__file__).resolve().parents[2]


def main(force=False):
    repair = runpy.run_path(str(ROOT / "scripts/ue/sa_calobra_material_repair.py"))
    state = repair["context"]()
    audit = getattr(unreal, "YacsTextureAuditLibrary", None)
    rows = []
    for texture in unreal.MaterialEditingLibrary.get_used_textures(state["current"]):
        row = {"texture": texture.get_path_name()}
        for key in (
            "srgb",
            "never_stream",
            "lod_bias",
            "max_texture_size",
            "compression_settings",
            "mip_gen_settings",
        ):
            row[key] = str(texture.get_editor_property(key))
        if audit and hasattr(audit, "describe_texture"):
            row["native"] = json.loads(audit.describe_texture(texture))
        rows.append(row)
    report = {
        "textures": rows,
        "cvars": {
            name: unreal.SystemLibrary.get_console_variable_int_value(name)
            for name in (
                "r.Streaming.PoolSize",
                "r.Streaming.MipBias",
                "sg.TextureQuality",
                "r.ScreenPercentage",
            )
        },
    }
    target = "residency-forced.json" if force else "residency.json"
    (repair["OUT"] / target).write_text(json.dumps(report, indent=2), encoding="utf-8")
    if force:
        state["current"].set_force_mip_levels_to_be_resident(
            False, False, 60.0, 0, False
        )
        unreal.AutomationLibrary.finish_loading_before_screenshot()
        state["residency_capture"] = unreal.AutomationLibrary.take_high_res_screenshot(
            res_x=1920,
            res_y=1080,
            filename=str(repair["OUT"] / "resident-comparison.png"),
            delay=5.0,
            force_game_view=True,
        )
    unreal.log("YACS_REPAIR_RESIDENCY_CAPTURED")


if __name__ == "__main__":
    main()
