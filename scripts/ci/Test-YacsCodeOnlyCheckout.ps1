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

    $lfsOutput = @(& git lfs ls-files --name-only)
    if ($LASTEXITCODE -ne 0) {
        throw 'Could not enumerate Git LFS tracked paths.'
    }
    $lfsPaths = @(
        $lfsOutput |
            ForEach-Object { $_.Trim() } |
            Where-Object { $_ }
    )

    $materialized = [System.Collections.Generic.List[string]]::new()
    $pointerOnly = 0
    $lazyMissing = 0

    foreach ($path in $lfsPaths) {
        # The committed Git blob is the source of truth. A blobless clone may
        # legitimately leave the working-tree path absent until it is needed,
        # but HEAD:path must still be a valid Git LFS pointer.
        & git cat-file blob "HEAD:$path" | & git lfs pointer --check --stdin *> $null
        if ($LASTEXITCODE -ne 0) {
            throw "Committed Git blob is not a valid LFS pointer: $path"
        }

        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
            $lazyMissing += 1
            Write-Host ("CODE-ONLY LFS LAZY: {0}" -f $path)
            continue
        }

        & git lfs pointer --check "--file=$path" *> $null
        if ($LASTEXITCODE -eq 0) {
            $pointerOnly += 1
            continue
        }

        [void]$materialized.Add($path)
    }

    if ($materialized.Count -gt 0) {
        throw (
            (
                "Code-only checkout materialized Git LFS payload(s): {0}. " +
                "Keep GIT_LFS_SKIP_SMUDGE=1 and pull assets only in an explicit asset lane."
            ) -f ($materialized -join ', ')
        )
    }

    Write-Host (
        "CODE-ONLY CHECKOUT PASS: tracked={0}; pointerOnly={1}; lazyMissing={2}; materialized=0." -f
        $lfsPaths.Count,
        $pointerOnly,
        $lazyMissing
    ) -ForegroundColor Green
} finally {
    Pop-Location
}
