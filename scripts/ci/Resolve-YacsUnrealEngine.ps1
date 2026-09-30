<#
.SYNOPSIS
    Canonical Unreal Engine resolver for YACS proof and cache lanes.

.DESCRIPTION
    Resolves the engine required by YetAnotherCyclingSim.uproject and returns
    one deterministic engine context. Build/preflight and cache validation must
    consume this function instead of maintaining independent search policies.
#>

function Resolve-YacsUnrealEngine {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)] [string] $ProjectPath,
        [string[]] $SearchRoots = @(
            'D:\Epic Games',
            'C:\Program Files\Epic Games',
            'C:\Epic Games',
            'D:\UE_5.8',
            'D:\UE_5.7',
            'C:\UE_5.8'
        )
    )

    if (-not (Test-Path -LiteralPath $ProjectPath -PathType Leaf)) {
        throw "YACS project file does not exist: $ProjectPath"
    }
    $ProjectPath = (Resolve-Path -LiteralPath $ProjectPath).Path

    try {
        $Project = Get-Content -LiteralPath $ProjectPath -Raw -ErrorAction Stop |
            ConvertFrom-Json -ErrorAction Stop
    }
    catch {
        throw "Cannot parse YACS project descriptor '$ProjectPath': $($_.Exception.Message)"
    }

    $Association = [string] $Project.EngineAssociation
    $AssociationMatch = [regex]::Match(
        $Association,
        '^(?<major>[0-9]+)\.(?<minor>[0-9]+)$'
    )
    if (-not $AssociationMatch.Success) {
        throw "Unsupported EngineAssociation '$Association' in '$ProjectPath'; expected major.minor."
    }
    $ExpectedMajor = [int] $AssociationMatch.Groups['major'].Value
    $ExpectedMinor = [int] $AssociationMatch.Groups['minor'].Value

    $Candidates = [System.Collections.Generic.List[string]]::new()
    foreach ($SearchRoot in $SearchRoots) {
        if (-not (Test-Path -LiteralPath $SearchRoot -PathType Container)) {
            continue
        }

        $DirectUat = Join-Path $SearchRoot 'Engine/Build/BatchFiles/RunUAT.bat'
        if (Test-Path -LiteralPath $DirectUat -PathType Leaf) {
            [void] $Candidates.Add((Resolve-Path -LiteralPath $SearchRoot).Path)
            continue
        }

        $Children = Get-ChildItem -LiteralPath $SearchRoot -Directory -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -match '^(UE_[0-9]+\.[0-9]+|UE_[0-9]+|UnrealEngine)$' } |
            Sort-Object -Property FullName
        foreach ($Child in $Children) {
            [void] $Candidates.Add($Child.FullName)
        }
    }

    $Seen = @{}
    foreach ($Candidate in $Candidates) {
        $Root = (Resolve-Path -LiteralPath $Candidate).Path
        $Key = $Root.ToLowerInvariant()
        if ($Seen.ContainsKey($Key)) { continue }
        $Seen[$Key] = $true

        $BuildVersionPath = Join-Path $Root 'Engine/Build/Build.version'
        $BuildBatPath = Join-Path $Root 'Engine/Build/BatchFiles/Build.bat'
        $UatPath = Join-Path $Root 'Engine/Build/BatchFiles/RunUAT.bat'
        $EditorCmdPath = Join-Path $Root 'Engine/Binaries/Win64/UnrealEditor-Cmd.exe'
        $EditorPath = Join-Path $Root 'Engine/Binaries/Win64/UnrealEditor.exe'

        if (-not (Test-Path -LiteralPath $BuildVersionPath -PathType Leaf)) { continue }
        if (-not (Test-Path -LiteralPath $BuildBatPath -PathType Leaf)) { continue }
        if (-not (Test-Path -LiteralPath $UatPath -PathType Leaf)) { continue }
        if (-not (Test-Path -LiteralPath $EditorCmdPath -PathType Leaf)) { continue }

        try {
            $VersionJson = Get-Content -LiteralPath $BuildVersionPath -Raw -ErrorAction Stop |
                ConvertFrom-Json -ErrorAction Stop
        }
        catch {
            continue
        }

        if ([int] $VersionJson.MajorVersion -ne $ExpectedMajor -or
            [int] $VersionJson.MinorVersion -ne $ExpectedMinor) {
            continue
        }

        $BuildVersionHash = (Get-FileHash -LiteralPath $BuildVersionPath -Algorithm SHA256).Hash.ToLowerInvariant()
        $BuildBatHash = (Get-FileHash -LiteralPath $BuildBatPath -Algorithm SHA256).Hash.ToLowerInvariant()
        $EditorCmdHash = (Get-FileHash -LiteralPath $EditorCmdPath -Algorithm SHA256).Hash.ToLowerInvariant()
        $Version = ('{0}.{1}.{2}-{3}' -f
            $VersionJson.MajorVersion,
            $VersionJson.MinorVersion,
            $VersionJson.PatchVersion,
            $VersionJson.Changelist)
        $CanonicalRoot = $Root.ToLowerInvariant()
        $Identity = @(
            "root=$CanonicalRoot",
            "association=$Association",
            "version=$Version",
            "buildVersionSha256=$BuildVersionHash",
            "buildBatSha256=$BuildBatHash",
            "editorCmdSha256=$EditorCmdHash"
        ) -join '|'
        $ResolvedEditorPath = if (Test-Path -LiteralPath $EditorPath -PathType Leaf) {
            $EditorPath
        }
        else {
            $null
        }

        return [pscustomobject]@{
            Root = $Root
            Association = $Association
            Version = $Version
            VersionObject = [pscustomobject]@{
                MajorVersion = [int] $VersionJson.MajorVersion
                MinorVersion = [int] $VersionJson.MinorVersion
                PatchVersion = [int] $VersionJson.PatchVersion
                Changelist = [int] $VersionJson.Changelist
                CompatibleChangelist = [int] $VersionJson.CompatibleChangelist
                IsLicenseeVersion = [bool] $VersionJson.IsLicenseeVersion
                BranchName = [string] $VersionJson.BranchName
            }
            BuildVersionPath = $BuildVersionPath
            BuildBatPath = $BuildBatPath
            UATPath = $UatPath
            UnrealEditorCmdPath = $EditorCmdPath
            UnrealEditorPath = $ResolvedEditorPath
            BuildVersionSha256 = $BuildVersionHash
            BuildBatSha256 = $BuildBatHash
            UnrealEditorCmdSha256 = $EditorCmdHash
            Identity = $Identity
        }
    }

    return $null
}
