"""Admission, runtime-only targeting and orderly lifecycle checks; no Unreal."""
import copy
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from scripts.ue import verify_lesson07_runtime_collision as verify


def world(path):
    return SimpleNamespace(get_path_name=lambda: path)


def inputs():
    planned, measured = [], []
    for index in range(15):
        actor = sorted(verify.ACTORS)[index % 4]
        component = verify.WORLD_PATH + ":PersistentLevel." + actor + ".LandscapeComponent_1"
        validity = int(index >= 3)
        planned.append({"id": str(index), "actor": actor, "component_path": component,
                        "source_validity": validity, "uniform_source_patch_samples": 64,
                        "local_vertex_indices": [0, 1, 255, 256]})
        measured.append({"id": str(index), "actor": actor, "component_path": component, "observed": True,
                         "native_corners": {"visibility_status": "ALLOCATED_READ",
                                            "vertex_indices": [0, 1, 255, 256],
                                            "samples": [[32768, 0, 0, 0, 255*(1-validity)]] * 4},
                         "center_collision": {"query_xy_cm": [0, 0], "hit": True}})
    return {"probes": planned}, {"probes": measured}


class AdmissionTests(unittest.TestCase):
    def test_runtime_world_must_be_a_distinct_exact_pie_copy(self):
        editor = world(verify.WORLD_PATH)
        pie_path = verify.WORLD_PATH.replace("/L_SaCalobra", "/UEDPIE_0_L_SaCalobra")
        self.assertEqual(verify.validate_runtime_world(world(pie_path), editor, True), pie_path)
        for candidate, active in ((editor, True), (None, True), (world(pie_path), False),
                                  (world(pie_path.replace("Lesson07", "Lesson06")), True)):
            with self.subTest(candidate=candidate, active=active), self.assertRaises(RuntimeError):
                verify.validate_runtime_world(candidate, editor, active)

    def test_queries_reuse_authenticated_native_centers_and_source_classes(self):
        plan, native = inputs()
        rows = verify.bind_queries(plan, native)
        self.assertEqual(len(rows), 15)
        self.assertEqual(sum(not r["source_validity"] for r in rows), 3)
        for mutation in ("xy", "visibility", "actor", "duplicate"):
            changed = copy.deepcopy(native)
            if mutation == "xy":
                changed["probes"][0]["center_collision"]["query_xy_cm"] = [1, 0]
            elif mutation == "visibility":
                changed["probes"][0]["native_corners"]["samples"][0][4] = 0
            elif mutation == "actor":
                changed["probes"][0]["actor"] = "Other"
            else:
                changed["probes"][1]["id"] = "0"
            with self.subTest(mutation=mutation), self.assertRaises(RuntimeError):
                verify.bind_queries(plan, changed)

    def test_unallocated_valid_control_remains_null_not_a_visibility_measurement(self):
        plan, native = inputs()
        corner = native["probes"][3]["native_corners"]
        corner["visibility_status"] = "NOT_ALLOCATED"
        corner["samples"] = [[32768, 0, 0, 0, None]] * 4
        result = verify.bind_queries(plan, native)
        self.assertEqual(result[3]["native_visibility_weights"], [None]*4)
        native["probes"][0]["native_corners"] = copy.deepcopy(corner)
        with self.assertRaisesRegex(RuntimeError, "conflicts"):
            verify.bind_queries(plan, native)


class TraceTests(unittest.TestCase):
    def test_runtime_holes_and_controls_are_compared_without_reinterpreting_hits(self):
        actor, render = Mock(), Mock()
        collision = Mock()
        collision.is_query_collision_enabled.return_value = True
        collision.get_owner.return_value = actor
        collision.get_render_component.return_value = render
        collision.get_path_name.return_value = "runtime_collision"
        render.get_path_name.return_value = "runtime_render"
        name = sorted(verify.ACTORS)[0]
        targets = {name: (actor, {"component": render}, {"component": collision})}
        for validity, hit in ((0, False), (0, True), (1, True), (1, False)):
            native = {"blocking_hit": hit, "hit_actor": actor, "hit_component": collision,
                      "impact_point": SimpleNamespace(x=1, y=2, z=3)}
            trace = Mock(return_value=SimpleNamespace(to_dict=lambda: native))
            api = SimpleNamespace(
                SystemLibrary=SimpleNamespace(line_trace_single=trace), Vector=lambda *values: values,
                TraceTypeQuery=SimpleNamespace(TRACE_TYPE_QUERY1=1), DrawDebugTrace=SimpleNamespace(NONE=0))
            probe = {"actor": name, "component_path": "component", "query_xy_cm": [1, 2],
                     "source_validity": validity}
            with self.subTest(validity=validity, hit=hit):
                result = verify.runtime_trace(api, object(), targets, probe)
                self.assertEqual(result["matches_source_class"], hit == bool(validity))
                self.assertEqual(result["hit"], hit)
                self.assertIs(trace.call_args.args[4], True)
        collision.get_owner.return_value = Mock()
        native["blocking_hit"] = True
        with self.assertRaisesRegex(RuntimeError, "another actor"):
            verify.runtime_trace(api, object(), targets, probe)


class LifecycleTests(unittest.TestCase):
    def test_end_play_completes_before_success_or_trace_error_returns(self):
        for fails in (False, True):
            with self.subTest(fails=fails):
                events = []
                editor_world = world(verify.WORLD_PATH)
                game_world = world(verify.WORLD_PATH.replace("/L_SaCalobra", "/UEDPIE_0_L_SaCalobra"))
                state = {"world": None, "playing": False}

                def start():
                    events.append("start")
                    state.update(world=game_world, playing=True)

                def stop():
                    events.append("stop_requested")
                    # Model an asynchronous end: the world remains until the next engine tick.

                level = SimpleNamespace(is_in_play_in_editor=lambda: state["playing"],
                                        editor_play_simulate=start, editor_request_end_play=stop)
                editor = SimpleNamespace(get_game_world=lambda: state["world"])
                api = SimpleNamespace(
                    LevelEditorSubsystem=1, UnrealEditorSubsystem=2,
                    get_editor_subsystem=lambda kind: level if kind == 1 else editor, log=lambda _: None,
                    GameplayStatics=SimpleNamespace(get_time_seconds=lambda _: 1.0),
                    EditorLoadingAndSavingUtils=SimpleNamespace(
                        get_dirty_map_packages=lambda: [], get_dirty_content_packages=lambda: [],
                        load_map=lambda _: editor_world))
                readback = ({"source_head": verify.SOURCE_HEAD}, [{}], {}, {})
                trace = Mock(side_effect=RuntimeError("trace failure")) if fails else Mock(
                    return_value={"matches_source_class": True})
                with patch.object(verify, "read_inputs", return_value=readback), \
                        patch.object(verify, "runtime_targets", return_value={}), \
                        patch.object(verify, "runtime_trace", trace):
                    result = {}
                    operation = verify.run(api, Path("."), result, float("inf"))
                    next(operation)
                    self.assertEqual(events, ["start"])
                    next(operation)
                    self.assertEqual(events, ["start", "stop_requested"])
                    self.assertNotIn("simulation_stopped", result)
                    next(operation)
                    state.update(world=None, playing=False)
                    if fails:
                        with self.assertRaisesRegex(RuntimeError, "trace failure"):
                            next(operation)
                    else:
                        with self.assertRaises(StopIteration):
                            next(operation)
                    self.assertTrue(result["simulation_stopped"])

    def test_existing_play_session_is_never_stopped(self):
        level = SimpleNamespace(is_in_play_in_editor=lambda: True, editor_request_end_play=Mock())
        api = SimpleNamespace(LevelEditorSubsystem=1, UnrealEditorSubsystem=2,
                              get_editor_subsystem=lambda _: level)
        with self.assertRaisesRegex(RuntimeError, "preserved"):
            next(verify.run(api, Path("."), {}, float("inf")))
        level.editor_request_end_play.assert_not_called()


if __name__ == "__main__":
    unittest.main()
