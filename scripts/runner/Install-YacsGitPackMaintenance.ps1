#requires -Version 7.4
[CmdletBinding()]
param([Parameter(Mandatory)][string]$WorkspaceConfig, [switch]$Apply)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
function Assert-NoReparse([string]$Path) {
    $part = [IO.Path]::GetFullPath($Path)
    while ($part) {
        if ((Test-Path -LiteralPath $part) -and ((Get-Item -LiteralPath $part -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw "Reparse path refused: $part" }
        $part = [IO.Path]::GetDirectoryName($part)
    }
}
Assert-NoReparse $WorkspaceConfig
$configPath = (Resolve-Path -LiteralPath $WorkspaceConfig).Path
$root = Split-Path -Parent $configPath
$config = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
if ($config.schema_version -ne 1 -or $config.runner -cne 'runner') { throw 'Canonical runner configuration required.' }
$runner = Join-Path $root 'runner'
$install = Join-Path $root 'tools/runner-git-maintenance'
foreach ($path in @($configPath, $runner, $install)) {
    Assert-NoReparse $path
}
$files = @('Invoke-YacsJobStarted.ps1', 'Assert-YacsDiskReserve.ps1', 'maintain_git_packs.py')
$hashes = [ordered]@{}
foreach ($name in $files) {
    $hashes[$name] = (Get-FileHash -LiteralPath (Join-Path $PSScriptRoot $name) -Algorithm SHA256).Hash.ToLowerInvariant()
}
$identity = $hashes | ConvertTo-Json -Compress
$sha = [Security.Cryptography.SHA256]::HashData([Text.Encoding]::UTF8.GetBytes($identity))
$bundleId = [Convert]::ToHexString($sha).ToLowerInvariant()
$bundle = Join-Path $install "bundles/$bundleId"
$entrypoint = Join-Path $install 'Invoke-YacsJobStarted.ps1'
$envPath = Join-Path $runner '.env'
foreach ($path in @($envPath, $entrypoint, $bundle)) { Assert-NoReparse $path }
$envText = [IO.File]::ReadAllText($envPath)
$linePattern = '(?m)^ACTIONS_RUNNER_HOOK_JOB_STARTED=[^\r\n]*(?=\r?$)'
$previous = [regex]::Matches($envText, $linePattern)
if ($previous.Count -gt 1) { throw 'Ambiguous pre-job hook configuration.' }
$result = [ordered]@{schema_version=1;apply=[bool]$Apply;bundle=$bundle;bundle_sha256=$bundleId;files=$hashes;entrypoint=$entrypoint;previous_hook=if($previous.Count){$previous[0].Value.TrimEnd("`r")}else{$null}}
if (-not $Apply) { $result | ConvertTo-Json -Depth 5; return }
if (Get-Process Runner.Worker,Runner.Listener -ErrorAction SilentlyContinue) { throw 'Stop only the idle listener before installation; never stop a Worker or Editor.' }
if (Test-Path -LiteralPath $bundle) {
    foreach ($name in $files) {
        Assert-NoReparse (Join-Path $bundle $name)
        if ((Get-FileHash -LiteralPath (Join-Path $bundle $name) -Algorithm SHA256).Hash.ToLowerInvariant() -cne $hashes[$name]) { throw 'Installed bundle drift; refusing replacement.' }
    }
} else {
    [void][IO.Directory]::CreateDirectory($bundle)
    foreach ($name in $files) { Copy-Item -LiteralPath (Join-Path $PSScriptRoot $name) -Destination (Join-Path $bundle $name) }
}
# Stable entrypoint verifies the entire immutable bundle before executing it.
$wrapper = @("#requires -Version 7.4", "`$ErrorActionPreference = 'Stop'", "`$bundle = Join-Path `$PSScriptRoot 'bundles/$bundleId'")
foreach ($name in $files) {
    $wrapper += "if ((Get-FileHash -LiteralPath (Join-Path `$bundle '$name') -Algorithm SHA256).Hash.ToLowerInvariant() -cne '$($hashes[$name])') { throw 'Git maintenance bundle hash mismatch: $name' }"
}
$wrapper += "& (Join-Path `$bundle 'Invoke-YacsJobStarted.ps1')"
$stamp = [Guid]::NewGuid().ToString('N')
if (Test-Path -LiteralPath $entrypoint) { Copy-Item -LiteralPath $entrypoint -Destination (Join-Path $install "$stamp.previous.ps1") }
$temporary = Join-Path $install "$stamp.new.ps1"
[IO.File]::WriteAllText($temporary, ($wrapper -join "`n") + "`n", [Text.UTF8Encoding]::new($false))
[IO.File]::Move($temporary, $entrypoint, $true)
$replacement = 'ACTIONS_RUNNER_HOOK_JOB_STARTED=' + $entrypoint
$updated = if ($previous.Count) { [regex]::Replace($envText, $linePattern, [Text.RegularExpressions.MatchEvaluator]{param($m) $replacement}) } else { $envText.TrimEnd("`r","`n") + "`r`n" + $replacement + "`r`n" }
$envTemporary = Join-Path $runner ".env.git-maintenance-$stamp"
[IO.File]::WriteAllText($envTemporary, $updated, [Text.UTF8Encoding]::new($false))
[IO.File]::Move($envTemporary, $envPath, $true)
$result.status = 'INSTALLED_RESTART_AND_JOB_PROOF_PENDING'
$result | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $install "$stamp.deployment.json") -Encoding utf8
$result | ConvertTo-Json -Depth 5
