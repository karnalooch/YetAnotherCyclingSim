"""Bounded mask-derived XY carriers in native PCG; no mesh or terrain admission."""

import hashlib
import json
from pathlib import Path
import re
import time
import traceback

import unreal


PACKAGE = "/Game/Generated/YACS/PCG365MaskXYDiagnostic"
GRAPH = PACKAGE + "/PCG_MaskXY"
MAP = PACKAGE + "/L_MaskXY"
FILES = (
    "Content" + GRAPH.removeprefix("/Game") + ".uasset",
    "Content" + MAP.removeprefix("/Game") + ".umap",
)
_ACTIVE = []


def require(value, message):
    if not value:
        raise RuntimeError(message)


def read_request(root):
    raw = (root / "mask-xy-request.json").read_bytes()
    request = json.loads(raw)
    require(
        request.get("placement") is False and request.get("qualified_assets") == [],
        "XY request must not qualify or place assets",
    )
    require(
        request.get("status") == "MASK_DERIVED_XY_GRAPH_REQUEST_ONLY",
        "Unexpected XY request status",
    )
    require(
        type(request.get("schema_version")) is int and request["schema_version"] == 1,
        "Unsupported XY request schema",
    )
    require(
        type(request.get("z_carrier_cm")) is int
        and request["z_carrier_cm"] == 0
        and request.get("z_semantics")
        == "DIAGNOSTIC_CARRIER_ONLY_NOT_SOURCE_OR_GROUND_HEIGHT",
        "XY Z carrier semantics differ",
    )
    require(
        request.get("terrain_contact") == "REQUIRED_UNSET"
        and request.get("native_consumption")
        == "CPU_AUTHENTICATED_POINTS_NOT_NATIVE_RASTER_SAMPLING",
        "XY request overstates native or terrain qualification",
    )
    bindings = request.get("source_bindings")
    require(isinstance(bindings, dict), "Missing source bindings")
    for key in ("candidate_sha256", "candidate_fingerprint", "producer_sha256_lf"):
        require(
            isinstance(bindings.get(key), str)
            and re.fullmatch("[0-9a-f]{64}", bindings[key]),
            "Invalid source binding: " + key,
        )
    require(
        isinstance(bindings.get("authenticated_inputs"), dict)
        and bool(bindings["authenticated_inputs"]),
        "Missing authenticated input receipt",
    )
    points = request.get("points")
    require(
        isinstance(points, list) and 1 <= len(points) <= 16, "Expected 1..16 XY points"
    )
    seed = request.get("recipe_seed")
    require(
        type(seed) is int and 0 <= seed <= 0x7FFFFFFF, "Invalid fixed component seed"
    )
    identities, seeds, cells = set(), set(), set()
    for point in points:
        require(isinstance(point, dict), "Invalid point record")
        require(
            not any("mesh" in key.lower() or "asset" in key.lower() for key in point),
            "Mesh or asset payload forbidden",
        )
        identity = point.get("candidate_id")
        require(
            isinstance(identity, str) and re.fullmatch("[0-9a-f]{64}", identity),
            "Invalid stable ID",
        )
        cell, xy, point_seed = (
            point.get("source_cell"),
            point.get("world_xy_cm"),
            point.get("point_seed"),
        )
        require(
            isinstance(cell, list)
            and len(cell) == 2
            and all(type(v) is int and v >= 0 for v in cell),
            "Invalid source cell",
        )
        require(
            isinstance(xy, list)
            and len(xy) == 2
            and all(type(v) is int for v in xy)
            and xy == [cell[1] * 50, cell[0] * 50],
            "XY does not match 50cm source grid",
        )
        require(
            type(point_seed) is int and 0 < point_seed <= 0x7FFFFFFF,
            "Invalid point seed",
        )
        require(
            type(point.get("band")) is int and point["band"] in (0, 1, 2),
            "Invalid source band",
        )
        require(
            identity not in identities
            and point_seed not in seeds
            and tuple(cell) not in cells,
            "Duplicate XY ID, seed or source cell",
        )
        identities.add(identity)
        seeds.add(point_seed)
        cells.add(tuple(cell))
    return request, hashlib.sha256(raw).hexdigest()


def record(transform, seed):
    return {
        "position_cm": [float(getattr(transform.translation, a)) for a in "xyz"],
        "scale": [float(getattr(transform.scale3d, a)) for a in "xyz"],
        "rotation_xyzw": [float(getattr(transform.rotation, a)) for a in "xyzw"],
        "seed": int(seed),
    }


def pin(node, field):
    pins = list(node.get_editor_property(field))
    require(len(pins) == 1, "Unexpected native pin inventory")
    return pins[0].get_editor_property("properties").get_editor_property("label")


class MaskXYGraph:
    def __init__(self, root, output, head, action, done):
        self.root, self.output = Path(root).resolve(), Path(output).resolve()
        require(
            self.root == Path(unreal.Paths.project_dir()).resolve(),
            "Wrong diagnostic project root",
        )
        require(
            self.output.is_relative_to(self.root) and self.output != self.root,
            "Unsafe output directory",
        )
        require(
            action in {"mask-xy-create", "mask-xy-reload"}, "Unknown mask XY action"
        )
        require(re.fullmatch("[0-9a-f]{40}", head), "Invalid exact source HEAD")
        self.request, self.request_sha = read_request(self.root)
        self.head, self.action, self.done = head, action, done
        self.report = {
            "schema_version": 1,
            "code_sha": head,
            "action": action,
            "status": "FAILED",
            "placement": False,
            "qualified_assets": [],
            "terrain_contact": "NOT_RUN",
            "proof_admission": "LOCAL_DIAGNOSTIC_ONLY",
            "native_build": "NOT_RUN_PREBUILT_DEPENDENCY",
            "performance_pass": False,
            "request_sha256": self.request_sha,
            "z_policy": "zero carrier only; not surface placement",
            "runs": [],
        }
        self.points_by_seed = {p["point_seed"]: p for p in self.request["points"]}
        self.expected = sorted(
            [
                record(
                    unreal.Transform(location=unreal.Vector(*p["world_xy_cm"], 0)),
                    p["point_seed"],
                )
                for p in self.request["points"]
            ],
            key=lambda p: p["seed"],
        )
        self.phase, self.completed, self.cleaned, self.cancelled = (
            "initial",
            False,
            False,
            False,
        )
        self.callback, self.stopped = None, False
        self.started = time.monotonic()

    def inventory(self):
        rows = []
        for relative in FILES:
            raw = (self.root / relative).read_bytes()
            require(bool(raw), "Empty saved native package")
            rows.append(
                {
                    "path": relative,
                    "bytes": len(raw),
                    "sha256": hashlib.sha256(raw).hexdigest(),
                }
            )
        return rows

    def begin(self):
        try:
            if self.action == "mask-xy-create":
                require(
                    not unreal.EditorAssetLibrary.does_asset_exist(GRAPH)
                    and not unreal.EditorAssetLibrary.does_asset_exist(MAP),
                    "Preserve existing diagnostic packages",
                )
                require(
                    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).new_level(
                        MAP, is_partitioned_world=False
                    ),
                    "Mask XY map creation failed",
                )
                self.graph = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
                    "PCG_MaskXY", PACKAGE, unreal.PCGGraph, unreal.PCGGraphFactory()
                )
                require(self.graph is not None, "Mask XY graph creation failed")
                node, settings = self.graph.add_node_of_type(
                    unreal.PCGCreatePointsSettings
                )
                settings.set_editor_property(
                    "coordinate_space", unreal.PCGCoordinateSpace.WORLD
                )
                settings.set_editor_property("cull_points_outside_volume", False)
                points = []
                for point_request in self.request["points"]:
                    point = unreal.PCGPoint()
                    point.transform = unreal.Transform(
                        location=unreal.Vector(*point_request["world_xy_cm"], 0)
                    )
                    point.seed = point_request["point_seed"]
                    points.append(point)
                settings.set_editor_property("points_to_create", points)
                node.set_node_position(-250, 0)
                output = self.graph.get_output_node()
                require(
                    self.graph.add_edge(
                        node,
                        pin(node, "output_pins"),
                        output,
                        pin(output, "input_pins"),
                    ),
                    "Mask XY edge creation failed",
                )
                actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
                volume = actors.spawn_actor_from_class(
                    unreal.PCGVolume, unreal.Vector()
                )
                require(volume is not None, "Mask XY PCG volume creation failed")
                volume.set_actor_label("PCG365_MaskXY")
                self.component = volume.pcg_component
                self.component.set_editor_property(
                    "generation_trigger",
                    unreal.PCGComponentGenerationTrigger.GENERATE_ON_DEMAND,
                )
                self.component.seed = self.request["recipe_seed"]
                self.component.set_graph(self.graph)
            else:
                marker = json.loads(
                    (self.root / "proof/mask-xy-create/saved-packages.json").read_text(
                        encoding="utf-8"
                    )
                )
                require(
                    marker.get("code_sha") == self.head
                    and marker.get("request_sha256") == self.request_sha,
                    "Saved metadata does not match HEAD/request",
                )
                self.saved_inventory = self.inventory()
                require(
                    marker.get("files") == self.saved_inventory,
                    "Saved package bytes differ",
                )
                require(
                    unreal.EditorLoadingAndSavingUtils.load_map(MAP),
                    "Mask XY map reload failed",
                )
                actors = unreal.get_editor_subsystem(
                    unreal.EditorActorSubsystem
                ).get_all_level_actors()
                volumes = [a for a in actors if isinstance(a, unreal.PCGVolume)]
                require(
                    len(volumes) == 1
                    and volumes[0].get_actor_label() == "PCG365_MaskXY",
                    "Unexpected saved PCG volume inventory",
                )
                require(
                    not any(
                        isinstance(a, unreal.StaticMeshActor)
                        or isinstance(a, unreal.LandscapeProxy)
                        for a in actors
                    ),
                    "Unexpected mesh or terrain actor",
                )
                self.component = volumes[0].pcg_component
                self.graph = self.component.get_graph()
            require(
                self.component.seed == self.request["recipe_seed"]
                and self.component.generation_trigger
                == unreal.PCGComponentGenerationTrigger.GENERATE_ON_DEMAND,
                "Component seed/trigger differs",
            )
            require(
                self.graph.get_path_name().split(".")[0] == GRAPH,
                "Graph package differs",
            )
            settings = [node.get_settings() for node in self.graph.nodes]
            require(
                len(settings) == 1
                and isinstance(settings[0], unreal.PCGCreatePointsSettings),
                "Unexpected node settings",
            )
            stored = sorted(
                [record(p.transform, p.seed) for p in settings[0].points_to_create],
                key=lambda p: p["seed"],
            )
            require(
                stored == self.expected
                and settings[0].coordinate_space == unreal.PCGCoordinateSpace.WORLD
                and settings[0].cull_points_outside_volume is False,
                "Stored XY recipe differs",
            )
            self.report["saved_recipe_verified_before_explicit_generation"] = (
                self.action == "mask-xy-reload"
            )
            self.world = unreal.get_editor_subsystem(
                unreal.UnrealEditorSubsystem
            ).get_editor_world()
            self.component.on_pcg_graph_generated_external.add_callable(self.generated)
            self.component.on_pcg_graph_cancelled_external.add_callable(
                self.cancelled_event
            )
            self.component.on_pcg_graph_cleaned_external.add_callable(
                self.cleaned_event
            )
            self.phase = "generation1"
            self.callback = unreal.register_slate_post_tick_callback(self.tick)
            self.component.generate_local(True)
        except Exception:
            self.fail()
        return self

    def generated(self, component):
        self.cancelled = self.cancelled or component != self.component
        self.completed = True

    def cancelled_event(self, component):
        self.cancelled = True

    def cleaned_event(self, component):
        self.cancelled = self.cancelled or component != self.component
        self.cleaned = component == self.component

    def snapshot(self):
        rows = []
        for tagged in self.component.get_generated_graph_output().tagged_data:
            fields = tagged.to_tuple()
            require(
                len(fields) == 4 and isinstance(fields[0], unreal.PCGBasePointData),
                "Unexpected PCG output",
            )
            data = fields[0]
            for index in range(data.get_num_points()):
                rows.append(record(data.get_transform(index), data.get_seed(index)))
        rows.sort(key=lambda p: p["seed"])
        require(rows == self.expected, "Native XY transforms/seeds differ from request")
        return [
            dict(
                row,
                candidate_id=self.points_by_seed[row["seed"]]["candidate_id"],
                source_cell=self.points_by_seed[row["seed"]]["source_cell"],
            )
            for row in rows
        ]

    def tick(self, delta):
        if self.stopped:
            return
        try:
            require(
                not self.cancelled and time.monotonic() - self.started <= 120,
                "Mask XY cancelled or deadline exceeded",
            )
            if self.phase.startswith("generation") and self.completed:
                self.completed = False
                self.report["runs"].append(self.snapshot())
                if len(self.report["runs"]) == 1:
                    self.phase = "cleanup"
                    self.component.cleanup_local(True)
                else:
                    require(
                        self.report["runs"][0] == self.report["runs"][1],
                        "XY regeneration differs",
                    )
                    if self.action == "mask-xy-create":
                        require(
                            unreal.EditorAssetLibrary.save_loaded_asset(
                                self.graph, only_if_is_dirty=False
                            ),
                            "Mask XY graph save failed",
                        )
                        require(
                            unreal.EditorLoadingAndSavingUtils.save_map(
                                self.world, MAP
                            ),
                            "Mask XY map save failed",
                        )
                        marker = {
                            "code_sha": self.head,
                            "request_sha256": self.request_sha,
                            "files": self.inventory(),
                        }
                        path = self.output / "saved-packages.json"
                        with path.open("x", encoding="utf-8") as stream:
                            json.dump(marker, stream, indent=2, allow_nan=False)
                    else:
                        require(
                            self.inventory() == self.saved_inventory,
                            "Reload/regeneration changed saved package bytes",
                        )
                    self.report["status"] = (
                        "MASK_XY_GRAPH_SAVED"
                        if self.action == "mask-xy-create"
                        else "MASK_XY_GRAPH_FRESH_RELOAD_REGENERATED"
                    )
                    self.stop()
            elif self.phase == "cleanup" and self.cleaned:
                output = self.component.get_generated_graph_output()
                require(
                    not output.tagged_data,
                    "PCG output remains after cleanup",
                )
                self.report["cleanup_output_empty"] = True
                self.report["identity_linkage"] = (
                    "request sidecar joined by verified unique native seed; "
                    "not native metadata propagation"
                )
                self.phase = "generation2"
                self.component.generate_local(True)
        except Exception:
            self.fail()

    def fail(self):
        self.report["status"] = "FAILED"
        self.report["error"] = traceback.format_exc()
        self.stop()

    def stop(self):
        if self.stopped:
            return
        self.stopped = True
        try:
            if self.callback is not None:
                unreal.unregister_slate_post_tick_callback(self.callback)
                self.callback = None
        except Exception:
            self.report.update(status="FAILED", error=traceback.format_exc())
        if self in _ACTIVE:
            _ACTIVE.remove(self)
        self.done(self.report)


def start(root, output, head, action, done):
    """Keep Slate ticking; parent callback writes receipt and owns process shutdown."""
    try:
        operation = MaskXYGraph(root, output, head, action, done)
    except Exception:
        done(
            {
                "status": "FAILED",
                "error": traceback.format_exc(),
                "placement": False,
                "qualified_assets": [],
                "proof_admission": "LOCAL_DIAGNOSTIC_ONLY",
            }
        )
        return None
    _ACTIVE.append(operation)
    return operation.begin()
