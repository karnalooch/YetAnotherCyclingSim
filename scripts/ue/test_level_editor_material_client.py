"""Synthetic host/HTTP fixtures for the owned material preview client.

No test launches Unreal, a server, Git, PowerShell or a host workflow. Successful
fixtures exercise the real path/context/history/readback controller, replacing
only immutable Git acquisition, Windows observation and the HTTP peer. They
are not native proof, browser reception or owner visual acceptance.
"""

from __future__ import annotations

import copy
import struct
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest import mock

from scripts.ue import level_editor_material_client as client

LAUNCHER_SHA = "a" * 40
START_TIME = "134050000000000000"


def write(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)


def document(path, value):
    write(path, client.canonical(value) + b"\n")


def float32(value):
    return struct.unpack("f", struct.pack("f", value))[0]


def png():
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    header = struct.pack(">IIBBBBB", 1280, 720, 8, 2, 0, 0, 0)
    pixels = (b"\x00" + b"\x35\x45\x55" * 1280) * 720
    # Explicit fixture marker and padding preserve the same >4 KiB bound as
    # native captures. This is a valid PNG, with no claim about scene pixels.
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header)
            + chunk(b"tEXt", b"Fixture\0SYNTHETIC NOT UNREAL " + b"x" * 8192)
            + chunk(b"IDAT", zlib.compress(pixels)) + chunk(b"IEND", b""))


PNG = png()


def original_state():
    prefix = client.preparation.MAP_PACKAGE + ".SyntheticWorld:PersistentLevel."
    rows = [{"actor": prefix + f"Paint{i}", "component": prefix + f"Paint{i}.Component",
             "slot": 0, "material": client.bridge.PAINT_MATERIAL,
             "original_material": client.bridge.PAINT_MATERIAL} for i in range(370)]
    return {"paint_roughness": float32(0.90), "paint_color": [float32(v) for v in [0.64, 0.63, 0.59, 1.0]],
            "binding_count": 370, "binding_sha256": client.digest(client.canonical(rows)), "bindings": rows,
            "bound_material": client.bridge.PAINT_MATERIAL, "parent_material": client.bridge.PAINT_MASTER,
            "transient_mid": False}


class Fixture:
    def __init__(self, base):
        self.base = base
        self.review_root = base / "review"
        self.source_root = base / "retained-source"
        self.session_id = "synthetic-1"
        self.launcher_root = self.source_root.parent / ("_level-editor-review-" + self.session_id)
        self.root = self.review_root / (client.preparation.RUNTIME_SHA[:12] + "-" + self.session_id)
        self.host_path = self.root / client.SESSION_RECEIPT
        self.initial = original_state()
        self.state = copy.deepcopy(self.initial)
        self.sequence, self.calls, self.transports, self.closes = 0, 0, 0, 0
        self.defer = False
        self.response_edit = self.final_edit = None
        self.call_error = None
        self.tool_extra = None
        self.identity = {"session_id": self.session_id, "editor_pid": 8765,
                         "editor_start_filetime_utc": START_TIME, "project_root": str(self.root),
                         "map_package": client.preparation.MAP_PACKAGE,
                         "runtime_source_sha": client.preparation.RUNTIME_SHA, "launcher_sha": LAUNCHER_SHA,
                         "launcher_root": str(self.launcher_root)}
        # Synthetic native identity, not a claim about the real package root.
        class_name = "YacsRoadMaterialPreview_0xA1B2C3D4"
        self.toolset_identity = {"class_name": class_name, "outer_name": "/Engine/PythonTypes",
                                 "class_path": "/Engine/PythonTypes." + class_name,
                                 "toolset_name": "PythonTypes." + class_name}
        self.tool = {"name": self.toolset_identity["toolset_name"] + ".preview", "description": "Synthetic fixture",
                     "inputSchema": {"type": "object", "properties": {"request_json": {"type": "string"}},
                                     "required": ["request_json"]}}
        self.sources = {relative: client.digest((client.ROOT / relative).read_bytes())
                        for relative in (*client.SOURCE_MODULES, client.CLIENT_SOURCE)}
        rows = [{"path": f"Content/Synthetic/Input{i}.uasset", "source_path": str(self.source_root / f"Content/Synthetic/Input{i}.uasset"),
                 "sha256": client.digest(f"SYNTHETIC {i}".encode()), "size_bytes": 12} for i in range(272)]
        for relative, pair in client.preparation.PINNED_PROJECT_FILES.items():
            path = self.launcher_root / relative
            write(path, (client.ROOT / relative).read_bytes())
            rows.append({"path": relative, "source_path": str(path), "sha256": pair[0], "size_bytes": pair[1]})
        self.saved_digest = client.digest(client.canonical([
            {key: row[key] for key in ("path", "sha256", "size_bytes")} for row in rows]))
        self.source_digest = client.digest(client.canonical([
            {"path": row["source_path"], "sha256": row["sha256"], "size_bytes": row["size_bytes"]} for row in rows]))
        self.ready = {"schema_version": 1, "status": "MATERIAL_BRIDGE_READY", **self.identity,
                      "sequence": 0, "endpoint": client.ENDPOINT, "tool_schema": self.tool,
                      "toolset_identity": self.toolset_identity,
                      "wire_parameter": "request_json", "initial_state": self.initial,
                      "source_world_saved": False, "performance_pass": False,
                      "owner_visual_status": "PENDING_FINAL_M3", "saved_inputs_sha256": self.saved_digest,
                      "source_inputs_sha256": self.source_digest,
                      "bridge_source_sha256": self.sources["scripts/ue/level_editor_material_bridge.py"]}
        document(self.root / client.bridge.READY_RELATIVE, self.ready)
        self.host = {"schema_version": 1, "status": "MATERIAL_BRIDGE_QUALIFICATION_PENDING",
                     "owner_handoff": False, "source_world_saved": False,
                     "runtime_source_sha": client.preparation.RUNTIME_SHA, "launcher_sha": LAUNCHER_SHA,
                     "launcher_root": str(self.launcher_root),
                     "session_id": self.session_id, "session_root": str(self.root), "stream_source": "LevelEditorViewport",
                     "editor_pid": 8765, "editor_start_filetime_utc": START_TIME,
                     "editor_start_time_utc": "2026-10-11T10:00:00.0000000Z",
                     "editor_executable_path": r"D:\yacs\engine\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe",
                     "material_bridge_ready_sha256": client.digest((self.root / client.bridge.READY_RELATIVE).read_bytes())}
        document(self.host_path, self.host)
        document(self.root / client.preparation.RECEIPT_NAME, {
            "status": "READY_FOR_EDITOR_LAUNCH", "runtime_source_sha": client.preparation.RUNTIME_SHA,
            "launcher_sha": LAUNCHER_SHA, "snapshot_files": rows, "synthetic": False,
            "snapshot_root": str(self.root), "runtime_source_root": str(self.source_root),
            "map_package": client.preparation.MAP_PACKAGE, "map_sha256": client.preparation.MAP_SHA256})
        self.process = {key: self.host[key] for key in ("editor_pid", "editor_start_filetime_utc", "editor_executable_path")}
        self.process["listeners"] = [{"address": "127.0.0.1", "port": 18784, "pid": 8765}]
        self.process["command_line"] = (f'"{self.host["editor_executable_path"]}" '
                                        f'"{self.root / "YetAnotherCyclingSim.uproject"}" '
                                        f'{client.preparation.MAP_PACKAGE} -RenderOffscreen')

    def request(self, name="one", action="set", sequence=None, **changes):
        result = {"schema_version": 1, "session_id": self.session_id, "request_id": name,
                  "action": action, "expected_sequence": self.sequence if sequence is None else sequence}
        if action == "set":
            result.update({"paint_roughness": 0.35, "paint_color": [0.35, 0.50, 0.70, 1.0]})
        result.update(changes)
        return result

    def execute(self, request, output_name=None):
        name = output_name or request["request_id"]
        request_path = self.base / (name + "-request.json")
        document(request_path, request)
        return client.run(self.host_path, request_path, self.base / (name + "-output"))

    def transport(self):
        fixture = self
        self.transports += 1

        class Peer:
            def initialize(self):
                pass

            def _post(self, method, params):
                assert method == "tools/list" and params == {}
                tools = [copy.deepcopy(fixture.tool)]
                if fixture.tool_extra is not None:
                    tools.append(fixture.tool_extra)
                return {"result": {"tools": tools}}

            def call(self, name, arguments):
                assert name == fixture.tool["name"] and set(arguments) == {"request_json"}
                return fixture.native(client._object(arguments["request_json"]))

            def close(self):
                fixture.closes += 1

        return Peer()

    def native(self, request):
        self.calls += 1
        if self.call_error is not None:
            raise self.call_error
        assert request["expected_sequence"] == self.sequence
        before = copy.deepcopy(self.state)
        if request["action"] == "restore":
            self.state = copy.deepcopy(self.initial)
        elif request["action"] == "set":
            self.state["transient_mid"] = True
            self.state["bound_material"] = "/Engine/Transient.SyntheticPreviewMID"
            self.state["parent_material"] = client.bridge.PAINT_MATERIAL
            self.state["paint_roughness"] = float32(request["paint_roughness"])
            self.state["paint_color"] = [float32(value) for value in request["paint_color"]]
            for row in self.state["bindings"]:
                row["material"] = self.state["bound_material"]
            self.state["binding_sha256"] = client.digest(client.canonical(self.state["bindings"]))
        if request["action"] != "inspect":
            self.sequence += 1
        relative = client.bridge.REQUEST_ROOT + "/" + request["request_id"]
        directory = self.root / relative
        directory.mkdir(parents=True)
        final = {"schema_version": 1, **self.identity, "request_id": request["request_id"], "action": request["action"],
                 "sequence": self.sequence, "before": before, "after": copy.deepcopy(self.state),
                 "receipt_relative_path": relative + "/receipt.json", "source_world_saved": False,
                 "performance_pass": False, "owner_visual_status": "PENDING_FINAL_M3", "status": "COMPLETED",
                 "capture_pending": False, "captures": [], "dirty_before": {"map": [], "content": []},
                 "dirty_after": {"map": [], "content": []}, "saved_inputs_before_sha256": self.saved_digest,
                 "saved_inputs_after_sha256": self.saved_digest, "source_inputs_before_sha256": self.source_digest,
                 "source_inputs_after_sha256": self.source_digest}
        if request["action"] == "set":
            for index in range(4):
                name = f"priming-{index}.png" if index < 3 else "preview.png"
                write(directory / name, PNG)
                final["captures"].append({"path": relative + "/" + name, "sha256": client.digest(PNG),
                                          "size_bytes": len(PNG), "priming": index < 3})
        result = copy.deepcopy(final)
        if request["action"] == "set":
            result.update({"status": "ACCEPTED", "capture_pending": True, "captures": []})
            for key in ("dirty_after", "saved_inputs_after_sha256", "source_inputs_after_sha256"):
                del result[key]
        if self.final_edit is not None:
            self.final_edit(final)
        if not self.defer:
            document(directory / "receipt.json", final)
        if self.response_edit is not None:
            self.response_edit(result)
        # Exercise the installed FString wrapping path on every positive run.
        return {"result": {"content": [{"type": "text", "text": client.canonical(
            client.canonical(result).decode()).decode()}], "isError": False}}


class ClientTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.fixture = Fixture(Path(self.temporary.name))
        for patcher in (
            mock.patch.object(client, "WINDOWS_HOST", True),
            mock.patch.object(client, "REVIEW_ROOT", self.fixture.review_root),
            mock.patch.object(client.preparation, "SOURCE_ROOT", self.fixture.source_root),
            mock.patch.object(client, "_sources", return_value=self.fixture.sources),
            mock.patch.object(client, "_windows_observation", side_effect=lambda _pid: copy.deepcopy(self.fixture.process)),
            mock.patch.object(client, "_Transport", side_effect=self.fixture.transport),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def context(self):
        return client._load_context(self.fixture.host_path)

    def assert_blocked(self, result, calls=0):
        self.assertEqual("BLOCKED", result["status"], result)
        self.assertEqual(calls, result["tools_call_count"])
        self.assertFalse(result["retry_permitted"])

    def test_real_path_context_accepts_qualification_and_final_handoff(self):
        self.assertEqual(self.fixture.root, self.context()["root"])
        self.fixture.host.update(status="BROWSER_VIDEO_RECEIVED", owner_handoff=True)
        document(self.fixture.host_path, self.fixture.host)
        self.assertEqual(self.fixture.identity, self.context()["identity"])
        self.fixture.host["owner_handoff"] = False
        document(self.fixture.host_path, self.fixture.host)
        with self.assertRaisesRegex(ValueError, "hand off"):
            self.context()

    def test_authenticated_ready_requires_generated_class_and_tool_to_agree(self):
        original = copy.deepcopy(self.fixture.ready)
        cases = [
            {"toolset_identity": None},
            {"toolset_identity": original["toolset_identity"] | {"class_path": "/Engine/Foreign.Class"}},
            {"tool_schema": original["tool_schema"] | {"name": "YacsRoadMaterialPreview.preview"}},
            {"tool_schema": original["tool_schema"] | {
                "name": "PythonTypes.YacsRoadMaterialPreview_0x11223344.preview"}},
        ]
        for edit in cases:
            with self.subTest(edit=edit):
                # Re-sign the synthetic receipt so rejection tests semantic
                # identity binding rather than the earlier raw-file hash gate.
                document(self.fixture.root / client.bridge.READY_RELATIVE, original | edit)
                self.fixture.host["material_bridge_ready_sha256"] = client.digest(
                    (self.fixture.root / client.bridge.READY_RELATIVE).read_bytes())
                document(self.fixture.host_path, self.fixture.host)
                with self.assertRaises(ValueError):
                    self.context()
        self.assertEqual(0, self.fixture.calls)
        self.assertEqual(0, self.fixture.transports)

    def test_mcp_catalog_must_match_concrete_ready_name_before_call(self):
        self.fixture.tool = self.fixture.tool | {
            "name": "PythonTypes.YacsRoadMaterialPreview_0x11223344.preview"}
        result = self.fixture.execute(self.fixture.request())
        self.assert_blocked(result)
        self.assertIn("Actual MCP tools/list", result["error"])
        self.assertEqual(0, self.fixture.calls)

    def test_generated_tool_capitalization_keeps_exact_class_identity(self):
        ready = copy.deepcopy(self.fixture.ready)
        ready["tool_schema"]["name"] = ready["toolset_identity"]["toolset_name"] + ".Preview"
        tool, parameter = client._schema(ready)
        self.assertEqual(ready["tool_schema"], tool)
        self.assertEqual("request_json", parameter)

    def test_two_changes_share_native_state_and_restore_original_bindings(self):
        first = self.fixture.execute(self.fixture.request())
        self.assertEqual("COMPLETED", first["status"], first.get("error"))
        second = self.fixture.execute(self.fixture.request("two", paint_roughness=0.75, paint_color=[0.65, 0.30, 0.20, 1.0]))
        self.assertEqual("COMPLETED", second["status"], second.get("error"))
        restored = self.fixture.execute(self.fixture.request("restore", "restore"))
        self.assertEqual("COMPLETED", restored["status"], restored.get("error"))
        self.assertEqual(first["after"], second["before"])
        self.assertEqual(second["after"], restored["before"])
        self.assertEqual(self.fixture.initial, restored["after"])
        self.assertEqual((1, 2, 3), tuple(row["sequence"] for row in (first, second, restored)))
        self.assertEqual((8765, 8765, 8765), tuple(row["editor_pid"] for row in (first, second, restored)))
        self.assertEqual((4, 4, 0), tuple(len(row["captures"]) for row in (first, second, restored)))
        self.assertEqual(3, self.fixture.calls)
        self.assertEqual(3, self.fixture.closes)
        self.assertTrue(first["process_readback"]["project_argument_verified"])
        self.assertTrue(all(type(row["elapsed_seconds"]) is float and row["elapsed_seconds"] > 0
                            and row["performance_pass"] is False for row in (first, second, restored)))

    def test_inspection_does_not_increment_sequence_or_capture(self):
        result = self.fixture.execute(self.fixture.request("inspect", "inspect"))
        self.assertEqual("COMPLETED", result["status"], result.get("error"))
        self.assertEqual(0, result["sequence"])
        self.assertEqual(result["before"], result["after"])
        self.assertEqual([], result["captures"])

    def test_followup_checkout_keeps_the_six_original_launcher_sources(self):
        self.assertNotEqual(client.ROOT, self.fixture.launcher_root)
        context = self.context()
        self.assertEqual(self.fixture.launcher_root, context["launcher_root"])
        self.assertEqual(set(client.preparation.PINNED_PROJECT_FILES), set(context["retained_project_inputs"]))
        result = self.fixture.execute(self.fixture.request("followup"))
        self.assertEqual("COMPLETED", result["status"], result.get("error"))
        relative = next(iter(client.preparation.PINNED_PROJECT_FILES))
        path = self.fixture.launcher_root / relative
        write(path, path.read_bytes() + b"changed")
        with self.assertRaisesRegex(ValueError, "Retained launcher project input bytes"):
            self.context()

    def test_input_boundaries_refuse_unknown_duplicate_nonfinite_and_stale(self):
        context = self.context()
        history = client._history(context)
        edits = [{"schema_version": True}, {"expected_sequence": True}, {"expected_sequence": -1},
                 {"session_id": "other"}, {"action": "save"}, {"request_id": "../escape"},
                 {"paint_roughness": True}, {"paint_roughness": 1.01}, {"paint_color": [0, 0, 0, 0.5]},
                 {"paint_color": [0, 0, 0]}, {"path": "/Game/Other"}, {"paint_color": [0, 0, False, 1]}]
        for edit in edits:
            with self.subTest(edit=edit), self.assertRaises(ValueError):
                client._request(client.canonical(self.fixture.request(**edit)), context, history)
        raw = client.canonical(self.fixture.request())
        for bad in (raw[:-1] + b',"schema_version":1}', raw.replace(b"0.35", b"1e999"),
                    raw.replace(b"0.35", b"NaN"), b" " * 4096 + raw):
            with self.subTest(raw=bad[:50]), self.assertRaises(ValueError):
                client._request(bad, context, history)
        restore = self.fixture.request("restore", "restore", paint_roughness=0.1)
        with self.assertRaises(ValueError):
            client._request(client.canonical(restore), context, history)

    def test_owned_process_and_listener_cannot_be_receipt_echoes(self):
        original = copy.deepcopy(self.fixture.process)
        edits = [{"editor_pid": 8766}, {"editor_start_filetime_utc": "134050000000000001"},
                 {"editor_executable_path": r"D:\Other\UnrealEditor.exe"},
                 {"listeners": [{"address": "0.0.0.0", "port": 18784, "pid": 8765}]},
                 {"listeners": [{"address": "127.0.0.1", "port": 18784, "pid": 9999}]},
                 {"command_line": original["command_line"].replace("YetAnotherCyclingSim.uproject", "Other.uproject")},
                 {"command_line": original["command_line"].replace(client.preparation.MAP_PACKAGE, "/Engine/Maps/Entry")}]
        for edit in edits:
            self.fixture.process = original | edit
            with self.subTest(edit=edit), self.assertRaises(ValueError):
                self.context()
        self.fixture.process = original

    def test_ready_source_and_launcher_anchor_must_match(self):
        self.fixture.ready["bridge_source_sha256"] = "0" * 64
        document(self.fixture.root / client.bridge.READY_RELATIVE, self.fixture.ready)
        with self.assertRaisesRegex(ValueError, "ready bytes"):
            self.context()
        self.fixture.host["material_bridge_ready_sha256"] = client.digest(
            (self.fixture.root / client.bridge.READY_RELATIVE).read_bytes())
        document(self.fixture.host_path, self.fixture.host)
        with self.assertRaisesRegex(ValueError, "exact launcher source"):
            self.context()

    def test_extra_tool_blocks_before_domain_call(self):
        self.fixture.tool_extra = {"name": "execute_python", "inputSchema": {}}
        result = self.fixture.execute(self.fixture.request())
        self.assert_blocked(result)
        self.assertEqual(0, self.fixture.calls)
        self.assertEqual(1, self.fixture.closes)

    def test_double_json_string_is_rejected_without_recursive_parsing(self):
        response = {"result": {"content": [{"type": "text", "text": '{"ok":true}'}]}}
        self.assertEqual({"ok": True}, client._domain_result(response))
        text = client.canonical(client.canonical(client.canonical({"ok": True}).decode()).decode()).decode()
        response["result"]["content"][0]["text"] = text
        with self.assertRaises(ValueError):
            client._domain_result(response)

    def test_duplicate_and_stale_requests_never_reach_second_call(self):
        request = self.fixture.request()
        self.assertEqual("COMPLETED", self.fixture.execute(request)["status"])
        duplicate = self.fixture.execute(self.fixture.request("one"), "duplicate")
        self.assert_blocked(duplicate)
        stale = self.fixture.execute(self.fixture.request("stale", sequence=0))
        self.assert_blocked(stale)
        self.assertEqual(1, self.fixture.calls)

    def test_timeout_is_uncertain_and_next_call_refuses_pending_directory(self):
        self.fixture.defer = True
        with mock.patch.object(client, "POLL_SECONDS", 0):
            first = self.fixture.execute(self.fixture.request())
        self.assert_blocked(first, calls=1)
        self.assertIn("timed out", first["error"])
        self.assertGreater(first["elapsed_seconds"], 0)
        next_call = self.fixture.execute(self.fixture.request("next"))
        self.assert_blocked(next_call)
        self.assertIn("pending or uncertain", next_call["error"])
        self.assertEqual(1, self.fixture.calls)

    def test_transport_failure_is_not_retried(self):
        self.fixture.call_error = TimeoutError("SYNTHETIC transport timeout")
        result = self.fixture.execute(self.fixture.request())
        self.assert_blocked(result, calls=1)
        self.assertEqual(1, self.fixture.calls)
        self.assertEqual(1, self.fixture.closes)

    def test_bad_native_before_or_after_cannot_pass_as_parameter_echo(self):
        self.fixture.response_edit = lambda value: value["after"].update(paint_roughness=0.99)
        result = self.fixture.execute(self.fixture.request())
        self.assert_blocked(result, calls=1)
        self.assertIn("effective paint", result["error"])

    def test_native_final_identity_or_conservation_drift_is_blocked(self):
        self.fixture.final_edit = lambda value: value.update(source_inputs_after_sha256="0" * 64)
        result = self.fixture.execute(self.fixture.request())
        self.assert_blocked(result, calls=1)
        self.assertIn("saved/dirty", result["error"])

    def test_png_hash_mismatch_blocks_completed_receipt(self):
        def corrupt(final):
            write(self.fixture.root / final["captures"][-1]["path"], PNG + b"changed")

        self.fixture.final_edit = corrupt
        result = self.fixture.execute(self.fixture.request())
        self.assert_blocked(result, calls=1)
        self.assertIn("PNG bytes", result["error"])

    def test_redirected_receipt_path_is_rejected(self):
        alternative = self.fixture.base / "outside"
        alternative.mkdir()
        alias = self.fixture.review_root / (client.preparation.RUNTIME_SHA[:12] + "-alias")
        try:
            alias.symlink_to(alternative, target_is_directory=True)
        except OSError as error:
            self.skipTest(f"Host cannot create a synthetic directory link: {error}")
        with self.assertRaisesRegex(ValueError, "symlink/reparse"):
            client._load_context(alias / client.SESSION_RECEIPT)

    def test_last_history_slot_is_reserved_for_restore(self):
        context = self.context()
        history = {"receipts": {f"prior-{i}": {} for i in range(255)}, "sequence": 255,
                   "current": self.fixture.initial}
        with self.assertRaisesRegex(ValueError, "reserved"):
            client._request(client.canonical(self.fixture.request(sequence=255)), context, history)
        restored = client._request(client.canonical(self.fixture.request("restore", "restore", sequence=255)), context, history)
        self.assertEqual("restore", restored["action"])

    def test_fresh_output_is_never_overwritten(self):
        output = self.fixture.base / "existing"
        output.mkdir()
        marker = output / "unique.txt"
        marker.write_bytes(b"keep")
        with self.assertRaisesRegex(ValueError, "already exists"):
            client.run(self.fixture.host_path, self.fixture.base / "absent.json", output)
        self.assertEqual(b"keep", marker.read_bytes())
        self.assertEqual(0, self.fixture.calls)


class SourceGateTests(unittest.TestCase):
    def test_actual_head_mismatch_blocks_before_blob_or_network_read(self):
        with mock.patch.object(client.committed_git, "_git_bounded", return_value=b"b" * 40 + b"\n"), \
                mock.patch.object(client.committed_git, "_read_exact_blobs") as blobs:
            with self.assertRaisesRegex(ValueError, "Actual client HEAD"):
                client._sources(LAUNCHER_SHA)
            blobs.assert_not_called()

    def test_target_sha_and_modified_client_are_refused(self):
        paths = (*client.SOURCE_MODULES, client.CLIENT_SOURCE)
        blobs = {path: (client.ROOT / path).read_bytes() for path in paths}
        with mock.patch.object(client.committed_git, "_git_bounded", return_value=LAUNCHER_SHA.encode() + b"\n"), \
                mock.patch.object(client.committed_git, "_read_exact_blobs", return_value=blobs), \
                mock.patch.dict(client.os.environ, {"TARGET_SHA": "b" * 40}), \
                self.assertRaisesRegex(ValueError, "TARGET_SHA"):
            client._sources(LAUNCHER_SHA)
        with mock.patch.object(client.committed_git, "_git_bounded", return_value=LAUNCHER_SHA.encode() + b"\n"), \
                mock.patch.object(client.committed_git, "_read_exact_blobs", return_value=blobs), \
                mock.patch.dict(client.os.environ, {"TARGET_SHA": LAUNCHER_SHA}):
            self.assertEqual(client.digest(blobs[client.CLIENT_SOURCE]), client._sources(LAUNCHER_SHA)[client.CLIENT_SOURCE])
            blobs[client.CLIENT_SOURCE] = b"different committed bytes"
            with self.assertRaisesRegex(ValueError, "committed launcher bytes"):
                client._sources(LAUNCHER_SHA)


if __name__ == "__main__":
    unittest.main()
