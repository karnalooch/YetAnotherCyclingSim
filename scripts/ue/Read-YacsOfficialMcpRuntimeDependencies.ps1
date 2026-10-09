#requires -Version 7.4
<#
.SYNOPSIS
    Read bounded installed Automation/MCP dependencies without runtime activation.
.DESCRIPTION
    Called by the exact-SHA native harness after its resolver and idle-host gates.
    Only installed source is read. Evidence stays in Git-ignored Saved output;
    no server, Editor, build, network, plugin registration or source execution.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string] $EngineRoot,
    [Parameter(Mandatory = $true)][string] $ArtifactRoot,
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-f]{40}$')][string] $ExpectedHead
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$RepoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../..')).Path
$ArtifactRoot = [IO.Path]::GetFullPath($ArtifactRoot)
$savedPrefix = [IO.Path]::GetFullPath((Join-Path $RepoRoot 'Saved')).TrimEnd('\', '/') + [IO.Path]::DirectorySeparatorChar
if (-not $ArtifactRoot.StartsWith($savedPrefix, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Runtime dependency evidence must remain below this checkout Saved directory.'
}
foreach ($candidate in @($ArtifactRoot, [IO.Path]::GetFullPath($EngineRoot))) {
    $cursor = $candidate
    while ($cursor) {
        if (Test-Path -LiteralPath $cursor) {
            if ((Get-Item -LiteralPath $cursor -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) {
                throw 'Runtime dependency paths cannot contain symlinks or junctions.'
            }
        }
        $parent = Split-Path -Path $cursor -Parent
        if ($parent -eq $cursor) { break }
        $cursor = $parent
    }
}
Push-Location -LiteralPath $RepoRoot
try {
    if ((& git rev-parse HEAD).Trim() -cne $ExpectedHead -or $LASTEXITCODE -ne 0) {
        throw 'Runtime dependency evidence must bind the exact native harness SHA.'
    }
    & git check-ignore --no-index --quiet -- (Join-Path $ArtifactRoot 'runtime-dependencies.json')
    if ($LASTEXITCODE -ne 0) { throw 'Runtime dependency evidence must be Git-ignored.' }
}
finally { Pop-Location }
if (-not (Test-Path -LiteralPath $ArtifactRoot -PathType Container)) {
    throw 'The native harness must create its exclusive evidence directory first.'
}
if (Test-Path -LiteralPath (Join-Path $ArtifactRoot 'runtime-dependencies.json')) {
    throw 'Runtime dependency receipt already exists.'
}

# Python is the existing native source-probe dependency. This constant program
# parses source as data; it never imports or executes installed Engine source.
$DependencyReader = @'
import hashlib, json, os, re, stat, sys
from datetime import datetime, timezone
from pathlib import Path

engine, artifact, exact_sha = Path(os.path.abspath(sys.argv[1])), Path(os.path.abspath(sys.argv[2])), sys.argv[3]
MAX_FILE, MAX_TOTAL, BASE_FILES, MAX_FILES = 2*1024*1024, 8*1024*1024, 16, 26
MAX_ENTRIES, MAX_DEPTH, MAX_SPAN_LINES, MAX_CONSOLE = 1024, 10, 1200, 500
MAX_CALLS, MAX_CONSOLE_CHARS = 128, 1024
MAX_DEPENDENCY_INCLUDES = 64
records, excerpts, gaps, calls, inventory = {}, [], [], [], []
selected_lines = {}
total_bytes = 0
receipt = dict(schema_version=1, exact_sha=exact_sha, inspected_at_utc=datetime.now(timezone.utc).isoformat(),
    status='PENDING', engine_identity=None, source_files=[], excerpts=[], gaps=[], direct_registration_calls=[],
    mcp_callsite_inventory=[], mcp_callsite_index_complete=False, declarations_require_primary_review=True,
    observed_server_dependency_includes=[],
    followed_binding_dependencies=[],
    source_only=True, official_mcp_transport_verified=False, official_mcp_admitted=False,
    argument_policy_parity_verified=False, local_only_binding_verified=False,
    existing_project_test_verified=False, native_bob_capture_verified=False,
    persistent_world_mutation=False, error=None)

def checked(root, path):
    root, path = root.absolute(), path.absolute()
    try: relative = path.relative_to(root)
    except ValueError: raise ValueError('PATH_OUTSIDE_APPROVED_ROOT')
    if '..' in relative.parts: raise ValueError('PATH_TRAVERSAL')
    cursor = root
    for part in ('', *relative.parts):
        if part: cursor /= part
        info = cursor.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise ValueError('LINK_OR_REPARSE_POINT')
    if not path.resolve().is_relative_to(root.resolve()): raise ValueError('PATH_OUTSIDE_APPROVED_ROOT')
    return path

def read(relative, purpose):
    global total_bytes
    if relative in records: return records[relative]
    path = checked(engine, engine / relative)
    before = path.stat()
    if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_FILE: raise ValueError('UNSUPPORTED_OR_OVERSIZED_SOURCE')
    if len(records) >= MAX_FILES or total_bytes + before.st_size > MAX_TOTAL: raise ValueError('GLOBAL_SOURCE_BUDGET')
    with path.open('rb') as stream: data = stream.read(MAX_FILE+1)
    after = path.stat()
    if len(data) > MAX_FILE or total_bytes + len(data) > MAX_TOTAL: raise ValueError('GLOBAL_SOURCE_BUDGET')
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns): raise ValueError('SOURCE_CHANGED_DURING_READ')
    total_bytes += len(data)
    item = dict(path=relative, purpose=purpose, sha256=hashlib.sha256(data).hexdigest(), byte_count=len(data),
                text=data.decode('utf-8-sig', errors='strict'))
    records[relative] = item
    return item

def cpp_mask(source, strings=True):
    # Retain exact character/newline positions. Raw string terminators are
    # recognized so embedded braces cannot create false complete bodies.
    output, position = list(source), 0
    while position < len(source):
        end, literal = None, False
        if source.startswith('//', position):
            end = source.find('\n', position)
            if end < 0: end = len(source)
            while end < len(source) and source[:end].rstrip('\r').endswith('\\'):
                continuation = source.find('\n', end+1)
                end = len(source) if continuation < 0 else continuation
        elif source.startswith('/*', position):
            stop = source.find('*/', position+2)
            if stop < 0: raise ValueError('UNTERMINATED_CPP_COMMENT')
            end = stop+2
        elif source.startswith('R"', position):
            literal = True
            raw = re.match(r'R"([^\s()\\]{0,16})\(', source[position:])
            if not raw: raise ValueError('UNSUPPORTED_CPP_RAW_LITERAL')
            stop = source.find(')'+raw.group(1)+'"', position+raw.end())
            if stop < 0: raise ValueError('UNTERMINATED_CPP_RAW_LITERAL')
            end = stop+len(raw.group(1))+2
        elif source[position] in '\"\'':
            literal = True
            quote, cursor = source[position], position+1
            while cursor < len(source):
                if source[cursor] == '\\': cursor += 2; continue
                if source[cursor] == quote: break
                cursor += 1
            if cursor >= len(source): raise ValueError('UNTERMINATED_CPP_LITERAL')
            end = cursor+1
        if end is None: position += 1; continue
        if strings or not literal:
            for index in range(position, end):
                if output[index] not in '\r\n': output[index] = ' '
        position = end
    return ''.join(output)

def add_span(item, topic, start, end, complete, reason=None):
    lines = item['text'].splitlines()
    used = selected_lines.setdefault(item['path'], set())
    remaining, selected_end = MAX_SPAN_LINES-len(used), start-1
    for index in range(start, end+1):
        if index not in used:
            if remaining <= 0: break
            remaining -= 1
        selected_end = index
    clipped = selected_end < end
    end = selected_end
    if end < start:
        gaps.append(dict(topic=topic, path=item['path'], reason='FILE_EXCERPT_LINE_LIMIT')); return
    used.update(range(start,end+1))
    key = (item['path'], topic, start, end)
    if any((x['path'], x['topic'], x['line_start'], x['line_end']) == key for x in excerpts): return
    code = cpp_mask(item['text'], strings=False).splitlines()
    excerpts.append(dict(path=item['path'], sha256=item['sha256'], purpose=item['purpose'], topic=topic,
        line_start=start, line_end=end, body_complete=complete and not clipped,
        context_truncated=clipped or not complete, truncation_reason=reason or ('SPAN_LINE_LIMIT' if clipped else None),
        lines=[dict(line=index+1, text=lines[index], code=bool(code[index].strip())) for index in range(start-1, end)]))
    if clipped or not complete: gaps.append(dict(topic=topic, path=item['path'], reason=reason or 'SPAN_LINE_LIMIT'))

def functions(item, pattern, topic, required=True):
    masked, found = cpp_mask(item['text']), 0
    for match in list(re.finditer(pattern, masked))[:24]:
        line_start = masked.rfind('\n', 0, match.start())+1
        prefix = masked[line_start:match.start()].strip()
        # A qualified invocation followed by an if/lambda brace is not a
        # definition. Require the actual return-type prefix before the name.
        if match.group().startswith('UAutomationTestToolsetSubsystem') and 'GetSubsystem' in match.group():
            valid_prefix = prefix in ('', 'static', 'inline', 'static inline')
        else:
            if not prefix:
                previous = masked[:line_start].rstrip()
                prefix = previous.rsplit('\n',1)[-1].strip() if previous else ''
            valid_prefix = bool(re.fullmatch(r'[\w:\s<>,*&]+', prefix)) and not any(
                word in {'if','while','for','switch','return','co_return','throw','new','delete','sizeof','decltype'}
                for word in re.findall(r'\b\w+\b',prefix))
        if not valid_prefix: continue
        parameters, signature_end = 1, match.end()
        while signature_end < len(masked) and parameters:
            if masked[signature_end] == '(': parameters += 1
            elif masked[signature_end] == ')': parameters -= 1
            signature_end += 1
        if parameters:
            gaps.append(dict(topic=topic, path=item['path'], reason='UNTERMINATED_FUNCTION_SIGNATURE')); continue
        opening = masked.find('{', signature_end)
        semicolon = masked.find(';', signature_end)
        if opening < 0 or (semicolon >= 0 and semicolon < opening): continue
        depth, cursor = 1, opening+1
        while cursor < len(masked) and depth:
            if masked[cursor] == '{': depth += 1
            elif masked[cursor] == '}': depth -= 1
            cursor += 1
        start = masked.count('\n', 0, match.start())+1
        end = masked.count('\n', 0, cursor)+1
        end = min(end, len(item['text'].splitlines()))
        add_span(item, topic, start, end, depth == 0, None if depth == 0 else 'UNTERMINATED_FUNCTION_BODY')
        found += 1
    if not found and required: gaps.append(dict(topic=topic, path=item['path'], reason='DEFINITION_NOT_FOUND'))
    return found

def full(item, topic):
    add_span(item, topic, 1, len(item['text'].splitlines()), True)

def named_contexts(item, pattern, topic, radius=20):
    lines=item['text'].splitlines()
    visible=cpp_mask(item['text'],strings=False).splitlines()
    for index,line in enumerate(visible):
        if re.search(pattern,line):
            add_span(item,topic,max(1,index+1-radius),min(len(lines),index+1+radius),False,
                     'NAMED_DECLARATION_CONTEXT_REQUIRES_PRIMARY_REVIEW')

def actual_includes(item):
    code = cpp_mask(item['text']).splitlines()
    visible = cpp_mask(item['text'], strings=False).splitlines()
    result = []
    for index,line in enumerate(visible):
        if not re.match(r'\s*#\s*include\b',code[index]): continue
        include = re.match(r'\s*#\s*include\s*[<"]([^>"]+)[>"]',line)
        if include: result.append((index+1,include.group(1)))
    return result

def optional(relative, purpose):
    path = engine / relative
    if not path.exists():
        gaps.append(dict(path=relative, reason='SOURCE_FILE_MISSING')); return None
    return read(relative, purpose)

def discover(root):
    found, count = [], 0
    checked(engine, root)
    def visit(directory, depth):
        nonlocal count
        if depth > MAX_DEPTH: raise ValueError('DISCOVERY_DEPTH_LIMIT')
        entries = []
        with os.scandir(directory) as scan:
            for entry in scan:
                count += 1
                if count > MAX_ENTRIES: raise ValueError('DISCOVERY_ENTRY_LIMIT')
                entries.append(entry)
        for entry in sorted(entries, key=lambda x: x.name):
            path = checked(engine, Path(entry.path))
            if entry.is_dir(follow_symlinks=False):
                if entry.name.lower() in {'test', 'tests', 'thirdparty', 'intermediate', 'binaries'} or entry.name.lower().endswith('tests'): continue
                visit(path, depth+1)
            elif entry.is_file(follow_symlinks=False) and path.suffix in {'.cpp', '.h'}:
                found.append(path.relative_to(engine).as_posix())
    visit(root, 0)
    return found

try:
    # Validate every root ancestor as well as descendants before the first read.
    for root in (engine, artifact):
        cursor = root
        while True:
            checked(cursor, cursor)
            if cursor.parent == cursor: break
            cursor = cursor.parent
    build = read('Engine/Build/Build.version', 'identity')
    version = json.loads(build['text'])
    if not isinstance(version, dict) or tuple(version.get(k) for k in ('MajorVersion','MinorVersion','PatchVersion','Changelist')) != (5,8,2,56702186):
        raise ValueError('ENGINE_IDENTITY_MISMATCH')
    receipt['engine_identity'] = dict(root=str(engine), version='5.8.2-56702186', build_version_sha256=build['sha256'])
    auto = 'Engine/Plugins/Experimental/Toolsets/AutomationTestToolset/Source/AutomationTestToolset/'
    item = optional(auto+'Private/AutomationTestToolset.cpp', 'automation')
    if item:
        functions(item, r'\bUAutomationTestToolsetSubsystem\s*\*\s*GetSubsystem\s*\(', 'GetSubsystem')
        for name in ('DiscoverTests','ListTests','RunTests','GetTestResults','GetTestStatus'):
            functions(item, r'\bUAutomationTestToolset::'+name+r'\s*\(', name)
    item = optional(auto+'Public/AutomationTestToolsetSubsystem.h', 'automation')
    if item: full(item, 'subsystem_public_declarations')
    item = optional(auto+'Private/AutomationTestToolsetSubsystem.cpp', 'automation')
    if item:
        functions(item,r'\bAutomationStateToString\s*\(','automation_state_strings',required=False)
        for name in ('FormatResultsJson','CollectLeafReports','EnableRunResultPolling'):
            functions(item, r'\bUAutomationTestToolsetSubsystem::'+name+r'\s*\(', name)
        names = sorted(set(re.findall(r'\bUAutomationTestToolsetSubsystem::(\w+)\s*\(', cpp_mask(item['text']))))
        for name in names:
            if re.search(r'Discover|Poll|Tick|Initialize|Pending|Complete|HandleTestsAvailable|HandleTestsRefreshed', name):
                functions(item, r'\bUAutomationTestToolsetSubsystem::'+re.escape(name)+r'\s*\(', name)

    mcp = 'Engine/Plugins/Experimental/ModelContextProtocol/Source/'
    for relative, topic in (
        ('ModelContextProtocolEngine/Public/ModelContextProtocolSettings.h','settings_declarations'),
        ('ModelContextProtocolEngine/Private/ModelContextProtocolSettings.cpp','settings_implementation'),
        ('ModelContextProtocolEditor/Private/ModelContextProtocolEditor.cpp','editor_registration_lifecycle')):
        item = optional(mcp+relative, 'mcp')
        if item: full(item, topic)
    source_inventory = []
    for module in ('ModelContextProtocol','ModelContextProtocolEngine','ModelContextProtocolEditor'):
        root = engine / mcp / module
        if not root.exists(): gaps.append(dict(path=str(root.relative_to(engine)), reason='MCP_MODULE_SOURCE_MISSING')); continue
        source_inventory.extend(discover(root))
    for basename in ('IModelContextProtocolModule.h',):
        matches = [x for x in source_inventory if Path(x).name == basename]
        if len(matches) != 1:
            gaps.append(dict(topic=basename, reason='CANONICAL_SOURCE_FILENAME_NOT_UNIQUE', candidates=matches)); continue
        item = read(matches[0], 'mcp')
        full(item, 'server_public_lifecycle')
    # These real dependency names came from the previous installed source run.
    # Reserve their reads before the optional bounded registration index.
    critical = (
        ('ModelContextProtocolServer.h','ModelContextProtocol','official_server_declarations'),
        ('ModelContextProtocolServer.cpp','ModelContextProtocol','official_server_implementation'),
        ('ModelContextProtocolToolLibrary.h','ModelContextProtocolEngine','direct_tool_library_declarations'),
        ('ModelContextProtocolToolLibrary.cpp','ModelContextProtocolEngine','direct_tool_library_controls'),
        ('IModelContextProtocolTool.h','ModelContextProtocol','direct_tool_interface'),
        ('ModelContextProtocolToolsetRegistryAdapter.cpp','ModelContextProtocolEditor','registry_adapter_implementation'),
        ('ModelContextProtocolModule.cpp','ModelContextProtocol','module_implementation'),
    )
    for basename, module, topic in critical:
        matches = [x for x in source_inventory if x.startswith(mcp+module+'/') and Path(x).name==basename]
        if len(matches)!=1:
            gaps.append(dict(topic=topic, reason='NAMED_DEPENDENCY_SOURCE_NOT_UNIQUE', candidates=matches)); continue
        item = read(matches[0], 'mcp')
        if basename=='ModelContextProtocolServer.cpp':
            names = sorted(set(re.findall(r'\bFModelContextProtocolServer::(\w+)\s*\(',cpp_mask(item['text']))))
            for name in names:
                if re.search(r'StartServer|StopServer|Handle|Request|Tool|Dispatch|Call|Tick',name):
                    functions(item,r'\bFModelContextProtocolServer::'+re.escape(name)+r'\s*\(',
                              'server_dependency_'+name,required=False)
        elif basename=='ModelContextProtocolToolsetRegistryAdapter.cpp':
            names = sorted(set(re.findall(r'\b(FToolsetRegistryToolAdapter(?:Manager)?)::(\w+)\s*\(',cpp_mask(item['text']))))
            for owner,name in names:
                if re.search(r'Run|Execute|Dispatch',name):
                    functions(item,r'\b'+owner+'::'+re.escape(name)+r'\s*\(','adapter_'+name,required=False)
        elif basename=='ModelContextProtocolModule.cpp':
            for name in ('AddTool','RemoveTool','RefreshTools','FindTool','GetTools'):
                functions(item,r'\bFModelContextProtocolModule::'+name+r'\s*\(','module_'+name)
        full(item,topic)
    server_source = next((x for x in records.values() if Path(x['path']).name in {'ModelContextProtocolServer.cpp','ModelContextProtocolServer.h'}
        and any(name=='HttpServerModule.h' for _,name in actual_includes(x))),None)
    if server_source:
        provenance = next(((line,name) for line,name in actual_includes(server_source) if name=='HttpServerModule.h'),None)
        if provenance:
            relative = 'Engine/Source/Runtime/Online/HTTPServer/Private/HttpServerModule.cpp'
            item = optional(relative,'mcp')
            if item:
                receipt['followed_binding_dependencies'].append(dict(path=relative,from_path=server_source['path'],
                    from_sha256=server_source['sha256'],include_line=provenance[0],include=provenance[1]))
                for name in sorted(set(re.findall(r'\bFHttpServerModule::(\w+)\s*\(',cpp_mask(item['text'])))):
                    if re.search(r'Router|Listen|Start|Stop',name):
                        functions(item,r'\bFHttpServerModule::'+re.escape(name)+r'\s*\(','http_'+name,required=False)
                full(item,'http_module_source')
                listener_include = next(((line,name) for line,name in actual_includes(item) if name=='HttpListener.h'),None)
                if listener_include:
                    listener = optional('Engine/Source/Runtime/Online/HTTPServer/Private/HttpListener.cpp','mcp')
                    if listener:
                        receipt['followed_binding_dependencies'].append(dict(path=listener['path'],from_path=item['path'],
                            from_sha256=item['sha256'],include_line=listener_include[0],include=listener_include[1]))
                        for name in sorted(set(re.findall(r'\bFHttpListener::(\w+)\s*\(',cpp_mask(listener['text'])))):
                            if re.search(r'Listen|Start|Init|Bind',name):
                                functions(listener,r'\bFHttpListener::'+re.escape(name)+r'\s*\(','http_'+name,required=False)
                        full(listener,'http_listener_source')
                        config_include=next(((line,name) for line,name in actual_includes(listener) if name=='HttpServerConfig.h'),None)
                        if config_include:
                            base='Engine/Source/Runtime/Online/HTTPServer/'
                            headers=[base+kind+'/HttpServerConfig.h' for kind in ('Private','Public')
                                if (engine/(base+kind+'/HttpServerConfig.h')).exists()]
                            if len(headers)==1:
                                config_header=read(headers[0],'mcp')
                                full(config_header,'http_config_declarations')
                                receipt['followed_binding_dependencies'].append(dict(path=headers[0],from_path=listener['path'],
                                    from_sha256=listener['sha256'],include_line=config_include[0],include=config_include[1]))
                            else: gaps.append(dict(topic='http_config_declarations',reason='NAMED_CONFIG_HEADER_NOT_UNIQUE',candidates=headers))
                            config=optional(base+'Private/HttpServerConfig.cpp','mcp')
                            if config:
                                named_contexts(config,r'\bIniSectionNameHTTPServerListeners\b',
                                               'http_config_section_name',6)
                                functions(config,r'\bFHttpServerConfig::GetListenerConfig\s*\(','http_config_getter')
                                functions(config,r'\bFHttpServerConfig::OnConfigSectionsChanged\s*\(','http_config_cache_invalidation')
                                full(config,'http_config_implementation')
                for backend in (item, records.get('Engine/Source/Runtime/Online/HTTPServer/Private/HttpListener.cpp')):
                    if not backend: continue
                    candidates=sorted(set(re.findall(r'\b(\w*(?:Config|Bind|Address)\w*)\s*\(',cpp_mask(backend['text']))))
                    for name in candidates:
                        functions(backend,r'\b'+re.escape(name)+r'\s*\(','http_helper_'+name,required=False)
    # The existing native test includes AutomationTest.h, and project activation
    # requires the actual Projects parser. These are fixed read-only inputs,
    # not a traversal of either outside-plugin source tree.
    for relative in ('Engine/Source/Runtime/Core/Public/Misc/AutomationTest.h',
                     'Engine/Source/Runtime/Core/Private/Misc/AutomationTest.cpp'):
        item=optional(relative,'expected_errors')
        if not item: continue
        functions(item,r'\bAutomationStateToString\s*\(','automation_state_strings',required=False)
        if relative.endswith('.h'):
            named_contexts(item,r'AddExpected(?:Error|Message|LogMessage)|[EF]AutomationExpected(?:Error|Message|LogMessage)(?:Flags)?',
                           'expected_error_declarations',18)
        else:
            named_contexts(item,r'FAutomationExpected(?:Error|Message|LogMessage)::FAutomationExpected(?:Error|Message|LogMessage)','expected_matcher_constructor_context',30)
            definitions=sorted(set(re.findall(r'\b(\w+)::(\w+)\s*\(',cpp_mask(item['text']))))
            for owner,name in definitions:
                if 'Expected' in owner or 'Expected' in name or (owner=='FAutomationTestBase' and name in {'AddError','AddWarning'}) or (owner=='FAutomationTestFramework' and name=='StopTest'):
                    functions(item,r'\b'+owner+'::'+name+r'\s*\(','expected_'+owner+'_'+name,required=False)
    for relative in ('Engine/Source/Runtime/Projects/Public/Interfaces/IPluginManager.h',
                     'Engine/Source/Runtime/Projects/Private/PluginManager.cpp'):
        item=optional(relative,'plugin_activation')
        if not item: continue
        named_contexts(item,r'EnablePlugins|DisablePlugins|ConfigureEnabledPlugin',
                       'fixed_plugin_activation_context',22)
        if relative.endswith('.cpp'):
            named_contexts(item,r'\bParsePluginsList\s*=', 'fixed_plugin_list_parser',45)
    # Two fixed PythonScriptPlugin files are the only added bridge inputs.
    # No installed Python is imported, and no command is executed by this probe.
    python_plugin='Engine/Plugins/Experimental/PythonScriptPlugin/Source/PythonScriptPlugin/'
    item=optional(python_plugin+'Public/IPythonScriptPlugin.h','python_bridge')
    if item: full(item,'python_bridge_public_declarations')
    item=optional(python_plugin+'Private/PythonScriptPlugin.cpp','python_bridge')
    if item:
        for name in ('ExecPythonCommand','ExecPythonCommandEx'):
            functions(item,r'\b(?:\w+::)?'+name+r'\s*\(','python_bridge_'+name,required=False)
        named_contexts(item,r'\bExecPythonCommand(?:Ex)?\s*\(', 'python_bridge_execution_context',24)
    # Prioritize already-read implementations, then bounded new cpp files.
    implementations = sorted(source_inventory)
    implementations.sort(key=lambda x: (x not in records,
        Path(x).name not in {'ModelContextProtocolModule.cpp','ModelContextProtocol.cpp'},
        not bool(re.search(r'ToolLibrary|ToolsetRegistryAdapter|ToolRegistration', Path(x).name)),
        not x.endswith('.cpp'), x))
    for relative in implementations:
        if relative not in records and (len(records) >= BASE_FILES or total_bytes + checked(engine,engine / relative).stat().st_size > MAX_TOTAL):
            inventory.append(dict(path=relative, scanned=False, reason='GLOBAL_SOURCE_BUDGET')); continue
        item = read(relative, 'mcp')
        inventory.append(dict(path=relative, scanned=True, sha256=item['sha256']))
        if relative.startswith(mcp+'ModelContextProtocol/') and relative.endswith('.cpp'):
            functions(item, r'\b\w+::StartServer\s*\(', 'server_start', required=False)
            for name in ('StartupModule','ShutdownModule','StopServer'):
                functions(item, r'\b\w+::'+name+r'\s*\(', 'server_'+name, required=False)
        masked_lines = cpp_mask(item['text']).splitlines()
        original_lines = item['text'].splitlines()
        for index, line in enumerate(masked_lines):
            if re.search(r'\b(?:AddTool|RegisterTool\w*)\s*\(', line):
                if len(calls) < MAX_CALLS:
                    calls.append(dict(path=relative, sha256=item['sha256'], line=index+1, text=original_lines[index]))
                elif not any(x.get('reason') == 'REGISTRATION_CALL_LIMIT' for x in gaps):
                    gaps.append(dict(topic='mcp_registration_callsites', reason='REGISTRATION_CALL_LIMIT'))
            if re.search(r'\b(?:DefaultBindAddress|BindAddress|GetHttpRouter|Listen|StartAllListeners)\b', line):
                add_span(item, 'observed_binding_context', max(1,index-3), min(len(original_lines),index+5), False,
                         'CONTEXT_ONLY_REQUIRES_PRIMARY_REVIEW')
    receipt['mcp_callsite_index_complete'] = all(x['scanned'] for x in inventory) and len(inventory)>0 and not any(x.get('reason') == 'REGISTRATION_CALL_LIMIT' for x in gaps)
    if not any(x['topic']=='server_start' for x in excerpts):
        gaps.append(dict(topic='server_start', reason='DEFINITION_NOT_ESTABLISHED_IN_BOUNDED_MCP_MODULE_SOURCE'))
    if not receipt['mcp_callsite_index_complete']: gaps.append(dict(topic='mcp_registration_callsites', reason='INCOMPLETE_IMPLEMENTATION_INDEX'))
    for item in records.values():
        if item['purpose'] != 'mcp': continue
        directives = cpp_mask(item['text']).splitlines()
        for index, line in enumerate(cpp_mask(item['text'], strings=False).splitlines()):
            if not re.match(r'\s*#\s*include\b', directives[index]): continue
            include = re.match(r'\s*#\s*include\s*[<"]([^>"]+)[>"]', line)
            if include and re.search(r'HTTP|Http|Server|Transport|Router|Listener|Socket', include.group(1)):
                if len(receipt['observed_server_dependency_includes']) < MAX_DEPENDENCY_INCLUDES:
                    receipt['observed_server_dependency_includes'].append(dict(path=item['path'], sha256=item['sha256'],
                        line=index+1, include=include.group(1)))
                elif not any(x.get('reason') == 'DEPENDENCY_INCLUDE_LIMIT' for x in gaps):
                    gaps.append(dict(topic='server_dependency_includes', reason='DEPENDENCY_INCLUDE_LIMIT'))
    receipt['status'] = 'PARTIAL_DEPENDENCY_EVIDENCE' if gaps else 'SOURCE_CONTEXTS_COLLECTED'
except Exception as error:
    receipt['status'], receipt['error'] = 'BLOCKED', str(error)
finally:
    receipt.update(source_files=[{k:v for k,v in x.items() if k != 'text'} for x in records.values()],
        source_file_count=len(records), total_source_bytes=total_bytes, excerpts=excerpts, gaps=gaps,
        direct_registration_calls=calls, mcp_callsite_inventory=inventory)
    destination = checked(artifact, artifact) / 'runtime-dependencies.json'
    with destination.open('x', encoding='utf-8', newline='\n') as output:
        json.dump(receipt, output, indent=2, ensure_ascii=False); output.write('\n')
    def console_summary(label, value):
        line = label+' '+json.dumps(value,sort_keys=True)
        print(line if len(line)<=MAX_CONSOLE_CHARS else line[:MAX_CONSOLE_CHARS]+' [CONSOLE_SUMMARY_TRUNCATED]')
    console_summary('RUNTIME_DEPENDENCIES',{k:receipt[k] for k in ('status','exact_sha','engine_identity','source_file_count','total_source_bytes','mcp_callsite_index_complete','error')})
    print('SOURCE_ONLY: no runtime, binding, argument parity or admission proof')
    console_summary('SERVER_DEPENDENCY_INCLUDES',dict(count=len(receipt['observed_server_dependency_includes']),
        inventory_truncated=any(x.get('reason')=='DEPENDENCY_INCLUDE_LIMIT' for x in gaps)))
    console_summary('FOLLOWED_BINDING_DEPENDENCIES',receipt['followed_binding_dependencies'])
    for purpose in ('automation','expected_errors','plugin_activation','python_bridge','mcp_transport','mcp'):
        console = []
        if purpose == 'mcp':
            console.extend('SERVER_INCLUDE '+json.dumps(item,sort_keys=True) for item in receipt['observed_server_dependency_includes'])
            console.extend('REGISTRATION_CALL '+json.dumps(call,sort_keys=True) for call in calls)
        priority = {
            'FormatResultsJson':0, 'DiscoverTests':1, 'GetSubsystem':2, 'RunTests':3,
            'automation_state_strings':0,
            'GetTestResults':4, 'GetTestStatus':5, 'ListTests':6, 'CollectLeafReports':7,
            'EnableRunResultPolling':8, 'subsystem_public_declarations':10,
            'direct_tool_library_controls':0, 'direct_tool_library_declarations':1,
            'direct_tool_interface':0, 'module_FindTool':0, 'module_GetTools':0,
            'python_bridge_public_declarations':0, 'python_bridge_ExecPythonCommand':1,
            'python_bridge_ExecPythonCommandEx':1, 'python_bridge_execution_context':2,
            'fixed_plugin_list_parser':0,
            'official_server_declarations':1,
            'module_AddTool':2, 'module_RemoveTool':2, 'module_RefreshTools':2,
            'server_start':0, 'settings_declarations':1, 'settings_implementation':2,
            'server_public_lifecycle':3, 'editor_registration_lifecycle':4,
            'observed_binding_context':6,
        }
        def console_purpose(excerpt):
            if excerpt['purpose']!='mcp': return excerpt['purpose']
            return 'mcp_transport' if excerpt['topic'].startswith(('server_','server_dependency_','official_server_','adapter_','http_')) else 'mcp'
        def console_priority(excerpt):
            if excerpt['topic']=='expected_error_declarations': return -3
            if excerpt['topic']=='expected_matcher_constructor_context': return -2
            if excerpt['topic'].startswith('expected_') and 'AddExpectedError' in excerpt['topic']: return -2
            if excerpt['topic'].startswith('expected_') and any(key in excerpt['topic'] for key in ('Matches','Match','Occurrence','Validate','Verify','HasMet')): return -1
            if excerpt['topic'].startswith('expected_') and not excerpt['topic'].endswith(('_StopTest','_AddError','_AddWarning')): return 0
            if excerpt['topic']=='server_dependency_ProcessToolCallJsonRpcCall': return -3
            if excerpt['topic'].startswith('adapter_'): return -2
            if excerpt['topic'].startswith('http_config'): return -1
            if excerpt['topic'].startswith('http_'): return 0
            if excerpt['topic'].startswith('server_dependency_'): return 1
            if excerpt['topic'].startswith('adapter_'): return 2
            return priority.get(excerpt['topic'],9)
        emitted_source_lines=set()
        for excerpt in sorted(excerpts,key=lambda x:(console_priority(x),x['path'],x['line_start'])):
            if console_purpose(excerpt) != purpose: continue
            if purpose in {'mcp','mcp_transport'} and excerpt['topic'] in {
                'settings_declarations','settings_implementation','server_public_lifecycle',
                'editor_registration_lifecycle','official_server_implementation',
                'registry_adapter_implementation','module_implementation',
                'server_StartupModule','server_ShutdownModule','server_StopServer',
                'http_module_source','http_listener_source','http_config_implementation',
                'http_StartupModule','http_StopListening','http_StopAllListeners','http_StartAllListeners',
                'http_HasPendingListeners','server_dependency_StopServer',
                'server_dependency_ScheduleToolsListChangedBroadcast',
                'server_dependency_ProcessPingJsonRpcCall','server_dependency_ProcessNotificationCancelledJsonRpcCall',
                'server_dependency_ProcessListResourcesJsonRpcCall','server_dependency_ProcessReadResourceJsonRpcCall'}:
                # Already-reviewed contexts / full-file backup remain in JSON;
                # use console capacity for the newly required control bodies.
                continue
            console.append('SOURCE '+excerpt['path']+':'+str(excerpt['line_start'])+'-'+str(excerpt['line_end'])+' sha256='+excerpt['sha256']+' topic='+excerpt['topic']+' body_complete='+str(excerpt['body_complete']))
            for line in excerpt['lines']:
                key=(excerpt['path'],line['line'])
                if line['code'] and key not in emitted_source_lines:
                    console.append(str(line['line'])+': '+line['text']); emitted_source_lines.add(key)
        truncated = len(console) > MAX_CONSOLE-2 or any(len(x)>MAX_CONSOLE_CHARS for x in console)
        print('PURPOSE '+purpose+' console_truncated='+str(truncated))
        for line in console[:MAX_CONSOLE-2]:
            print(line if len(line)<=MAX_CONSOLE_CHARS else line[:MAX_CONSOLE_CHARS]+' [CONSOLE_LINE_TRUNCATED]')
        print('END_PURPOSE '+purpose+' console_truncated='+str(truncated))
    console_summary('DEPENDENCY_GAPS',gaps)
sys.exit(1 if receipt['status']=='BLOCKED' else 0)
'@
# Keep the owned program off Windows' 32,767-character process command line.
$DependencyReader | & python - $EngineRoot $ArtifactRoot $ExpectedHead
if ($LASTEXITCODE -ne 0) { throw 'Read-only runtime dependency preflight was blocked; inspect runtime-dependencies.json.' }
