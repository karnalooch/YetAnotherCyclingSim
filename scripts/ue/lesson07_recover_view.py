"""One-shot Lesson07 viewport recovery through the existing local Wingman bridge.

Owner scope: recover the camera in the existing editor; read the two existing
material instances. No asset/map save, material write, level lifecycle operation,
arbitrary caller payload, retry, new server or change to the frozen observer.
The existing Invoke-YacsLesson07RemoteProbe preflight must succeed first.
Sources: https://ai.locodev.dev/docs/developers/antigravity
https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/UnrealEditorSubsystem
"""
from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from urllib.parse import urlsplit

PROJECT = Path('D:/yacs/project')
REPORTS = Path('D:/yacs/lesson07-remote/reports')
ROOT = '/Game/Generated/YACS/Lesson07_Unified'
ACTIVE = ROOT + '/Materials/MI_Landscape_Instance_YACS'
CANDIDATE = ROOT + '/Materials/SideFX_OneToOne_20261021/MI_Pegasus_Source_YACS'
WORLD = ROOT + '/L_SaCalobra_Lesson07.L_SaCalobra_Lesson07'
SCHEMAS = {
    'execute_python': '021f8f2a2f45d8e2047a61d14f619f302ba99f981925b0c6d7b2c3eed4bd6e08',
    'take_viewport_screenshot': '4ef41b0bf0c6c93d64a049687e0e43565fb351cd484169b58473801840b3dcdc',
    'edit_material_instance': 'f55278fdd0e125dfd8a9844a3508b85ba6f210e3491542dab7239215e2ed73e8',
}
CAMERA_CODE = r'''def _yacs_l07_recover_camera():
    import unreal, math, json
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    expected = '/Game/Generated/YACS/Lesson07_Unified/L_SaCalobra_Lesson07.L_SaCalobra_Lesson07'
    if world is None or world.get_path_name() != expected:
        raise RuntimeError('L07_CAMERA_WRONG_WORLD')
    if editor.get_game_world() is not None:
        raise RuntimeError('L07_CAMERA_PIE_ACTIVE')
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = [a for a in subsystem.get_all_level_actors()
              if a.get_class().get_name() in ('Landscape', 'LandscapeStreamingProxy')]
    if len(actors) != 4:
        raise RuntimeError('L07_CAMERA_EXPECTED_FOUR_LANDSCAPES')
    before = editor.get_level_viewport_camera_info()
    if before is None:
        raise RuntimeError('L07_CAMERA_NO_LEVEL_VIEWPORT')
    def vec(v): return [float(v.x), float(v.y), float(v.z)]
    def rot(r): return [float(r.pitch), float(r.yaw), float(r.roll)]
    transforms = [str(a.get_actor_transform()) for a in actors]
    bounds = []
    for actor in actors:
        origin, extent = actor.get_actor_bounds(False)
        o, e = vec(origin), vec(extent)
        if not all(math.isfinite(v) for v in o + e) or min(e[:2]) <= 100:
            raise RuntimeError('L07_CAMERA_INVALID_LOADED_BOUNDS')
        bounds.append({'actor': actor.get_actor_label(), 'origin': o, 'extent': e})
    # Frame the tile closest to the previous view, from above ALL tile bounds.
    old = vec(before[0])
    chosen = min(bounds, key=lambda b: sum((b['origin'][i] - old[i]) ** 2 for i in (0, 1)))
    center, extent = chosen['origin'], chosen['extent']
    radius = max(extent[:2])
    highest = max(b['origin'][2] + b['extent'][2] for b in bounds)
    position = [center[0] - 1.4 * radius, center[1] - 1.4 * radius,
                highest + 1.2 * radius]
    delta = [center[i] - position[i] for i in range(3)]
    rotation = [math.degrees(math.atan2(delta[2], math.hypot(delta[0], delta[1]))),
                math.degrees(math.atan2(delta[1], delta[0])), 0.0]
    editor.set_level_viewport_camera_info(
        unreal.Vector(x=position[0], y=position[1], z=position[2]),
        unreal.Rotator(pitch=rotation[0], yaw=rotation[1], roll=rotation[2]))
    after = editor.get_level_viewport_camera_info()
    if after is None or max(abs(vec(after[0])[i] - position[i]) for i in range(3)) > 1.0:
        raise RuntimeError('L07_CAMERA_POSITION_READBACK_MISMATCH')
    if max(abs((rot(after[1])[i] - rotation[i] + 180) % 360 - 180) for i in range(3)) > 0.05:
        raise RuntimeError('L07_CAMERA_ROTATION_READBACK_MISMATCH')
    if transforms != [str(a.get_actor_transform()) for a in actors]:
        raise RuntimeError('L07_CAMERA_LANDSCAPE_CHANGED')
    print('YACS_L07_CAMERA:' + json.dumps({
        'world': expected, 'bounds': bounds, 'before': [vec(before[0]), rot(before[1])],
        'after': [vec(after[0]), rot(after[1])], 'transforms_unchanged': True,
        'assets_saved': False, 'material_changed': False}))
_yacs_l07_recover_camera()
del _yacs_l07_recover_camera
'''


def require(ok, code):
    if not ok:
        raise RuntimeError(code)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')


def plan():
    return [
        {'name': 'execute_python', 'arguments': {'code': CAMERA_CODE, 'mode': 'file'}},
        {'name': 'take_viewport_screenshot', 'arguments': {'return_image': False}},
        {'name': 'edit_material_instance', 'arguments': {'name': ACTIVE}},
        {'name': 'edit_material_instance', 'arguments': {'name': CANDIDATE}},
    ]


def endpoint(config):
    require(isinstance(config, dict), 'CONFIG_SHAPE')
    u = urlsplit(config.get('url', ''))
    require(u.scheme == 'http' and u.hostname == '127.0.0.1' and u.path == '/loco'
            and not u.username and not u.password and not u.query and not u.fragment
            and u.port is not None and 1024 <= u.port <= 65535, 'LOOPBACK_ENDPOINT_REQUIRED')
    token = config.get('token')
    require(isinstance(token, str) and 16 <= len(token) <= 4096
            and all(32 < ord(c) < 127 for c in token), 'INVALID_LOCAL_TOKEN')
    return u.port, token


def plain(path):
    path = Path(path)
    for part in [path, *path.parents]:
        if part.exists():
            require(not part.is_symlink() and not (getattr(part.stat(), 'st_file_attributes', 0) & 0x400),
                    'REDIRECTED_PATH')
    return path


def owner(port):
    # Fixed read-only OS query; port has already passed strict numeric validation.
    script = r'''$ErrorActionPreference='Stop'
$p=@(Get-CimInstance Win32_Process -Filter "Name='UnrealEditor.exe'")
if($p.Count -ne 1){throw 'OWNER_SINGLE_EDITOR_REQUIRED'}
$p=$p[0]
if($p.ExecutablePath -ine 'D:\yacs\engine\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe'){throw 'OWNER_EXE'}
if($p.CommandLine -notmatch '(?i)(?:^|[\s\"])D:[\\/]yacs[\\/]project[\\/]YetAnotherCyclingSim\.uproject(?:[\s\"]|$)'){throw 'OWNER_PROJECT'}
if($p.SessionId -le 0){throw 'OWNER_INTERACTIVE_SESSION'}
$l=@(Get-NetTCPConnection -State Listen -LocalPort PORT_VALUE -ErrorAction Stop)
if($l.Count -ne 1 -or $l[0].LocalAddress -cne '127.0.0.1' -or $l[0].OwningProcess -ne $p.ProcessId){throw 'OWNER_LISTENER'}
$process=Get-Process -Id $p.ProcessId
@{pid=[int]$p.ProcessId;start=[string]$process.StartTime.ToUniversalTime().ToFileTimeUtc();session=[int]$p.SessionId;port=PORT_VALUE}|ConvertTo-Json -Compress
'''.replace('PORT_VALUE', str(port))
    run = subprocess.run(['pwsh', '-NoLogo', '-NoProfile', '-NonInteractive', '-Command', script],
                         capture_output=True, text=True, timeout=15, check=False)
    require(run.returncode == 0, 'CURRENT_OWNER_VERIFICATION_FAILED')
    result = json.loads(run.stdout)
    require(set(result) == {'pid', 'start', 'session', 'port'}, 'OWNER_RESULT_SHAPE')
    return result


class Client:
    """Finite local MCP transaction; Wingman approval and F49 checks stay active."""
    def __init__(self, port, token):
        self.port, self.token = port, token
        self.identity = owner(port)
        self.session = None
        self.count = 0
        self.next_call = 0

    def rpc(self, method, params=None, notification=False):
        require(method in ('initialize', 'notifications/initialized', 'tools/list', 'tools/call'), 'RPC_METHOD')
        if method == 'tools/call':
            require(self.next_call < len(plan()) and params == plan()[self.next_call], 'FIXED_CALL_ONLY')
            self.next_call += 1  # A timeout or refusal is never retried.
        require(self.count < 12, 'REQUEST_LIMIT')
        require(owner(self.port) == self.identity, 'OWNER_CHANGED_BEFORE_REQUEST')
        self.count += 1
        request = {'jsonrpc': '2.0', 'method': method}
        if not notification:
            request['id'] = self.count
        if params is not None:
            request['params'] = params
        headers = {'Authorization': 'Bearer ' + self.token, 'Content-Type': 'application/json',
                   'Accept': 'application/json, text/event-stream', 'MCP-Protocol-Version': '2025-03-26'}
        if self.session:
            headers['Mcp-Session-Id'] = self.session
        connection = http.client.HTTPConnection('127.0.0.1', self.port, timeout=25)
        try:
            connection.request('POST', '/loco', canonical(request), headers)
            response = connection.getresponse()
            require(response.status in (200, 202, 204), 'MCP_HTTP_' + str(response.status))
            sid = response.getheader('Mcp-Session-Id')
            if sid:
                require(len(sid) <= 256 and '\r' not in sid and '\n' not in sid, 'SESSION_HEADER')
                self.session = sid
            if notification:
                result = None
            else:
                kind = (response.getheader('Content-Type') or '').split(';')[0].strip()
                if kind == 'application/json':
                    raw = response.read(2 * 1024 * 1024 + 1)
                    require(len(raw) <= 2 * 1024 * 1024, 'RESPONSE_SIZE')
                    message = json.loads(raw)
                else:
                    require(kind == 'text/event-stream', 'RESPONSE_CONTENT_TYPE')
                    data, total = [], 0
                    deadline = time.monotonic() + 25
                    message = None
                    while time.monotonic() < deadline:
                        line = response.readline(128 * 1024 + 1)
                        total += len(line)
                        require(line and len(line) <= 128 * 1024 and total <= 2 * 1024 * 1024, 'SSE_SIZE_OR_EOF')
                        if line in (b'\n', b'\r\n') and data:
                            event = json.loads(b'\n'.join(data)); data = []
                            if event.get('id') == self.count:
                                message = event; break
                            require('id' not in event and 'method' in event, 'UNEXPECTED_SERVER_MESSAGE')
                        elif line.startswith(b'data:'):
                            data.append(line[5:].strip())
                    require(message is not None, 'MCP_DEADLINE')
                require(isinstance(message, dict) and message.get('id') == self.count, 'RPC_RESPONSE_ID')
                require('error' not in message, 'MCP_RPC_REFUSED')
                result = message.get('result')
                require(isinstance(result, dict), 'RPC_RESULT')
                if method == 'tools/call':
                    require(not result.get('isError', False), 'NATIVE_TOOL_REFUSED_NO_RETRY')
                return result
        finally:
            connection.close()
            require(owner(self.port) == self.identity, 'OWNER_CHANGED_AFTER_REQUEST')
        return result


def native_text(result, token, session=None):
    blocks = result.get('content')
    require(isinstance(blocks, list) and 0 < len(blocks) <= 16, 'NATIVE_RESULT_SHAPE')
    require(all(b.get('type') == 'text' and isinstance(b.get('text'), str) for b in blocks), 'NATIVE_TEXT_ONLY')
    text = '\n'.join(b['text'] for b in blocks)
    require(0 < len(text) <= 128 * 1024, 'NATIVE_TEXT_SIZE')
    for secret in (token, session):
        if secret:
            text = text.replace(secret, '[REDACTED]')
    return text


def retain_image(text, destination, started):
    matches = re.findall(r'[A-Za-z]:[/\\][^\r\n\"<>]*?\.jpe?g', text, re.I)
    require(len(matches) == 1, 'CAPTURE_PATH_NOT_UNIQUE')
    source = plain(matches[0])
    expected = plain(PROJECT / 'Saved/LocoHelperAI/ViewportShots').resolve()
    require(source.resolve().is_relative_to(expected), 'CAPTURE_PATH_OUTSIDE_VIEWPORT_SHOTS')
    require(source.is_file() and started - 2 <= source.stat().st_mtime
            and 1024 <= source.stat().st_size <= 8 * 1024 * 1024, 'CAPTURE_NOT_FRESH')
    data = source.read_bytes()
    require(data[:2] == b'\xff\xd8' and data[-2:] == b'\xff\xd9', 'CAPTURE_NOT_JPEG')
    shutil.copyfile(source, plain(destination))
    return hashlib.sha256(data).hexdigest()


def run(args):
    require(os.name == 'nt', 'WINDOWS_HOST_REQUIRED')
    require(re.fullmatch(r'[0-9]{6,16}-[0-9]{1,3}', args.run_token), 'RUN_TOKEN')
    require(re.fullmatch(r'[0-9a-f]{40}', args.expected_head), 'SOURCE_SHA')
    head = subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True, text=True, check=True).stdout.strip()
    require(head == args.expected_head, 'CHECKOUT_SOURCE_MISMATCH')
    base = plain(REPORTS / args.run_token)
    prior = json.loads((base / 'probe.json').read_text(encoding='utf-8-sig'))
    require(prior.get('source_commit') == head and prior.get('identity_stable_across_probe') is True
            and prior.get('client_exit_code') == 0, 'EXISTING_PREFLIGHT_REQUIRED')
    output = plain(base / 'view-recovery')
    output.mkdir(exist_ok=False)
    report = {'source_commit': head, 'status': 'STARTED', 'calls': [], 'material_changed': False,
              'assets_saved': False, 'performance_pass': False, 'visual_acceptance': False}
    protected = [PROJECT / 'Content/Generated/YACS/Lesson07_Unified/L_SaCalobra_Lesson07.umap',
                 PROJECT / 'Content/Generated/YACS/Lesson07_Unified/Materials/MI_Landscape_Instance_YACS.uasset',
                 PROJECT / 'Content/Generated/YACS/Lesson07_Unified/Materials/SideFX_OneToOne_20261021/MI_Pegasus_Source_YACS.uasset']
    def fingerprints():
        result = {}
        for path in protected:
            with plain(path).open('rb') as source:
                result[str(path)] = hashlib.file_digest(source, 'sha256').hexdigest()
        return result
    before = fingerprints()
    try:
        config_path = plain(PROJECT / 'Saved/LocoAI/external-mcp-config.json')
        require(config_path.stat().st_size <= 16384, 'CONFIG_SIZE')
        port, token = endpoint(json.loads(config_path.read_text(encoding='utf-8-sig')))
        client = Client(port, token)
        report['owner'] = client.identity
        init = client.rpc('initialize', {'protocolVersion': '2025-03-26', 'capabilities': {},
                                        'clientInfo': {'name': 'yacs-l07-recover-view', 'version': '1'}})
        require(init.get('protocolVersion') == '2025-03-26', 'PROTOCOL_MISMATCH')
        client.rpc('notifications/initialized', notification=True)
        schemas = {}
        page = client.rpc('tools/list', {})
        for _ in range(4):
            for tool in page.get('tools', []):
                if tool.get('name') in SCHEMAS:
                    schemas[tool['name']] = hashlib.sha256(canonical(tool.get('inputSchema'))).hexdigest()
            if not page.get('nextCursor'):
                break
            page = client.rpc('tools/list', {'cursor': page['nextCursor']})
        require(not page.get('nextCursor') and schemas == SCHEMAS, 'INSTALLED_TOOL_SCHEMA_CHANGED')
        for index, call in enumerate(plan()):
            started = time.time()
            result = client.rpc('tools/call', call)
            text = native_text(result, token, client.session)
            row = {'index': index, 'tool': call['name'], 'text': text}
            report['calls'].append(row)
            if index == 0:
                tagged = re.findall(r'(?m)^YACS_L07_CAMERA:(.+)$', text)
                require(len(tagged) == 1, 'CAMERA_READBACK_MISSING')
                camera = json.loads(tagged[0])
                require(camera.get('world') == WORLD and camera.get('transforms_unchanged') is True,
                        'CAMERA_INVARIANTS')
                report['camera'] = camera
            if index == 1:
                report['image_sha256'] = retain_image(text, output / 'landscape.jpg', started)
            require(fingerprints() == before, 'PROTECTED_PACKAGE_CHANGED')
            (output / 'result.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        report['status'] = 'CAMERA_RECOVERED_MATERIAL_READ_ONLY'
    except Exception as error:
        report['status'] = 'STOPPED'
        report['error'] = str(error)[:300] if isinstance(error, RuntimeError) else type(error).__name__
        raise
    finally:
        report['protected_packages_unchanged'] = fingerprints() == before
        (output / 'result.json').write_text(json.dumps(report, indent=2), encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-head', required=True)
    parser.add_argument('--run-token', required=True)
    try:
        run(parser.parse_args())
    except Exception as error:
        print('L07_VIEW_RECOVERY_STOPPED:' + (str(error)[:300] if isinstance(error, RuntimeError) else type(error).__name__))
        sys.exit(1)
