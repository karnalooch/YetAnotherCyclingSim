<#
.SYNOPSIS
    Canonical YACS Unreal build-environment identity.

.DESCRIPTION
    Combines the canonical Unreal Engine identity with the active MSVC/linker
    and Windows SDK resource-tool identity. Compile caches may be reused across
    source revisions only while this environment identity remains stable.
#>

$EngineResolver = Join-Path $PSScriptRoot 'Resolve-YacsUnrealEngine.ps1'
if (-not (Test-Path -LiteralPath $EngineResolver -PathType Leaf)) {
    throw "Canonical Unreal Engine resolver is missing: $EngineResolver"
}
. $EngineResolver

function Resolve-YacsUnrealToolchain {
    [CmdletBinding()]
    param()

    $ProgramFilesX86 = [Environment]::GetEnvironmentVariable('ProgramFiles(x86)')
    $ProgramFiles = [Environment]::GetEnvironmentVariable('ProgramFiles')
    if (-not $ProgramFilesX86 -or -not $ProgramFiles) {
        return $null
    }

    $VsRoots = [System.Collections.Generic.List[string]]::new()
    $VsWhere = Join-Path $ProgramFilesX86 'Microsoft Visual Studio/Installer/vswhere.exe'
    if (Test-Path -LiteralPath $VsWhere -PathType Leaf) {
        $Resolved = @(
            & $VsWhere -products * -latest `
                -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 `
                -property installationPath 2>$null
        )
        foreach ($Path in $Resolved) {
            if ($Path -and (Test-Path -LiteralPath $Path -PathType Container)) {
                [void] $VsRoots.Add((Resolve-Path -LiteralPath $Path).Path)
            }
        }
    }

    foreach ($Edition in @('BuildTools','Community','Professional','Enterprise')) {
        $Candidate = Join-Path $ProgramFiles "Microsoft Visual Studio/2022/$Edition"
        if (Test-Path -LiteralPath $Candidate -PathType Container) {
            [void] $VsRoots.Add((Resolve-Path -LiteralPath $Candidate).Path)
        }
    }

    $Compiler = $null
    $Linker = $null
    foreach ($VsRoot in @($VsRoots | Select-Object -Unique)) {
        $MsvcRoot = Join-Path $VsRoot 'VC/Tools/MSVC'
        if (-not (Test-Path -LiteralPath $MsvcRoot -PathType Container)) { continue }
        $ToolVersion = Get-ChildItem -LiteralPath $MsvcRoot -Directory -ErrorAction SilentlyContinue |
            Sort-Object -Property Name -Descending |
            Select-Object -First 1
        if (-not $ToolVersion) { continue }

        $Cl = Join-Path $ToolVersion.FullName 'bin/Hostx64/x64/cl.exe'
        $Link = Join-Path $ToolVersion.FullName 'bin/Hostx64/x64/link.exe'
        if ((Test-Path -LiteralPath $Cl -PathType Leaf) -and
            (Test-Path -LiteralPath $Link -PathType Leaf)) {
            $Compiler = $Cl
            $Linker = $Link
            break
        }
    }

    if (-not $Compiler) {
        $Command = Get-Command cl.exe -ErrorAction SilentlyContinue
        if ($Command) {
            $Compiler = $Command.Source
            $LinkCandidate = Join-Path (Split-Path -Parent $Compiler) 'link.exe'
            if (Test-Path -LiteralPath $LinkCandidate -PathType Leaf) {
                $Linker = $LinkCandidate
            }
        }
    }

    if (-not $Compiler -or -not $Linker) {
        return $null
    }

    $SdkRc = $null
    $SdkBin = Join-Path $ProgramFilesX86 'Windows Kits/10/bin'
    if (Test-Path -LiteralPath $SdkBin -PathType Container) {
        $SdkRc = Get-ChildItem -LiteralPath $SdkBin -Directory -ErrorAction SilentlyContinue |
            Sort-Object -Property Name -Descending |
            ForEach-Object { Join-Path $_.FullName 'x64/rc.exe' } |
            Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } |
            Select-Object -First 1
    }

    $ClHash = (Get-FileHash -LiteralPath $Compiler -Algorithm SHA256).Hash.ToLowerInvariant()
    $LinkHash = (Get-FileHash -LiteralPath $Linker -Algorithm SHA256).Hash.ToLowerInvariant()
    $RcHash = if ($SdkRc) {
        (Get-FileHash -LiteralPath $SdkRc -Algorithm SHA256).Hash.ToLowerInvariant()
    }
    else {
        'unresolved'
    }
    $RcPath = if ($SdkRc) { $SdkRc.ToLowerInvariant() } else { 'unresolved' }
    $Identity = @(
        "cl=$($Compiler.ToLowerInvariant())",
        "clSha256=$ClHash",
        "link=$($Linker.ToLowerInvariant())",
        "linkSha256=$LinkHash",
        "rc=$RcPath",
        "rcSha256=$RcHash"
    ) -join '|'

    return [pscustomobject]@{
        CompilerPath = $Compiler
        LinkerPath = $Linker
        ResourceCompilerPath = $SdkRc
        Identity = $Identity
    }
}

function Resolve-YacsUnrealBuildEnvironment {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)] [string] $ProjectPath
    )

    $Engine = Resolve-YacsUnrealEngine -ProjectPath $ProjectPath
    $Toolchain = Resolve-YacsUnrealToolchain
    if (-not $Engine -or -not $Toolchain) {
        return $null
    }

    $Seed = "$($Engine.Identity)`n$($Toolchain.Identity)"
    $Bytes = [System.Text.Encoding]::UTF8.GetBytes($Seed)
    $Hasher = [System.Security.Cryptography.SHA256]::Create()
    try {
        $Identity = ([System.BitConverter]::ToString($Hasher.ComputeHash($Bytes))).Replace('-', '').ToLowerInvariant()
    }
    finally {
        $Hasher.Dispose()
    }

    return [pscustomobject]@{
        Engine = $Engine
        Toolchain = $Toolchain
        Identity = $Identity
    }
}
