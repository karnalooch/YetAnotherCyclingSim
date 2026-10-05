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

function ConvertFrom-YacsLfsListing {
    param(
        [Parameter(Mandatory=$true)] [string[]] $Lines,
        [Parameter(Mandatory=$true)] [string] $Context
    )

    $records = @{}
    foreach ($rawLine in $Lines) {
        $line = [string]$rawLine
        if (-not $line) {
            continue
        }

        # git lfs ls-files --long emits:
        # <64-char oid> <* for materialized | - for pointer> <path>
        $match = [regex]::Match(
            $line,
            '^(?<oid>[0-9a-fA-F]{64}) (?<state>[*-]) (?<path>.+)$'
        )
        if (-not $match.Success) {
            throw "Unexpected Git LFS listing in ${Context}: $line"
        }

        $path = $match.Groups['path'].Value
        if ($records.ContainsKey($path)) {
            throw "Duplicate Git LFS path in ${Context}: $path"
        }

        $records[$path] = [pscustomobject]@{
            Oid = $match.Groups['oid'].Value.ToLowerInvariant()
            State = $match.Groups['state'].Value
        }
    }

    return $records
}

$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
Push-Location -LiteralPath $RepoRoot
try {
    & git lfs version | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw 'Git LFS is required to verify the code-only checkout contract.'
    }

    # Enumerate committed pointers once. Supplying HEAD makes the repository tree
    # the source of truth without spawning one git cat-file / git-lfs process per
    # asset.
    $headOutput = @(& git lfs ls-files --long HEAD)
    if ($LASTEXITCODE -ne 0) {
        throw 'Could not enumerate committed Git LFS pointers at HEAD.'
    }
    $head = ConvertFrom-YacsLfsListing -Lines $headOutput -Context 'HEAD'

    # Enumerate working-tree state once. Git LFS reports '*' for a materialized
    # object and '-' for a pointer, so hundreds of per-file pointer checks are
    # unnecessary.
    $workOutput = @(& git lfs ls-files --long)
    if ($LASTEXITCODE -ne 0) {
        throw 'Could not enumerate working-tree Git LFS state.'
    }
    $work = ConvertFrom-YacsLfsListing -Lines $workOutput -Context 'working tree'

    $materialized = [System.Collections.Generic.List[string]]::new()
    $pointerOnly = 0
    $lazyMissing = 0

    foreach ($path in @($head.Keys | Sort-Object)) {
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
            $lazyMissing += 1
            Write-Host ("CODE-ONLY LFS LAZY: {0}" -f $path)
            continue
        }

        if (-not $work.ContainsKey($path)) {
            throw "Working-tree Git LFS state is missing for committed pointer: $path"
        }

        switch ($work[$path].State) {
            '-' {
                $pointerOnly += 1
            }
            '*' {
                [void]$materialized.Add($path)
            }
            default {
                throw "Unsupported Git LFS state for ${path}: $($work[$path].State)"
            }
        }
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
        $head.Count,
        $pointerOnly,
        $lazyMissing
    ) -ForegroundColor Green
} finally {
    Pop-Location
}
