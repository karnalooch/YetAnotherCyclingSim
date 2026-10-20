#requires -Version 7.4
<#
.SYNOPSIS
  Exercise the real Lesson07 JSON validators without Windows, UE or task actions.
#>
[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$source=Join-Path $PSScriptRoot 'Start-YacsLesson07RemoteEditor.ps1'
$tokens=$null; $parseErrors=$null
$ast=[Management.Automation.Language.Parser]::ParseFile($source,[ref]$tokens,[ref]$parseErrors)
if (@($parseErrors).Count) { throw 'Lesson07 launcher did not parse.' }
# Load only these pure data validators, never the launcher's executable body.
foreach ($name in @('Stop-L07','Get-L07ReleaseEntry','Assert-L07ProjectIdentity')) {
    $nodes=@($ast.FindAll({
        param($node)
        $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -ceq $name
    },$false))
    if ($nodes.Count -ne 1) { throw 'Expected one production validator.' }
    . ([scriptblock]::Create($nodes[0].Extent.Text))
}
function Require([bool]$Condition,[string]$Message) {
    if (-not $Condition) { throw $Message }
}
function Expect-ProjectBlock([Collections.IDictionary]$Project, [string]$DescriptorSha256=('0'*64)) {
    $blocked=$false
    try { Assert-L07ProjectIdentity $Project $DescriptorSha256 } catch {
        Require ($_.Exception.Data['l07_reason'] -ceq 'PROJECT_MODULES_OR_ENGINE') 'Wrong project failure reason.'
        $blocked=$true
    }
    Require $blocked 'Invalid project was admitted.'
}
function Expect-ReleaseBlock([Collections.IDictionary]$Install,[string]$Relative) {
    $blocked=$false
    try { $null=Get-L07ReleaseEntry $Install $Relative } catch {
        Require ($_.Exception.Data['l07_reason'] -ceq 'RELEASE_FILE_HASH') 'Wrong release failure reason.'
        $blocked=$true
    }
    Require $blocked 'Invalid release entry was admitted.'
}
$json='{"EngineAssociation":"5.8","Modules":[{"Name":"YetAnotherCyclingSim","Type":"Runtime"},{"Name":"YetAnotherCyclingSimEditor","Type":"Editor"}],"Description":"PRIVATE_SENTINEL"}'
$report=[ordered]@{}
$valid=$json | ConvertFrom-Json -AsHashtable
Assert-L07ProjectIdentity $valid ('0'*64)
Require ($report.project_observation.required_runtime_matches -eq 1 -and $report.project_observation.required_editor_matches -eq 1) 'Valid JSON dictionary modules were not matched.'
Require ($report.project_observation.engine_association -ceq '5.8' -and $report.project_observation.modules.Count -eq 2) 'Safe project observation is incomplete.'
Require ($report.project_observation.admission_basis -ceq 'NUMERIC_5_8') 'Original numeric engine admission changed.'
Require (($report | ConvertTo-Json -Depth 8) -notmatch 'PRIVATE_SENTINEL|Description') 'Unselected project content leaked.'
$cases=1
foreach ($fixture in @(
    '{"EngineAssociation":"5.8","Modules":[{"Name":"YetAnotherCyclingSim","Type":"Runtime"}]}',
    '{"EngineAssociation":"5.8","Modules":[{"Name":"YetAnotherCyclingSim","Type":"Runtime"},{"Name":"YetAnotherCyclingSim","Type":"Runtime"},{"Name":"YetAnotherCyclingSimEditor","Type":"Editor"}]}',
    '{"EngineAssociation":"5.9","Modules":[{"Name":"YetAnotherCyclingSim","Type":"Runtime"},{"Name":"YetAnotherCyclingSimEditor","Type":"Editor"}]}',
    '{"EngineAssociation":"5.8","Modules":[{"Name":"yetanothercyclingsim","Type":"Runtime"},{"Name":"YetAnotherCyclingSimEditor","Type":"Editor"}]}',
    '{"EngineAssociation":"5.8","Modules":[{"Name":"YetAnotherCyclingSim","Type":"Editor"},{"Name":"YetAnotherCyclingSimEditor","Type":"Editor"}]}',
    '{"EngineAssociation":"5.8","Modules":[{"Name":"YetAnotherCyclingSim","Type":"Runtime"},{"Name":"YetAnotherCyclingSimEditor","Type":"Runtime"}]}',
    '{"EngineAssociation":["5.8","INVALID"],"Modules":[{"Name":"YetAnotherCyclingSim","Type":"Runtime"},{"Name":"YetAnotherCyclingSimEditor","Type":"Editor"}]}',
    '{"EngineAssociation":null,"Modules":[{"Name":"YetAnotherCyclingSim","Type":"Runtime"},{"Name":"YetAnotherCyclingSimEditor","Type":"Editor"}]}',
    '{"EngineAssociation":"5.8","Modules":[{"Name":["YetAnotherCyclingSim","INVALID"],"Type":"Runtime"},{"Name":"YetAnotherCyclingSimEditor","Type":"Editor"}]}',
    '{"EngineAssociation":"5.8","Modules":[{"Name":"YetAnotherCyclingSim","Type":["Runtime","INVALID"]},{"Name":"YetAnotherCyclingSimEditor","Type":"Editor"}]}',
    '{"EngineAssociation":"5.8","Modules":["INVALID"]}',
    '{"EngineAssociation":"PRIVATE_SENTINEL","Modules":[{"Name":"INVALID/PRIVATE_SENTINEL","Type":"PRIVATE_SENTINEL"}]}'
)) {
    $report=[ordered]@{}
    Expect-ProjectBlock ($fixture | ConvertFrom-Json -AsHashtable)
    Require (($report | ConvertTo-Json -Depth 8) -notmatch 'PRIVATE_SENTINEL') 'Invalid project values were not sanitized.'
    $cases++
}
# Exercise the actual tracked .uproject through the same dictionary-producing API.
$tracked=Get-Content -LiteralPath (Join-Path $PSScriptRoot '../../YetAnotherCyclingSim.uproject') -Raw | ConvertFrom-Json -AsHashtable
$report=[ordered]@{}
Assert-L07ProjectIdentity $tracked ('0'*64)
$cases++
# Only the actual observed GUID together with the exact descriptor hash passes.
$knownGuid='{FEF18A3B-4D4B-15FD-E2E3-E5AA38A2AB75}'
$knownHash='f00d5117b63b3a6a5d200ff4ffab035a770712cd358b3e6f4cb50b6063c06c66'
$custom=$json | ConvertFrom-Json -AsHashtable
$custom['EngineAssociation']=$knownGuid
$report=[ordered]@{}
Assert-L07ProjectIdentity $custom $knownHash
Require ($report.project_observation.admission_basis -ceq 'OBSERVED_GUID_AND_DESCRIPTOR_SHA256' -and
    $report.project_observation.engine_association -ceq $knownGuid -and
    $report.project_observation.descriptor_sha256 -ceq $knownHash) 'Pinned custom engine observation did not pass.'
$cases++
Expect-ProjectBlock $custom ('0'*64)
$cases++
Expect-ProjectBlock $custom ''
$cases++
$custom['EngineAssociation']='{00000000-4D4B-15FD-E2E3-E5AA38A2AB75}'
Expect-ProjectBlock $custom $knownHash
$cases++
$custom['EngineAssociation']=$knownGuid
$custom['Modules'][1]['Type']='Runtime'
Expect-ProjectBlock $custom $knownHash
$cases++
$relative='scripts/ue/Start-YacsLesson07RemoteEditor.ps1'
$release='{"files":[{"path":"scripts/ue/Start-YacsLesson07RemoteEditor.ps1","sha256":"known"}]}' | ConvertFrom-Json -AsHashtable
Require ((Get-L07ReleaseEntry $release $relative)['sha256'] -ceq 'known') 'Valid release dictionary entry was not matched.'
$cases++
Expect-ReleaseBlock $release 'scripts/ue/Missing.ps1'
$cases++
$duplicate='{"files":[{"path":"scripts/ue/Start-YacsLesson07RemoteEditor.ps1"},{"path":"scripts/ue/Start-YacsLesson07RemoteEditor.ps1"}]}' | ConvertFrom-Json -AsHashtable
Expect-ReleaseBlock $duplicate $relative
$cases++
$wrongCase='{"files":[{"path":"scripts/ue/start-YacsLesson07RemoteEditor.ps1"}]}' | ConvertFrom-Json -AsHashtable
Expect-ReleaseBlock $wrongCase $relative
$cases++
$arrayPath='{"files":[{"path":["scripts/ue/Start-YacsLesson07RemoteEditor.ps1","INVALID"]}]}' | ConvertFrom-Json -AsHashtable
Expect-ReleaseBlock $arrayPath $relative
$cases++
[ordered]@{status='LESSON07_REMOTE_JSON_PREFLIGHT_PASS';cases=$cases;powershell_version=$PSVersionTable.PSVersion.ToString();native_host_actions=$false} | ConvertTo-Json -Compress
