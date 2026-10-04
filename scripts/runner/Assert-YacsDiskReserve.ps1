#requires -Version 7.4
function Assert-YacsDiskReserve {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$Path,
        [ValidateRange(1, 4096)][double]$MinimumFreeGiB = 50,
        [long]$AvailableBytes = -1
    )
    $root = [IO.Path]::GetPathRoot([IO.Path]::GetFullPath($Path))
    if ($AvailableBytes -lt 0) { $AvailableBytes = ([IO.DriveInfo]::new($root)).AvailableFreeSpace }
    $free = $AvailableBytes / 1GB
    if ($free -lt $MinimumFreeGiB) {
        throw ('YACS disk reserve: {0:N2} GiB free on {1}; {2:N0} GiB required. Job stopped before heavy work. Review stale build outputs; do not delete source assets or retained caches.' -f $free, $root, $MinimumFreeGiB)
    }
    Write-Output ('YACS disk reserve OK: {0:N2} GiB free; minimum {1:N0} GiB.' -f $free, $MinimumFreeGiB)
}
