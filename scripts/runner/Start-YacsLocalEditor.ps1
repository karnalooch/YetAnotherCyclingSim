#requires -Version 7.4
<#
.SYNOPSIS
    Starts the local YACS Unreal Editor only when the shared home host is free.

.DESCRIPTION
    The home workstation is also the yacs-ue58 self-hosted runner. This launcher
    gives an already-running remote Unreal proof priority and refuses to start a
    second local/unknown Editor. Remote workflows use the same host-state
    classifier and yield when local Unreal work already owns the machine.
#>
[CmdletBinding()]
param(
    [string] $ProjectPath = (Join-Path (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../..')).Path 'YetAnotherCyclingSim.uproject'),
    [string[]] $AdditionalArguments = @()
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$StateScript = Join-Path $PSScriptRoot 'Get-YacsUnrealHostState.ps1'
$State = & $StateScript

if ($State.status -ne 'IDLE') {
    $State | ConvertTo-Json -Depth 8 | Write-Host
    if ($State.status -eq 'REMOTE_BUSY') {
        throw 'YACS Unreal host is owned by remote CI. Wait until the remote Unreal process exits before starting local UE.'
    }
    throw "YACS Unreal host is not idle (status=$($State.status)). Refusing to start another Editor."
}

$ProjectPath = (Resolve-Path -LiteralPath $ProjectPath).Path
$Resolver = Join-Path $PSScriptRoot '../ci/Resolve-YacsUnrealEngine.ps1'
. $Resolver
$Engine = Resolve-YacsUnrealEngine -ProjectPath $ProjectPath
if ($null -eq $Engine -or -not $Engine.UnrealEditorPath) {
    throw 'No compatible Unreal Editor was discovered for the YACS project.'
}

$Arguments = @(('"' + $ProjectPath + '"'), '-NoP4') + $AdditionalArguments
$Process = Start-Process -FilePath $Engine.UnrealEditorPath -ArgumentList $Arguments -PassThru

Write-Host (
    "YACS LOCAL EDITOR STARTED: pid={0}; engine={1}; project={2}" -f
        $Process.Id,
        $Engine.Version,
        $ProjectPath
)
Write-Host 'Remote Unreal workflows will now fail closed while this local Editor remains active.'
