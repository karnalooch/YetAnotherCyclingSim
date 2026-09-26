<#
.SYNOPSIS
    Fail closed when a code-only CI checkout materializes Git LFS payloads.

.DESCRIPTION
    The hosted UE code canary only needs project source/config/scripts. Large
    Unreal/source-media assets are expected to remain as Git LFS pointer files.
    This guard prevents an accidental checkout or workflow change from turning
    a code-only lane into an expensive asset download.
#>
[CmdletBinding()]
param(
    [string] $RepoRoot = (Resolve-Path -LiteralPath (Join-Path -Path $PSScriptRoot -ChildPath '../..')).Path
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
Push-Location -LiteralPath $RepoRoot
try {
    & git lfs version | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw 'Git LFS is required to verify the code-only checkout contract.'
    }

    $lfsPaths = @(
        & git lfs ls-files --name-only |
            ForEach-Object { $_.Trim() } |
            Where-Object { $_ }
    )
    if ($LASTEXITCODE -ne 0) {
        throw 'Could not enumerate Git LFS tracked paths.'
    }

    $materialized = [System.Collections.Generic.List[string]]::new()
    foreach ($path in $lfsPaths) {
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
            throw "Tracked Git LFS path is missing from checkout: $path"
        }

        & git lfs pointer --check "--file=$path" *> $null
        if ($LASTEXITCODE -ne 0) {
            [void]$materialized.Add($path)
        }
    }

    if ($materialized.Count -gt 0) {
        throw (
            "Code-only checkout materialized Git LFS payload(s): {0}. " +
            "Keep GIT_LFS_SKIP_SMUDGE=1 and pull assets only in an explicit asset lane."
        ) -f ($materialized -join ', ')
    }

    Write-Host (
        "CODE-ONLY CHECKOUT PASS: {0} Git LFS path(s) remain pointer-only." -f
        $lfsPaths.Count
    ) -ForegroundColor Green
} finally {
    Pop-Location
}
