"""Owned isolated #365 native diagnostics; never Sa Calobra placement admission.

The launcher stages an empty content-only project and authenticated dependencies.
Inspect reads the installed Epic graph skill and reflected APIs before authoring.
Native output remains local diagnostic evidence, not a Proof Broker receipt.
"""

import hashlib
import json
import os
import sys
from pathlib import Path
import time
import traceback

import unreal


OUTPUT = Path(os.environ["YACS_PCG_PROBE_OUTPUT"])
ACTION = os.environ["YACS_PCG_PROBE_ACTION"]
HEAD = os.environ["YACS_PCG_PROBE_EXPECTED_HEAD"]
CONTACT_ACTIONS = {f"collection-contact-{index:02d}" for index in range(10)} | {
    "collection-contact-reload", "collection-contact-render"
}
PACKAGE = "/Game/Generated/YACS/PCG365Mechanical"
GRAPH_PATH = PACKAGE + "/PCG_XYFixture"
MAP_PATH = PACKAGE + "/L_XYFixture"
FIXTURE_POINTS = ((0, 0, 50, 36501), (200, 0, 50, 36502), (0, 200, 50, 36503))
ACTIVE = None
QUIT_CALLBACK = None


def write_new(name, value):
    path = OUTPUT / name
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, sort_keys=True, indent=2))


def vector(value):
    return [float(value.x), float(value.y), float(value.z)]


def native_tool(class_path, name, arguments):
    cls = unreal.load_class(None, class_path)
    if not cls:
        raise RuntimeError("Missing installed toolset: " + class_path)
    registry = unreal.ToolsetRegistry
    if not registry.is_toolset_class_registered(cls):
        registry.register_toolset_class(cls)
    schema = json.loads(registry.get_toolset_json_schema(cls))
    result = registry.execute_tool(schema["name"], name, json.dumps(arguments))
    if not result.get_editor_property("bIsComplete") or result.error:
        raise RuntimeError("Native synchronous reader failed: " + str(result.error))
    wrapped = json.loads(result.value)
    if not isinstance(wrapped, dict) or set(wrapped) != {"returnValue"}:
        raise RuntimeError("Unexpected native tool result wrapper")
    return wrapped["returnValue"]


def inspect_mesh(path):
    mesh = unreal.load_asset(path)
    if not isinstance(mesh, unreal.StaticMesh):
        raise RuntimeError("Expected native StaticMesh: " + path)
    bounds = mesh.get_bounds()
    subsystem = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    import_data = mesh.get_editor_property("asset_import_data")
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    options = unreal.AssetRegistryDependencyOptions(
        include_soft_package_references=True,
        include_hard_package_references=True,
        include_searchable_names=False,
        include_soft_management_references=False,
        include_hard_management_references=False,
    )
    package = mesh.get_path_name().split(".")[0]
    dependencies = [str(item) for item in registry.get_dependencies(package, options)]
    asset_data = unreal.AssetRegistryHelpers.create_asset_data(mesh)
    import_tag = asset_data.get_tag_value("AssetImportData")
    if import_tag is not None and not isinstance(import_tag, str):
        raise RuntimeError("Unexpected native import tag return type")
    return {
        "object_path": mesh.get_path_name(),
        "class": mesh.get_class().get_name(),
        "bounds_origin_cm": vector(bounds.origin),
        "bounds_extent_cm": vector(bounds.box_extent),
        "sphere_radius_cm": float(bounds.sphere_radius),
        "lod_count": mesh.get_num_lods(),
        "lod_vertices": [
            subsystem.get_number_verts(mesh, lod) for lod in range(mesh.get_num_lods())
        ],
        "lod_uv_channels": [
            subsystem.get_num_uv_channels(mesh, lod)
            for lod in range(mesh.get_num_lods())
        ],
        "collision_complexity": str(subsystem.get_collision_complexity(mesh)),
        "import_filenames": list(import_data.extract_filenames())
        if import_data
        else [],
        "loaded_asset_import_tag": json.loads(import_tag) if import_tag else None,
        "package_dependencies": dependencies,
        "missing_game_dependencies": [
            item
            for item in dependencies
            if item.startswith("/Game/")
            and not unreal.EditorAssetLibrary.does_asset_exist(item)
        ],
        "material_slots": [
            str(slot.material_slot_name) for slot in mesh.static_materials
        ],
        "material_objects": [
            slot.material_interface.get_path_name() if slot.material_interface else None
            for slot in mesh.static_materials
        ],
        "qualification_status": "PENDING",
        "source_provenance": "NOT_ADMITTED",
    }


def inspect():
    # Read through Epic's reflected skill API; do not parse cooked/uasset bytes.
    skill_class = unreal.load_class(None, "/Script/ToolsetRegistry.AgentSkillToolset")
    if not skill_class:
        raise RuntimeError("Installed AgentSkillToolset class is unavailable")
    registry = unreal.ToolsetRegistry
    if not registry.is_toolset_class_registered(skill_class):
        registry.register_toolset_class(skill_class)
    schema = json.loads(registry.get_toolset_json_schema(skill_class))
    write_new("installed-skill-tool-schema.json", schema)

    def call_skill(name, arguments):
        # AICallable functions are not Python methods. Use the installed registry
        # wrapper; these two native skill readers are synchronous. A pending or
        # failed result is a hard diagnostic failure, never fabricated output.
        result = registry.execute_tool(schema["name"], name, json.dumps(arguments))
        if not result.get_editor_property("bIsComplete"):
            raise RuntimeError("Native skill reader did not complete synchronously")
        if result.error:
            raise RuntimeError(result.error)
        wrapped = json.loads(result.value)
        if not isinstance(wrapped, dict) or set(wrapped) != {"returnValue"}:
            raise RuntimeError("Unexpected native tool result wrapper")
        return wrapped["returnValue"]

    skills = call_skill("ListSkills", {})
    selected = [str(path) for path in skills if "Skill_PCGGraphGeneration" in str(path)]
    if len(selected) != 1:
        raise RuntimeError("Expected one installed PCG graph skill: " + repr(selected))
    details = call_skill("GetSkills", {"skillPaths": selected})
    prompts = {}
    for path, detail in details.items():
        keys = [key for key in detail if key.casefold() == "instructions"]
        if len(keys) != 1 or not isinstance(detail[keys[0]], str):
            raise RuntimeError("Malformed installed skill details")
        prompts[str(path)] = detail[keys[0]]
    if len(prompts) != 1 or not all(prompts.values()):
        raise RuntimeError("PCG graph skill did not return instructions")
    write_new("installed-pcg-skill.json", prompts)
    types = (
        "PCGCreatePointsSettings",
        "PCGPoint",
        "PCGGraph",
        "PCGGraphFactory",
        "PCGComponent",
        "PCGVolume",
        "PCGPointData",
        "PCGDataCollection",
        "PCGStaticMeshSpawnerSettings",
        "PCGExSampleNearestSurfaceSettings",
        "AgentSkillToolset",
        "PCGToolset",
        "StaticMeshEditorSubsystem",
        "EditorActorSubsystem",
        "SystemLibrary",
        "CollisionResponseType",
        "CollisionEnabled",
        "TraceTypeQuery",
        "DrawDebugTrace",
        "PrimitiveComponent",
        "MaterialEditingLibrary",
        "MaterialEditorOnlyData",
        "MaterialProperty",
    )
    inventory = {
        name: sorted(
            item for item in dir(getattr(unreal, name)) if not item.startswith("_")
        )
        if hasattr(unreal, name)
        else None
        for name in types
    }
    write_new("reflected-pcg-api.json", inventory)
    meshes = [inspect_mesh("/Engine/BasicShapes/Cube.Cube")]
    boulder = "/Game/Prototype/Environment/Stage3G/Imported/Meshes/SM_Stage3G_Boulder"
    if unreal.EditorAssetLibrary.does_asset_exist(boulder):
        meshes.append(inspect_mesh(boulder))
    write_new("native-mesh-inventory.json", meshes)
    return {
        "status": "NATIVE_INSPECTION_COMPLETED",
        "skill_paths": selected,
        "skill_sha256": hashlib.sha256(
            json.dumps(prompts, sort_keys=True).encode()
        ).hexdigest(),
        "mesh_count": len(meshes),
    }


def main():
    global ACTIVE
    receipt = {
        "schema_version": 1,
        "issue": 365,
        "code_sha": HEAD,
        "action": ACTION,
        "placement": False,
        "proof_admission": "LOCAL_DIAGNOSTIC_ONLY",
        "native_build": "NOT_RUN_PREBUILT_DEPENDENCY",
        "terrain_contact": "NOT_RUN",
        "qualified_assets": [],
        "owner_visual_status": "PENDING_FINAL_M3",
        "performance_pass": False,
        "status": "FAILED",
    }
    try:
        if ACTION in {"mask-xy-create", "mask-xy-reload"}:
            unreal.EditorPythonScripting.set_keep_python_script_alive(True)
            root = Path(unreal.Paths.project_dir()).resolve()
            sys.path.insert(0, str(root))
            from scripts.ue import sa_calobra_pcg_mask_xy_graph

            ACTIVE = sa_calobra_pcg_mask_xy_graph.start(
                root, OUTPUT, HEAD, ACTION, finish
            )
            return
        if ACTION in CONTACT_ACTIONS | {
            "material",
            "material-reload",
            "terrain",
            "settle-render",
            "rock-qualify",
            "rock-reload",
            "rock-render",
            "rock-pack",
            "rock-pack-reload",
            "rock-collection",
            "rock-collection-reload",
            "rock-collection-render",
        }:
            unreal.EditorPythonScripting.set_keep_python_script_alive(True)
            if not unreal.EditorLoadingAndSavingUtils.new_blank_map(False):
                raise RuntimeError(
                    "Transient diagnostic editor world initialization failed"
                )
            root = Path(unreal.Paths.project_dir()).resolve()
            sys.path.insert(0, str(root))
            from scripts.ue import sa_calobra_pcg_material_binding as binding_helper

            if ACTION == "material":
                binding = binding_helper.prepare_binding(root / "forge-source", HEAD)
                binding_helper.save_binding(binding)
                write_new("binding.json", binding)
                receipt["status"] = "MATERIAL_BINDING_SAVED"
                receipt["binding"] = binding
            else:
                binding = json.loads(
                    (root / "proof/material/binding.json").read_text(encoding="utf-8")
                )
                if binding["code_sha"] != HEAD:
                    raise RuntimeError("Material binding source SHA differs")
                receipt["binding_readback"] = binding_helper.verify_binding(binding)
                if ACTION in CONTACT_ACTIONS:
                    from scripts.ue import sa_calobra_pcg_collection_contact as contact

                    if ACTION == "collection-contact-render":
                        ACTIVE = contact.start(root, OUTPUT, HEAD, binding, finish)
                        return
                    if ACTION == "collection-contact-reload":
                        receipt.update(contact.reload(root, OUTPUT, HEAD, binding))
                    else:
                        receipt.update(contact.run(root, OUTPUT, HEAD, binding, int(ACTION[-2:])))
                elif ACTION == "rock-render":
                    from scripts.ue import sa_calobra_pcg_rock_capture

                    ACTIVE = sa_calobra_pcg_rock_capture.start(
                        root, OUTPUT, HEAD, binding, finish
                    )
                    return
                elif ACTION in {"rock-qualify", "rock-reload"}:
                    from scripts.ue import sa_calobra_pcg_rock_qualification as rocks

                    operation = rocks.run if ACTION == "rock-qualify" else rocks.reload
                    receipt.update(operation(root, OUTPUT, HEAD, binding))
                elif ACTION in {"rock-pack", "rock-pack-reload"}:
                    from scripts.ue import sa_calobra_pcg_rock_variant_pack as pack

                    operation = pack.build if ACTION == "rock-pack" else pack.reload
                    receipt.update(operation(root, OUTPUT, HEAD, binding))
                elif ACTION in {
                    "rock-collection",
                    "rock-collection-reload",
                    "rock-collection-render",
                }:
                    from scripts.ue import sa_calobra_pcg_rock_collection as collection

                    if ACTION == "rock-collection-render":
                        ACTIVE = collection.start_capture(
                            root, OUTPUT, HEAD, binding, finish
                        )
                        return
                    operation = (
                        collection.build
                        if ACTION == "rock-collection"
                        else collection.reload
                    )
                    receipt.update(operation(root, OUTPUT, HEAD, binding))
                elif ACTION == "material-reload":
                    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
                    actor = actors.spawn_actor_from_class(
                        unreal.StaticMeshActor, unreal.Vector()
                    )
                    actor.static_mesh_component.set_static_mesh(
                        unreal.load_asset(binding["derived_mesh"])
                    )
                    receipt["binding_readback"] = binding_helper.verify_binding(
                        binding, actor.static_mesh_component
                    )
                    receipt["status"] = "MATERIAL_BINDING_FRESH_READBACK"
                elif ACTION == "settle-render":
                    start_boulder_capture(root, binding, receipt)
                    return
                else:
                    from scripts.ue import sa_calobra_pcg_terrain_contact

                    receipt["contact_measurements"] = (
                        sa_calobra_pcg_terrain_contact.measure(root, binding)
                    )
                    receipt["status"] = "REAL_TERRAIN_CONTACT_MEASURED"
            finish(receipt)
            return
        if ACTION in {"create", "reload"}:
            unreal.EditorPythonScripting.set_keep_python_script_alive(True)
            ACTIVE = MechanicalGraph(receipt)
            ACTIVE.begin()
            return
        if ACTION != "inspect":
            raise RuntimeError("Unknown native diagnostic action")
        receipt.update(inspect())
    except Exception:
        receipt["error"] = traceback.format_exc()
        unreal.log_error(receipt["error"])
    finish(receipt)


def start_boulder_capture(root, binding, receipt):
    from scripts.ue import sa_calobra_pcg_boulder_settle as settle
    from scripts.ue import sa_calobra_pcg_boulder_capture as capture

    measured, world, actor, target = settle.prepare(root, binding)
    receipt["boulder_fit"] = measured
    radius = max(measured["actor_bounds_cm"]["extent"])
    captures = {}

    def move_to(location):
        actor.set_actor_location(unreal.Vector(*location), False, False)
        if vector(actor.get_actor_location()) != [float(v) for v in location]:
            raise RuntimeError("Boulder comparison transform readback differs")

    def complete_after(result):
        captures["after"] = result
        receipt["captures"] = captures
        if result.get("error") or result.get("status") != "CAPTURE_COMPLETED":
            receipt["error"] = "After capture failed: " + json.dumps(result)
        else:
            receipt["status"] = "BOULDER_FITTED_REAL_GPU_CAPTURED"
        finish(receipt)

    def complete_before(result):
        captures["before"] = result
        if result.get("error") or result.get("status") != "CAPTURE_COMPLETED":
            receipt["error"] = "Before capture failed: " + json.dumps(result)
            finish(receipt)
            return
        move_to(measured["after_location_cm"])
        global ACTIVE
        ACTIVE = capture.start_capture(
            world,
            unreal.Vector(*target),
            OUTPUT / "after",
            complete_after,
            framing_radius_cm=radius,
        )

    move_to(measured["before_location_cm"])
    global ACTIVE
    ACTIVE = capture.start_capture(
        world,
        unreal.Vector(*target),
        OUTPUT / "before",
        complete_before,
        framing_radius_cm=radius,
    )


def finish(receipt):
    if ACTION in CONTACT_ACTIONS | {
        "rock-qualify",
        "rock-reload",
        "rock-render",
        "rock-pack",
        "rock-pack-reload",
        "rock-collection",
        "rock-collection-reload",
        "rock-collection-render",
    }:
        # Installed AutomationBlueprintFunctionLibrary.cpp:702 flushes async
        # loading and finishes asset compilation. A receipt alone is insufficient
        # when the process later fails during teardown.
        unreal.AutomationLibrary.finish_loading_before_screenshot()
        receipt["asset_compilation_loading_barrier_completed"] = True
    write_new(ACTION + "-receipt.json", receipt)
    if ACTION in CONTACT_ACTIONS | {
        "material",
        "material-reload",
        "terrain",
        "settle-render",
        "mask-xy-create",
        "mask-xy-reload",
        "rock-qualify",
        "rock-reload",
        "rock-render",
        "rock-pack",
        "rock-pack-reload",
        "rock-collection",
        "rock-collection-reload",
        "rock-collection-render",
    }:
        # Let the startup-script stack unwind before editor teardown. This is
        # lifecycle sequencing, not a substitute for clean process completion.
        global QUIT_CALLBACK
        ticks = 0
        rock_action = ACTION in CONTACT_ACTIONS | {
            "rock-qualify",
            "rock-reload",
            "rock-render",
            "rock-pack",
            "rock-pack-reload",
            "rock-collection",
            "rock-collection-reload",
            "rock-collection-render",
        }
        quit_not_before = time.monotonic() + (5.0 if rock_action else 0.0)

        def quit_after_tick(delta):
            global QUIT_CALLBACK
            nonlocal ticks
            ticks += 1
            if ticks < (20 if rock_action else 2) or time.monotonic() < quit_not_before:
                return
            unreal.unregister_slate_post_tick_callback(QUIT_CALLBACK)
            QUIT_CALLBACK = None
            if rock_action:
                unreal.AutomationLibrary.finish_loading_before_screenshot()
            unreal.SystemLibrary.quit_editor()

        QUIT_CALLBACK = unreal.register_slate_post_tick_callback(quit_after_tick)
        return
    unreal.SystemLibrary.quit_editor()


def pin(node, field):
    pins = list(node.get_editor_property(field))
    if not pins:
        raise RuntimeError("Native graph pin missing: " + field)
    return pins[0].get_editor_property("properties").get_editor_property("label")


def transform_record(transform, seed):
    return {
        "position_cm": vector(transform.translation),
        "scale": vector(transform.scale3d),
        "seed": int(seed),
        "rotation_xyzw": [float(getattr(transform.rotation, axis)) for axis in "xyzw"],
    }


class MechanicalGraph:
    """Three synthetic points; independent of region eligibility and asset admission."""

    def __init__(self, receipt):
        self.receipt = receipt
        self.phase = "initial"
        self.completed = False
        self.cleaned = False
        self.cancelled = False
        self.runs = []
        self.start = time.monotonic()
        self.callback = None

    def begin(self):
        if ACTION == "create":
            schemas = {
                name: native_tool(
                    "/Script/PCGToolset.PCGToolset",
                    "GetNativeNodeSchema",
                    {"nodeName": name},
                )
                for name in ("Create Points", "Projection", "Static Mesh Spawner")
            }
            write_new("native-node-schemas.json", schemas)
            if unreal.EditorAssetLibrary.does_asset_exist(
                GRAPH_PATH
            ) or unreal.EditorAssetLibrary.does_asset_exist(MAP_PATH):
                raise RuntimeError("Preserve existing mechanical graph/map")
            if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).new_level(
                MAP_PATH, is_partitioned_world=False
            ):
                raise RuntimeError("Mechanical map creation failed")
            self.world = unreal.get_editor_subsystem(
                unreal.UnrealEditorSubsystem
            ).get_editor_world()
            self.graph = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
                "PCG_XYFixture", PACKAGE, unreal.PCGGraph, unreal.PCGGraphFactory()
            )
            node, settings = self.graph.add_node_of_type(unreal.PCGCreatePointsSettings)
            settings.set_editor_property(
                "coordinate_space", unreal.PCGCoordinateSpace.WORLD
            )
            settings.set_editor_property("cull_points_outside_volume", False)
            points = []
            for x, y, z, seed in FIXTURE_POINTS:
                point = unreal.PCGPoint()
                point.transform = unreal.Transform(location=unreal.Vector(x, y, z))
                point.seed = seed
                points.append(point)
            settings.set_editor_property("points_to_create", points)
            node.set_node_position(-250, 0)
            output = self.graph.get_output_node()
            if not self.graph.add_edge(
                node, pin(node, "output_pins"), output, pin(output, "input_pins")
            ):
                raise RuntimeError("Native point graph edge failed")
            actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
            volume = actors.spawn_actor_from_class(unreal.PCGVolume, unreal.Vector())
            volume.set_actor_label("PCG365_MechanicalPoints")
            self.component = volume.pcg_component
            self.component.set_editor_property(
                "generation_trigger",
                unreal.PCGComponentGenerationTrigger.GENERATE_ON_DEMAND,
            )
            self.component.seed = 36501
            self.component.set_graph(self.graph)
            self.create_ground(actors)
        else:
            if not unreal.EditorLoadingAndSavingUtils.load_map(MAP_PATH):
                raise RuntimeError("Fresh mechanical map load failed")
            self.world = unreal.get_editor_subsystem(
                unreal.UnrealEditorSubsystem
            ).get_editor_world()
            actors = unreal.get_editor_subsystem(
                unreal.EditorActorSubsystem
            ).get_all_level_actors()
            volumes = [
                actor
                for actor in actors
                if isinstance(actor, unreal.PCGVolume)
                and actor.get_actor_label() == "PCG365_MechanicalPoints"
            ]
            if len(volumes) != 1:
                raise RuntimeError("Saved graph actor inventory differs")
            self.component = volumes[0].pcg_component
            if (
                self.component.seed != 36501
                or self.component.generation_trigger
                != unreal.PCGComponentGenerationTrigger.GENERATE_ON_DEMAND
            ):
                raise RuntimeError("Saved component seed/trigger differs")
            self.graph = self.component.get_graph()
            if self.graph.get_path_name().split(".")[0] != GRAPH_PATH:
                raise RuntimeError("Saved graph identity differs")
            settings = [node.get_settings() for node in self.graph.nodes]
            if len(settings) != 1 or not isinstance(
                settings[0], unreal.PCGCreatePointsSettings
            ):
                raise RuntimeError("Saved graph node structure differs")
            stored = [
                transform_record(point.transform, point.seed)
                for point in settings[0].points_to_create
            ]
            expected = [
                transform_record(
                    unreal.Transform(location=unreal.Vector(x, y, z)), seed
                )
                for x, y, z, seed in FIXTURE_POINTS
            ]
            if (
                stored != expected
                or settings[0].coordinate_space != unreal.PCGCoordinateSpace.WORLD
                or settings[0].cull_points_outside_volume
            ):
                raise RuntimeError("Saved recipe differs before regeneration")
            self.receipt["saved_recipe_verified_before_explicit_generation"] = True
        self.component.on_pcg_graph_generated_external.add_callable(self.generated)
        self.component.on_pcg_graph_cancelled_external.add_callable(
            self.cancelled_event
        )
        self.component.on_pcg_graph_cleaned_external.add_callable(self.cleaned_event)
        self.phase = "generation1"
        self.callback = unreal.register_slate_post_tick_callback(self.tick)
        self.component.generate_local(True)

    def create_ground(self, actors):
        mesh = unreal.load_asset("/Engine/BasicShapes/Cube.Cube")
        for label, location, scale in (
            ("PCG365_AnalyticGround", (0, 0, -5), (10, 10, 0.1)),
            ("PCG365_UnrelatedCollider", (0, 0, 100), (0.2, 0.2, 0.2)),
        ):
            actor = actors.spawn_actor_from_class(
                unreal.StaticMeshActor, unreal.Vector(*location)
            )
            actor.set_actor_label(label)
            actor.static_mesh_component.set_static_mesh(mesh)
            actor.set_actor_scale3d(unreal.Vector(*scale))
            actor.static_mesh_component.set_collision_enabled(
                unreal.CollisionEnabled.QUERY_ONLY
            )
            actor.static_mesh_component.set_collision_response_to_all_channels(
                unreal.CollisionResponseType.ECR_BLOCK
            )

    def contact(self):
        actors = unreal.get_editor_subsystem(
            unreal.EditorActorSubsystem
        ).get_all_level_actors()
        ground = [
            actor
            for actor in actors
            if actor.get_actor_label() == "PCG365_AnalyticGround"
        ]
        if len(ground) != 1:
            raise RuntimeError("Ambiguous analytic fixture ground")
        ignore = [actor for actor in actors if actor != ground[0]]
        foreign = unreal.SystemLibrary.line_trace_single(
            self.world,
            unreal.Vector(0, 0, 300),
            unreal.Vector(0, 0, -100),
            unreal.TraceTypeQuery.ECC_VISIBILITY,
            False,
            [],
            unreal.DrawDebugTrace.NONE,
            True,
        )
        if (
            foreign is None
            or foreign.to_tuple()[9].get_actor_label() != "PCG365_UnrelatedCollider"
        ):
            raise RuntimeError("Unrelated-collider negative control is not effective")
        rows = []
        # Finite 3x3 support grid per cube; sampled fixture evidence only.
        for x, y, _, _ in FIXTURE_POINTS:
            for dx in (-50, 0, 50):
                for dy in (-50, 0, 50):
                    hit = unreal.SystemLibrary.line_trace_single(
                        self.world,
                        unreal.Vector(x + dx, y + dy, 300),
                        unreal.Vector(x + dx, y + dy, -100),
                        unreal.TraceTypeQuery.ECC_VISIBILITY,
                        False,
                        ignore,
                        unreal.DrawDebugTrace.NONE,
                        True,
                    )
                    values = () if hit is None else hit.to_tuple()
                    if (
                        len(values) != 18
                        or values[0] is not True
                        or values[1] is not False
                        or values[9] != ground[0]
                    ):
                        raise RuntimeError(
                            "Fixture trace missed or hit unauthorized owner"
                        )
                    if abs(float(values[4].z)) > 0.001:
                        raise RuntimeError("Analytic ground fixture is not Z=0")
                    rows.append(
                        {
                            "xy_cm": [x + dx, y + dy],
                            "hit_cm": vector(values[4]),
                            "owner": values[9].get_actor_label(),
                        }
                    )
        miss = unreal.SystemLibrary.line_trace_single(
            self.world,
            unreal.Vector(2000, 2000, 300),
            unreal.Vector(2000, 2000, -100),
            unreal.TraceTypeQuery.ECC_VISIBILITY,
            False,
            ignore,
            unreal.DrawDebugTrace.NONE,
            True,
        )
        if miss is not None:
            raise RuntimeError("Unsupported fixture did not reject")
        return {
            "status": "ANALYTIC_FIXTURE_SAMPLED_ONLY",
            "samples": rows,
            "unsupported_rejected": True,
            "unrelated_actor_excluded": True,
            "regional_terrain_admission": False,
            "fixture_numeric_epsilon_m": 0.00001,
        }

    def generated(self, component):
        if component != self.component:
            self.cancelled = True
        self.completed = True

    def cancelled_event(self, component):
        self.cancelled = True

    def cleaned_event(self, component):
        self.cleaned = component == self.component

    def snapshot(self):
        collection = self.component.get_generated_graph_output()
        rows = []
        for tagged in collection.tagged_data:
            fields = tagged.to_tuple()
            if len(fields) != 4:
                raise RuntimeError("Unexpected native tagged-data break shape")
            data = fields[0]
            if not isinstance(data, unreal.PCGBasePointData):
                raise RuntimeError("Native output is not point data")
            for index in range(data.get_num_points()):
                rows.append(
                    transform_record(data.get_transform(index), data.get_seed(index))
                )
        rows.sort(key=lambda row: row["seed"])
        expected = [
            transform_record(unreal.Transform(location=unreal.Vector(x, y, z)), seed)
            for x, y, z, seed in FIXTURE_POINTS
        ]
        if rows != expected:
            raise RuntimeError(
                "Native point transforms/seeds differ from mechanical recipe"
            )
        return rows

    def tick(self, delta):
        try:
            if self.cancelled or time.monotonic() - self.start > 120:
                raise RuntimeError("Native generation cancelled or deadline exceeded")
            if self.phase.startswith("generation") and self.completed:
                self.runs.append(self.snapshot())
                self.completed = False
                if len(self.runs) == 1:
                    self.phase = "cleanup"
                    self.component.cleanup_local(True)
                else:
                    if self.runs[0] != self.runs[1]:
                        raise RuntimeError("Native regeneration differs")
                    self.receipt["fixture_contact"] = self.contact()
                    self.receipt["runs"] = self.runs
                    if ACTION == "create":
                        if not unreal.EditorAssetLibrary.save_loaded_asset(
                            self.graph, only_if_is_dirty=False
                        ):
                            raise RuntimeError("Mechanical graph save failed")
                        if not unreal.EditorLoadingAndSavingUtils.save_map(
                            self.world, MAP_PATH
                        ):
                            raise RuntimeError("Mechanical map save failed")
                        root = Path(unreal.Paths.project_dir())
                        files = []
                        for package, suffix in (
                            (GRAPH_PATH, ".uasset"),
                            (MAP_PATH, ".umap"),
                        ):
                            relative = (
                                "Content/" + package.removeprefix("/Game/") + suffix
                            )
                            data = (root / relative).read_bytes()
                            files.append(
                                {
                                    "path": relative,
                                    "bytes": len(data),
                                    "sha256": hashlib.sha256(data).hexdigest(),
                                }
                            )
                        write_new(
                            "saved-packages.json", {"code_sha": HEAD, "files": files}
                        )
                    self.receipt["status"] = (
                        "MECHANICAL_GRAPH_SAVED"
                        if ACTION == "create"
                        else "MECHANICAL_GRAPH_FRESH_RELOAD_REGENERATED"
                    )
                    self.stop()
            elif self.phase == "cleanup" and self.cleaned:
                self.phase = "generation2"
                self.component.generate_local(True)
        except Exception:
            self.receipt["status"] = "FAILED"
            self.receipt["error"] = traceback.format_exc()
            unreal.log_error(self.receipt["error"])
            self.stop()

    def stop(self):
        if self.callback is not None:
            unreal.unregister_slate_post_tick_callback(self.callback)
            self.callback = None
        finish(self.receipt)


main()
