"""Synthetic loopback HTTP fixtures; no Unreal or real credentials are used."""

from __future__ import annotations

from contextlib import contextmanager
import builtins
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import io
import itertools
import json
import os
from pathlib import Path
import re
import tempfile
import threading
import time
import sys
import unittest
from unittest import mock

from scripts.ue import lesson07_wingman_client as client


TOKEN = "SYNTHETIC_SECRET_7ec473bf_NOT_A_CREDENTIAL"

# Exact raw inputSchema retained in the authenticated 2026-10-21 bridge receipt.
INSTALLED_VAULT_SCHEMA = {
    "properties": {
        "action": {
            "description": "'list' (default) or 'install'.",
            "enum": ["list", "install"], "type": "string",
        },
        "dry_run": {
            "description": "[install] Report what would be copied without writing anything (default false).",
            "type": "boolean",
        },
        "filter": {
            "description": "[list] Only show entries whose name contains this text, case-insensitive.",
            "type": "string",
        },
        "force": {
            "description": "[install] Install an entry that is NOT an AssetPack (a Project or plugin) by copying only its Content (default false). The Config folder and .uproject are not copied, so the assets may reference settings this project lacks. Only pass this when the user has asked for it after being told what is left behind.",
            "type": "boolean",
        },
        "name": {
            "description": "[install] The vault entry to install, as the 'entry' value printed by action=list. A case-insensitive partial match is accepted when it is unambiguous.",
            "type": "string",
        },
    },
    "type": "object",
}

# Exact raw inputSchema from authenticated discovery run 39515925462, source 96a7.
INSTALLED_PYTHON_SCHEMA = {
    "properties": {
        "code": {
            "description": "Python code to execute. Pass this OR 'file' - at least one is required, and 'file' wins when both are given. Use 'import unreal' for UE APIs. Example: unreal.EditorAssetLibrary.save_asset('/Game/BP_MyActor'). Runs in the editor's PERSISTENT interpreter namespace - globals survive between calls, so any global left holding an unreal.Object pins it for the session and blocks a later delete of its asset. The result carries a 'UObject pin report' footer naming every new holder this call created; 'del <name>' in your NEXT call releases it.",
            "type": "string",
        },
        "file": {
            "description": "Path to a Python 3 script file to execute (absolute, or relative to the project directory; UTF-8; 2 MB cap). A file-only call is fully supported: pass this OR 'code' (at least one is required), and this one wins when both are passed. Use for multi-line scripts - the file path avoids every JSON/transport escaping layer that mangles inline code.",
            "type": "string",
        },
        "mode": {
            "description": "Execution mode: 'file' (default, multi-line script, side effects) or 'eval' (a single expression whose value-repr is returned in command_result with no print needed). Note: 'eval' must be ONE expression; loco helpers / multi-line setup must run in a prior 'file' call (module imports persist in the interpreter).",
            "enum": ["file", "eval"],
            "type": "string",
        },
    },
    "type": "object",
}


# Exact raw screenshot inputSchema retained by authenticated discovery.
INSTALLED_CAPTURE_SCHEMA = {
    "properties": {
        "camera_location": {
            "description": "Optional [X, Y, Z] world location to frame this ONE capture from. The Level Editor camera is moved for the capture and restored before the tool returns, so the user's view is never left moved. Refused while PIE is the capture target. Must be exactly 3 JSON numbers.",
            "items": {"type": "number"},
            "type": "array",
        },
        "camera_rotation": {
            "description": "Optional [Pitch, Yaw, Roll] camera rotation in degrees for this ONE capture. The order is Pitch, Yaw, Roll - NOT the (Roll, Pitch, Yaw) order that UE's Python unreal.Rotator() positional constructor uses, which silently aims the camera at the ground. Restored with the rest of the camera.",
            "items": {"type": "number"},
            "type": "array",
        },
        "focus_actor": {
            "description": "Outliner label of a LEVEL ACTOR to frame, e.g. 'BP_Coin_2'. Computes a bounds-scaled 3/4 view and points the camera at it, then restores your viewport like any other override here. Resolves exact label first, then case-insensitive substring over label + internal name. Frames on COLLIDING bounds when they are tighter, so a Character is framed on its body and not on its perception sphere. Mutually exclusive with camera_location / camera_rotation, which it would otherwise silently overwrite. An ASSET is not framable this way - this is level actors only.",
            "type": "string",
        },
        "focus_margin": {
            "description": "Distance multiplier for focus_actor (default 1.0 = the standard 3/4 view; >1 pulls the camera back for context, <1 tightens). Ignored without focus_actor.",
            "type": "number",
        },
        "fov": {
            "description": "Optional horizontal field of view in degrees for this ONE capture, 5 to 170. Lower = tighter framing on a distant actor. Restored with the rest of the camera.",
            "type": "number",
        },
        "return_image": {
            "description": "Default true: return the capture inline as IMAGE_BASE64:jpeg:<payload>. false = write the JPEG to Saved/LocoHelperAI/ViewportShots/ and return the saved file path plus the capture metadata only - recommended for external callers, where the payload is pure token cost (T-258).",
            "type": "boolean",
        },
    },
    "type": "object",
}

CAPTURE_TEXT = (
    "Saved JPEG: D:/yacs/project/Saved/LocoHelperAI/ViewportShots/synthetic.jpg\n"
    "Viewport: Level Editor; width=956; height=431"
)


def identity(port):
    now = datetime.now(timezone.utc)
    return {
        "schema_version": 1,
        "status": "L07_WINGMAN_HOST_IDENTITY_VERIFIED",
        "observed_utc": now.isoformat(),
        "pid": 1234,
        "process_created_utc": (now - timedelta(minutes=4)).isoformat(),
        "executable": client.EXECUTABLE,
        "project": client.PROJECT,
        "canonical_project_argument_matches": True,
        "listener": {"address": "127.0.0.1", "port": port, "pid": 1234},
    }


def config(port):
    return {"url": f"http://127.0.0.1:{port}/loco", "token": TOKEN, "type": "http"}


def default_reply(request):
    method = request["method"]
    if method == "notifications/initialized":
        return 202, {}, b""
    if method == "initialize":
        result = {
            "protocolVersion": client.PROTOCOL,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "Synthetic", "version": "1"},
            "instructions": TOKEN,
        }
        headers = {"Mcp-Session-Id": "synthetic-session-1"}
    elif method == "tools/list":
        result = {
            "tools": [
                {
                    "name": "execute_python",
                    "description": TOKEN,
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "code": {
                                "type": "string",
                                "description": TOKEN,
                                "default": TOKEN,
                            }
                        },
                        "required": ["code"],
                        "additionalProperties": False,
                    },
                }
            ]
        }
        headers = {}
    elif method == "session/status":
        result = {
            "signed_in": True,
            "plan": "Premium",
            "email": "synthetic@example.invalid",
            "user_id": TOKEN,
            "token": TOKEN,
        }
        headers = {}
    else:
        raise AssertionError("Unexpected fixture request")
    return (
        200,
        {"Content-Type": "application/json", **headers},
        client.canonical({"jsonrpc": "2.0", "id": request["id"], "result": result}),
    )


def observation():
    return {
        "status": client.OBSERVER_STATUS,
        "pid": 1234,
        "project": "D:/yacs/project/",
        "project_file": client.PROJECT,
        "world": client.OBSERVER_WORLD,
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "dirty_sets_equal": None,
        "limitations": {
            "mutating_apis_requested": False,
            "asset_loads_requested": False,
            "new_captures": False,
            "visual_acceptance": False,
            "performance_pass": False,
        },
        "validation": {"visual_or_native_graph_acceptance": False},
    }


def tool_result(observed=None):
    envelope = {
        "observer_sha256": client.OBSERVER_SHA256,
        "observation": observation() if observed is None else observed,
    }
    return {
        "isError": False,
        "content": [
            {
                "type": "text",
                "text": client.OBSERVER_TAG + client.canonical(envelope).decode(),
            }
        ],
    }


def observer_reply(request):
    if request["method"] == "tools/call":
        return (
            200,
            {"Content-Type": "application/json"},
            client.canonical(
                {"jsonrpc": "2.0", "id": request["id"], "result": tool_result()}
            ),
        )
    status, headers, raw = default_reply(request)
    if request["method"] == "tools/list":
        payload = json.loads(raw)
        payload["result"]["tools"][0]["inputSchema"] = INSTALLED_PYTHON_SCHEMA
        raw = client.canonical(payload)
    return status, headers, raw


def capture_reply(request):
    if request["method"] == "tools/call":
        return (
            200,
            {"Content-Type": "application/json"},
            client.canonical(
                {
                    "jsonrpc": "2.0",
                    "id": request["id"],
                    "result": {
                        "isError": False,
                        "content": [{"type": "text", "text": CAPTURE_TEXT}],
                    },
                }
            ),
        )
    status, headers, raw = observer_reply(request)
    if request["method"] == "tools/list":
        payload = json.loads(raw)
        listing = payload["result"]["tools"]
        listing[0]["description"] = "Installed Python description."
        listing.append(
            {
                "name": "take_viewport_screenshot",
                "description": "Save the current viewport without camera overrides.",
                "inputSchema": INSTALLED_CAPTURE_SCHEMA,
            }
        )
        for name in (
            "read_bp",
            "edit_graph",
            "explore",
            "code_search",
            "edit_texture",
            "edit_material_instance",
            "edit_asset",
            "edit_level",
            "edit_material",
            "edit_material_function",
            "edit_data_asset",
            "download_asset",
            "vault_asset",
        ):
            listing.append(
                {
                    "name": name,
                    "description": "Installed dedicated operation: " + name,
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "asset_path": {
                                "type": "string",
                                "default": "/Game/Example",
                                "description": "Installed argument description.",
                            }
                        },
                    },
                }
            )
        raw = client.canonical(payload)
    return status, headers, raw


# Synthetic schemas exercise full raw-schema pinning without copying large vendor
# descriptions. Production pins are checked against the retained native receipt.
INSPECTION_FIXTURE_SCHEMAS = {
    name: {"type": "object", "description": "Synthetic schema: " + name}
    for name in (
        "explore",
        "edit_material",
        "edit_material_instance",
        "edit_texture",
        "edit_asset",
        "code_search",
    )
}
INSPECTION_FIXTURE_HASHES = {
    name: hashlib.sha256(client.canonical(schema)).hexdigest()
    for name, schema in INSPECTION_FIXTURE_SCHEMAS.items()
}


def registry_records():
    # Independent path/class fixture: these are the existing eleven assets that
    # must be proved present before any name-only tool can be admitted.
    root = "/Game/Generated/YACS/Lesson07_Unified/"
    return [
        {
            "name": suffix.rsplit("/", 1)[1],
            "path": root + suffix.rsplit("/", 1)[0],
            "class": kind,
            "class_path": "/Script/Engine." + kind,
            "loaded": True,
        }
        for suffix, kind in (
            ("Materials/M_Landscape_YACS", "Material"),
            ("Materials/MI_Landscape_Instance_YACS", "MaterialInstanceConstant"),
            ("Materials/TA_Colour_Unified", "Texture2DArray"),
            ("Materials/TA_Normal_Unified", "Texture2DArray"),
            ("Materials/TA_Masks_Unified", "Texture2DArray"),
            ("Textures/Slices/T_Grass_Normal", "Texture2D"),
            ("Textures/Slices/T_Grass_Masks", "Texture2D"),
            ("Textures/Slices/T_Cliffs_Normal", "Texture2D"),
            ("Textures/Slices/T_Cliffs_Masks", "Texture2D"),
            ("Textures/T_PE_Terrain_IDMap", "Texture2D"),
            ("Textures/T_PE_Terrain_Color", "Texture2D"),
        )
    ]


def registry_text(records=None):
    rows = registry_records() if records is None else records
    count = len(rows)
    loaded = sum(row.get("loaded", False) for row in rows)
    root = "/Game/Generated/YACS/Lesson07_Unified"
    return (
        f"# ASSETS {root} shown={count} total={count} offset=0 limit=200 loaded={loaded}/{count}\n"
        "#json-explore:" + json.dumps({
            "mode": "assets", "scope": root, "shown": count, "total": count,
            "offset": 0, "limit": 200, "truncated": False,
            "raw_from_registry": count, "loaded_in_shown": loaded,
            "filters": {"pattern": "", "query": "", "type": "", "class_path": "", "class_filter_recursive": False},
            "rows": rows,
        })
    )


def inspection_reply(request):
    status, headers, raw = capture_reply(request)
    if request["method"] in {"tools/list", "tools/call"}:
        payload = json.loads(raw)
        if request["method"] == "tools/list":
            for descriptor in payload["result"]["tools"]:
                if descriptor["name"] in INSPECTION_FIXTURE_SCHEMAS:
                    descriptor["inputSchema"] = INSPECTION_FIXTURE_SCHEMAS[
                        descriptor["name"]
                    ]
        else:
            name = request["params"]["name"]
            payload["result"] = {
                "isError": False,
                "content": [
                    {
                        "type": "text",
                        "text": registry_text()
                        if name == "explore"
                        else "Uninterpreted native response: " + name,
                    }
                ],
            }
        raw = client.canonical(payload)
    return status, headers, raw


@contextmanager
def peer(responder=default_reply):
    requests = []

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *_args):
            pass

        def do_POST(self):
            request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            requests.append(
                {"path": self.path, "headers": dict(self.headers), "body": request}
            )
            try:
                status, headers, body = responder(request)
                self.send_response(status)
                for key, value in headers.items():
                    self.send_header(key, value)
                if "Content-Length" not in headers:
                    self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    thread = threading.Thread(
        target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
    )
    thread.start()
    try:
        yield server.server_port, requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def connection(port, timeout=2, state=None):
    return client.DiscoveryClient(
        client.Discovery.from_mapping(config(port)),
        identity(port),
        timeout=timeout,
        observation_state=state,
    )


class AdmissionTests(unittest.TestCase):
    def test_metadata_is_bounded_and_cannot_supply_missing_or_malformed_core(self):
        metadata = {"metadata": {**config(19315), "note": "synthetic metadata"}}
        for key in ("url", "token", "type"):
            missing = {**config(19315), **metadata}
            del missing[key]
            with self.subTest(missing=key), self.assertRaises(client.ProbeError):
                client.Discovery.from_mapping(missing)
        for key, value in (
            ("url", "http://example.invalid:19315/loco"),
            ("url", {"url": config(19315)["url"]}),
            ("token", "bad token with spaces"),
            ("token", None),
            ("type", "sse"),
            ("type", {"type": "http"}),
        ):
            with (
                self.subTest(key=key, value=value),
                self.assertRaises(client.ProbeError),
            ):
                client.Discovery.from_mapping({**config(19315), **metadata, key: value})
        for value in ("x" * client.CONFIG_LIMIT, float("nan"), object()):
            with (
                self.subTest(metadata_type=type(value).__name__),
                self.assertRaises(client.ProbeError),
            ):
                client.Discovery.from_mapping({**config(19315), "metadata": value})

    def test_invalid_endpoint_and_header_input_rejected(self):
        invalid = [
            "https://127.0.0.1:19315/loco",
            "http://localhost:19315/loco",
            "http://127.0.0.2:19315/loco",
            "http://127.0.0.1.evil:19315/loco",
            "http://secret@127.0.0.1:19315/loco",
            "http://127.0.0.1:19315/loco?token=x",
            "http://127.0.0.1:19315/loco#x",
            "http://127.0.0.1:19315/loco?",
            "http://127.0.0.1:19315/loco#",
            "http://127.0.0.1:0/loco",
            "http://127.0.0.1:65536/loco",
            "http://127.0.0.1:19315/mcp",
            "http://127.0.0.1:19315/loco/",
            "http://127.0.0.1:19315/loco\n",
        ]
        for url in invalid:
            with self.subTest(url=url), self.assertRaises(client.ProbeError):
                client.Discovery.from_mapping({**config(19315), "url": url})
        for token in (None, "", "x\r\nInjected: yes", "Bearer with spaces", "x" * 4097):
            with (
                self.subTest(token_type=type(token).__name__),
                self.assertRaises(client.ProbeError),
            ):
                client.Discovery.from_mapping({**config(19315), "token": token})

    def test_bad_external_identity_never_opens_connection(self):
        cases = []
        for field, value in (
            ("pid", True),
            ("canonical_project_argument_matches", False),
            ("project", r"D:\other\YetAnotherCyclingSim.uproject"),
            ("executable", r"D:\other\UnrealEditor.exe"),
            ("status", "READ_ONLY_BRIDGE_DISCOVERY_NOT_RUNTIME_PROOF"),
        ):
            cases.append({**identity(19315), field: value})
        cases.append(
            {
                **identity(19315),
                "listener": {"address": "127.0.0.1", "port": 19316, "pid": 1234},
            }
        )
        cases.append(
            {
                **identity(19315),
                "listener": {"address": "127.0.0.1", "port": 19315, "pid": 5678},
            }
        )
        cases.append(
            {
                **identity(19315),
                "observed_utc": (
                    datetime.now(timezone.utc) - timedelta(minutes=3)
                ).isoformat(),
            }
        )
        cases.append(
            {
                **identity(19315),
                "observed_utc": (
                    datetime.now(timezone.utc) + timedelta(minutes=3)
                ).isoformat(),
            }
        )
        with mock.patch.object(client.http.client, "HTTPConnection") as http:
            for value in cases:
                with self.subTest(value=value), self.assertRaises(client.ProbeError):
                    client.DiscoveryClient(
                        client.Discovery.from_mapping(config(19315)), value
                    )
            http.assert_not_called()

    def test_no_tool_call_or_arbitrary_method_surface(self):
        with peer() as (port, requests):
            probe = connection(port)
            for method in (
                "tools/call",
                "execute_python",
                "resources/read",
                "session/logout",
            ):
                with self.subTest(method=method), self.assertRaises(client.ProbeError):
                    probe._post(method)
            self.assertEqual(requests, [])

    def test_duplicate_json_members_rejected_without_value_disclosure(self):
        with self.assertRaises(client.ProbeError) as caught:
            client.parse_json(b'{"token":"' + TOKEN.encode() + b'","token":"x"}')
        self.assertEqual(str(caught.exception), "DUPLICATE_JSON_KEY")
        self.assertNotIn(TOKEN, str(caught.exception))


class WireTests(unittest.TestCase):
    def test_selected_installed_contracts_retain_exact_schemas_and_safe_metadata(self):
        input_schema = {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Python source"},
                "mode": {
                    "type": "string",
                    "enum": ["first", "second"],
                    "default": "first",
                },
            },
            "required": ["code"],
            "additionalProperties": False,
        }
        output_schema = {
            "type": "object",
            "properties": {
                "output": {"type": "string"},
                "success": {"type": "boolean"},
            },
        }
        annotations = {
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": False,
        }
        selected = {
            "name": "execute_python",
            "inputSchema": input_schema,
            "outputSchema": output_schema,
            "description": "Synthetic installed contract; data only.",
            "annotations": {**annotations, "title": TOKEN, "unrecognized": TOKEN},
            "unknown_metadata": TOKEN,
        }

        def contract_reply(request):
            if request["method"] == "tools/list":
                return (
                    200,
                    {"Content-Type": "application/json"},
                    client.canonical(
                        {
                            "jsonrpc": "2.0",
                            "id": request["id"],
                            "result": {
                                "tools": [
                                    selected,
                                    {
                                        "name": "take_viewport_screenshot",
                                        "inputSchema": {
                                            "type": "object",
                                            "properties": {
                                                "return_image": {
                                                    "type": "boolean",
                                                    "default": True,
                                                }
                                            },
                                        },
                                    },
                                    {
                                        "name": "other_tool",
                                        "inputSchema": input_schema,
                                        "outputSchema": output_schema,
                                        "description": TOKEN,
                                    },
                                ]
                            },
                        }
                    ),
                )
            return default_reply(request)

        with peer(contract_reply) as (port, requests):
            report = connection(port).probe()
        contracts = report["installed_tool_contracts"]
        self.assertEqual(set(contracts), {"execute_python", "take_viewport_screenshot"})
        self.assertEqual(
            contracts["execute_python"],
            {
                "status": "RETAINED",
                "inputSchema": input_schema,
                "outputSchema": output_schema,
                "description": selected["description"],
                "annotations": annotations,
            },
        )
        self.assertIs(
            contracts["take_viewport_screenshot"]["inputSchema"]["properties"][
                "return_image"
            ]["default"],
            True,
        )
        self.assertNotIn("outputSchema", contracts["take_viewport_screenshot"])
        for row in report["tools"]:
            if row["name"] in {"execute_python", "other_tool"}:
                self.assertEqual(
                    row["inputSchema"]["properties"]["mode"], {"type": "string"}
                )
        self.assertEqual(report["status"], "DISCOVERY_COMPLETE")
        self.assertEqual(report["native_tool_calls"], 0)
        self.assertEqual(len(requests), 4)
        self.assertNotIn(TOKEN.encode(), client.canonical(report))

    def test_selected_contract_exclusions_never_expose_credentials_or_large_values(
        self,
    ):
        nested = {"type": "string"}
        for _ in range(13):
            nested = {"items": nested}
        cases = [
            ({"description": TOKEN}, "CONTRACT_CREDENTIAL"),
            (
                {"inputSchema": {"type": "object", "default": {"secret": TOKEN}}},
                "CONTRACT_CREDENTIAL",
            ),
            (
                {
                    "inputSchema": {
                        "type": "object",
                        "enum": ["x" * client.CONTRACT_LIMIT],
                    }
                },
                "CONTRACT_SIZE",
            ),
            (
                {"description": "x" * (client.CONTRACT_DESCRIPTION_LIMIT + 1)},
                "CONTRACT_DESCRIPTION",
            ),
            ({"outputSchema": nested}, "CONTRACT_DEPTH"),
            ({"annotations": {"readOnlyHint": "true"}}, "CONTRACT_ANNOTATIONS"),
        ]
        for fields, reason in cases:

            def excluded_reply(request):
                if request["method"] == "tools/list":
                    return (
                        200,
                        {"Content-Type": "application/json"},
                        client.canonical(
                            {
                                "jsonrpc": "2.0",
                                "id": request["id"],
                                "result": {
                                    "tools": [
                                        {
                                            "name": "execute_python",
                                            "inputSchema": {"type": "object"},
                                            **fields,
                                        }
                                    ]
                                },
                            }
                        ),
                    )
                return default_reply(request)

            with self.subTest(reason=reason), peer(excluded_reply) as (port, requests):
                report = connection(port).probe()
            self.assertEqual(
                report["installed_tool_contracts"]["execute_python"],
                {"status": "EXCLUDED", "reason": reason},
            )
            self.assertEqual(report["status"], "DISCOVERY_COMPLETE")
            self.assertEqual(report["native_tool_calls"], 0)
            self.assertEqual(len(requests), 4)
            self.assertNotIn(TOKEN.encode(), client.canonical(report))

    def test_json_escaped_credential_in_contract_is_excluded(self):
        token = 'synthetic\\secret"value'
        contract = client.installed_tool_contract(
            {
                "inputSchema": {"type": "object", "default": {"note": token}},
            },
            token,
        )
        self.assertEqual(
            contract, {"status": "EXCLUDED", "reason": "CONTRACT_CREDENTIAL"}
        )

    def test_large_edit_graph_contract_retains_only_complete_bounded_description(self):
        description = "Synthetic graph description.\nThe final line must remain intact."
        tool = {
            "name": "edit_graph", "description": description,
            "inputSchema": {"type": "object", "enum": ["x" * client.CONTRACT_LIMIT]},
            "outputSchema": {"type": "object"},
        }

        def large_contract_reply(request):
            if request["method"] == "tools/list":
                return 200, {"Content-Type": "application/json"}, client.canonical({
                    "jsonrpc": "2.0", "id": request["id"], "result": {"tools": [tool]}})
            return default_reply(request)

        with peer(large_contract_reply) as (port, requests):
            report = connection(port).probe()
        retained = report["installed_tool_contracts"]["edit_graph"]
        self.assertEqual(retained, {
            "status": "EXCLUDED", "reason": "CONTRACT_SIZE",
            "description_only": {"status": "RETAINED_DESCRIPTION_ONLY",
                                 "description": description, "schema_retained": False,
                                 "truncated": False},
        })
        self.assertLessEqual(len(client.canonical(retained)), client.CONTRACT_LIMIT)
        self.assertNotIn("inputSchema", retained)
        self.assertNotIn("outputSchema", retained)
        self.assertEqual(report["native_tool_calls"], 0)
        self.assertFalse(any(row["body"]["method"] == "tools/call" for row in requests))
        self.assertEqual(client.installed_tool_contract({**tool, "name": "edit_material"}, TOKEN),
                         {"status": "EXCLUDED", "reason": "CONTRACT_SIZE"})

    def test_graph_description_fallback_preserves_existing_length_and_type_limits(self):
        base = {"name": "edit_graph", "inputSchema": {
            "type": "object", "enum": ["x" * client.CONTRACT_LIMIT]}}
        for description in ("x" * (client.CONTRACT_DESCRIPTION_LIMIT + 1), None, ["description"]):
            with self.subTest(description_type=type(description).__name__):
                self.assertEqual(client.installed_tool_contract({**base, "description": description}, TOKEN),
                                 {"status": "EXCLUDED", "reason": "CONTRACT_DESCRIPTION"})
        # The description limit is unchanged; the complete fallback must also
        # fit the existing serialized contract cap, without a shortened string.
        description = "x" * client.CONTRACT_DESCRIPTION_LIMIT
        retained = client.installed_tool_contract({**base, "description": description}, TOKEN)
        self.assertEqual(retained["description_only"]["description"], description)
        self.assertEqual(client.installed_tool_contract(base, TOKEN),
                         {"status": "EXCLUDED", "reason": "CONTRACT_SIZE"})
        wide = "\u2603" * client.CONTRACT_DESCRIPTION_LIMIT
        self.assertEqual(client.installed_tool_contract({**base, "description": wide}, TOKEN),
                         {"status": "EXCLUDED", "reason": "CONTRACT_SIZE"})
        mixed = "x" * 15000 + "\u00e9" * 1000
        self.assertLessEqual(len(mixed), client.CONTRACT_DESCRIPTION_LIMIT)
        self.assertGreater(len(mixed.encode("utf-8")), client.CONTRACT_DESCRIPTION_LIMIT)
        self.assertLess(len(client.canonical({"description": mixed})), client.CONTRACT_LIMIT)
        for description in (mixed, "invalid surrogate \ud800"):
            with self.subTest(description_length=len(description)):
                self.assertEqual(client.installed_tool_contract({**base, "description": description}, TOKEN),
                                 {"status": "EXCLUDED", "reason": "CONTRACT_SIZE"})
        escaped = "\u2603" * (client.CONTRACT_DESCRIPTION_LIMIT // 3)
        self.assertLessEqual(len(escaped.encode("utf-8")), client.CONTRACT_DESCRIPTION_LIMIT)
        self.assertGreater(len(client.canonical({"description": escaped})), client.CONTRACT_LIMIT)
        self.assertEqual(client.installed_tool_contract({**base, "description": escaped}, TOKEN),
                         {"status": "EXCLUDED", "reason": "CONTRACT_SIZE"})

    def test_graph_description_fallback_never_salvages_a_credential_rejection(self):
        base = {"name": "edit_graph", "description": "Synthetic safe description",
                "inputSchema": {"type": "object", "enum": ["x" * client.CONTRACT_LIMIT]}}
        for token in (TOKEN, 'synthetic\\secret"value'):
            for fields in ({"description": "prefix " + token + " suffix"},
                           {"inputSchema": {**base["inputSchema"], "default": token}}):
                with self.subTest(token=token, location=next(iter(fields))):
                    result = client.installed_tool_contract({**base, **fields}, token)
                    self.assertEqual(result, {"status": "EXCLUDED", "reason": "CONTRACT_CREDENTIAL"})
                    self.assertNotIn(token.encode(), client.canonical(result))
        # The raw serialized check must still apply even when the schema-size
        # rejection happens first and no decoded string contains this token.
        token = r"\u2603"
        for fields in ({"description": "Synthetic snowman \u2603"},
                       {"inputSchema": {**base["inputSchema"], "default": "\u2603"}}):
            with self.subTest(serialized_secret_location=next(iter(fields))):
                self.assertNotIn(token, str(fields))
                self.assertIn(token.encode(), client.canonical(fields))
                result = client.installed_tool_contract({**base, **fields}, token)
                self.assertEqual(result, {"status": "EXCLUDED", "reason": "CONTRACT_SIZE"})
                self.assertNotIn(token.encode(), client.canonical(result))
        self.assertEqual(client.installed_tool_contract(base, "RETAINED_DESCRIPTION_ONLY"),
                         {"status": "EXCLUDED", "reason": "CONTRACT_SIZE"})

    def test_extra_discovery_metadata_never_changes_route_auth_or_report(self):
        ignored_secret = "SYNTHETIC_IGNORED_METADATA_VALUE"
        with peer() as (port, requests):
            discovery = client.Discovery.from_mapping(
                {
                    **config(port),
                    "metadata": {
                        "url": "https://example.invalid/alternate",
                        "token": ignored_secret,
                        "type": "sse",
                    },
                    "headers": {"Authorization": "Bearer " + ignored_secret},
                    "endpoint": "https://example.invalid/alternate",
                    "arbitrary_note": ignored_secret,
                }
            )
            self.assertEqual(discovery, client.Discovery(port, TOKEN))
            report = client.DiscoveryClient(discovery, identity(port)).probe()
        self.assertEqual(report["status"], "DISCOVERY_COMPLETE")
        self.assertEqual(len(requests), 4)
        for request in requests:
            self.assertEqual(request["path"], client.ENDPOINT)
            self.assertEqual(request["headers"]["Authorization"], "Bearer " + TOKEN)
            self.assertNotIn(ignored_secret.encode(), client.canonical(request))
        self.assertNotIn(ignored_secret.encode(), client.canonical(report))
        self.assertNotIn(TOKEN.encode(), client.canonical(report))
        self.assertEqual(report["native_tool_calls"], 0)

    def test_handshake_auth_session_headers_and_sanitized_schema(self):
        with (
            peer() as (port, requests),
            mock.patch.dict(
                os.environ,
                {
                    "HTTP_PROXY": "http://example.invalid:9",
                    "http_proxy": "http://example.invalid:9",
                },
            ),
        ):
            report = connection(port).probe()
        self.assertEqual(report["status"], "DISCOVERY_COMPLETE")
        self.assertEqual(
            [r["body"]["method"] for r in requests],
            ["initialize", "notifications/initialized", "tools/list", "session/status"],
        )
        for number, row in enumerate(requests):
            self.assertEqual(row["path"], "/loco")
            self.assertEqual(row["headers"]["Authorization"], "Bearer " + TOKEN)
            self.assertEqual(
                row["headers"]["Accept"], "application/json, text/event-stream"
            )
            if number:
                self.assertEqual(
                    row["headers"]["Mcp-Session-Id"], "synthetic-session-1"
                )
        schema = report["tools"][0]["inputSchema"]
        self.assertEqual(schema["required"], ["code"])
        self.assertEqual(schema["properties"]["code"], {"type": "string"})
        raw = client.canonical(report)
        self.assertNotIn(TOKEN.encode(), raw)
        self.assertNotIn(b"synthetic@example.invalid", raw)
        self.assertEqual(report["native_tool_calls"], 0)
        self.assertFalse(report["performance_pass"])

    def test_incremental_sse_notifications_and_multiline_data(self):
        def sse(request):
            status, headers, raw = default_reply(request)
            if status == 202:
                return status, headers, raw
            payload = json.loads(raw)
            raw = json.dumps(payload, indent=2).encode()
            event = (
                b": keepalive\n\nid: ignored\ndata: "
                + client.canonical(
                    {
                        "jsonrpc": "2.0",
                        "method": "notifications/message",
                        "params": {"message": TOKEN},
                    }
                )
                + b"\n\n"
            )
            event += (
                b"event: message\n"
                + b"\n".join(b"data: " + line for line in raw.splitlines())
                + b"\n\n"
            )
            return (
                200,
                {**headers, "Content-Type": "text/event-stream; charset=utf-8"},
                event,
            )

        with peer(sse) as (port, requests):
            report = connection(port).probe()
        self.assertEqual(report["status"], "DISCOVERY_COMPLETE")
        self.assertEqual(report["notifications_received"], 3)
        self.assertEqual(len(requests), 4)
        self.assertNotIn(TOKEN.encode(), client.canonical(report))

    def test_redirect_is_not_followed_or_retried(self):
        with peer(
            lambda _request: (307, {"Location": "http://example.invalid/" + TOKEN}, b"")
        ) as (port, requests):
            with self.assertRaises(client.ProbeError) as caught:
                connection(port).probe()
            self.assertEqual(caught.exception.code, "HTTP_REDIRECT_DENIED")
            self.assertEqual(len(requests), 1)
            self.assertNotIn(TOKEN, str(caught.exception))

    def test_timeout_is_bounded_and_not_retried(self):
        def delayed(request):
            time.sleep(0.3)
            return default_reply(request)

        with peer(delayed) as (port, requests):
            started = time.monotonic()
            with self.assertRaises(client.ProbeError) as caught:
                connection(port, timeout=0.08).probe()
            self.assertLess(time.monotonic() - started, 1.0)
            self.assertEqual(caught.exception.code, "REQUEST_TIMEOUT")
            self.assertEqual(len(requests), 1)

    def test_http_error_body_cannot_leak_secret(self):
        with peer(
            lambda _r: (401, {"Content-Type": "application/json"}, TOKEN.encode())
        ) as (port, requests):
            with self.assertRaises(client.ProbeError) as caught:
                connection(port).probe()
            self.assertEqual(str(caught.exception), "HTTP_STATUS")
            self.assertEqual(len(requests), 1)

    def test_protocol_mismatch_stops_before_initialized(self):
        def mismatched(request):
            status, headers, raw = default_reply(request)
            payload = json.loads(raw)
            payload["result"]["protocolVersion"] = "2024-11-05"
            return status, headers, client.canonical(payload)

        with peer(mismatched) as (port, requests):
            with self.assertRaises(client.ProbeError) as caught:
                connection(port).probe()
            self.assertEqual(caught.exception.code, "PROTOCOL_MISMATCH")
            self.assertEqual(len(requests), 1)

    def test_wrong_response_id_stops_without_retry(self):
        def wrong_id(request):
            status, headers, raw = default_reply(request)
            payload = json.loads(raw)
            payload["id"] = request["id"] + 1
            return status, headers, client.canonical(payload)

        with peer(wrong_id) as (port, requests):
            with self.assertRaises(client.ProbeError) as caught:
                connection(port).probe()
            self.assertEqual(caught.exception.code, "RPC_RESPONSE_ID")
            self.assertEqual(len(requests), 1)

    def test_oversized_declared_response_stops_before_body(self):
        with peer(
            lambda _r: (
                200,
                {
                    "Content-Type": "application/json",
                    "Content-Length": str(client.RESPONSE_LIMIT + 1),
                },
                b"",
            )
        ) as (port, requests):
            with self.assertRaises(client.ProbeError) as caught:
                connection(port).probe()
            self.assertEqual(caught.exception.code, "HTTP_DECLARED_SIZE")
            self.assertEqual(len(requests), 1)

    def test_signed_out_zero_tools_is_explicit(self):
        def signed_out(request):
            status, headers, raw = default_reply(request)
            if request["method"] == "tools/list":
                raw = client.canonical(
                    {"jsonrpc": "2.0", "id": request["id"], "result": {"tools": []}}
                )
            elif request["method"] == "session/status":
                raw = client.canonical(
                    {
                        "jsonrpc": "2.0",
                        "id": request["id"],
                        "result": {"signed_in": False},
                    }
                )
            return status, headers, raw

        with peer(signed_out) as (port, _requests):
            report = connection(port).probe()
        self.assertEqual(report["status"], "DISCOVERY_SIGNED_OUT")
        self.assertEqual(report["tools"], [])
        self.assertFalse(report["session"]["signed_in"])

    def test_tool_rpc_error_retains_only_code_and_does_not_retry(self):
        def locked(request):
            if request["method"] == "tools/list":
                return (
                    200,
                    {"Content-Type": "application/json"},
                    client.canonical(
                        {
                            "jsonrpc": "2.0",
                            "id": request["id"],
                            "error": {
                                "code": -32004,
                                "message": TOKEN,
                                "data": {"email": "private@example.invalid"},
                            },
                        }
                    ),
                )
            return default_reply(request)

        with peer(locked) as (port, requests):
            report = connection(port).probe()
        self.assertEqual(
            report["tool_list_error"], {"code": "RPC_ERROR", "rpc_code": -32004}
        )
        self.assertEqual(report["status"], "DISCOVERY_INCOMPLETE")
        self.assertEqual(sum(r["body"]["method"] == "tools/list" for r in requests), 1)
        self.assertNotIn(TOKEN.encode(), client.canonical(report))


class ObserverTests(unittest.TestCase):
    def test_one_fixed_call_preserves_partial_findings_and_false_acceptance(self):
        state = client.ObservationState()
        with peer(observer_reply) as (port, requests):
            probe = connection(port, state=state)
            report = probe.probe(observe_lesson07=True)
            with self.assertRaises(client.ProbeError):
                probe._post("tools/call", probe._observer_params)
        self.assertEqual(report["status"], "OBSERVATION_COMPLETE")
        self.assertEqual(report["native_tool_calls"], 1)
        self.assertIs(report["native_tool_attempted"], True)
        self.assertIs(report["native_tool_completed"], True)
        self.assertEqual(report["native_material_readback"], client.OBSERVER_STATUS)
        self.assertIsNone(report["observation"]["dirty_sets_equal"])
        self.assertFalse(report["visual_acceptance"])
        self.assertFalse(report["performance_pass"])
        self.assertFalse(report["plugin_execution_defaults_verified"])
        calls = [r for r in requests if r["body"]["method"] == "tools/call"]
        self.assertEqual(len(calls), 1)
        params = calls[0]["body"]["params"]
        self.assertEqual(set(params), {"name", "arguments"})
        self.assertEqual(params["name"], "execute_python")
        self.assertEqual(set(params["arguments"]), {"code", "mode"})
        self.assertEqual(params["arguments"]["mode"], "file")
        self.assertNotIn("file", params["arguments"])
        self.assertEqual(
            report["observer_input_schema_sha256"], client.OBSERVER_SCHEMA_SHA256
        )
        code = params["arguments"]["code"]
        self.assertIn(client.OBSERVER_SHA256, code)
        self.assertIn("collect_json", code)
        self.assertNotIn(TOKEN, code)
        request_size = len(client.canonical(calls[0]["body"]))
        self.assertGreater(request_size, client.CONFIG_LIMIT)
        self.assertLess(request_size, client.OBSERVER_REQUEST_LIMIT)
        self.assertNotIn(TOKEN.encode(), client.canonical(report))

    def test_raw_defaults_not_sanitized_schema_decide_admission(self):
        def changed_default(request):
            status, headers, raw = observer_reply(request)
            if request["method"] == "tools/list":
                payload = json.loads(raw)
                payload["result"]["tools"][0]["inputSchema"]["properties"]["mode"][
                    "default"
                ] = "eval"
                raw = client.canonical(payload)
            return status, headers, raw

        state = client.ObservationState()
        with peer(changed_default) as (port, requests):
            with self.assertRaises(client.ProbeError) as caught:
                connection(port, state=state).probe(observe_lesson07=True)
        self.assertEqual(caught.exception.code, "OBSERVER_TOOL_SCHEMA_UNSUPPORTED")
        self.assertFalse(state.attempted)
        self.assertIs(state.completed, False)
        self.assertEqual(len(requests), 4)

    def test_unknown_required_optional_or_constraint_arguments_rejected(self):
        base = INSTALLED_PYTHON_SCHEMA
        cases = [
            {**base, "required": []},
            {**base, "required": ["python_code"]},
            {**base, "additionalProperties": True},
            {**base, "default": {}},
            {**base, "oneOf": [base]},
            {**base, "properties": {**base["properties"], "mode": {"type": "string"}}},
            {**base, "properties": {**base["properties"], "file": {"type": "number"}}},
            {
                **base,
                "properties": {**base["properties"], "timeout": {"type": "number"}},
            },
            {
                **base,
                "properties": {
                    **base["properties"],
                    "code": {
                        **base["properties"]["code"],
                        "description": "Changed installed contract",
                    },
                },
            },
            {**base, "properties": {"code": {"type": "string", "enum": ["x"]}}},
            {**base, "properties": {"code": {"type": "string", "maxLength": 1}}},
        ]
        for schema in cases:
            with self.subTest(schema=schema), self.assertRaises(client.ProbeError):
                client.validate_observer_schema(schema)
        self.assertEqual(
            client.validate_observer_schema(base), client.OBSERVER_SCHEMA_SHA256
        )

    def test_signed_out_and_incomplete_or_duplicate_inventory_cannot_call(self):
        for fault in ("signed_out", "pagination", "duplicate", "missing_tool"):

            def changed(request):
                status, headers, raw = observer_reply(request)
                if request["method"] == "session/status" and fault == "signed_out":
                    payload = json.loads(raw)
                    payload["result"]["signed_in"] = False
                    raw = client.canonical(payload)
                if request["method"] == "tools/list":
                    payload = json.loads(raw)
                    if fault == "pagination":
                        payload["result"]["nextCursor"] = "repeated"
                    elif fault == "duplicate":
                        payload["result"]["tools"] *= 2
                    elif fault == "missing_tool":
                        payload["result"]["tools"] = []
                    raw = client.canonical(payload)
                return status, headers, raw

            state = client.ObservationState()
            with self.subTest(fault=fault), peer(changed) as (port, requests):
                with self.assertRaises(client.ProbeError):
                    connection(port, state=state).probe(observe_lesson07=True)
                self.assertFalse(state.attempted)
                self.assertFalse(
                    any(r["body"]["method"] == "tools/call" for r in requests)
                )

    def test_changed_source_refuses_before_native_submission(self):
        state = client.ObservationState()
        with (
            peer(observer_reply) as (port, requests),
            mock.patch.object(client, "OBSERVER_SHA256", "0" * 64),
        ):
            with self.assertRaises(client.ProbeError) as caught:
                connection(port, state=state).probe(observe_lesson07=True)
        self.assertEqual(caught.exception.code, "OBSERVER_SOURCE_HASH")
        self.assertFalse(state.attempted)
        self.assertEqual(len(requests), 4)

    def test_inline_program_uses_verified_snapshot_in_fresh_namespace(self):
        source = (
            b'assert __name__ == "_yacs_lesson07_observer"\n'
            b'assert "existing_private_global" not in globals()\n'
            b'def collect_json():\n    return \'{"status":"synthetic"}\'\n'
        )
        with tempfile.TemporaryDirectory() as directory:
            source_path = Path(directory) / client.OBSERVER_FILE
            source_path.write_bytes(source)
            digest = hashlib.sha256(source).hexdigest()
            with (
                mock.patch.object(
                    client, "__file__", str(Path(directory) / "client.py")
                ),
                mock.patch.object(client, "OBSERVER_SHA256", digest),
            ):
                code = client.observer_loader()
            namespace = {"existing_private_global": object()}
            stdout = io.StringIO()
            # The remote program must not revisit the host source path.
            source_path.write_text('raise AssertionError("EXECUTED_CHANGED_SOURCE")')
            with (
                mock.patch("sys.stdout", stdout),
                mock.patch.object(
                    Path, "open", side_effect=AssertionError("Native file I/O")
                ),
                mock.patch.object(
                    builtins, "open", side_effect=AssertionError("Native file I/O")
                ),
                mock.patch.object(
                    io, "open", side_effect=AssertionError("Native file I/O")
                ),
            ):
                exec(code, namespace, namespace)
            self.assertEqual(
                set(namespace), {"existing_private_global", "__builtins__"}
            )
            self.assertEqual(stdout.getvalue().count(client.OBSERVER_TAG), 1)
            envelope = json.loads(stdout.getvalue()[len(client.OBSERVER_TAG) :])
            self.assertEqual(envelope["observer_sha256"], digest)
            self.assertEqual(envelope["observation"], {"status": "synthetic"})
            with self.assertRaisesRegex(RuntimeError, "OBSERVER_SOURCE_HASH"):
                exec(code.replace("synthetic", "tampered"), {})
            self.assertNotIn(str(source_path), code)
            # A new request cannot accept the changed local source.
            with (
                mock.patch.object(
                    client, "__file__", str(Path(directory) / "client.py")
                ),
                mock.patch.object(client, "OBSERVER_SHA256", digest),
                self.assertRaisesRegex(client.ProbeError, "OBSERVER_SOURCE_HASH"),
            ):
                client.observer_loader()
            self.assertFalse((Path(directory) / "__pycache__").exists())

    def test_real_pinned_collector_runs_with_fake_unreal_without_file_io(self):
        from scripts.ue.test_lesson07_observe_editor import Fixture

        fixture = Fixture()
        code = client.observer_loader()
        namespace = {"existing_private_global": object()}
        stdout = io.StringIO()
        with (
            mock.patch.dict(sys.modules, {"unreal": fixture.api}),
            mock.patch("sys.stdout", stdout),
            mock.patch.object(
                Path, "open", side_effect=AssertionError("Native file I/O")
            ),
            mock.patch.object(
                builtins, "open", side_effect=AssertionError("Native file I/O")
            ),
            mock.patch.object(
                io, "open", side_effect=AssertionError("Native file I/O")
            ),
            mock.patch.object(
                os, "open", side_effect=AssertionError("Native file I/O")
            ),
        ):
            exec(code, namespace, namespace)
        fixture.forbidden.assert_not_called()
        self.assertEqual(set(namespace), {"existing_private_global", "__builtins__"})
        self.assertNotIn("_yacs_lesson07_observer", sys.modules)
        self.assertEqual(stdout.getvalue().count(client.OBSERVER_TAG), 1)
        envelope = json.loads(stdout.getvalue()[len(client.OBSERVER_TAG) :])
        self.assertEqual(envelope["observer_sha256"], client.OBSERVER_SHA256)
        self.assertEqual(envelope["observation"]["status"], client.OBSERVER_STATUS)
        self.assertEqual(envelope["observation"]["world"], client.OBSERVER_WORLD)
        self.assertIs(envelope["observation"]["limitations"]["new_captures"], False)
        self.assertIs(
            envelope["observation"]["limitations"]["visual_acceptance"], False
        )

    def test_request_caps_remain_fixed_and_oversize_stops_before_send(self):
        with mock.patch.object(client.http.client, "HTTPConnection") as http:
            with self.assertRaisesRegex(client.ProbeError, "REQUEST_SIZE"):
                connection(19315)._post(
                    "tools/list", {"cursor": "x" * client.CONFIG_LIMIT}
                )
            http.assert_not_called()
        state = client.ObservationState()
        with (
            peer(observer_reply) as (port, requests),
            mock.patch.object(
                client,
                "observer_loader",
                return_value="x" * client.OBSERVER_REQUEST_LIMIT,
            ),
        ):
            with self.assertRaisesRegex(client.ProbeError, "REQUEST_SIZE"):
                connection(port, state=state).probe(observe_lesson07=True)
        self.assertFalse(state.attempted)
        self.assertIs(state.completed, False)
        self.assertEqual(len(requests), 4)
        self.assertFalse(any(r["body"]["method"] == "tools/call" for r in requests))

    def test_one_large_sse_result_only_allowed_for_observer_and_total_is_bounded(self):
        def sse(request):
            status, headers, raw = observer_reply(request)
            if request["method"] == "tools/call":
                value = observation()
                value["synthetic_bounded_diagnostic"] = "x" * (client.LINE_LIMIT + 1)
                payload = {
                    "jsonrpc": "2.0",
                    "id": request["id"],
                    "result": tool_result(value),
                }
                return (
                    200,
                    {"Content-Type": "text/event-stream"},
                    b"data: " + client.canonical(payload) + b"\n\n",
                )
            return status, headers, raw

        with peer(sse) as (port, _requests):
            report = connection(port).probe(observe_lesson07=True)
        self.assertEqual(report["status"], "OBSERVATION_COMPLETE")

        def oversized(request):
            if request["method"] == "tools/call":
                return (
                    200,
                    {
                        "Content-Type": "text/event-stream",
                        "Content-Length": str(client.RESPONSE_LIMIT + 1),
                    },
                    b"",
                )
            return observer_reply(request)

        state = client.ObservationState()
        with peer(oversized) as (port, requests):
            with self.assertRaises(client.ProbeError) as caught:
                connection(port, state=state).probe(observe_lesson07=True)
        self.assertEqual(caught.exception.code, "HTTP_DECLARED_SIZE")
        self.assertTrue(state.attempted)
        self.assertIsNone(state.completed)
        self.assertEqual(sum(r["body"]["method"] == "tools/call" for r in requests), 1)

        def large_discovery(request):
            status, headers, raw = default_reply(request)
            if request["method"] == "initialize":
                payload = json.loads(raw)
                payload["result"]["instructions"] = "x" * client.LINE_LIMIT
                return (
                    200,
                    {**headers, "Content-Type": "text/event-stream"},
                    b"data: " + client.canonical(payload) + b"\n\n",
                )
            return status, headers, raw

        with peer(large_discovery) as (port, _requests):
            with self.assertRaises(client.ProbeError) as caught:
                connection(port).probe()
        self.assertEqual(caught.exception.code, "HTTP_BODY_SIZE")

    def test_tool_timeout_is_attempted_unknown_completion_without_retry(self):
        def delayed(request):
            if request["method"] == "tools/call":
                time.sleep(0.3)
            return observer_reply(request)

        state = client.ObservationState()
        with peer(delayed) as (port, requests):
            with self.assertRaises(client.ProbeError) as caught:
                connection(port, timeout=0.08, state=state).probe(observe_lesson07=True)
        self.assertEqual(caught.exception.code, "REQUEST_TIMEOUT")
        self.assertTrue(state.attempted)
        self.assertIsNone(state.completed)
        self.assertFalse(state.response_received)
        self.assertEqual(sum(r["body"]["method"] == "tools/call" for r in requests), 1)

    def test_cli_retains_sanitized_tool_error_and_unknown_completion_without_retry(
        self,
    ):
        cause = "RuntimeError: synthetic plugin execution failure"
        secret = "OTHER_SYNTHETIC_CREDENTIAL"

        def failed(request):
            if request["method"] == "tools/call":
                return (
                    200,
                    {"Content-Type": "application/json"},
                    client.canonical(
                        {
                            "jsonrpc": "2.0",
                            "id": request["id"],
                            "result": {
                                "isError": True,
                                "content": [
                                    {
                                        "type": "text",
                                        "text": cause
                                        + "\nhttps://example.invalid/private "
                                        + TOKEN
                                        + " synthetic-session-1\nBearer "
                                        + secret,
                                    }
                                ],
                            },
                        }
                    ),
                )
            return observer_reply(request)

        with (
            tempfile.TemporaryDirectory() as directory,
            peer(failed) as (port, requests),
        ):
            output = Path(directory) / "report.json"
            stdout = io.StringIO()

            def from_fixture(_path, *, observe_lesson07, observation_state):
                return connection(port, state=observation_state).probe(
                    observe_lesson07=observe_lesson07
                )

            with (
                mock.patch.object(client, "probe_from_files", side_effect=from_fixture),
                mock.patch("sys.stdout", stdout),
            ):
                code = client.main(
                    [
                        "--identity-receipt",
                        str(Path(directory) / "identity.json"),
                        "--output",
                        str(output),
                        "--observe-lesson07",
                    ]
                )
            raw = output.read_text()
            report = json.loads(raw)
        self.assertEqual(code, 1)
        self.assertEqual(report["status"], "OBSERVATION_FAILED")
        self.assertEqual(report["error_code"], "OBSERVER_TOOL_ERROR")
        self.assertEqual(report["native_tool_calls"], 1)
        self.assertTrue(report["native_tool_attempted"])
        self.assertTrue(report["native_tool_response_received"])
        self.assertIsNone(report["native_tool_completed"])
        self.assertEqual(report["native_material_readback"], "UNVERIFIED")
        self.assertIn(cause, report["native_tool_error"]["sanitized_text"])
        self.assertEqual(report["native_tool_error"]["retained_text_blocks"], 1)
        self.assertFalse(report["native_tool_error"]["text_truncated"])
        for private in (
            TOKEN,
            secret,
            "synthetic-session-1",
            "example.invalid/private",
        ):
            self.assertNotIn(private, raw)
            self.assertNotIn(private, stdout.getvalue())
        self.assertNotIn(cause, stdout.getvalue())
        self.assertEqual(sum(r["body"]["method"] == "tools/call" for r in requests), 1)

    def test_error_redaction_precedes_truncation_and_removes_credentials_and_controls(
        self,
    ):
        secret = "SYNTHETIC_BOUNDARY_SECRET"
        prefix = "x" * (client.OBSERVER_ERROR_TEXT_LIMIT - 5)
        result = {
            "isError": True,
            "content": [{"type": "text", "text": prefix + secret}],
        }
        report = client.observer_error_diagnostic(result, (secret,))
        self.assertEqual(
            report["sanitized_text"],
            (prefix + "[REDACTED]")[: client.OBSERVER_ERROR_TEXT_LIMIT],
        )
        self.assertTrue(report["text_truncated"])
        for sensitive in (
            "Authorization: Basic " + secret,
            '"api_key": "' + secret + '"',
            "password = 'first line\n" + secret + "'",
            "client-secret=" + secret,
            "access_token=" + secret,
            "to\u200bken=" + secret,
            "Bea\x00rer\t" + secret,
            "https://user:" + secret + "@example.invalid/private",
        ):
            with self.subTest(sensitive=sensitive):
                result["content"][0]["text"] = "Cause: plugin failed\n" + sensitive
                report = client.observer_error_diagnostic(result, ())
                self.assertIn("Cause: plugin failed", report["sanitized_text"])
                self.assertNotIn(secret, report["sanitized_text"])
                self.assertTrue(
                    all(char.isprintable() for char in report["sanitized_text"])
                )

    def test_error_diagnostics_bound_blocks_and_ignore_non_error_and_nontext_values(
        self,
    ):
        result = {
            "isError": True,
            "content": [
                {"type": "image", "text": TOKEN},
                {"type": "text", "text": "\ud800\x1b\x00native cause\n"},
            ]
            + [{"type": "text", "text": "x" * 1000}] * 6
            + [{"type": "text", "text": TOKEN}],
            "structuredContent": {"message": TOKEN},
        }
        report = client.observer_error_diagnostic(result, ())
        self.assertEqual(
            len(report["sanitized_text"]), client.OBSERVER_ERROR_TEXT_LIMIT
        )
        self.assertEqual(report["retained_text_blocks"], 7)
        self.assertTrue(report["content_blocks_truncated"])
        self.assertTrue(report["text_truncated"])
        self.assertTrue(report["sanitized_text"].startswith("native cause"))
        self.assertTrue(all(char.isprintable() for char in report["sanitized_text"]))
        self.assertNotIn(TOKEN.encode(), client.canonical(report))
        for flag in (False, 0, 1, "true", None):
            self.assertIsNone(
                client.observer_error_diagnostic({**result, "isError": flag}, ())
            )
        report = client.observer_error_diagnostic(
            {"isError": True, "content": TOKEN}, ()
        )
        self.assertEqual(report["retained_text_blocks"], 0)
        self.assertEqual(report["sanitized_text"], "")

    def test_unsupported_wrapper_reports_only_shape_and_keeps_attempt_unknown(self):
        def wrapped(request):
            if request["method"] == "tools/call":
                wrapper = {
                    "success": True,
                    "output": tool_result()["content"][0]["text"]
                    + "\nUObject pin report: "
                    + TOKEN,
                    "logs": [TOKEN],
                    TOKEN: {TOKEN: TOKEN},
                }
                return (
                    200,
                    {"Content-Type": "application/json"},
                    client.canonical(
                        {
                            "jsonrpc": "2.0",
                            "id": request["id"],
                            "result": {
                                "isError": False,
                                "content": [
                                    {"type": "text", "text": json.dumps(wrapper)}
                                ],
                                TOKEN: TOKEN,
                            },
                        }
                    ),
                )
            return observer_reply(request)

        with (
            tempfile.TemporaryDirectory() as directory,
            peer(wrapped) as (port, requests),
        ):
            output = Path(directory) / "report.json"
            stdout = io.StringIO()

            def from_fixture(_path, *, observe_lesson07, observation_state):
                return connection(port, state=observation_state).probe(
                    observe_lesson07=observe_lesson07
                )

            with (
                mock.patch.object(client, "probe_from_files", side_effect=from_fixture),
                mock.patch("sys.stdout", stdout),
            ):
                code = client.main(
                    [
                        "--identity-receipt",
                        str(Path(directory) / "identity.json"),
                        "--output",
                        str(output),
                        "--observe-lesson07",
                    ]
                )
            report = json.loads(output.read_bytes())
        self.assertEqual(code, 1)
        self.assertEqual(report["status"], "OBSERVATION_FAILED")
        self.assertEqual(report["error_code"], "OBSERVER_RESULT_TAG")
        self.assertEqual(report["native_tool_calls"], 1)
        self.assertTrue(report["native_tool_attempted"])
        self.assertTrue(report["native_tool_response_received"])
        self.assertIsNone(report["native_tool_completed"])
        self.assertEqual(report["native_material_readback"], "UNVERIFIED")
        shape = report["native_tool_result_shape"]
        self.assertEqual(shape["unknown_field_count"], 1)
        block = shape["content_blocks"][0]
        self.assertTrue(block["text_json_parsed"])
        self.assertEqual(block["text_json"]["unknown_field_count"], 1)
        self.assertEqual(block["text_json"]["fields"]["success"], {"type": "boolean"})
        self.assertEqual(
            block["text_json"]["fields"]["logs"], {"type": "array", "count": 1}
        )
        self.assertEqual(block["text_json"]["fields"]["output"]["tag_occurrences"], 1)
        self.assertTrue(
            block["text_json"]["fields"]["output"]["has_uobject_pin_footer"]
        )
        self.assertNotIn(TOKEN.encode(), client.canonical(report))
        self.assertNotIn(TOKEN, stdout.getvalue())
        self.assertEqual(sum(r["body"]["method"] == "tools/call" for r in requests), 1)

    def test_shape_diagnostics_bound_blocks_and_never_echo_unknown_keys_or_types(self):
        shape = client.observer_result_shape(
            {
                "content": [{"type": TOKEN, TOKEN: TOKEN, "text": "\ud800"}] * 20,
                "structuredContent": {"command_result": TOKEN, TOKEN: TOKEN},
                TOKEN: TOKEN,
            }
        )
        self.assertEqual(shape["fields"]["content"], {"type": "array", "count": 20})
        self.assertEqual(len(shape["content_blocks"]), 8)
        self.assertTrue(shape["content_blocks_truncated"])
        self.assertTrue(
            all(block["content_type"] == "other" for block in shape["content_blocks"])
        )
        self.assertTrue(
            all(block["text_json_parsed"] is False for block in shape["content_blocks"])
        )
        self.assertEqual(shape["structured_content"]["unknown_field_count"], 1)
        self.assertEqual(
            shape["structured_content"]["fields"]["command_result"]["type"], "string"
        )
        self.assertNotIn(TOKEN.encode(), client.canonical(shape))
        self.assertLess(len(client.canonical(shape)), 4096)

    def test_untrusted_result_errors_duplicates_wrappers_and_identity_rejected(self):
        bad_results = []
        good = tool_result()
        bad_results.extend(
            [
                {**good, "isError": True},
                {**good, "isError": 0},
                {**good, "content": good["content"] * 2},
                {
                    **good,
                    "content": [
                        {"type": "text", "text": TOKEN + good["content"][0]["text"]}
                    ],
                },
                {**good, "structuredContent": {"output": good["content"][0]["text"]}},
                {
                    **good,
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps({"output": good["content"][0]["text"]}),
                        }
                    ],
                },
            ]
        )
        for field, value in (
            ("pid", 1235),
            ("pid", True),
            ("project_file", "D:/other/project.uproject"),
            ("project", "D:/other"),
            ("world", "/Game/Other.Other"),
            ("status", "PASS"),
            (
                "observed_at_utc",
                (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat(),
            ),
            (
                "observed_at_utc",
                (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
            ),
            (
                "limitations",
                {**observation()["limitations"], "visual_acceptance": True},
            ),
            ("validation", {"visual_or_native_graph_acceptance": True}),
        ):
            bad_results.append(tool_result({**observation(), field: value}))
        wrong_hash = tool_result()
        wrong_hash["content"][0]["text"] = wrong_hash["content"][0]["text"].replace(
            client.OBSERVER_SHA256, "0" * 64
        )
        bad_results.append(wrong_hash)
        for bad in bad_results:

            def reply(request):
                if request["method"] == "tools/call":
                    return (
                        200,
                        {"Content-Type": "application/json"},
                        client.canonical(
                            {"jsonrpc": "2.0", "id": request["id"], "result": bad}
                        ),
                    )
                return observer_reply(request)

            state = client.ObservationState()
            with self.subTest(result=bad), peer(reply) as (port, requests):
                with self.assertRaises(client.ProbeError) as caught:
                    connection(port, state=state).probe(observe_lesson07=True)
                self.assertTrue(state.attempted)
                self.assertIsNone(state.completed)
                self.assertEqual(
                    sum(r["body"]["method"] == "tools/call" for r in requests), 1
                )
                self.assertNotIn(TOKEN, str(caught.exception))

    def test_cli_keeps_attempt_and_completion_after_post_call_file_recheck_failure(
        self,
    ):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            receipt, discovery_path, output = (
                root / "identity.json",
                root / "config.json",
                root / "report.json",
            )

            def changed(request):
                if request["method"] == "tools/call":
                    receipt.write_bytes(receipt.read_bytes() + b" ")
                return observer_reply(request)

            with peer(changed) as (port, requests):
                receipt.write_bytes(client.canonical(identity(port)))
                discovery_path.write_bytes(client.canonical(config(port)))
                original = client.probe_from_files

                def from_fixture(path, **kwargs):
                    return original(path, discovery_path, **kwargs)

                stdout = io.StringIO()
                with (
                    mock.patch.object(client, "WINDOWS_HOST", True),
                    mock.patch.object(
                        client, "probe_from_files", side_effect=from_fixture
                    ),
                    mock.patch("sys.stdout", stdout),
                ):
                    code = client.main(
                        [
                            "--identity-receipt",
                            str(receipt),
                            "--output",
                            str(output),
                            "--observe-lesson07",
                        ]
                    )
            report = json.loads(output.read_bytes())
            self.assertEqual(code, 1)
            self.assertEqual(report["status"], "OBSERVATION_FAILED")
            self.assertEqual(report["error_code"], "INPUT_CHANGED")
            self.assertEqual(report["native_tool_calls"], 1)
            self.assertTrue(report["native_tool_attempted"])
            self.assertTrue(report["native_tool_completed"])
            self.assertEqual(report["native_material_readback"], "UNVERIFIED")
            self.assertIn("native_tool_calls=1", stdout.getvalue())
            self.assertEqual(
                sum(r["body"]["method"] == "tools/call" for r in requests), 1
            )
            self.assertNotIn(TOKEN.encode(), output.read_bytes())

    def test_cli_unexpected_failure_after_send_retains_unknown_completion(self):
        def failed(_identity, **kwargs):
            state = kwargs["observation_state"]
            state.attempted = True
            state.completed = None
            raise ValueError(TOKEN)

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "report.json"
            stdout = io.StringIO()
            with (
                mock.patch.object(client, "probe_from_files", side_effect=failed),
                mock.patch("sys.stdout", stdout),
            ):
                code = client.main(
                    [
                        "--identity-receipt",
                        str(Path(directory) / "identity.json"),
                        "--output",
                        str(output),
                        "--observe-lesson07",
                    ]
                )
            report = json.loads(output.read_bytes())
            self.assertEqual(code, 1)
            self.assertEqual(report["error_code"], "UNEXPECTED_CLIENT_FAILURE")
            self.assertEqual(report["native_tool_calls"], 1)
            self.assertIsNone(report["native_tool_completed"])
            self.assertNotIn(TOKEN.encode(), output.read_bytes())
            self.assertNotIn(TOKEN, stdout.getvalue())


class CaptureTests(unittest.TestCase):
    def test_one_fixed_capture_retains_text_and_never_loads_or_calls_python(self):
        state = client.ObservationState()
        with (
            peer(capture_reply) as (port, requests),
            mock.patch.object(
                client, "observer_loader", side_effect=AssertionError("No Python")
            ) as loader,
        ):
            probe = connection(port, state=state)
            report = probe.probe(capture_lesson07=True)
            with self.assertRaisesRegex(client.ProbeError, "METHOD_NOT_ALLOWED"):
                probe._post("tools/call", probe._capture_params)
        loader.assert_not_called()
        calls = [
            row["body"] for row in requests if row["body"]["method"] == "tools/call"
        ]
        self.assertEqual(len(calls), 1)
        self.assertEqual(
            calls[0]["params"],
            {"name": client.CAPTURE_TOOL, "arguments": {"return_image": False}},
        )
        self.assertEqual(report["status"], "CAPTURE_RESPONSE_RECEIVED")
        self.assertEqual(report["native_tool_calls"], 1)
        self.assertTrue(report["native_tool_attempted"])
        self.assertTrue(report["native_tool_completed"])
        self.assertTrue(report["native_tool_response_received"])
        self.assertEqual(report["native_tool_name"], client.CAPTURE_TOOL)
        self.assertLessEqual(
            client.utc(report["native_tool_started_utc"]),
            client.utc(report["native_tool_response_received_utc"]),
        )
        self.assertEqual(
            report["capture_input_schema_sha256"], client.CAPTURE_SCHEMA_SHA256
        )
        self.assertEqual(report["capture_arguments"], {"return_image": False})
        self.assertEqual(report["capture_result"]["text"], CAPTURE_TEXT)
        self.assertFalse(report["capture_result"]["text_truncated"])
        self.assertEqual(report["capture_result"]["text_block_count"], 1)
        self.assertRegex(report["capture_result"]["response_sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(report["native_material_readback"], "NOT_RUN")
        self.assertFalse(report["capture_file_verified"])
        self.assertFalse(report["visual_acceptance"])
        self.assertNotIn("observer_source_sha256", report)
        self.assertFalse(state.source_verified)

    def test_modes_and_extra_capture_arguments_are_rejected_before_network(self):
        with peer(capture_reply) as (port, requests):
            probe = connection(port)
            with self.assertRaisesRegex(
                client.ProbeError, "NATIVE_MODES_MUTUALLY_EXCLUSIVE"
            ):
                probe.probe(observe_lesson07=True, capture_lesson07=True)
            for arguments in (
                {"return_image": True},
                {"return_image": 0},
                {"return_image": False, "fov": 90},
            ):
                probe._capture_params = {
                    "name": client.CAPTURE_TOOL,
                    "arguments": arguments,
                }
                with self.assertRaisesRegex(client.ProbeError, "CAPTURE_ARGUMENTS"):
                    probe._post("tools/call", probe._capture_params)
        self.assertEqual(requests, [])
        with (
            mock.patch("sys.stderr", io.StringIO()),
            mock.patch.object(client, "probe_from_files") as probe,
        ):
            with self.assertRaises(SystemExit) as caught:
                client.main(
                    [
                        "--identity-receipt",
                        "/unused.json",
                        "--output",
                        "/unused-output.json",
                        "--observe-lesson07",
                        "--capture-lesson07",
                    ]
                )
        self.assertEqual(caught.exception.code, 2)
        probe.assert_not_called()

    def test_schema_drift_missing_tool_and_signed_out_refuse_before_capture(self):
        for fault, expected in (
            ("drift", "CAPTURE_TOOL_SCHEMA_UNSUPPORTED"),
            ("missing", "CAPTURE_TOOL_SCHEMA_UNSUPPORTED"),
            ("signed_out", "CAPTURE_SIGNED_OUT"),
        ):

            def reply(request, fault=fault):
                status, headers, raw = capture_reply(request)
                if request["method"] == "tools/list":
                    payload = json.loads(raw)
                    if fault == "missing":
                        payload["result"]["tools"] = [
                            row
                            for row in payload["result"]["tools"]
                            if row["name"] != client.CAPTURE_TOOL
                        ]
                    elif fault == "drift":
                        payload["result"]["tools"][1]["inputSchema"]["properties"][
                            "return_image"
                        ]["default"] = False
                    raw = client.canonical(payload)
                if request["method"] == "session/status" and fault == "signed_out":
                    payload = json.loads(raw)
                    payload["result"]["signed_in"] = False
                    raw = client.canonical(payload)
                return status, headers, raw

            state = client.ObservationState()
            with self.subTest(fault=fault), peer(reply) as (port, requests):
                with self.assertRaisesRegex(client.ProbeError, expected):
                    connection(port, state=state).probe(capture_lesson07=True)
            self.assertFalse(state.attempted)
            self.assertFalse(state.completed)
            self.assertFalse(
                any(row["body"]["method"] == "tools/call" for row in requests)
            )

    def test_capture_result_failures_keep_one_attempt_and_never_retry_or_fallback(self):
        good = {"isError": False, "content": [{"type": "text", "text": CAPTURE_TEXT}]}
        for result, expected in (
            (
                {
                    "isError": True,
                    "content": [
                        {"type": "text", "text": "Capture refused; Bearer " + TOKEN}
                    ],
                },
                "CAPTURE_TOOL_ERROR",
            ),
            ({**good, "isError": 0}, "CAPTURE_RESULT_SHAPE"),
            (
                {**good, "structuredContent": {"output": CAPTURE_TEXT}},
                "CAPTURE_RESULT_WRAPPER_UNSUPPORTED",
            ),
            (
                {**good, "content": [{"type": "image", "data": TOKEN}]},
                "CAPTURE_RESULT_SHAPE",
            ),
            (
                {
                    **good,
                    "content": [{"type": "text", "text": "IMAGE_BASE64:jpeg:" + TOKEN}],
                },
                "CAPTURE_INLINE_IMAGE_DENIED",
            ),
            ({**good, "content": good["content"] * 9}, "CAPTURE_RESULT_SHAPE"),
            (
                {
                    **good,
                    "content": [
                        {"type": "text", "text": "x" * (client.CAPTURE_TEXT_LIMIT + 1)}
                    ],
                },
                "CAPTURE_RESULT_TEXT_SIZE",
            ),
        ):

            def reply(request, result=result):
                if request["method"] == "tools/call":
                    return (
                        200,
                        {"Content-Type": "application/json"},
                        client.canonical(
                            {"jsonrpc": "2.0", "id": request["id"], "result": result}
                        ),
                    )
                return capture_reply(request)

            state = client.ObservationState()
            with self.subTest(expected=expected), peer(reply) as (port, requests):
                with self.assertRaisesRegex(client.ProbeError, expected):
                    connection(port, state=state).probe(capture_lesson07=True)
            self.assertTrue(state.attempted)
            self.assertTrue(state.response_received)
            self.assertIsNone(state.completed)
            calls = [
                row["body"] for row in requests if row["body"]["method"] == "tools/call"
            ]
            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0]["params"]["name"], client.CAPTURE_TOOL)
            self.assertNotIn(TOKEN.encode(), client.canonical(state.report_fields()))
            if expected == "CAPTURE_TOOL_ERROR":
                self.assertIn("Capture refused", state.tool_error["sanitized_text"])
            if expected == "CAPTURE_RESULT_TEXT_SIZE":
                self.assertTrue(state.capture_result["text_truncated"])
                self.assertEqual(
                    len(state.capture_result["text"]), client.CAPTURE_TEXT_LIMIT
                )

    def test_capture_metadata_redacts_actual_credentials_before_truncation(self):
        state = client.ObservationState(capture_requested=True)
        raw_text = (
            CAPTURE_TEXT
            + "\n"
            + TOKEN
            + " synthetic-session-1\nhttps://private.invalid/path\ntoken='other secret\nsecond line'"
        )
        result = {"isError": False, "content": [{"type": "text", "text": raw_text}]}
        report = client.retain_capture_result(
            result, state, (TOKEN, "synthetic-session-1")
        )
        self.assertTrue(report["text"].startswith(CAPTURE_TEXT))
        for private in (
            TOKEN,
            "synthetic-session-1",
            "private.invalid",
            "other secret",
            "second line",
        ):
            self.assertNotIn(private, report["text"])
        self.assertTrue(
            all(char.isprintable() or char == "\n" for char in report["text"])
        )
        prefix = "x" * (client.CAPTURE_TEXT_LIMIT - 5)
        result["content"][0]["text"] = prefix + TOKEN
        with self.assertRaisesRegex(client.ProbeError, "CAPTURE_RESULT_TEXT_SIZE"):
            client.retain_capture_result(result, state, (TOKEN,))
        self.assertEqual(
            state.capture_result["text"],
            (prefix + "[REDACTED]")[: client.CAPTURE_TEXT_LIMIT],
        )

    def test_capture_timeout_remains_unknown_without_retry(self):
        def delayed(request):
            if request["method"] == "tools/call":
                time.sleep(0.3)
            return capture_reply(request)

        state = client.ObservationState()
        with peer(delayed) as (port, requests):
            with self.assertRaisesRegex(client.ProbeError, "REQUEST_TIMEOUT"):
                connection(port, timeout=0.08, state=state).probe(capture_lesson07=True)
        self.assertTrue(state.attempted)
        self.assertIsNone(state.completed)
        self.assertFalse(state.response_received)
        self.assertIsNone(state.response_received_utc)
        self.assertEqual(
            sum(row["body"]["method"] == "tools/call" for row in requests), 1
        )

    def test_capture_cli_preserves_completion_and_result_after_file_recheck_failure(
        self,
    ):
        for change_identity in (False, True):
            with (
                self.subTest(change_identity=change_identity),
                tempfile.TemporaryDirectory() as directory,
            ):
                root = Path(directory)
                receipt, config_path, output = (
                    root / "identity.json",
                    root / "config.json",
                    root / "report.json",
                )

                def reply(request):
                    if request["method"] == "tools/call" and change_identity:
                        receipt.write_bytes(receipt.read_bytes() + b" ")
                    return capture_reply(request)

                with peer(reply) as (port, requests):
                    receipt.write_bytes(client.canonical(identity(port)))
                    config_path.write_bytes(client.canonical(config(port)))
                    original = client.probe_from_files

                    def from_fixture(path, **kwargs):
                        return original(path, config_path, **kwargs)

                    stdout = io.StringIO()
                    with (
                        mock.patch.object(client, "WINDOWS_HOST", True),
                        mock.patch.object(
                            client, "probe_from_files", side_effect=from_fixture
                        ),
                        mock.patch("sys.stdout", stdout),
                    ):
                        code = client.main(
                            [
                                "--identity-receipt",
                                str(receipt),
                                "--output",
                                str(output),
                                "--capture-lesson07",
                            ]
                        )
                report = json.loads(output.read_bytes())
                self.assertEqual(code, 1 if change_identity else 0)
                self.assertEqual(
                    report["status"],
                    "CAPTURE_FAILED"
                    if change_identity
                    else "CAPTURE_RESPONSE_RECEIVED",
                )
                self.assertTrue(report["native_tool_completed"])
                self.assertEqual(report["native_tool_calls"], 1)
                self.assertEqual(report["capture_result"]["text"], CAPTURE_TEXT)
                self.assertEqual(report["native_material_readback"], "NOT_RUN")
                if change_identity:
                    self.assertEqual(report["error_code"], "INPUT_CHANGED")
                else:
                    self.assertEqual(report["external_host_identity"]["pid"], 1234)
                self.assertIn("L07_WINGMAN_CAPTURE", stdout.getvalue())
                self.assertNotIn(CAPTURE_TEXT, stdout.getvalue())
                self.assertNotIn(TOKEN.encode(), output.read_bytes())
                self.assertEqual(
                    sum(row["body"]["method"] == "tools/call" for row in requests), 1
                )

    def test_failed_capture_cli_preserves_safe_discovery_contracts_without_replay(self):
        def failed(request):
            status, headers, raw = capture_reply(request)
            payload = json.loads(raw) if raw else None
            if request["method"] == "tools/list":
                payload["result"]["tools"][0]["description"] = TOKEN
                raw = client.canonical(payload)
            elif request["method"] == "tools/call":
                payload["result"] = {
                    "isError": True,
                    "content": [
                        {
                            "type": "text",
                            "text": "Native capture refused.\n"
                            + TOKEN
                            + " synthetic-session-1\npassword='private value'",
                        }
                    ],
                }
                raw = client.canonical(payload)
            return status, headers, raw

        with (
            tempfile.TemporaryDirectory() as directory,
            peer(failed) as (port, requests),
        ):
            output = Path(directory) / "report.json"
            stdout = io.StringIO()

            def from_fixture(
                _path, *, observe_lesson07, capture_lesson07, observation_state
            ):
                return connection(port, state=observation_state).probe(
                    observe_lesson07=observe_lesson07, capture_lesson07=capture_lesson07
                )

            with (
                mock.patch.object(client, "probe_from_files", side_effect=from_fixture),
                mock.patch("sys.stdout", stdout),
            ):
                code = client.main(
                    [
                        "--identity-receipt",
                        str(Path(directory) / "identity.json"),
                        "--output",
                        str(output),
                        "--capture-lesson07",
                    ]
                )
            raw = output.read_bytes()
            report = json.loads(raw)
        self.assertEqual(code, 1)
        self.assertEqual(report["status"], "CAPTURE_FAILED")
        self.assertEqual(report["error_code"], "CAPTURE_TOOL_ERROR")
        self.assertEqual(report["native_tool_calls"], 1)
        self.assertIsNone(report["native_tool_completed"])
        self.assertTrue(report["tool_list_complete"])
        contracts = report["installed_tool_contracts"]
        self.assertEqual(set(contracts), client.CONTRACT_TOOLS)
        self.assertEqual(
            contracts["execute_python"],
            {"status": "EXCLUDED", "reason": "CONTRACT_CREDENTIAL"},
        )
        self.assertEqual(
            contracts[client.CAPTURE_TOOL]["inputSchema"], INSTALLED_CAPTURE_SCHEMA
        )
        for name in (
            "read_bp",
            "edit_graph",
            "explore",
            "code_search",
            "edit_texture",
            "edit_material_instance",
            "edit_asset",
            "edit_level",
            "edit_material",
            "edit_material_function",
            "edit_data_asset",
            "download_asset",
            "vault_asset",
        ):
            self.assertEqual(contracts[name]["status"], "RETAINED")
            self.assertEqual(
                contracts[name]["description"], "Installed dedicated operation: " + name
            )
            self.assertEqual(
                contracts[name]["inputSchema"]["properties"]["asset_path"],
                {
                    "type": "string",
                    "default": "/Game/Example",
                    "description": "Installed argument description.",
                },
            )
        for secret in (TOKEN, "synthetic-session-1", "private value"):
            self.assertNotIn(secret.encode(), raw)
            self.assertNotIn(secret, stdout.getvalue())
        self.assertNotIn("tools", report)
        self.assertLess(len(raw), client.RESPONSE_LIMIT)
        self.assertEqual(
            sum(row["body"]["method"] == "tools/list" for row in requests), 1
        )
        self.assertEqual(
            sum(row["body"]["method"] == "tools/call" for row in requests), 1
        )

    def test_discovery_retains_exact_dedicated_contracts_without_calling_them(self):
        with peer(capture_reply) as (port, requests):
            report = connection(port).probe()
        contracts = report["installed_tool_contracts"]
        self.assertEqual(set(contracts), client.CONTRACT_TOOLS)
        self.assertEqual(
            contracts[client.CAPTURE_TOOL]["inputSchema"], INSTALLED_CAPTURE_SCHEMA
        )
        for name in (
            "read_bp",
            "edit_graph",
            "explore",
            "code_search",
            "edit_texture",
            "edit_material_instance",
            "edit_asset",
            "edit_level",
            "edit_material",
            "edit_material_function",
            "edit_data_asset",
            "download_asset",
            "vault_asset",
        ):
            self.assertEqual(contracts[name]["status"], "RETAINED")
            self.assertEqual(
                contracts[name]["description"], "Installed dedicated operation: " + name
            )
            self.assertEqual(
                contracts[name]["inputSchema"]["properties"]["asset_path"],
                {
                    "type": "string",
                    "default": "/Game/Example",
                    "description": "Installed argument description.",
                },
            )
        self.assertEqual(report["native_tool_calls"], 0)
        self.assertFalse(any(row["body"]["method"] == "tools/call" for row in requests))


class InspectionTests(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(
            client, "INSPECTION_SCHEMA_SHA256", INSPECTION_FIXTURE_HASHES
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_six_fixed_reads_keep_raw_evidence_and_refuse_a_seventh_call(self):
        with (
            peer(inspection_reply) as (port, requests),
            mock.patch.object(client, "observer_loader") as loader,
        ):
            probe = connection(port)
            report = probe.probe(inspect_lesson07=True)
            with self.assertRaisesRegex(client.ProbeError, "METHOD_NOT_ALLOWED"):
                probe._post("tools/call", probe._inspection_params)
        loader.assert_not_called()
        calls = [
            r["body"]["params"] for r in requests if r["body"]["method"] == "tools/call"
        ]
        self.assertEqual(
            [call["name"] for call in calls],
            [
                "explore",
                "edit_material_instance",
                "edit_texture",
                "edit_material",
                "edit_asset",
                "code_search",
            ],
        )
        paths = [record["path"] + "/" + record["name"] for record in registry_records()]
        self.assertEqual(calls[1]["arguments"], {"name": paths[1]})
        self.assertEqual(calls[2]["arguments"], {"names": paths[2:]})
        self.assertEqual(
            calls[3]["arguments"],
            {
                "name": paths[0],
                "save": False,
                "section": "properties",
                "limit": 1000,
                "offset": 0,
            },
        )
        self.assertEqual(
            calls[4]["arguments"], {"save_assets": {"paths": paths, "dry_run": True}}
        )
        self.assertIs(calls[3]["arguments"]["save"], False)
        self.assertEqual(report["status"], "INSPECTION_RESPONSES_RECEIVED")
        self.assertEqual(report["native_tool_calls"], 6)
        for key in (
            "native_tool_attempted",
            "native_tool_completed",
            "native_tool_response_received",
            "inspection_registry_verified",
        ):
            self.assertIs(report[key], True)
        self.assertEqual(
            report["native_material_readback"], "RAW_RESPONSES_REVIEW_PENDING"
        )
        self.assertFalse(report["visual_acceptance"])
        self.assertFalse(report["performance_pass"])
        self.assertNotIn("capture_result", report)
        self.assertNotIn("observer_source_sha256", report)
        self.assertEqual(len(report["inspection_results"]), 6)
        for row in report["inspection_results"]:
            self.assertTrue(row["completed"])
            self.assertTrue(row["response_received"])
            self.assertIsNone(row["error_code"])
            self.assertLessEqual(len(client.canonical(row)), 64 * 1024)
        self.assertLessEqual(
            len(client.canonical(report["inspection_results"])), 512 * 1024
        )

    def test_all_schema_pins_are_checked_before_any_native_call(self):
        def drift_last_schema(request):
            status, headers, raw = inspection_reply(request)
            if request["method"] == "tools/list":
                payload = json.loads(raw)
                for tool in payload["result"]["tools"]:
                    if tool["name"] == "code_search":
                        tool["inputSchema"]["new_optional_argument"] = True
                raw = client.canonical(payload)
            return status, headers, raw

        with peer(drift_last_schema) as (port, requests):
            state = client.ObservationState()
            with self.assertRaisesRegex(
                client.ProbeError, "INSPECTION_TOOL_SCHEMA_UNSUPPORTED"
            ):
                connection(port, state=state).probe(inspect_lesson07=True)
        self.assertFalse(any(r["body"]["method"] == "tools/call" for r in requests))
        self.assertEqual(state.report_fields()["native_tool_calls"], 0)
        self.assertFalse(state.completed)

    def test_actual_native_registry_fixture_passes_the_fixed_inspection_batch(self):
        fixture = Path(__file__).parent / "fixtures" / "lesson07_explore_assets_native_20261021.txt"
        raw = fixture.read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), "a595806f3bb85800b99b9ed9a61cd8582a802a9679fc490f13fe523388acd8b1")
        text = raw.decode("utf-8")
        client.verify_inspection_registry(text)

        def actual_registry(request):
            status, headers, raw = inspection_reply(request)
            if request["method"] == "tools/call" and request["params"]["name"] == "explore":
                payload = json.loads(raw)
                payload["result"]["content"][0]["text"] = text
                raw = client.canonical(payload)
            return status, headers, raw

        with peer(actual_registry) as (port, requests):
            report = connection(port).probe(inspect_lesson07=True)
        self.assertEqual(report["status"], "INSPECTION_RESPONSES_RECEIVED")
        self.assertEqual(report["native_tool_calls"], 6)
        self.assertTrue(report["inspection_registry_verified"])
        self.assertEqual(report["inspection_results"][0]["result"]["text"], text)
        self.assertEqual(sum(r["body"]["method"] == "tools/call" for r in requests), 6)

    def test_registry_metadata_is_typed_complete_and_consistent_with_header(self):
        text = registry_text()
        header, encoded = text.split("#json-explore:", 1)
        original = json.loads(encoded)
        cases = [
            ("truncated", value) for value in (True, 0, "false", None)
        ] + [
            (key, value)
            for key in ("shown", "total", "offset", "limit", "raw_from_registry", "loaded_in_shown")
            for value in (False, str(original[key]), original[key] + 1)
        ] + [
            ("mode", "actors"), ("scope", "/Game/Other"),
            ("rows", {"rows": original["rows"]}), ("error", "native error"),
        ]
        for key, value in cases:
            with self.subTest(key=key, value=value), self.assertRaises(client.ProbeError):
                client.verify_inspection_registry(header + "#json-explore:" + json.dumps({**original, key: value}))
        for prefix in ("", " "):
            with self.assertRaises(client.ProbeError):
                client.verify_inspection_registry(text + "\n" + prefix + "#json-explore:" + encoded)

    def test_uncertain_registry_is_retained_and_stops_before_name_only_tools(self):
        records = registry_records()
        missing_mi = [
            row for row in records if row["class"] != "MaterialInstanceConstant"
        ]
        split = [
            {"name": row["name"], "nested": {key: value for key, value in row.items() if key != "name"}}
            for row in records
        ]
        wrong_class = [dict(row) for row in records]
        wrong_class[1]["class"] = "Material"
        wrong_class[1]["class_path"] = "/Script/Engine.Material"
        wrong_class_path = [dict(row) for row in records]
        wrong_class_path[1]["class_path"] = "/Script/Engine.Material"
        unsafe_name = [dict(row) for row in records]
        unsafe_name[1]["name"] = "../MI_Landscape_Instance_YACS"
        wrong_directory = [dict(row) for row in records]
        wrong_directory[1]["path"] = "/Game/Generated/YACS/Lesson07_Unified/Textures"
        duplicate_key = registry_text().replace(
            '"rows":', '"rows": [], "rows":', 1
        )
        for text in (
            registry_text(missing_mi),
            registry_text(split),
            registry_text(wrong_class),
            registry_text(wrong_class_path),
            registry_text(unsafe_name),
            registry_text(wrong_directory),
            registry_text(records + [records[1]]),
            registry_text().replace("shown=11", "shown=10"),
            registry_text().replace("#json-explore:", "unknown-output:"),
            duplicate_key,
        ):

            def uncertain(request):
                status, headers, raw = inspection_reply(request)
                if request["method"] == "tools/call":
                    payload = json.loads(raw)
                    payload["result"]["content"][0]["text"] = text
                    raw = client.canonical(payload)
                return status, headers, raw

            with self.subTest(text=text[:100]), peer(uncertain) as (port, requests):
                state = client.ObservationState()
                with self.assertRaises(client.ProbeError):
                    connection(port, state=state).probe(inspect_lesson07=True)
            self.assertEqual(
                sum(r["body"]["method"] == "tools/call" for r in requests), 1
            )
            self.assertFalse(state.inspection_registry_verified)
            self.assertEqual(state.inspection_results[0]["result"]["text"], text)
            self.assertTrue(state.inspection_results[0]["completed"])
            self.assertIsNone(state.completed)

    def test_failed_batch_cli_preserves_completed_rows_and_redacts_error_without_retry(
        self,
    ):
        for fail_at, timeout in (
            ("edit_texture", False),
            ("edit_material_instance", True),
        ):

            def failed(request):
                status, headers, raw = inspection_reply(request)
                if (
                    request["method"] == "tools/call"
                    and request["params"]["name"] == fail_at
                ):
                    if timeout:
                        time.sleep(0.3)
                    else:
                        payload = json.loads(raw)
                        payload["result"] = {
                            "isError": True,
                            "content": [
                                {
                                    "type": "text",
                                    "text": "Native inspection refused.\n"
                                    + TOKEN
                                    + " synthetic-session-1\npassword=private-value",
                                }
                            ],
                        }
                        raw = client.canonical(payload)
                return status, headers, raw

            with (
                self.subTest(fail_at=fail_at),
                tempfile.TemporaryDirectory() as directory,
                peer(failed) as (port, requests),
            ):
                output = Path(directory) / "report.json"
                stdout = io.StringIO()

                def from_fixture(
                    _path, *, observe_lesson07, inspect_lesson07, observation_state
                ):
                    return connection(
                        port, timeout=0.15 if timeout else 2, state=observation_state
                    ).probe(
                        observe_lesson07=observe_lesson07,
                        inspect_lesson07=inspect_lesson07,
                    )

                with (
                    mock.patch.object(
                        client, "probe_from_files", side_effect=from_fixture
                    ),
                    mock.patch("sys.stdout", stdout),
                ):
                    code = client.main(
                        [
                            "--identity-receipt",
                            str(Path(directory) / "identity.json"),
                            "--output",
                            str(output),
                            "--inspect-lesson07",
                        ]
                    )
                raw = output.read_bytes()
                report = json.loads(raw)
            self.assertEqual(code, 1)
            self.assertEqual(report["status"], "INSPECTION_FAILED")
            self.assertEqual(
                report["error_code"],
                "REQUEST_TIMEOUT" if timeout else "INSPECTION_TOOL_ERROR",
            )
            count = 2 if timeout else 3
            self.assertEqual(report["native_tool_calls"], count)
            self.assertIsNone(report["native_tool_completed"])
            self.assertFalse(report["native_tool_response_received"])
            self.assertTrue(report["inspection_registry_verified"])
            self.assertTrue(report["tool_list_complete"])
            self.assertEqual(
                report["installed_tool_contracts"]["edit_asset"]["inputSchema"],
                INSPECTION_FIXTURE_SCHEMAS["edit_asset"],
            )
            rows = report["inspection_results"]
            self.assertEqual(len(rows), count)
            self.assertTrue(all(row["completed"] is True for row in rows[:-1]))
            self.assertTrue(rows[-1]["attempted"])
            self.assertIsNone(rows[-1]["completed"])
            self.assertIs(rows[-1]["response_received"], not timeout)
            if not timeout:
                self.assertIn("Native inspection refused.", rows[-1]["result"]["text"])
            for secret in (TOKEN, "synthetic-session-1", "private-value"):
                self.assertNotIn(secret.encode(), raw)
                self.assertNotIn(secret, stdout.getvalue())
            self.assertEqual(
                sum(r["body"]["method"] == "tools/call" for r in requests), count
            )
            self.assertEqual(
                sum(r["body"]["method"] == "tools/list" for r in requests), 1
            )

    def test_retained_text_bounds_serialized_unicode_bytes_and_redacts_first(self):
        row = {}
        result = {"content": [{"type": "text", "text": "ą" * (64 * 1024) + TOKEN}]}
        with self.assertRaisesRegex(client.ProbeError, "INSPECTION_RESULT_SIZE"):
            client.retain_inspection_result(result, row, (TOKEN,))
        self.assertLessEqual(len(client.canonical(row)), 64 * 1024)
        self.assertTrue(row["result"]["text_truncated"])
        result["content"][0]["text"] = (
            "Cause\n"
            + TOKEN
            + "\nhttps://example.invalid/private\npassword=private-value"
        )
        client.retain_inspection_result(result, row, (TOKEN,))
        for secret in (TOKEN, "example.invalid/private", "private-value"):
            self.assertNotIn(secret, row["result"]["text"])
        self.assertIn("Cause\n", row["result"]["text"])

    def test_mixed_modes_and_mutated_fixed_requests_refuse_before_network(self):
        with peer(inspection_reply) as (port, requests):
            for other in ("observe_lesson07", "capture_lesson07"):
                with self.assertRaisesRegex(
                    client.ProbeError, "NATIVE_MODES_MUTUALLY_EXCLUSIVE"
                ):
                    connection(port).probe(inspect_lesson07=True, **{other: True})
            probe = connection(port)
            state = probe.observation_state
            state.inspection_requested = True
            state.inspection_schema_sha256 = dict(INSPECTION_FIXTURE_HASHES)
            row = {"attempted": False, "completed": False}
            state.inspection_results.append(row)
            probe._inspection_row = row
            probe._inspection_params = {
                "name": "explore",
                "arguments": {"path": "/Game/Other"},
            }
            with self.assertRaisesRegex(client.ProbeError, "INSPECTION_ARGUMENTS"):
                probe._post("tools/call", probe._inspection_params)
        self.assertEqual(requests, [])


TRIAL_FIXTURE_HASHES = {
    name: INSPECTION_FIXTURE_HASHES[name]
    for name in ("explore", "edit_material_instance", "edit_asset")
}
TRIAL_FIXTURE_HASHES[client.CAPTURE_TOOL] = client.CAPTURE_SCHEMA_SHA256


def trial_snapshot():
    return json.loads((Path(__file__).parent / "fixtures" /
                       "lesson07_macro_baseline_native_20261021.json").read_bytes())


def trial_mi_text(snapshot, path):
    return ("# MATERIAL INSTANCE " + path.rsplit("/", 1)[1]
            + "\nparent = M_Landscape_YACS\n"
            "= saved=false (read-only call - asset untouched, not saved)\n"
            "#json-mi:" + json.dumps(snapshot))


def trial_host_check(host, discovery):
    return {"verified_utc": datetime.now(timezone.utc).isoformat(),
            "pid": host["pid"], "process_start_filetime_utc": "134370120000674689",
            "executable": client.EXECUTABLE,
            "listener": {"address": "127.0.0.1", "port": discovery.port,
                         "pid": host["pid"]}}


class TrialPeer:
    """Stateful native-tool fixture with real captured MI values, no UE calls."""

    def __init__(self):
        self.snapshot = trial_snapshot()
        self.backup = None
        self.calls = []
        self.captures = 0
        self.before = lambda _peer, _params: None
        self.after = lambda _peer, _params, text: text
        self.registry = registry_records()

    def __call__(self, request):
        if request["method"] != "tools/call":
            return inspection_reply(request)
        params = request["params"]
        self.calls.append(params)
        override = self.before(self, params)
        if override is not None:
            result = override
        else:
            name, args = params["name"], params["arguments"]
            if name == "explore":
                text = registry_text(self.registry)
            elif name == "edit_material_instance":
                if "scalars" in args:
                    macro = next(row for row in self.snapshot["scalars"]
                                 if row["name"] == "Macro Tiling")
                    value = args["scalars"][0]["value"]
                    macro["value"] = client.struct.unpack("<f", client.struct.pack("<f", value))[0]
                    text = (f"~ scalar Macro Tiling = {value}\n"
                            "= parent=M_Landscape_YACS; saved=true; failures=0\n")
                else:
                    snapshot = self.backup if args["name"] == client.TRIAL_BACKUP else self.snapshot
                    text = trial_mi_text(snapshot, args["name"])
            elif name == "edit_asset":
                if "duplicate_asset" in args:
                    self.backup = json.loads(json.dumps(self.snapshot))
                    text = "# EDIT ASSET\n= duplicated " + client.TRIAL_BACKUP + "\n= failures=0\n"
                else:
                    text = ("# EDIT ASSET\n~ would save " + client.TRIAL_MI
                            + " (dirty=0)\n= save_assets dry_run: 1 package(s) considered, nothing written\n\n= failures=0\n")
            elif name == "take_viewport_screenshot":
                self.captures += 1
                text = ("Viewport screenshot saved: D:/yacs/project/Saved/LocoHelperAI/ViewportShots/"
                        f"Viewport_LevelEditor_20261021_02010{self.captures}.jpg (956x431, 45551 bytes). "
                        "Image payload NOT inlined (return_image:false). viewport_type=LevelEditor | "
                        "world_name=L_SaCalobra_Lesson07 | is_pie_running=0 | retry_count=1 | "
                        "black_frame_detected=0 | avg_brightness=118.85 | near_black_fraction=0.000")
            else:
                raise AssertionError("Unexpected native fixture tool " + name)
            result = {"isError": False, "content": [{"type": "text", "text": self.after(self, params, text)}]}
        return (200, {"Content-Type": "application/json"},
                client.canonical({"jsonrpc": "2.0", "id": request["id"], "result": result}))


class TrialTests(unittest.TestCase):
    def setUp(self):
        for patcher in (
            mock.patch.object(client, "TRIAL_SCHEMA_SHA256", TRIAL_FIXTURE_HASHES),
            mock.patch.object(client, "verify_trial_host_identity", side_effect=trial_host_check),
            mock.patch.object(client.time, "sleep"),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def run_failure(self, native, code, *, guard=None):
        state = client.ObservationState()
        with peer(native) as (port, _requests):
            probe = connection(port, state=state)
            if guard:
                probe._trial_files_guard = guard
            with self.assertRaisesRegex(client.ProbeError, code):
                probe.probe(trial_macro=True)
        return state

    def test_exact_fixed_twelve_calls_three_captures_and_whole_baseline_restoration(self):
        native = TrialPeer()
        with peer(native) as (port, requests), mock.patch.object(client, "observer_loader") as loader:
            probe = connection(port)
            report = probe.probe(trial_macro=True)
            with self.assertRaisesRegex(client.ProbeError, "METHOD_NOT_ALLOWED"):
                probe._post("tools/call", probe._trial_params)
        loader.assert_not_called()
        mi = "/Game/Generated/YACS/Lesson07_Unified/Materials/MI_Landscape_Instance_YACS"
        backup = "/Game/Generated/YACS/Lesson07_Unified/RepairBackups/MI_PreMacroTrial_20261021"
        camera = {"return_image": False,
                  "camera_location": [-16145.268182324218, 84377.62518478667, 49067.09993071173],
                  "camera_rotation": [-18.85209781522559, 165.400053560734, 0], "fov": 90}
        expected = [
            ("explore", {"path": "/Game/Generated/YACS/Lesson07_Unified", "recursive": True, "limit": 200, "offset": 0}),
            ("edit_material_instance", {"name": mi}),
            ("edit_asset", {"save_assets": {"paths": [mi], "dry_run": True}}),
            ("take_viewport_screenshot", camera),
            ("edit_asset", {"duplicate_asset": {"from": mi, "to": backup}}),
            ("edit_material_instance", {"name": backup}),
            ("edit_material_instance", {"name": mi, "scalars": [{"name": "Macro Tiling", "value": 0.05}]}),
            ("edit_material_instance", {"name": mi}),
            ("take_viewport_screenshot", camera),
            ("edit_material_instance", {"name": mi, "scalars": [{"name": "Macro Tiling", "value": 0.25}]}),
            ("edit_material_instance", {"name": mi}),
            ("take_viewport_screenshot", camera),
        ]
        self.assertEqual(native.calls, [{"name": name, "arguments": args} for name, args in expected])
        self.assertEqual(native.snapshot, trial_snapshot())
        self.assertEqual(native.backup, trial_snapshot())
        self.assertEqual(report["status"], "TRIAL_MACRO_RESTORED_REVIEW_PENDING")
        self.assertEqual(report["native_material_readback"], "TRIAL_BASELINE_RESTORED_CAPTURE_REVIEW_PENDING")
        self.assertEqual(report["native_tool_calls"], 12)
        for key in ("native_tool_attempted", "native_tool_completed", "native_tool_response_received",
                    "trial_registry_verified", "trial_backup_attempted", "trial_backup_verified",
                    "trial_mutation_attempted", "trial_restore_attempted", "trial_restore_verified"):
            self.assertIs(report[key], True, key)
        for key in ("performance_pass", "visual_acceptance"):
            self.assertIs(report[key], False)
        self.assertIsNone(report["trial_manual_restore"])
        self.assertEqual(len(report["trial_host_checks"]), 12)
        self.assertEqual(list(report["trial_captures"]), ["A_baseline", "B_macro_005", "A_restored"])
        for stage, index in (("A_baseline", 4), ("B_macro_005", 9), ("A_restored", 12)):
            row = report["trial_results"][index - 1]
            self.assertEqual(row["index"], index)
            self.assertEqual(row["stage"], stage)
            self.assertEqual(report["trial_captures"][stage], {
                "capture_arguments": camera, "capture_result": row["result"],
                "native_tool_started_utc": row["started_utc"],
                "native_tool_response_received_utc": row["response_received_utc"]})
            self.assertEqual(set(row["result"]), {"text", "text_truncated", "text_block_count", "response_sha256"})
        for row in report["trial_results"]:
            self.assertIs(row["validated"], True)
            self.assertIs(row["completed"], True)
            self.assertIsNone(row["error_code"])
        self.assertNotIn(TOKEN.encode(), client.canonical(report))
        self.assertEqual(sum(r["body"]["method"] == "tools/list" for r in requests), 1)

    def test_fixture_pins_ordered_values_and_overrides_including_layer_duplicates(self):
        snapshot = trial_snapshot()
        self.assertEqual(hashlib.sha256(client.canonical(snapshot)).hexdigest(), client.TRIAL_BASELINE_SHA256)
        self.assertEqual(len(snapshot["scalars"]), 61)
        self.assertGreater(len(snapshot["scalars"]), len({row["name"] for row in snapshot["scalars"]}))
        for change in ("value", "override", "order"):
            changed = trial_snapshot()
            if change == "value":
                changed["scalars"][0]["value"] += 1
            elif change == "override":
                changed["scalars"][0]["overridden"] = not changed["scalars"][0]["overridden"]
            else:
                changed["scalars"][0], changed["scalars"][1] = changed["scalars"][1], changed["scalars"][0]
            with self.subTest(change=change), self.assertRaisesRegex(client.ProbeError, "TRIAL_BASELINE_DRIFT"):
                client.verify_trial_mi(trial_mi_text(changed, client.TRIAL_MI), client.TRIAL_MI, 0.25)

    def test_prewrite_baseline_dirty_backup_and_context_drifts_stop_before_macro(self):
        for case, code, count in (
            ("baseline", "TRIAL_BASELINE_DRIFT", 2),
            ("dirty", "TRIAL_DIRTY_OR_UNKNOWN", 3),
            ("world", "TRIAL_CAPTURE_CONTEXT", 4),
            ("backup", "TRIAL_BASELINE_DRIFT", 6),
            ("exists", "TRIAL_BACKUP_EXISTS", 1),
        ):
            native = TrialPeer()
            if case == "baseline":
                native.snapshot["scalars"][0]["value"] += 1
            if case == "exists":
                native.registry.append({"path": client.TRIAL_BACKUP.rsplit("/", 1)[0],
                                        "name": client.TRIAL_BACKUP.rsplit("/", 1)[1],
                                        "class": "MaterialInstanceConstant", "class_path": "/Script/Engine.MaterialInstanceConstant", "loaded": False})
            def alter(peer, params, text):
                if case == "dirty" and len(peer.calls) == 3:
                    return text.replace("dirty=0", "dirty=1")
                if case == "world" and len(peer.calls) == 4:
                    return text.replace("world_name=L_SaCalobra_Lesson07", "world_name=OtherWorld")
                if case == "backup" and len(peer.calls) == 6:
                    copy = json.loads(json.dumps(peer.backup))
                    copy["scalars"][0]["overridden"] = not copy["scalars"][0]["overridden"]
                    return trial_mi_text(copy, client.TRIAL_BACKUP)
                return text
            native.after = alter
            with self.subTest(case=case):
                state = self.run_failure(native, code)
                self.assertEqual(len(native.calls), count)
                self.assertFalse(state.trial_mutation_attempted)
                self.assertFalse(state.trial_restore_attempted)

    def test_all_trial_schemas_are_pinned_before_native_calls(self):
        native = TrialPeer()
        def changed_schema(request):
            status, headers, raw = native(request)
            if request["method"] == "tools/list":
                payload = json.loads(raw)
                next(t for t in payload["result"]["tools"] if t["name"] == "take_viewport_screenshot")["inputSchema"]["new"] = True
                raw = client.canonical(payload)
            return status, headers, raw
        state = self.run_failure(changed_schema, "TRIAL_TOOL_SCHEMA_UNSUPPORTED")
        self.assertFalse(state.attempted)
        self.assertEqual(native.calls, [])

    def test_fresh_identity_or_input_file_drift_blocks_write_and_recovery(self):
        for source in ("identity", "file"):
            native = TrialPeer()
            def host(host, discovery):
                if len(native.calls) == 6:
                    raise client.ProbeError("TRIAL_IDENTITY_CHANGED")
                return trial_host_check(host, discovery)
            def guard():
                if len(native.calls) == 6:
                    raise client.ProbeError("INPUT_CHANGED")
            with self.subTest(source=source), mock.patch.object(client, "verify_trial_host_identity", side_effect=host if source == "identity" else trial_host_check):
                state = self.run_failure(native, "TRIAL_IDENTITY_CHANGED|INPUT_CHANGED", guard=guard if source == "file" else None)
                self.assertFalse(state.trial_mutation_attempted)
                self.assertEqual(len(native.calls), 6)
                self.assertFalse(state.trial_results[-1]["attempted"])

    def test_capture_denial_after_candidate_restores_once_without_retrying_capture(self):
        native = TrialPeer()
        def deny_b(peer, _params):
            if len(peer.calls) == 9:
                return {"isError": True, "content": [{"type": "text", "text": "Capture access denied; " + TOKEN}]}
        native.before = deny_b
        state = self.run_failure(native, "INSPECTION_TOOL_ERROR")
        self.assertEqual([row["stage"] for row in state.trial_results[-3:]], ["recovery_read", "recovery_restore", "recovery_verify"])
        self.assertEqual(native.snapshot, trial_snapshot())
        self.assertTrue(state.trial_restore_verified)
        self.assertEqual(list(state.trial_captures), ["A_baseline"])
        self.assertEqual(sum("scalars" in c["arguments"] for c in native.calls), 2)
        self.assertEqual(sum(c["name"] == "take_viewport_screenshot" for c in native.calls), 2)
        self.assertIn("Capture access denied", state.trial_results[8]["result"]["text"])
        self.assertNotIn(TOKEN.encode(), client.canonical(state.report_fields()))
        self.assertIsNone(state.completed)

    def test_explicit_mi_denial_is_final_and_never_retried(self):
        for fail_at in (7, 10):
            native = TrialPeer()
            def deny(peer, _params):
                if len(peer.calls) == fail_at:
                    return {"isError": True, "content": [{"type": "text", "text": "Operation denied."}]}
            native.before = deny
            with self.subTest(fail_at=fail_at):
                state = self.run_failure(native, "INSPECTION_TOOL_ERROR")
                self.assertEqual(len(native.calls), fail_at)
                self.assertTrue(state.trial_mutation_attempted)
                self.assertFalse(state.trial_restore_verified)
                self.assertEqual(state.trial_recovery_error, "TRIAL_RECOVERY_DENIED")
                self.assertEqual(state.report_fields()["trial_manual_restore"]["scalars"], [{"name": "Macro Tiling", "value": 0.25}])

    def test_unknown_candidate_with_other_parameter_change_is_not_overwritten(self):
        native = TrialPeer()
        def change_other(peer, _params):
            if len(peer.calls) == 8:
                peer.snapshot["scalars"][0]["value"] += 1
        native.before = change_other
        state = self.run_failure(native, "TRIAL_BASELINE_DRIFT")
        self.assertEqual(len(native.calls), 9)
        self.assertEqual(state.trial_results[-1]["stage"], "recovery_read")
        self.assertFalse(state.trial_restore_attempted)
        self.assertFalse(state.trial_restore_verified)
        self.assertIsNotNone(state.report_fields()["trial_manual_restore"])

    def test_uncertain_apply_response_recovers_only_after_reading_exact_candidate(self):
        native = TrialPeer()
        original = client.DiscoveryClient._read_result
        def timeout_after_apply(probe, *args, **kwargs):
            result = original(probe, *args, **kwargs)
            if len(native.calls) == 7:
                raise client.ProbeError("REQUEST_TIMEOUT")
            return result
        with mock.patch.object(client.DiscoveryClient, "_read_result", timeout_after_apply):
            state = self.run_failure(native, "REQUEST_TIMEOUT")
        self.assertFalse(state.trial_results[6]["response_received"])
        self.assertIsNone(state.trial_results[6]["completed"])
        self.assertEqual([row["stage"] for row in state.trial_results[-3:]], ["recovery_read", "recovery_restore", "recovery_verify"])
        self.assertTrue(state.trial_restore_verified)
        self.assertEqual(native.snapshot, trial_snapshot())

    def test_uncertain_restore_is_not_repeated_and_baseline_can_be_read_verified(self):
        native = TrialPeer()
        original = client.DiscoveryClient._read_result
        def timeout_after_restore(probe, *args, **kwargs):
            result = original(probe, *args, **kwargs)
            if len(native.calls) == 10:
                raise client.ProbeError("REQUEST_TIMEOUT")
            return result
        with mock.patch.object(client.DiscoveryClient, "_read_result", timeout_after_restore):
            state = self.run_failure(native, "REQUEST_TIMEOUT")
        self.assertEqual(len(native.calls), 11)
        self.assertEqual(state.trial_results[-1]["stage"], "recovery_read")
        self.assertTrue(state.trial_restore_verified)
        self.assertEqual(sum("scalars" in c["arguments"] for c in native.calls), 2)

    def test_failed_restore_that_did_not_apply_gets_no_second_restore(self):
        native = TrialPeer()
        original = client.DiscoveryClient._read_result
        def ignore_restore(peer, _params):
            if len(peer.calls) == 10:
                return {"content": [{"type": "text", "text": "No conclusive result"}]}
        native.before = ignore_restore
        def timeout_after_restore(probe, *args, **kwargs):
            result = original(probe, *args, **kwargs)
            if len(native.calls) == 10:
                raise client.ProbeError("REQUEST_TIMEOUT")
            return result
        with mock.patch.object(client.DiscoveryClient, "_read_result", timeout_after_restore):
            state = self.run_failure(native, "REQUEST_TIMEOUT")
        self.assertEqual(len(native.calls), 11)
        self.assertFalse(state.trial_restore_verified)
        self.assertEqual(state.trial_recovery_error, "TRIAL_RESTORE_ALREADY_ATTEMPTED")

    def test_late_identity_failure_leaves_manual_restore_without_new_native_attempt(self):
        native = TrialPeer()
        def change_after_apply(host, discovery):
            if len(native.calls) == 7:
                raise client.ProbeError("TRIAL_IDENTITY_CHANGED")
            return trial_host_check(host, discovery)
        with mock.patch.object(client, "verify_trial_host_identity", side_effect=change_after_apply):
            state = self.run_failure(native, "TRIAL_IDENTITY_CHANGED")
        self.assertEqual(len(native.calls), 7)
        self.assertTrue(state.trial_mutation_attempted)
        self.assertFalse(state.trial_restore_attempted)
        self.assertEqual(state.trial_recovery_error, "TRIAL_RECOVERY_IDENTITY_UNSAFE")

    def test_late_trial_never_mutates_without_full_restoration_reserve(self):
        native = TrialPeer()
        with peer(native) as (port, _requests):
            probe = connection(port)
            original = probe._trial_validate
            def consume_budget(row):
                original(row)
                if row["stage"] == "backup_mi":
                    probe._trial_started = time.monotonic() - 108
            with mock.patch.object(probe, "_trial_validate", side_effect=consume_budget):
                with self.assertRaisesRegex(client.ProbeError, "TRIAL_RESTORE_BUDGET"):
                    probe.probe(trial_macro=True)
            self.assertEqual(len(native.calls), 6)
            self.assertTrue(probe.observation_state.trial_backup_verified)
            self.assertFalse(probe.observation_state.trial_mutation_attempted)

    def test_capture_path_reuse_triggers_restore_and_a2_failure_keeps_verified_restore(self):
        for fail_at in (9, 12):
            native = TrialPeer()
            def reused_path(peer, _params, text):
                if len(peer.calls) == fail_at:
                    return text.replace(f"02010{peer.captures}.jpg", "020101.jpg")
                return text
            native.after = reused_path
            with self.subTest(fail_at=fail_at):
                state = self.run_failure(native, "TRIAL_CAPTURE_PATH_REUSED")
                self.assertTrue(state.trial_restore_verified)
                self.assertEqual(native.snapshot, trial_snapshot())
                self.assertNotIn("A_restored", state.trial_captures)
                self.assertEqual(len(native.calls), 12)
                self.assertEqual(sum("scalars" in c["arguments"] for c in native.calls), 2)

    def test_mixed_modes_and_changed_fixed_arguments_are_rejected_before_network(self):
        with peer(TrialPeer()) as (port, requests):
            for other in ("observe_lesson07", "capture_lesson07", "inspect_lesson07"):
                with self.assertRaisesRegex(client.ProbeError, "NATIVE_MODES_MUTUALLY_EXCLUSIVE"):
                    connection(port).probe(trial_macro=True, **{other: True})
            probe = connection(port)
            state = probe.observation_state
            state.trial_requested = True
            state.trial_schema_sha256 = dict(TRIAL_FIXTURE_HASHES)
            row = {"stage": "registry", "attempted": False}
            state.trial_results.append(row)
            probe._trial_row = row
            probe._trial_params = {"name": "explore", "arguments": {"path": "/Game/Other"}}
            with self.assertRaisesRegex(client.ProbeError, "TRIAL_ARGUMENTS"):
                probe._post("tools/call", probe._trial_params)
        self.assertEqual(requests, [])

    def test_file_entry_point_and_failure_cli_preserve_original_identity_and_typed_flags(self):
        native = TrialPeer()
        with tempfile.TemporaryDirectory() as directory, peer(native) as (port, _requests):
            root = Path(directory)
            receipt, discovery, output = root / "identity.json", root / "discovery.json", root / "bridge.json"
            host = identity(port)
            host["process_start_filetime_utc"] = "134370120000674689"
            receipt.write_bytes(client.canonical(host))
            discovery.write_bytes(client.canonical(config(port)))
            with mock.patch.object(client, "WINDOWS_HOST", True):
                report = client.probe_from_files(receipt, discovery, trial_macro=True)
            self.assertEqual(report["external_host_identity"], client.validate_identity(host, client.Discovery.from_mapping(config(port))))
            self.assertEqual(receipt.read_bytes(), client.canonical(host))
            state = client.ObservationState(trial_requested=True)
            state.trial_external_host_identity = report["external_host_identity"]
            state.trial_mutation_attempted = True
            state.trial_restore_verified = True
            def failed_probe(_receipt, *, observation_state, **options):
                self.assertIs(options["trial_macro"], True)
                observation_state.__dict__.update(state.__dict__)
                raise client.ProbeError("TRIAL_CAPTURE_CONTEXT")
            with mock.patch.object(client, "probe_from_files", side_effect=failed_probe), mock.patch("sys.stdout", new_callable=io.StringIO):
                result = client.main(["--identity-receipt", str(receipt), "--output", str(output), "--trial-macro"])
            self.assertEqual(result, 1)
            failed = json.loads(output.read_bytes())
            self.assertEqual(failed["status"], "TRIAL_MACRO_FAILED")
            self.assertIs(failed["trial_restore_verified"], True)
            self.assertEqual(failed["external_host_identity"], report["external_host_identity"])
            for key in ("trial_mutation_attempted", "trial_restore_verified", "trial_backup_verified", "trial_registry_verified"):
                self.assertIs(type(failed[key]), bool)


def apply_peer():
    native = TrialPeer()
    native.backup = trial_snapshot()
    native.registry.append({
        "path": "/Game/Generated/YACS/Lesson07_Unified/RepairBackups",
        "name": "MI_PreMacroTrial_20261021", "class": "MaterialInstanceConstant",
        "class_path": "/Script/Engine.MaterialInstanceConstant", "loaded": True,
    })
    return native


class ApplyReviewedMacroTests(unittest.TestCase):
    def setUp(self):
        for patcher in (
            mock.patch.object(client, "TRIAL_SCHEMA_SHA256", TRIAL_FIXTURE_HASHES),
            mock.patch.object(client, "verify_trial_host_identity", side_effect=trial_host_check),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.receipt_check = mock.patch.object(client, "verify_reviewed_macro_receipt")
        self.receipt_guard = self.receipt_check.start()
        self.addCleanup(self.receipt_check.stop)

    def failure(self, native, code):
        state = client.ObservationState()
        with peer(native) as (port, _requests):
            with self.assertRaisesRegex(client.ProbeError, code):
                connection(port, state=state).probe(apply_reviewed_macro=True)
        report = state.report_fields()
        self.assertIs(report["apply_verified"], False)
        return state, report

    def test_seven_fixed_calls_apply_only_reviewed_delta_and_keep_existing_backup(self):
        native = apply_peer()
        with tempfile.TemporaryDirectory() as directory, peer(native) as (port, requests):
            root = Path(directory)
            receipt, discovery = root / "identity.json", root / "discovery.json"
            host = identity(port)
            host["process_start_filetime_utc"] = "134370120000674689"
            receipt.write_bytes(client.canonical(host))
            discovery.write_bytes(client.canonical(config(port)))
            with mock.patch.object(client, "WINDOWS_HOST", True), mock.patch.object(client, "observer_loader") as loader:
                report = client.probe_from_files(receipt, discovery, apply_reviewed_macro=True)
        loader.assert_not_called()
        self.assertEqual([c["name"] for c in native.calls], [
            "explore", "edit_material_instance", "edit_asset", "edit_material_instance",
            "edit_material_instance", "edit_material_instance", "take_viewport_screenshot",
        ])
        self.assertEqual(native.calls[0]["arguments"], {
            "path": "/Game/Generated/YACS/Lesson07_Unified", "limit": 200, "offset": 0, "recursive": True,
        })
        mi = "/Game/Generated/YACS/Lesson07_Unified/Materials/MI_Landscape_Instance_YACS"
        backup = "/Game/Generated/YACS/Lesson07_Unified/RepairBackups/MI_PreMacroTrial_20261021"
        self.assertEqual([c["arguments"] for c in native.calls[1:6]], [
            {"name": mi}, {"save_assets": {"paths": [mi], "dry_run": True}}, {"name": backup},
            {"name": mi, "scalars": [{"name": "Macro Tiling", "value": 0.05}]}, {"name": mi},
        ])
        self.assertEqual(native.calls[6]["arguments"], client.trial_capture_arguments())
        expected = trial_snapshot()
        next(row for row in expected["scalars"] if row["name"] == "Macro Tiling")["value"] = 0.05000000074505806
        self.assertEqual(native.snapshot, expected)
        self.assertEqual(native.backup, trial_snapshot())
        self.assertEqual(report["status"], "APPLY_REVIEWED_MACRO_VERIFIED_REVIEW_PENDING")
        self.assertEqual(report["native_material_readback"], "REVIEWED_MACRO_APPLIED_CAPTURE_REVIEW_PENDING")
        self.assertEqual(report["native_tool_calls"], 7)
        self.assertEqual(self.receipt_guard.call_count, len(requests))
        for key in ("apply_verified", "apply_candidate_verified", "apply_reviewed_trial_verified",
                    "apply_mutation_attempted", "apply_registry_verified", "apply_backup_verified",
                    "native_tool_attempted", "native_tool_completed", "native_tool_response_received"):
            self.assertIs(report[key], True, key)
        for key in ("apply_backup_attempted", "apply_restore_attempted", "apply_restore_verified",
                    "performance_pass", "visual_acceptance"):
            self.assertIs(report[key], False, key)
        self.assertIsNone(report["apply_manual_restore"])
        self.assertFalse(any(key.startswith("trial_") for key in report))
        self.assertEqual(list(report["apply_captures"]), ["B_applied_macro_005"])
        row = report["apply_results"][6]
        self.assertEqual((row["index"], row["stage"]), (7, "B_applied_macro_005"))
        self.assertEqual(report["apply_captures"]["B_applied_macro_005"], {
            "capture_arguments": row["arguments"], "capture_result": row["result"],
            "native_tool_started_utc": row["started_utc"],
            "native_tool_response_received_utc": row["response_received_utc"],
        })
        self.assertEqual(report["external_host_identity"], client.validate_identity(host, client.Discovery.from_mapping(config(port))))
        self.assertEqual(report["apply_reviewed_trial_sha256"], "e901c56e83821e771816be8f4dff49cfdad21c015f0b516cd06368cce9d072f4")
        self.assertEqual(report["apply_reviewed_trial_path"], r"D:\yacs\lesson07-remote\reports\39532652532-1\bridge.json")
        self.assertEqual(report["apply_reviewed_trial_source_commit"], "71914188cbdaeac200074b8a070e2f44ed50e501")

    def test_reviewed_receipt_hash_is_mandatory_before_any_rpc(self):
        self.receipt_check.stop()
        raw = b"Synthetic reviewed A/B/A receipt for checksum admission only"
        with mock.patch.object(client, "read_bounded", return_value=raw) as read:
            with self.assertRaisesRegex(client.ProbeError, "APPLY_REVIEWED_TRIAL_HASH"):
                client.verify_reviewed_macro_receipt()
            read.assert_called_once_with(client.APPLY_REVIEWED_TRIAL_PATH, client.RESPONSE_LIMIT)
            with mock.patch.object(client, "APPLY_REVIEWED_TRIAL_SHA256", hashlib.sha256(raw).hexdigest()):
                client.verify_reviewed_macro_receipt()
        with mock.patch.object(client, "read_bounded", side_effect=client.ProbeError("READ_DENIED")):
            with self.assertRaisesRegex(client.ProbeError, "APPLY_REVIEWED_TRIAL_UNAVAILABLE"):
                client.verify_reviewed_macro_receipt()
        with mock.patch.object(client, "read_bounded", return_value=raw), peer(apply_peer()) as (port, requests):
            state = client.ObservationState()
            with self.assertRaisesRegex(client.ProbeError, "APPLY_REVIEWED_TRIAL_HASH"):
                connection(port, state=state).probe(apply_reviewed_macro=True)
        self.assertEqual(requests, [])
        self.assertFalse(state.apply_reviewed_trial_verified)
        self.assertFalse(state.trial_mutation_attempted)

    def test_missing_wrong_class_or_changed_backup_and_current_drift_refuse_prewrite(self):
        for case, code, count in (
            ("missing", "APPLY_EXISTING_BACKUP_REQUIRED", 1),
            ("class", "APPLY_EXISTING_BACKUP_REQUIRED", 1),
            ("baseline", "TRIAL_BASELINE_DRIFT", 2),
            ("backup", "TRIAL_BASELINE_DRIFT", 4),
        ):
            native = apply_peer()
            if case == "missing":
                native.registry.pop()
            elif case == "class":
                native.registry[-1].update({"class": "Texture2D", "class_path": "/Script/Engine.Texture2D"})
            else:
                snapshot = native.snapshot if case == "baseline" else native.backup
                snapshot["scalars"][0]["overridden"] = False
            with self.subTest(case=case):
                state, report = self.failure(native, code)
                self.assertEqual(len(native.calls), count)
                self.assertFalse(report["apply_mutation_attempted"])
                self.assertFalse(report["apply_restore_attempted"])

    def test_apply_capture_failure_performs_one_verified_rollback_within_ten_calls(self):
        native = apply_peer()
        def deny_capture(peer, _params):
            if len(peer.calls) == 7:
                return {"isError": True, "content": [{"type": "text", "text": "Capture denied."}]}
        native.before = deny_capture
        _state, report = self.failure(native, "INSPECTION_TOOL_ERROR")
        self.assertEqual(len(native.calls), 10)
        self.assertEqual([row["stage"] for row in report["apply_results"][-3:]],
                         ["recovery_read", "recovery_restore", "recovery_verify"])
        self.assertTrue(report["apply_restore_verified"])
        self.assertFalse(report["apply_candidate_verified"])
        self.assertEqual(native.snapshot, trial_snapshot())
        self.assertEqual(sum("scalars" in c["arguments"] for c in native.calls), 2)
        self.assertEqual(sum(c["name"] == "take_viewport_screenshot" for c in native.calls), 1)

    def test_apply_mi_denial_is_final_and_no_backup_is_created(self):
        for fail_at in (5, 6):
            native = apply_peer()
            def deny_mi(peer, _params):
                if len(peer.calls) == fail_at:
                    return {"isError": True, "content": [{"type": "text", "text": "MI write/read denied."}]}
            native.before = deny_mi
            with self.subTest(fail_at=fail_at):
                _state, report = self.failure(native, "INSPECTION_TOOL_ERROR")
                self.assertEqual(len(native.calls), fail_at)
                self.assertTrue(report["apply_mutation_attempted"])
                self.assertFalse(report["apply_restore_attempted"])
                self.assertIsNotNone(report["apply_manual_restore"])
                self.assertFalse(any("duplicate_asset" in c["arguments"] for c in native.calls))

    def test_live_candidate_without_confirmed_save_is_not_accepted(self):
        for marker in ("saved=false", "failures=1"):
            native = apply_peer()
            def unconfirmed(peer, _params, text):
                if len(peer.calls) == 5:
                    return text.replace("saved=true" if marker.startswith("saved") else "failures=0", marker)
                return text
            native.after = unconfirmed
            with self.subTest(marker=marker):
                _state, report = self.failure(native, "APPLY_SAVE_UNCONFIRMED")
                self.assertEqual(len(native.calls), 8)
                self.assertTrue(report["apply_restore_verified"])
                self.assertFalse(report["apply_candidate_verified"])
                self.assertEqual(native.snapshot, trial_snapshot())
                self.assertEqual(native.captures, 0)

    def test_changed_review_receipt_after_mutation_blocks_further_rpc_and_reports_manual_restore(self):
        native = apply_peer()
        def checked():
            if len(native.calls) == 5:
                raise client.ProbeError("APPLY_REVIEWED_TRIAL_HASH")
        self.receipt_guard.side_effect = checked
        _state, report = self.failure(native, "APPLY_REVIEWED_TRIAL_HASH")
        self.assertEqual(len(native.calls), 5)
        self.assertFalse(report["apply_reviewed_trial_verified"])
        self.assertFalse(report["apply_restore_attempted"])
        self.assertIsNotNone(report["apply_manual_restore"])

    def test_apply_requires_restoration_reserve_and_rejects_all_mixed_modes(self):
        native = apply_peer()
        with peer(native) as (port, requests):
            for other in ("observe_lesson07", "capture_lesson07", "inspect_lesson07", "trial_macro"):
                with self.assertRaisesRegex(client.ProbeError, "NATIVE_MODES_MUTUALLY_EXCLUSIVE"):
                    connection(port).probe(apply_reviewed_macro=True, **{other: True})
            self.assertEqual(requests, [])
            probe = connection(port)
            original = probe._trial_validate
            def consume_budget(row):
                original(row)
                if row["stage"] == "backup_mi":
                    probe._trial_started = time.monotonic() - 108
            with mock.patch.object(probe, "_trial_validate", side_effect=consume_budget):
                with self.assertRaisesRegex(client.ProbeError, "TRIAL_RESTORE_BUDGET"):
                    probe.probe(apply_reviewed_macro=True)
            self.assertEqual(len(native.calls), 4)
            self.assertFalse(probe.observation_state.trial_mutation_attempted)

    def test_apply_failure_cli_retains_typed_state_without_claiming_success(self):
        def failed(_receipt, *, observation_state, **options):
            self.assertIs(options["apply_reviewed_macro"], True)
            observation_state.trial_mutation_attempted = True
            observation_state.apply_verified = True
            raise client.ProbeError("INPUT_CHANGED")
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(client, "probe_from_files", side_effect=failed), mock.patch("sys.stdout", new_callable=io.StringIO) as stdout:
            output = Path(directory) / "bridge.json"
            result = client.main(["--identity-receipt", str(Path(directory) / "identity.json"),
                                  "--output", str(output), "--apply-reviewed-macro"])
            report = json.loads(output.read_bytes())
        self.assertEqual(result, 1)
        self.assertEqual(report["status"], "APPLY_REVIEWED_MACRO_FAILED")
        self.assertIn("L07_WINGMAN_APPLY_REVIEWED_MACRO", stdout.getvalue())
        self.assertIs(report["apply_verified"], False)
        self.assertIs(report["apply_mutation_attempted"], True)
        self.assertIsNotNone(report["apply_manual_restore"])


def vault_reply(request):
    status, headers, raw = capture_reply(request)
    if request["method"] in {"tools/list", "tools/call"}:
        payload = json.loads(raw)
        if request["method"] == "tools/list":
            for tool in payload["result"]["tools"]:
                if tool["name"] == "vault_asset":
                    tool["inputSchema"] = INSTALLED_VAULT_SCHEMA
        else:
            payload["result"] = {"content": [{"type": "text", "text": (
                "Uninterpreted owned inventory: QUARRY CLIFF\n"
                "UnrelatedPrivatePack /Users/PrivateOwner\n"
                + TOKEN + " synthetic-session-1 password=private-value"
            )}]}
        raw = client.canonical(payload)
    return status, headers, raw


class VaultInspectionTests(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(client, "verify_trial_host_identity", side_effect=trial_host_check)
        self.host_check = patcher.start()
        self.addCleanup(patcher.stop)

    def test_exact_three_filtered_reads_with_fresh_identity_before_and_after_each(self):
        self.assertEqual(hashlib.sha256(client.canonical(INSTALLED_VAULT_SCHEMA)).hexdigest(),
                         "13ca66118e6fa53a0c8e1651374d001f756f7f0633d374bc5367336f06519ebf")
        with peer(vault_reply) as (port, requests), mock.patch.object(client, "observer_loader") as loader:
            probe = connection(port)
            report = probe.probe(inspect_vault=True)
            with self.assertRaisesRegex(client.ProbeError, "METHOD_NOT_ALLOWED"):
                probe._post("tools/call", probe._vault_params)
        loader.assert_not_called()
        calls = [r["body"]["params"] for r in requests if r["body"]["method"] == "tools/call"]
        self.assertEqual(calls, [
            {"name": "vault_asset", "arguments": {"action": "list", "filter": "limestone"}},
            {"name": "vault_asset", "arguments": {"action": "list", "filter": "cliff"}},
            {"name": "vault_asset", "arguments": {"action": "list", "filter": "rock"}},
        ])
        self.assertEqual(report["status"], "VAULT_INSPECTION_RESPONSES_RECEIVED")
        self.assertEqual(report["native_tool_calls"], 3)
        for field in ("native_tool_attempted", "native_tool_completed", "native_tool_response_received"):
            self.assertIs(report[field], True)
        for field in ("vault_inventory_accepted", "vault_license_verified", "visual_acceptance", "performance_pass"):
            self.assertIs(report[field], False)
        self.assertEqual(report["native_material_readback"], "NOT_RUN")
        self.assertNotIn("observer_source_sha256", report)
        self.assertEqual(self.host_check.call_count, 6)
        self.assertEqual([(r["filter"], r["phase"]) for r in report["vault_host_checks"]],
                         [(name, phase) for name in ("limestone", "cliff", "rock") for phase in ("before", "after")])
        public = client.vault_public_report(report)
        self.assertTrue(public["shortlisted_candidate_text_observed"]["Quarry Cliff"])
        self.assertEqual(sum(public["shortlisted_candidate_text_observed"].values()), 1)
        self.assertEqual(len(public["shortlisted_candidate_text_observed"]), 6)
        for value in ("UnrelatedPrivatePack", "PrivateOwner", TOKEN, "synthetic-session-1", "private-value"):
            self.assertNotIn(value.encode(), client.canonical(public))
        for row in report["vault_results"]:
            self.assertLessEqual(len(client.canonical(row)), 64 * 1024)
        self.assertNotIn(TOKEN.encode(), client.canonical(report))

    def test_schema_missing_drift_duplicate_and_signed_out_stop_before_any_inventory(self):
        for failure in ("missing", "drift", "duplicate", "signed_out"):
            def failed(request):
                status, headers, raw = vault_reply(request)
                if request["method"] == "tools/list":
                    payload = json.loads(raw)
                    listing = payload["result"]["tools"]
                    vault = next(tool for tool in listing if tool["name"] == "vault_asset")
                    if failure == "missing":
                        listing.remove(vault)
                    elif failure == "drift":
                        vault["inputSchema"]["additionalProperties"] = False
                    elif failure == "duplicate":
                        listing.append(vault)
                    raw = client.canonical(payload)
                elif request["method"] == "session/status" and failure == "signed_out":
                    payload = json.loads(raw)
                    payload["result"]["signed_in"] = False
                    raw = client.canonical(payload)
                return status, headers, raw
            # Isolate the mutated fixture so the production schema pin never changes.
            with self.subTest(failure=failure), mock.patch(__name__ + ".INSTALLED_VAULT_SCHEMA", json.loads(json.dumps(INSTALLED_VAULT_SCHEMA))):
                with peer(failed) as (port, requests):
                    state = client.ObservationState()
                    with self.assertRaises(client.ProbeError):
                        connection(port, state=state).probe(inspect_vault=True)
                self.assertFalse(any(r["body"]["method"] == "tools/call" for r in requests))
                self.assertEqual(state.report_fields()["native_tool_calls"], 0)

    def test_install_force_arbitrary_filters_extra_keys_and_mixed_modes_are_rejected(self):
        variants = (
            {"action": "install", "name": "Any"},
            {"action": "install", "name": "Any", "dry_run": True},
            {"action": "list", "filter": "limestone", "force": False},
            {"action": "list", "filter": "limestone", "name": "Any"},
            {"action": "list", "filter": "other"},
            {"action": "list"},
        )
        with peer(vault_reply) as (port, requests):
            for other in ("observe_lesson07", "capture_lesson07", "inspect_lesson07", "trial_macro", "apply_reviewed_macro"):
                with self.subTest(mode=other), self.assertRaisesRegex(client.ProbeError, "NATIVE_MODES_MUTUALLY_EXCLUSIVE"):
                    connection(port).probe(inspect_vault=True, **{other: True})
            for arguments in variants:
                probe = connection(port)
                state = probe.observation_state
                state.vault_requested, state.vault_schema_sha256 = True, client.VAULT_SCHEMA_SHA256
                row = {"attempted": False, "completed": False}
                state.vault_results.append(row)
                probe._vault_row = row
                probe._vault_params = {"name": "vault_asset", "arguments": arguments}
                with self.subTest(arguments=arguments), self.assertRaisesRegex(client.ProbeError, "VAULT_INSPECTION_ARGUMENTS"):
                    probe._post("tools/call", probe._vault_params)
            with mock.patch("sys.stderr", io.StringIO()), self.assertRaises(SystemExit):
                client.main(["--identity-receipt", "i.json", "--output", "o.json", "--inspect-vault", "--observe-lesson07"])
        self.assertEqual(requests, [])

    def test_each_identity_drift_stops_without_any_retry_or_further_filter(self):
        for fail_at, expected_calls in ((1, 0), (2, 1), (3, 1), (6, 3)):
            count = 0
            def drift(host, discovery):
                nonlocal count
                count += 1
                if count == fail_at:
                    raise client.ProbeError("TRIAL_IDENTITY_CHANGED")
                return trial_host_check(host, discovery)
            with self.subTest(fail_at=fail_at), peer(vault_reply) as (port, requests):
                self.host_check.side_effect = drift
                state = client.ObservationState()
                with self.assertRaisesRegex(client.ProbeError, "TRIAL_IDENTITY_CHANGED"):
                    connection(port, state=state).probe(inspect_vault=True)
            self.assertEqual(sum(r["body"]["method"] == "tools/call" for r in requests), expected_calls)
            self.assertEqual(state.report_fields()["native_tool_calls"], expected_calls)
            self.assertIsNot(state.completed, True)

    def test_tool_error_timeout_oversize_and_inline_image_stop_at_second_filter(self):
        for failure in ("tool_error", "timeout", "oversize", "inline_image"):
            def failed(request):
                status, headers, raw = vault_reply(request)
                if request["method"] == "tools/call" and request["params"]["arguments"]["filter"] == "cliff":
                    if failure == "timeout":
                        time.sleep(0.2)
                    else:
                        payload = json.loads(raw)
                        if failure == "tool_error":
                            payload["result"]["isError"] = True
                        else:
                            payload["result"]["content"][0]["text"] = "a" * (70 * 1024) if failure == "oversize" else "data:image/jpeg;base64:NOT_REAL"
                        raw = client.canonical(payload)
                return status, headers, raw
            with self.subTest(failure=failure), peer(failed) as (port, requests):
                state = client.ObservationState()
                with self.assertRaises(client.ProbeError):
                    connection(port, timeout=0.1 if failure == "timeout" else 2, state=state).probe(inspect_vault=True)
            self.assertEqual(sum(r["body"]["method"] == "tools/call" for r in requests), 2)
            self.assertEqual(state.report_fields()["native_tool_calls"], 2)
            self.assertTrue(state.vault_results[0]["completed"])
            self.assertIsNone(state.vault_results[1]["completed"])
            self.assertIsNone(state.completed)
            self.assertNotIn(TOKEN.encode(), client.canonical(state.report_fields()))
            self.assertNotIn("UnrelatedPrivatePack", str(client.vault_public_report(state.report_fields())))

    def test_file_guard_checks_before_and_after_each_call_without_replay(self):
        for filename in ("identity.json", "discovery.json"):
            with self.subTest(filename=filename), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                def changed(request):
                    response = vault_reply(request)
                    if request["method"] == "tools/call":
                        (root / filename).write_text("{}")
                    return response
                with peer(changed) as (port, requests), mock.patch.object(client, "WINDOWS_HOST", True):
                    (root / "identity.json").write_bytes(client.canonical(identity(port)))
                    (root / "discovery.json").write_bytes(client.canonical(config(port)))
                    state = client.ObservationState(vault_requested=True)
                    with self.assertRaisesRegex(client.ProbeError, "INPUT_CHANGED"):
                        client.probe_from_files(root / "identity.json", root / "discovery.json",
                                                inspect_vault=True, observation_state=state)
                self.assertEqual(sum(r["body"]["method"] == "tools/call" for r in requests), 1)
                self.assertIsNone(state.completed)
                self.assertTrue(state.vault_results[0]["response_received"])
                self.assertIsNone(state.vault_results[0]["completed"])

    def test_cli_keeps_private_inventory_local_and_emits_only_fixed_shortlist_booleans(self):
        for native_error in (False, True):
            def responded(request):
                status, headers, raw = vault_reply(request)
                if native_error and request["method"] == "tools/call":
                    payload = json.loads(raw)
                    payload["result"]["isError"] = True
                    raw = client.canonical(payload)
                return status, headers, raw
            with self.subTest(native_error=native_error), tempfile.TemporaryDirectory() as directory, peer(responded) as (port, requests):
                root = Path(directory)
                receipt, discovery, output = root / "identity.json", root / "config.json", root / "bridge.json"
                receipt.write_bytes(client.canonical(identity(port)))
                discovery.write_bytes(client.canonical(config(port)))
                real_from_files = client.probe_from_files
                stdout = io.StringIO()
                with mock.patch.object(client, "WINDOWS_HOST", True), mock.patch("sys.stdout", stdout), mock.patch.object(
                    client, "probe_from_files", side_effect=lambda path, **kwargs: real_from_files(path, discovery, **kwargs)
                ):
                    code = client.main(["--identity-receipt", str(receipt), "--output", str(output), "--inspect-vault"])
                private = json.loads(output.read_bytes())
                public = json.loads((root / "vault-summary.json").read_bytes())
            self.assertEqual(code, 1 if native_error else 0)
            self.assertEqual(private["status"], "VAULT_INSPECTION_FAILED" if native_error else "VAULT_INSPECTION_RESPONSES_RECEIVED")
            self.assertEqual(private["native_tool_calls"], 1 if native_error else 3)
            self.assertEqual(private["native_material_readback"], "NOT_RUN")
            self.assertIn("UnrelatedPrivatePack", private["vault_results"][0]["result"]["text"])
            self.assertEqual(public["raw_responses"], "RETAINED_ON_HOST_NOT_PUBLISHED")
            self.assertTrue(public["shortlisted_candidate_text_observed"]["Quarry Cliff"])
            for secret in ("UnrelatedPrivatePack", "PrivateOwner", TOKEN, "synthetic-session-1", "private-value"):
                self.assertNotIn(secret, stdout.getvalue())
                self.assertNotIn(secret.encode(), client.canonical(public))
            self.assertFalse(public["vault_inventory_accepted"])
            self.assertFalse(public["vault_license_verified"])


def source_assets_registry_text(query="tkekcgfn", total=1):
    rows = [{
        "name": f"T_{query.upper()}_{index}", "path": "/Game/Imported/Surfaces",
        "class": "Texture2D", "class_path": "/Script/Engine.Texture2D", "loaded": False,
    } for index in range(min(total, 200))]
    return (
        f"# ASSETS /Game shown={len(rows)} total={total} offset=0 limit=200 loaded=0/{len(rows)}"
        + (" TRUNCATED" if total > 200 else "")
        + "\n#json-explore:" + json.dumps({
            "mode": "assets", "scope": "/Game", "shown": len(rows),
            "total": total, "offset": 0, "limit": 200, "truncated": total > 200,
            "raw_from_registry": total, "loaded_in_shown": 0,
            "filters": {"pattern": "", "query": query, "type": "/Script/Engine.Texture2D",
                        "class_path": "/Script/Engine.Texture2D", "class_filter_recursive": True},
            "rows": rows,
        })
    )


def source_assets_reply(request):
    status, headers, raw = inspection_reply(request)
    if request["method"] == "tools/call":
        name = request["params"]["name"]
        text = source_assets_registry_text(request["params"]["arguments"]["query"]) if name == "explore" else (
            trial_mi_text(trial_snapshot(), client.TRIAL_MI) if name == "edit_material_instance"
            else "#json-textures:" + json.dumps([
                {"path": "/Game/Generated/YACS/Lesson07_Unified/Materials/TA_" + channel + "_Unified",
                 "source_width": 2048, "source_height": 2048}
                for channel in ("Colour", "Normal", "Masks")
            ])
        )
        payload = json.loads(raw)
        payload["result"] = {"content": [{"type": "text", "text": text}]}
        raw = client.canonical(payload)
    return status, headers, raw


class SourceAssetsInspectionTests(unittest.TestCase):
    def setUp(self):
        self.hashes = {name: INSPECTION_FIXTURE_HASHES[name]
                       for name in ("explore", "edit_material_instance", "edit_texture")}
        for target, replacement in (("SOURCE_ASSETS_SCHEMA_SHA256", self.hashes),
                                    ("verify_trial_host_identity", trial_host_check)):
            patcher = mock.patch.object(client, target, replacement)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_seven_fixed_reads_aggregate_all_five_pages_without_pagination(self):
        queries = ("tkekcgfn", "vjulbjjr", "wenocdss", "ultncbnlw", "ullmagidy")
        for totals in ((0, 0, 0, 0, 0), (1, 1, 1, 1, 1), (1, 1, 201, 1, 1)):
            def respond(request, totals=totals):
                status, headers, raw = source_assets_reply(request)
                if request["method"] == "tools/call" and request["params"]["name"] == "explore":
                    query = request["params"]["arguments"]["query"]
                    payload = json.loads(raw)
                    payload["result"]["content"][0]["text"] = source_assets_registry_text(query, totals[queries.index(query)])
                    raw = client.canonical(payload)
                return status, headers, raw
            with self.subTest(totals=totals), peer(respond) as (port, requests), mock.patch.object(client, "observer_loader") as loader:
                probe = connection(port)
                report = probe.probe(inspect_source_assets=True)
                with self.assertRaisesRegex(client.ProbeError, "METHOD_NOT_ALLOWED"):
                    probe._post("tools/call", probe._source_assets_params)
            calls = [r["body"]["params"] for r in requests if r["body"]["method"] == "tools/call"]
            self.assertEqual(calls, [
                {"name": "explore", "arguments": {"path": "/Game", "recursive": True,
                                                  "type": "/Script/Engine.Texture2D", "query": query,
                                                  "limit": 200, "offset": 0}}
                for query in queries
            ] + [
                {"name": "edit_material_instance", "arguments": {"name": "/Game/Generated/YACS/Lesson07_Unified/Materials/MI_Landscape_Instance_YACS"}},
                {"name": "edit_texture", "arguments": {"names": [
                    "/Game/Generated/YACS/Lesson07_Unified/Materials/TA_Colour_Unified",
                    "/Game/Generated/YACS/Lesson07_Unified/Materials/TA_Normal_Unified",
                    "/Game/Generated/YACS/Lesson07_Unified/Materials/TA_Masks_Unified",
                ]}},
            ])
            self.assertEqual(report["status"], "SOURCE_ASSETS_INSPECTION_RESPONSES_RECEIVED")
            self.assertEqual(report["native_tool_calls"], 7)
            for field in ("native_tool_attempted", "native_tool_completed", "native_tool_response_received", "source_assets_registry_verified"):
                self.assertIs(report[field], True)
            self.assertEqual(report["source_assets_queries_verified"], list(queries))
            self.assertIs(report["source_assets_inventory_complete"], all(total <= 200 for total in totals))
            for field in ("source_assets_pagination_attempted", "source_assets_mi_associations_verified",
                          "source_assets_array_source_refs_verified", "visual_acceptance", "performance_pass"):
                self.assertIs(report[field], False)
            self.assertEqual([(r["index"], r["phase"]) for r in report["source_assets_host_checks"]],
                             [(index, phase) for index in range(1, 8) for phase in ("before", "after")])
            self.assertNotIn("observer_source_sha256", report)
            loader.assert_not_called()

    def test_recorded_zero_page_requires_new_scope_and_each_exact_query(self):
        # Exact explore text from run 39654531355 attempt 2; historical scope is not /Game proof.
        recorded = (
            "# ASSETS /Game/Megascans/Surfaces shown=0 total=0 offset=0 limit=200 loaded=0/0\n"
            "# SOURCE asset registry (on-disk index). Rows are registry-only unless tagged 'loaded' "
            "(in memory now); explore does not load assets to list them.\n"
            "# CLASS /Script/Engine.Texture2D (+subclasses, filtered at registry level)\n"
            "# DIAGNOSTIC the registry returned 0 assets for class /Script/Engine.Texture2D "
            "under /Game/Megascans/Surfaces - the class path may not exist or nothing derives from it\n"
            '#json-explore:{"mode":"assets","scope":"/Game/Megascans/Surfaces","shown":0,'
            '"total":0,"offset":0,"limit":200,"truncated":false,"raw_from_registry":0,'
            '"loaded_in_shown":0,"filters":{"pattern":"","query":"","type":"/Script/Engine.Texture2D",'
            '"class_path":"/Script/Engine.Texture2D","class_filter_recursive":true},"rows":[]}\n'
        )
        self.assertEqual(hashlib.sha256(recorded.encode()).hexdigest(),
                         "5017a0dbd8e80efac35fd83dbbd9ecdca39c24b55325abcb0a82539103c3183b")
        with self.assertRaisesRegex(client.ProbeError, "SOURCE_ASSETS_REGISTRY_FORMAT"):
            client.verify_source_assets_registry(recorded, "tkekcgfn")
        for query in ("tkekcgfn", "vjulbjjr", "wenocdss", "ultncbnlw", "ullmagidy"):
            # Only the newly requested scope/filter change; the observed zero-row contract stays exact.
            text = recorded.replace("/Game/Megascans/Surfaces", "/Game").replace('"query":""', '"query":"' + query + '"')
            self.assertIs(client.verify_source_assets_registry(text, query), True)
            wrong_query = "vjulbjjr" if query == "tkekcgfn" else "tkekcgfn"
            with self.assertRaisesRegex(client.ProbeError, "SOURCE_ASSETS_REGISTRY_FILTER"):
                client.verify_source_assets_registry(text, wrong_query)

    def test_wrong_registry_scope_counts_filters_duplicates_and_paths_stop_before_mi(self):
        variants = (
            (3, '"scope": "/Game"', '"scope": "/Game/Other"'),
            (1, '"shown": 1', '"shown": true'),
            (1, '"truncated": false', '"truncated": true'),
            (1, '"class_filter_recursive": true', '"class_filter_recursive": false'),
            (1, '/Imported/Surfaces', '/../Other'),
            (5, '"total": 1', '"total": 2'),
            (4, '"query": "ultncbnlw"', '"query": "tkekcgfn"'),
            (2, 'T_VJULBJJR_0', 'T_Renamed_0'),
            (3, '"rows": [', '"rows": [\n#json-explore:{}\n'),
        )
        for fail_at, old, new in variants:
            calls_seen = 0
            def respond(request, fail_at=fail_at, old=old, new=new):
                nonlocal calls_seen
                status, headers, raw = source_assets_reply(request)
                if request["method"] == "tools/call":
                    calls_seen += 1
                    if calls_seen == fail_at:
                        payload = json.loads(raw)
                        content = payload["result"]["content"][0]
                        self.assertIn(old, content["text"])
                        content["text"] = content["text"].replace(old, new)
                        raw = client.canonical(payload)
                return status, headers, raw
            with self.subTest(fail_at=fail_at, old=old), peer(respond) as (port, requests):
                state = client.ObservationState()
                with self.assertRaises(client.ProbeError):
                    connection(port, state=state).probe(inspect_source_assets=True)
            self.assertEqual(sum(r["body"]["method"] == "tools/call" for r in requests), fail_at)
            self.assertEqual(state.source_assets_queries_verified, list(client.SOURCE_ASSETS_QUERIES[:fail_at - 1]))
            self.assertFalse(state.source_assets_registry_verified)
            self.assertFalse(state.source_assets_inventory_complete)
            self.assertIsNone(state.completed)

    def test_all_three_schema_pins_and_sign_in_are_required_before_native_calls(self):
        for failure in ("explore", "edit_material_instance", "edit_texture", "signed_out"):
            def respond(request, failure=failure):
                status, headers, raw = source_assets_reply(request)
                payload = json.loads(raw) if raw else None
                if request["method"] == "tools/list" and failure != "signed_out":
                    for tool in payload["result"]["tools"]:
                        if tool["name"] == failure:
                            tool["inputSchema"] = {**tool["inputSchema"], "new": True}
                    raw = client.canonical(payload)
                if request["method"] == "session/status" and failure == "signed_out":
                    payload["result"]["signed_in"] = False
                    raw = client.canonical(payload)
                return status, headers, raw
            with (self.subTest(failure=failure), peer(respond) as (port, requests),
                  self.assertRaises(client.ProbeError)):
                connection(port).probe(inspect_source_assets=True)
            self.assertFalse(any(r["body"]["method"] == "tools/call" for r in requests))

    def test_read_errors_timeout_oversize_inline_images_and_wrong_asset_stop_without_retry(self):
        for failure in ("tool_error", "timeout", "oversize", "inline_image", "mi_saved", "wrong_array"):
            def respond(request, failure=failure):
                status, headers, raw = source_assets_reply(request)
                target = "edit_texture" if failure == "wrong_array" else "edit_material_instance"
                if request["method"] == "tools/call" and request["params"]["name"] == target:
                    if failure == "timeout":
                        time.sleep(0.2)
                    else:
                        payload = json.loads(raw)
                        result = payload["result"]
                        if failure == "tool_error":
                            result["isError"] = True
                        else:
                            text = result["content"][0]["text"]
                            result["content"][0]["text"] = (
                                "a" * (70 * 1024) if failure == "oversize"
                                else "data:image/jpeg;base64:NOT_REAL" if failure == "inline_image"
                                else text.replace("saved=false", "saved=true") if failure == "mi_saved"
                                else text.replace("TA_Normal_Unified", "TA_Other_Unified")
                            )
                        raw = client.canonical(payload)
                return status, headers, raw
            with self.subTest(failure=failure), peer(respond) as (port, requests):
                state = client.ObservationState()
                with self.assertRaises(client.ProbeError):
                    connection(port, timeout=0.1 if failure == "timeout" else 2, state=state).probe(inspect_source_assets=True)
            count = 7 if failure == "wrong_array" else 6
            self.assertEqual(sum(r["body"]["method"] == "tools/call" for r in requests), count)
            self.assertEqual(state.report_fields()["native_tool_calls"], count)
            self.assertIsNone(state.completed)
            self.assertEqual(len(state.source_assets_host_checks), count * 2)

    def test_host_change_or_changed_input_stops_with_exact_attempt_accounting(self):
        for fail_at, expected in ((1, 0), (2, 1), (9, 4), (10, 5), (11, 5), (14, 7)):
            checks = 0
            def changed(host, discovery, fail_at=fail_at):
                nonlocal checks
                checks += 1
                if checks == fail_at:
                    raise client.ProbeError("TRIAL_IDENTITY_CHANGED")
                return trial_host_check(host, discovery)
            with self.subTest(fail_at=fail_at), peer(source_assets_reply) as (port, requests), mock.patch.object(client, "verify_trial_host_identity", side_effect=changed):
                state = client.ObservationState()
                with self.assertRaisesRegex(client.ProbeError, "TRIAL_IDENTITY_CHANGED"):
                    connection(port, state=state).probe(inspect_source_assets=True)
            self.assertEqual(sum(r["body"]["method"] == "tools/call" for r in requests), expected)
            self.assertEqual(state.report_fields()["native_tool_calls"], expected)
            self.assertIsNot(state.completed, True)
        for filename in ("identity.json", "discovery.json"):
            with self.subTest(filename=filename), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                def changed_file(request, root=root, filename=filename):
                    result = source_assets_reply(request)
                    if request["method"] == "tools/call":
                        (root / filename).write_text("{}")
                    return result
                with peer(changed_file) as (port, requests), mock.patch.object(client, "WINDOWS_HOST", True):
                    (root / "identity.json").write_bytes(client.canonical(identity(port)))
                    (root / "discovery.json").write_bytes(client.canonical(config(port)))
                    with self.assertRaisesRegex(client.ProbeError, "INPUT_CHANGED"):
                        client.probe_from_files(root / "identity.json", root / "discovery.json", inspect_source_assets=True)
                self.assertEqual(sum(r["body"]["method"] == "tools/call" for r in requests), 1)

    def test_fixed_arguments_modes_and_cli_reject_authoring_and_keep_errors_bounded(self):
        with peer(source_assets_reply) as (port, requests):
            for mode in ("observe_lesson07", "capture_lesson07", "inspect_lesson07", "inspect_vault", "trial_macro", "apply_reviewed_macro", "import_surfaces"):
                with self.subTest(mode=mode), self.assertRaisesRegex(client.ProbeError, "NATIVE_MODES_MUTUALLY_EXCLUSIVE"):
                    connection(port).probe(inspect_source_assets=True, **{mode: True})
            for arguments in ({"path": "/Game/Other"}, {"path": "/Game", "offset": 200},
                              {**client.source_assets_inspection_plan()[0]["arguments"], "query": "another_id"}):
                probe = connection(port)
                state = probe.observation_state
                state.source_assets_requested, state.source_assets_schema_sha256 = True, self.hashes
                row = {"attempted": False, "completed": False}
                state.source_assets_results.append(row)
                probe._source_assets_row = row
                probe._source_assets_params = {"name": "explore", "arguments": arguments}
                with self.assertRaisesRegex(client.ProbeError, "SOURCE_ASSETS_ARGUMENTS"):
                    probe._post("tools/call", probe._source_assets_params)
            # A completed row alone cannot admit the next ID without its verified filter.
            for prior_queries in ([], ["vjulbjjr"]):
                probe = connection(port)
                state = probe.observation_state
                state.source_assets_requested, state.source_assets_schema_sha256 = True, self.hashes
                state.source_assets_queries_verified = prior_queries
                row = {"attempted": False, "completed": False}
                state.source_assets_results = [{"attempted": True, "completed": True}, row]
                probe._source_assets_row = row
                probe._source_assets_params = client.source_assets_inspection_plan()[1]
                with self.assertRaisesRegex(client.ProbeError, "SOURCE_ASSETS_ARGUMENTS"):
                    probe._post("tools/call", probe._source_assets_params)
            self.assertEqual(requests, [])
        for fail in (False, True):
            def respond(request, fail=fail):
                status, headers, raw = source_assets_reply(request)
                if fail and request["method"] == "tools/call":
                    payload = json.loads(raw)
                    payload["result"] = {"isError": True, "content": [{"type": "text", "text": "denied " + TOKEN}]}
                    raw = client.canonical(payload)
                return status, headers, raw
            with self.subTest(fail=fail), tempfile.TemporaryDirectory() as directory, peer(respond) as (port, requests):
                root = Path(directory)
                receipt, discovery, output = root / "identity.json", root / "config.json", root / "bridge.json"
                receipt.write_bytes(client.canonical(identity(port)))
                discovery.write_bytes(client.canonical(config(port)))
                real = client.probe_from_files
                stdout = io.StringIO()
                with mock.patch.object(client, "WINDOWS_HOST", True), mock.patch("sys.stdout", stdout), mock.patch.object(
                    client, "probe_from_files", side_effect=lambda path, real=real, discovery=discovery, **kwargs: real(path, discovery, **kwargs)
                ):
                    code = client.main(["--identity-receipt", str(receipt), "--output", str(output), "--inspect-source-assets"])
                report = json.loads(output.read_bytes())
            self.assertEqual(code, 1 if fail else 0)
            self.assertEqual(report["status"], "SOURCE_ASSETS_INSPECTION_FAILED" if fail else "SOURCE_ASSETS_INSPECTION_RESPONSES_RECEIVED")
            self.assertEqual(report["native_tool_calls"], 1 if fail else 7)
            self.assertEqual(report["native_material_readback"], "RAW_RESPONSES_REVIEW_PENDING")
            self.assertNotIn(TOKEN, stdout.getvalue())
            self.assertNotIn(TOKEN.encode(), client.canonical(report))


class FileTests(unittest.TestCase):
    def test_end_to_end_files_keep_credentials_private_and_output_new(self):
        with tempfile.TemporaryDirectory() as directory, peer() as (port, _requests):
            root = Path(directory)
            config_path, receipt, output = (
                root / "discovery.json",
                root / "identity.json",
                root / "probe.json",
            )
            config_path.write_bytes(client.canonical(config(port)))
            receipt.write_bytes(client.canonical(identity(port)))
            with mock.patch.object(client, "WINDOWS_HOST", True):
                report = client.probe_from_files(receipt, config_path)
            client.write_report(output, report)
            self.assertNotIn(TOKEN.encode(), output.read_bytes())
            self.assertIn(TOKEN.encode(), config_path.read_bytes())
            self.assertEqual(
                report["post_request_host_recheck"], "REQUIRED_FROM_HARNESS"
            )
            with self.assertRaises(client.ProbeError):
                client.write_report(output, {"overwrite": True})

    def test_reparse_input_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, link = root / "source.json", root / "linked.json"
            source.write_bytes(b"{}")
            try:
                link.symlink_to(source)
            except OSError:
                self.skipTest("Symlink creation not permitted")
            with self.assertRaises(client.ProbeError) as caught:
                client.read_bounded(link, 64)
            self.assertEqual(caught.exception.code, "REPARSE_PATH")

    def test_cli_suppresses_unexpected_exception_message(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "probe.json"
            stdout = io.StringIO()
            with (
                mock.patch.object(
                    client, "probe_from_files", side_effect=ValueError(TOKEN)
                ),
                mock.patch("sys.stdout", stdout),
            ):
                code = client.main(
                    [
                        "--identity-receipt",
                        str(Path(directory) / "identity.json"),
                        "--output",
                        str(output),
                    ]
                )
            self.assertEqual(code, 1)
            self.assertNotIn(TOKEN, stdout.getvalue())
            self.assertNotIn(TOKEN.encode(), output.read_bytes())
            self.assertEqual(
                json.loads(output.read_bytes())["error_code"],
                "UNEXPECTED_CLIENT_FAILURE",
            )



class SurfaceImportTests(unittest.TestCase):
    RENDERED_SHA256 = "a" * 64
    SUMMARY = {
        "status": "SURFACE_REPAIR_SAVED_NATIVE_READBACK_PENDING_VISUAL", "saved": True,
        "changed_slots": [0, 3], "classification_changed": False, "terrain_changed": False,
        "normal_flatten_preserved": True, "failure_count": 0,
    }

    def fixture(self, *, deny_import=False, bad_schema=False):
        def reply(request):
            if request["method"] == "tools/list":
                schema = {**INSTALLED_PYTHON_SCHEMA, "extra": True} if bad_schema else INSTALLED_PYTHON_SCHEMA
                result = {"tools": [{"name": "execute_python", "inputSchema": schema},
                                    {"name": "take_viewport_screenshot", "inputSchema": INSTALLED_CAPTURE_SCHEMA}]}
            elif request["method"] == "tools/call":
                importing = request["params"]["name"] == "execute_python"
                denied = importing and deny_import
                text = "Safety gate blocked this call - F49" if denied else (
                    client.SURFACE_TAG + json.dumps(self.SUMMARY) if importing else "synthetic capture")
                result = {"isError": denied, "content": [{"type": "text", "text": text}]}
            else:
                return default_reply(request)
            return 200, {"Content-Type": "application/json"}, client.canonical(
                {"jsonrpc": "2.0", "id": request["id"], "result": result})
        return reply

    @contextmanager
    def admitted(self):
        with (mock.patch.object(client, "verify_surface_source", return_value={
                  "template_sha256": client.SURFACE_IMPORT_SHA256,
                  "rendered_sha256": self.RENDERED_SHA256}),
              mock.patch.object(client, "verify_trial_host_identity", side_effect=lambda i, d: {
                  "verified_utc": datetime.now(timezone.utc).isoformat(), "pid": i["pid"]}),
              mock.patch.object(client, "retain_surface_capture", side_effect=lambda token, row: {"index": row["index"]}),
              mock.patch.object(client, "read_surface_receipt", return_value=self.SUMMARY)):
            yield

    def test_six_fixed_calls_use_one_import_same_before_after_and_review_views(self):
        state = client.ObservationState()
        with peer(self.fixture()) as (port, requests), self.admitted():
            report = connection(port, state=state).probe(import_surfaces=True, surface_run_token="123-1")
        calls = [r["body"]["params"] for r in requests if r["body"]["method"] == "tools/call"]
        self.assertEqual(calls, client.surface_plan("123-1"))
        self.assertEqual(calls[0], calls[2])
        self.assertEqual([call["name"] for call in calls], [client.CAPTURE_TOOL, client.OBSERVER_TOOL] + [client.CAPTURE_TOOL] * 4)
        self.assertEqual([(call["arguments"]["camera_location"], call["arguments"]["camera_rotation"], call["arguments"]["fov"])
                          for call in calls[3:]], [
            ([-810000, -900000, 724000], [-29.462259194079675, 48.01278750418334, 0], 75),
            ([-278375, 199525, 180000], [-9.706195089959548, 45, 0], 50),
            ([-250925, -184475, 33571], [-89.90162277905554, 90, 0], 50),
        ])
        self.assertEqual(set(calls[1]["arguments"]), {"file", "mode"})
        self.assertNotIn("code", calls[1]["arguments"])
        self.assertTrue(report["surface_verified"])
        self.assertEqual(report["native_tool_calls"], 6)
        self.assertEqual(len(report["surface_captures"]), 5)
        self.assertEqual(len(report["surface_host_checks"]), 12)
        self.assertEqual(report["surface_import_template_sha256"], client.SURFACE_IMPORT_SHA256)
        self.assertEqual(report["surface_import_source_sha256"], self.RENDERED_SHA256)
        self.assertFalse(report["visual_acceptance"])

    def test_capture_camera_metadata_must_match_and_restore_every_fixed_view(self):
        self.assertEqual([spec[0] for spec in client.surface_capture_specs().values()], [
            "surface-before.jpg", "surface-after.jpg", "surface-panorama.jpg",
            "surface-puig-major.jpg", "surface-scree.jpg"])
        for index, (_, camera) in client.surface_capture_specs().items():
            location = ",".join(f"{value:.1f}" for value in camera["camera_location"])
            rotation = ",".join(f"{key}={value:.1f}" for key, value in zip(("P", "Y", "R"), camera["camera_rotation"]))
            text = ("D:/yacs/project/Saved/LocoHelperAI/ViewportShots/Viewport_LevelEditor_20261021_022446.jpg "
                    "viewport_type=LevelEditor | world_name=L_SaCalobra_Lesson07 | is_pie_running=0 | black_frame_detected=0 | "
                    f"camera_override=1 | applied_location=({location}) | applied_rotation=({rotation}) | "
                    f"applied_fov={camera['fov']:.1f} | camera_restored=1")
            with self.subTest(index=index):
                client.verify_trial_capture(text, expected=camera)
                for invalid in (text.replace("camera_restored=1", "camera_restored=0"),
                                text.replace("camera_override=1", "camera_override=0"),
                                text.replace(f"applied_fov={camera['fov']:.1f}", "applied_fov=1.0"),
                                text.replace(f"applied_location=({location})", "applied_location=(0.0,0.0,0.0)"),
                                text.replace(f"applied_rotation=({rotation})", "applied_rotation=(P=0.0,Y=0.0,R=0.0)")):
                    with self.assertRaisesRegex(client.ProbeError, "SURFACE_CAPTURE_CAMERA"):
                        client.verify_trial_capture(invalid, expected=camera)
                # Existing macro callers retain the original context-only default.
                client.verify_trial_capture(text.split("camera_override", 1)[0])
                with self.assertRaisesRegex(client.ProbeError, "SURFACE_CAPTURE_CAMERA"):
                    client.retain_surface_capture("123-1", {
                        "index": index, "arguments": {**camera, "fov": 1}, "result": {"text": text}})

    def test_import_denial_stops_once_without_after_capture_or_observer(self):
        state = client.ObservationState()
        with peer(self.fixture(deny_import=True)) as (port, requests), self.admitted():
            with self.assertRaisesRegex(client.ProbeError, "INSPECTION_TOOL_ERROR"):
                connection(port, state=state).probe(import_surfaces=True, surface_run_token="123-1")
        calls = [r["body"]["params"] for r in requests if r["body"]["method"] == "tools/call"]
        self.assertEqual(len(calls), 2)
        self.assertEqual([row["name"] for row in calls], [client.CAPTURE_TOOL, client.OBSERVER_TOOL])
        self.assertFalse(state.surface_verified)
        self.assertIsNone(state.completed)
        self.assertIn("F49", state.tool_error["sanitized_text"])

    def test_schema_drift_stops_before_any_native_call(self):
        with peer(self.fixture(bad_schema=True)) as (port, requests), self.admitted():
            with self.assertRaises(client.ProbeError):
                connection(port).probe(import_surfaces=True, surface_run_token="123-1")
        self.assertFalse(any(r["body"]["method"] == "tools/call" for r in requests))

    def test_paths_and_unsigned_or_changed_importer_are_rejected(self):
        for token in ("../123-1", "123-1/other", "123-0?", "0-1", "123-0", "1;python", None):
            with self.subTest(token=token), self.assertRaises(client.ProbeError):
                client.surface_plan(token)
        with mock.patch.object(client, "read_bounded", return_value=client.surface_source_prefix("123-1") + b"changed importer"):
            with self.assertRaisesRegex(client.ProbeError, "SURFACE_IMPORT_SOURCE_HASH"):
                client.verify_surface_source("123-1")

    def test_file_context_prefix_is_exact_and_body_remains_the_reviewed_template(self):
        template = Path(__file__).with_name(client.SURFACE_IMPORT_FILE).read_bytes()
        self.assertEqual(hashlib.sha256(template).hexdigest(), client.SURFACE_IMPORT_SHA256)
        prefix = (b"__file__ = 'D:/yacs/project/Saved/RuntimeProof/Lesson07SurfaceRepair-20261021/"
                  b"123-1/apply_lesson07_surface_repair.py'\n")
        self.assertEqual(client.surface_source_prefix("123-1"), prefix)
        rendered = prefix + template
        self.assertEqual(client.render_surface_source("123-1", template), rendered)
        with self.assertRaisesRegex(client.ProbeError, "SURFACE_IMPORT_SOURCE_HASH"):
            client.render_surface_source("123-1", template + b"\n")
        with mock.patch.object(client, "read_bounded", return_value=rendered):
            self.assertEqual(client.verify_surface_source("123-1"), {
                "template_sha256": client.SURFACE_IMPORT_SHA256,
                "rendered_sha256": hashlib.sha256(rendered).hexdigest()})
        # A different run, an unstaged template, another statement, altered line
        # endings or any changed body is rejected without executing Python.
        for bad_prefix in (b"", prefix.replace(b"123-1", b"123-2"),
                           prefix.replace(b"D:/yacs/project", b"D:/other/project"),
                           prefix.replace(b"\n", b"\r\n")):
            with self.subTest(prefix=bad_prefix), mock.patch.object(client, "read_bounded", return_value=bad_prefix + template):
                with self.assertRaisesRegex(client.ProbeError, "SURFACE_IMPORT_SOURCE_PREFIX"):
                    client.verify_surface_source("123-1")
        for body in (b"__name__ = '__main__'\n" + template, template + b"\n", template.replace(b"import unreal", b"import other")):
            with self.subTest(body_sha=hashlib.sha256(body).hexdigest()), mock.patch.object(client, "read_bounded", return_value=prefix + body):
                with self.assertRaisesRegex(client.ProbeError, "SURFACE_IMPORT_SOURCE_HASH"):
                    client.verify_surface_source("123-1")

    def test_wrong_file_context_stops_before_any_native_call_and_reports_no_rendered_hash(self):
        template = Path(__file__).with_name(client.SURFACE_IMPORT_FILE).read_bytes()
        rendered = client.surface_source_prefix("123-2") + template
        state = client.ObservationState()
        with peer(self.fixture()) as (port, requests), mock.patch.object(client, "read_bounded", return_value=rendered):
            with self.assertRaisesRegex(client.ProbeError, "SURFACE_IMPORT_SOURCE_PREFIX"):
                connection(port, state=state).probe(import_surfaces=True, surface_run_token="123-1")
        self.assertFalse(any(r["body"]["method"] == "tools/call" for r in requests))
        self.assertIsNone(state.report_fields()["surface_import_source_sha256"])
        self.assertFalse(state.surface_verified)

    def test_native_receipt_cannot_promote_failure_or_geometry_change(self):
        self.assertEqual(client.verify_surface_summary(client.SURFACE_TAG + json.dumps(self.SUMMARY)), self.SUMMARY)
        for update in ({"saved": 1}, {"terrain_changed": True}, {"failure_count": False},
                       {"failure_count": 1}, {"changed_slots": [0, 1, 3]}, {"normal_flatten_preserved": False}):
            with self.subTest(update=update), self.assertRaises(client.ProbeError):
                client.verify_surface_summary(client.SURFACE_TAG + json.dumps({**self.SUMMARY, **update}))

    def test_saved_receipt_must_be_fresh_and_stable(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(client, "SURFACE_ROOT", Path(directory)):
            stage = client.surface_stage("123-1")
            stage.mkdir()
            path = stage / "live-import.json"
            path.write_bytes(client.canonical(self.SUMMARY))
            row = {"started_utc": datetime.now(timezone.utc).isoformat()}
            self.assertEqual(client.read_surface_receipt("123-1", row), self.SUMMARY)
            os.utime(path, (1, 1))
            with self.assertRaisesRegex(client.ProbeError, "SURFACE_RECEIPT_STALE"):
                client.read_surface_receipt("123-1", row)
            path.write_bytes(client.canonical(self.SUMMARY))
            read = client.read_bounded

            def change_after_read(receipt_path, limit):
                raw = read(receipt_path, limit)
                timestamp = path.stat().st_mtime + 1
                os.utime(path, (timestamp, timestamp))
                return raw

            with mock.patch.object(client, "read_bounded", side_effect=change_after_read):
                with self.assertRaisesRegex(client.ProbeError, "SURFACE_RECEIPT_CHANGED"):
                    client.read_surface_receipt("123-1", row)

    def test_workflow_all_1024_intents_require_one_owner_operation(self):
        workflow = Path(__file__).resolve().parents[2] / ".github/workflows/yacs-lesson07-remote-editor.yml"
        source = workflow.read_text(encoding="utf-8")
        markers = ("remote-editor", "observe-editor", "discover-editor", "capture-editor", "inspect-editor",
                   "inspect-vault", "trial-macro", "apply-macro", "import-surfaces", "inspect-source-assets")
        for bits in itertools.product((False, True), repeat=len(markers)):
            selected = {name for name, bit in zip(markers, bits) if bit}
            for job in ("await_ci", "observe_cpu"):
                section = source.split("  " + job + ":", 1)[1]
                expression = section.split("    if: >-", 1)[1].split("    runs-on:", 1)[0]
                for owner in (True, False):
                    expr = expression.replace("github.actor == github.repository_owner", str(owner))
                    expr = re.sub(r"github\.(?:event_name|repository|ref) == '[^']*'", "True", expr)
                    expr = re.sub(r"contains\(github.event.head_commit.message, '\[l07-([^']+)\]'\)",
                                  lambda match: str(match.group(1) in selected), expr)
                    expr = expr.replace("&&", " and ").replace("||", " or ").replace("!", " not ")
                    actual = eval(" ".join(expr.split()), {"__builtins__": {}}, {})
                    expected = owner and len(selected) == 1 and (
                        ("remote-editor" in selected) if job == "await_ci" else ("remote-editor" not in selected))
                    self.assertEqual(actual, expected, (job, selected, owner))

    def test_import_is_mutually_exclusive_with_every_existing_native_mode(self):
        for mode in ("observe_lesson07", "capture_lesson07", "inspect_lesson07", "inspect_vault", "trial_macro", "apply_reviewed_macro"):
            with self.subTest(mode=mode), peer() as (port, requests):
                with self.assertRaisesRegex(client.ProbeError, "NATIVE_MODES_MUTUALLY_EXCLUSIVE"):
                    connection(port).probe(import_surfaces=True, surface_run_token="123-1", **{mode: True})
                self.assertEqual(requests, [])

if __name__ == "__main__":
    unittest.main()
