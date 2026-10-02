#requires -Version 7.4
[CmdletBinding()]
param([Parameter(Mandatory)][string]$RunnerRoot, [ValidateSet('Worker','Runner')][string]$Kind = 'Worker')
$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot 'RunnerMonitor.psm1') -Force
$diag = Join-Path $RunnerRoot '_diag'
$current = ''; $cursor = @{}
Write-Host 'Local diagnostic stream. Ctrl+C closes this viewer; it does not stop the runner.'
while ($true) {
    $latest = Get-ChildItem -LiteralPath $diag -Filter ($Kind + '_*.log') -File | Sort-Object Name | Select-Object -Last 1
    if ($latest) {
        if ($latest.FullName -ne $current) {
            $current = $latest.FullName
            Write-Host ("`nReading " + $latest.Name) -ForegroundColor Cyan
            Get-Content -LiteralPath $current -Tail 60
            $cursor = @{ Offset = $latest.Length; Pending = ''; Decoder = [Text.Encoding]::UTF8.GetDecoder() }
        }
        Read-YacsLogDelta $current $cursor
    }
    Start-Sleep -Seconds 1
}
