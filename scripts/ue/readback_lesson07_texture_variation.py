"""Read the saved L07 TextureVariation graph without modifying editor assets.

The saved UE graphs are the authoring source: Epic TextureVariation, shared
shifted UVs/gradients, and bounded Pegasus array-function copies. No custom
terrain or stochastic-sampling algorithm is introduced by this adapter.
"""

import json
from pathlib import Path

BASE = "/Game/Generated/YACS/Lesson07_Unified/Materials"
VARIATION = "/Engine/Functions/Engine_MaterialFunctions03/Texturing/TextureVariation"


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def main():
    import unreal

    project = Path(
        unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    ).resolve()
    require(
        project == Path(__file__).resolve().parents[2],
        "Active Unreal project differs from this script checkout",
    )
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    require(
        world.get_path_name()
        == BASE.rsplit("/", 1)[0] + "/L_SaCalobra_Lesson07.L_SaCalobra_Lesson07",
        "Wrong active world",
    )
    lib = unreal.MaterialEditingLibrary
    master = unreal.load_asset(BASE + "/M_Landscape_YACS")
    instance = unreal.load_asset(BASE + "/MI_Landscape_Instance_YACS")
    require(instance.get_editor_property("parent") == master, "Instance parent differs")
    require(
        not master.get_editor_property("enable_tessellation"), "Unexpected tessellation"
    )

    def inputs(node):
        return dict(
            zip(
                map(str, lib.get_material_expression_input_names(node)),
                lib.get_inputs_for_material_expression(master, node),
            )
        )

    expressions = list(lib.get_material_expressions(master))
    calls = [
        n
        for n in expressions
        if isinstance(n, unreal.MaterialExpressionMaterialFunctionCall)
    ]
    variations = [
        n
        for n in calls
        if n.get_editor_property("material_function").get_path_name().split(".")[0]
        == VARIATION
    ]
    require(len(variations) == 2, "Expected shared detail and macro variation nodes")
    for node in variations:
        connected = inputs(node)
        for name, expected in (
            ("Variation Scale", 1.0),
            ("Variation Levels", 13.0),
            ("Heightmap Influence", 0.0),
        ):
            require(
                connected[name].get_editor_property("r") == expected,
                "Variation setting differs: " + name,
            )
        require(
            not connected["Random Rotation and Scale"].get_editor_property("value"),
            "Rotation must remain disabled",
        )
        require(
            connected["Use Dither"].get_editor_property("value"),
            "Expected temporal dither",
        )
    functions = {}
    for suffix, sampler_type in (
        ("Colour", unreal.MaterialSamplerType.SAMPLERTYPE_COLOR),
        ("Normal", unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL),
        ("Masks", unreal.MaterialSamplerType.SAMPLERTYPE_MASKS),
    ):
        path = BASE + "/Functions/MF_YACS_ArrayVariation" + suffix
        function = unreal.load_asset(path)
        nodes = list(lib.get_material_function_expressions(function))
        samples = [
            n for n in nodes if isinstance(n, unreal.MaterialExpressionTextureSample)
        ]
        require(len(samples) == 4, "Expected four corner samples: " + suffix)
        for node in samples:
            require(
                node.get_editor_property("mip_value_mode")
                == unreal.TextureMipValueMode.TMVM_DERIVATIVE,
                "Missing explicit derivatives",
            )
            require(
                node.get_editor_property("sampler_type") == sampler_type,
                "Wrong channel sampler interpretation",
            )
            for name in ("DDX(UVs)", "DDY(UVs)"):
                append = inputs(node)[name]
                require(
                    isinstance(append, unreal.MaterialExpressionAppendVector),
                    "Expected 3D array gradient",
                )
                require(
                    inputs(append)["B"].get_editor_property("r") == 0.0,
                    "Array index gradient must be zero",
                )
        users = [
            n for n in calls if n.get_editor_property("material_function") == function
        ]
        require(len(users) == 2, "Expected detail and macro sampler calls")
        for node in users:
            connected = inputs(node)
            require(connected["UVS"] in variations, "Shifted UVs not connected")
            require(
                connected["UV_DDX"] == connected["UVS"] == connected["UV_DDY"],
                "PBR UV gradients not shared",
            )
        functions[suffix] = {
            "path": path,
            "samples": len(samples),
            "call_output_names": [
                [str(n) for n in lib.get_material_expression_output_names(call)]
                for call in users
            ],
        }
    by_name = {n.get_name(): n for n in expressions}
    normal = inputs(by_name["MaterialExpressionMaterialFunctionCall_30"])
    require(
        all(
            normal[name] == by_name["MaterialExpressionMaterialFunctionCall_43"]
            for name in ("X", "Y", "Z")
        ),
        "Signed normal components differ",
    )
    report = {
        "status": "NATIVE_TEXTURE_VARIATION_GRAPH_READBACK_PASS",
        "world": world.get_path_name(),
        "functions": functions,
        "variation_scale": 1.0,
        "variation_levels": 13.0,
        "random_offset_variation": lib.get_material_instance_scalar_parameter_value(
            instance, "Random Offset Variation"
        ),
        "anti_aliasing_method": unreal.SystemLibrary.get_console_variable_int_value(
            "r.AntiAliasingMethod"
        ),
        "statistics": str(lib.get_statistics(instance)),
        "asset_writes": False,
        "map_saved": False,
        "render_acceptance": False,
        "fresh_reopen_verified": False,
    }
    proof = project / "Saved/RuntimeProof/Lesson07Squares-20261020-1"
    proof.mkdir(parents=True, exist_ok=True)
    (proof / "graph-readback.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print("YACS_TEXTURE_VARIATION_GRAPH_READBACK_PASS")


if __name__ == "__main__":
    main()
