#requires -Version 7.4
<#
.SYNOPSIS
    Read the fixed accepted #363 artifact and compare its retained host metadata.

.DESCRIPTION
    Trusted native-proof preflight only. The parent must resolve the exact engine
    and obtain an idle host before invoking this script. Downloads one fixed
    repository artifact, verifies its immutable ZIP hash, and reads only six
    fixed JSON members. No Editor/server, extraction of assets/PNGs, restoration,
    source/profile read, cleanup or consumer admission is performed.

    YACS_CHECKPOINT_READ_TOKEN needs actions:read. It is never logged. HttpClient
    uses its normal redirect handling, which removes Authorization on redirects.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string] $ArtifactRoot
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$RepoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$SourceSha = '94827365ef8e83e52717bb21f9d6efa921aa2d1e'
$SourceRun = '37954100285'
$SourceAttempt = 1
$ArtifactId = '11628546016'
$ZipSha256 = '3f65958a52cd476bbf268eea7cb884ada06206e15b3fd00286162848e0bece9c'
$ExpectedZipBytes = 10037061
$DownloadLimit = 16MB
$JsonLimit = 2MB
$ArchiveLimit = 64MB
$HostProofRoot = 'D:\yacs\work\proofs\sa-calobra-whole-map\94827365ef8e83e52717bb21f9d6efa921aa2d1e\37954100285-1'
$SelectedNames = @(
    'saved-material-consumer/consumer-manifest.json',
    'saved-material-consumer/delivery-package-manifest.json',
    'saved-material-consumer/reload-receipt.json',
    'saved-material-consumer/fresh-render-receipt.json',
    'checkout-restoration.json',
    'checkout-restoration-post-material.json'
)
$AdditionalHostNames = @(
    'whole-map-master-receipt.json',
    'generated-assets-verification.json',
    'native-proof-verification.json',
    'capture/whole-map-prep/whole-map-prep-receipt.json',
    'whole-map-prep/surface-prep-manifest.json',
    'native-api-evidence.json'
)
$script:CheckpointConsoleLines = 0

function Write-CheckpointLine {
    param([Parameter(Mandatory)][string] $Text)
    if ($Text.Length -gt 8192) {
        $Text = 'YACS_ACCEPTED363_CONSOLE_TRUNCATED ' + ([ordered]@{
            record = ($Text -split ' ', 2)[0]
            reason = 'LINE_CHARACTER_LIMIT'
            original_chars = $Text.Length
            limit_chars = 8192
            full_json_retained = $true
        } | ConvertTo-Json -Compress -Depth 4)
    }
    $script:CheckpointConsoleLines += @($Text -split '\r?\n').Count
    if ($script:CheckpointConsoleLines -gt 1000) {
        throw 'Accepted checkpoint console output exceeded its fixed line bound.'
    }
    Write-Host $Text
}

function Assert-NoCheckpointAlias {
    param([Parameter(Mandatory)][string] $Path)
    $cursor = [IO.Path]::GetFullPath($Path)
    while ($cursor) {
        if (Test-Path -LiteralPath $cursor) {
            $entry = Get-Item -LiteralPath $cursor -Force
            if ($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) {
                throw 'Accepted checkpoint paths cannot use symlinks or junctions.'
            }
        }
        $parent = [IO.Path]::GetDirectoryName($cursor)
        if ($parent -eq $cursor) { break }
        $cursor = $parent
    }
}

function Get-CheckpointBytesIdentity {
    param([Parameter(Mandatory)][byte[]] $Bytes)
    $digest = [Security.Cryptography.SHA256]::HashData($Bytes)
    return [ordered]@{
        sha256 = [Convert]::ToHexString($digest).ToLowerInvariant()
        size_bytes = $Bytes.Length
    }
}

function Read-BoundedCheckpointStream {
    param(
        [Parameter(Mandatory)][IO.Stream] $Stream,
        [Parameter(Mandatory)][long] $Limit
    )
    $memory = [IO.MemoryStream]::new()
    try {
        $buffer = [byte[]]::new(64KB)
        $total = 0L
        while (($count = $Stream.Read($buffer, 0, $buffer.Length)) -gt 0) {
            $total += $count
            if ($total -gt $Limit) { throw 'Accepted checkpoint JSON exceeds its read bound.' }
            $memory.Write($buffer, 0, $count)
        }
        return ,$memory.ToArray()
    }
    finally { $memory.Dispose() }
}

function Read-CheckpointHostJson {
    param([Parameter(Mandatory)][string] $Name)
    $receipt.retained_metadata_path = $Name
    $receipt.retained_metadata_observed_bytes = $null
    $path = Join-Path $HostProofRoot $Name
    Assert-NoCheckpointAlias $path
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        return [ordered]@{ status = 'MISSING'; sha256 = $null; size_bytes = $null }
    }
    $file = [IO.FileStream]::new($path, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::Read)
    try {
        $receipt.retained_metadata_observed_bytes = $file.Length
        if ($file.Length -gt $JsonLimit) { throw 'Retained checkpoint JSON exceeds its bound.' }
        $bytes = Read-BoundedCheckpointStream -Stream $file -Limit $JsonLimit
        if ($bytes.Length -ne $file.Length) { throw 'Retained checkpoint JSON changed during read.' }
    }
    finally { $file.Dispose() }
    return [ordered]@{ status = 'READ'; bytes = $bytes; identity = (Get-CheckpointBytesIdentity $bytes) }
}

if (-not $IsWindows) { throw 'Accepted checkpoint discovery requires the trusted Windows host.' }
if (-not [IO.Path]::IsPathFullyQualified($ArtifactRoot)) { throw 'Use an absolute parent artifact directory.' }
Assert-NoCheckpointAlias $RepoRoot
Assert-NoCheckpointAlias $ArtifactRoot
$ArtifactRoot = [IO.Path]::GetFullPath($ArtifactRoot)
if ($RepoRoot.TrimEnd('\', '/') -ieq 'D:\yacs\project') {
    throw 'Accepted checkpoint discovery cannot write evidence into the live project.'
}
$allowedRoot = [IO.Path]::GetFullPath((Join-Path $RepoRoot 'Saved/RuntimeProof'))
$relativeRoot = [IO.Path]::GetRelativePath($allowedRoot, $ArtifactRoot)
if ($relativeRoot -eq '.' -or [IO.Path]::IsPathFullyQualified($relativeRoot) `
    -or $relativeRoot -eq '..' -or $relativeRoot.StartsWith('..\') -or $relativeRoot.StartsWith('../')) {
    throw 'Accepted checkpoint evidence must stay below the isolated Saved/RuntimeProof root.'
}
if (-not (Test-Path -LiteralPath $ArtifactRoot -PathType Container)) {
    throw 'The trusted parent must reserve its artifact directory before discovery.'
}
$output = Join-Path $ArtifactRoot 'Accepted363'
if (Test-Path -LiteralPath $output) { throw 'Accepted363 evidence already exists; no overwrite.' }
& git -C $RepoRoot check-ignore --no-index --quiet -- (Join-Path $output 'accepted-read.json')
if ($LASTEXITCODE -ne 0) { throw 'Accepted checkpoint evidence destination must be Git-ignored.' }
New-Item -ItemType Directory -Path $output | Out-Null
$zipPath = Join-Path $output 'accepted.zip'
$receipt = [ordered]@{
    schema_version = 1
    status = 'READ_PENDING'
    source_exact_sha = $SourceSha
    source_run_id = $SourceRun
    source_run_attempt = $SourceAttempt
    source_proof_root = $HostProofRoot
    artifact_id = $ArtifactId
    artifact_name = "sa-calobra-material-review-$SourceSha-$SourceRun-$SourceAttempt"
    expected_zip_sha256 = $ZipSha256
    expected_zip_size_bytes = $ExpectedZipBytes
    downloaded_zip_sha256 = $null
    downloaded_zip_size_bytes = $null
    download_http_status = $null
    zip_verified = $false
    archive_entry_count = $null
    archive_uncompressed_bytes = $null
    selected_json = @()
    additional_host_json = @()
    consumer_assets = @()
    consumer_metadata = $null
    consumer_admission = 'PENDING_VALIDATION'
    native_runtime_verified = $false
    official_mcp_admitted = $false
    restoration_performed = $false
    retained_metadata_path = $null
    retained_metadata_observed_bytes = $null
    error_code = $null
    local_exception_type = $null
    error = $null
}
$phase = 'download'
try {
    if (-not $env:YACS_CHECKPOINT_READ_TOKEN) { throw 'An actions-read token is required for the fixed artifact.' }
    $client = [Net.Http.HttpClient]::new()
    $deadline = [Threading.CancellationTokenSource]::new([TimeSpan]::FromSeconds(60))
    $request = [Net.Http.HttpRequestMessage]::new(
        [Net.Http.HttpMethod]::Get,
        'https://api.github.com/repos/karnalooch/YetAnotherCyclingSim/actions/artifacts/11628546016/zip'
    )
    $response = $null
    $download = $null
    $destination = $null
    try {
        $client.Timeout = [TimeSpan]::FromSeconds(60)
        $request.Headers.Authorization = [Net.Http.Headers.AuthenticationHeaderValue]::new('Bearer', $env:YACS_CHECKPOINT_READ_TOKEN)
        $request.Headers.UserAgent.ParseAdd('YACS-Accepted363-Checkpoint-Read')
        $request.Headers.Accept.ParseAdd('application/vnd.github+json')
        $request.Headers.Add('X-GitHub-Api-Version', '2022-11-28')
        $response = $client.SendAsync($request, [Net.Http.HttpCompletionOption]::ResponseHeadersRead, $deadline.Token).GetAwaiter().GetResult()
        $receipt.download_http_status = [int]$response.StatusCode
        if (-not $response.IsSuccessStatusCode) { throw 'The fixed accepted artifact download was unsuccessful.' }
        if ($response.Content.Headers.ContentLength -and $response.Content.Headers.ContentLength -gt $DownloadLimit) {
            throw 'Accepted artifact declared a download larger than its fixed bound.'
        }
        $download = $response.Content.ReadAsStreamAsync($deadline.Token).GetAwaiter().GetResult()
        $destination = [IO.FileStream]::new($zipPath, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
        $buffer = [byte[]]::new(64KB)
        $downloaded = 0L
        while (($count = $download.ReadAsync($buffer, 0, $buffer.Length, $deadline.Token).GetAwaiter().GetResult()) -gt 0) {
            $downloaded += $count
            if ($downloaded -gt $DownloadLimit) { throw 'Accepted artifact exceeded its streamed download bound.' }
            $destination.Write($buffer, 0, $count)
        }
        $receipt.downloaded_zip_size_bytes = $downloaded
    }
    finally {
        if ($destination) { $destination.Dispose() }
        if ($download) { $download.Dispose() }
        if ($response) { $response.Dispose() }
        $request.Dispose()
        $deadline.Dispose()
        $client.Dispose()
    }
    $phase = 'ZIP identity'
    $receipt.downloaded_zip_sha256 = (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($receipt.downloaded_zip_size_bytes -ne $ExpectedZipBytes -or $receipt.downloaded_zip_sha256 -cne $ZipSha256) {
        throw 'Accepted artifact ZIP differs from its immutable identity.'
    }
    $receipt.zip_verified = $true
    $phase = 'bounded ZIP directory'
    $zipStream = [IO.FileStream]::new($zipPath, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::Read)
    $archive = $null
    $values = @{}
    try {
        $archive = [IO.Compression.ZipArchive]::new($zipStream, [IO.Compression.ZipArchiveMode]::Read, $true)
        if ($archive.Entries.Count -gt 512) { throw 'Accepted artifact ZIP exceeds its entry bound.' }
        $entries = [Collections.Generic.Dictionary[string, IO.Compression.ZipArchiveEntry]]::new([StringComparer]::OrdinalIgnoreCase)
        $uncompressed = 0L
        foreach ($entry in $archive.Entries) {
            $name = $entry.FullName
            $trimmed = $name.TrimEnd('/')
            if (-not $trimmed -or $name.Contains('\') -or $name.Contains(':') -or $name.Contains([char]0) `
                -or $name.StartsWith('/') -or @($trimmed.Split('/') | Where-Object { $_ -in @('', '.', '..') }).Count) {
                throw 'Accepted artifact ZIP contains an unsafe entry name.'
            }
            $fileType = ($entry.ExternalAttributes -shr 16) -band 0xF000
            if ($fileType -notin @(0, 0x8000, 0x4000) -or $entries.ContainsKey($name)) {
                throw 'Accepted artifact ZIP contains aliases or duplicate entries.'
            }
            $entries.Add($name, $entry)
            $uncompressed += $entry.Length
            if ($uncompressed -gt $ArchiveLimit) { throw 'Accepted artifact ZIP exceeds its uncompressed byte bound.' }
        }
        $receipt.archive_entry_count = $archive.Entries.Count
        $receipt.archive_uncompressed_bytes = $uncompressed
        $phase = 'selected JSON'
        foreach ($name in $SelectedNames) {
            if (-not $entries.ContainsKey($name) -or $entries[$name].FullName -cne $name) {
                throw 'Accepted artifact is missing a fixed JSON member.'
            }
            $entry = $entries[$name]
            if ($entry.Length -gt $JsonLimit) { throw 'Accepted artifact JSON exceeds its declared byte bound.' }
            $entryStream = $entry.Open()
            try { $bytes = Read-BoundedCheckpointStream -Stream $entryStream -Limit $JsonLimit }
            finally { $entryStream.Dispose() }
            if ($bytes.Length -ne $entry.Length) { throw 'Accepted artifact JSON length differs from its ZIP entry.' }
            $value = [Text.Encoding]::UTF8.GetString($bytes) | ConvertFrom-Json -AsHashtable -Depth 64
            if ($value -isnot [Collections.IDictionary]) {
                throw 'Accepted artifact JSON has an unsupported top-level schema.'
            }
            # The frozen producer's reload receipt intentionally has no schema
            # field. All other selected members use schema_version 1.
            if ($name -eq 'saved-material-consumer/reload-receipt.json') {
                if ($value.Contains('schema_version') -or $value.status -cne 'SAVED_MATERIAL_CONSUMER_RELOADED') {
                    throw 'Accepted artifact reload receipt differs from its frozen producer contract.'
                }
            }
            elseif ($value.schema_version -ne 1) {
                throw 'Accepted artifact JSON has an unsupported top-level schema.'
            }
            if ($name -ne 'saved-material-consumer/delivery-package-manifest.json' -and $value.exact_sha -cne $SourceSha) {
                throw 'Accepted artifact JSON has a different source checkpoint SHA.'
            }
            $target = Join-Path (Join-Path $output 'json') $name
            Assert-NoCheckpointAlias $target
            New-Item -ItemType Directory -Path (Split-Path $target -Parent) -Force | Out-Null
            $writer = [IO.FileStream]::new($target, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
            try { $writer.Write($bytes, 0, $bytes.Length) }
            finally { $writer.Dispose() }
            $identity = Get-CheckpointBytesIdentity $bytes
            $hostJson = Read-CheckpointHostJson $name
            $hostIdentity = if ($hostJson.status -eq 'READ') { $hostJson.identity } else { $null }
            $row = [ordered]@{
                path = $name
                archive_sha256 = $identity.sha256
                size_bytes = $identity.size_bytes
                host_status = $hostJson.status
                host_sha256 = if ($hostIdentity) { $hostIdentity.sha256 } else { $null }
                host_size_bytes = if ($hostIdentity) { $hostIdentity.size_bytes } else { $null }
                host_matches_archive = if ($hostIdentity) { $hostIdentity.sha256 -ceq $identity.sha256 -and $hostIdentity.size_bytes -eq $identity.size_bytes } else { $null }
            }
            $receipt.selected_json += $row
            $values[$name] = $value
            Write-CheckpointLine ('YACS_ACCEPTED363_JSON ' + ($row | ConvertTo-Json -Compress -Depth 8))
        }
    }
    finally {
        if ($archive) { $archive.Dispose() }
        $zipStream.Dispose()
    }
    $phase = 'retained metadata'
    $consumer = $values['saved-material-consumer/consumer-manifest.json']
    $sourceProofFields = @{
        'whole-map-master-receipt.json' = 'master_receipt_sha256'
        'generated-assets-verification.json' = 'retained_packages_receipt_sha256'
        'native-proof-verification.json' = 'native_verification_sha256'
        'capture/whole-map-prep/whole-map-prep-receipt.json' = 'capture_receipt_sha256'
        'whole-map-prep/surface-prep-manifest.json' = 'prep_manifest_sha256'
    }
    foreach ($name in $AdditionalHostNames) {
        $hostJson = Read-CheckpointHostJson $name
        $expectedHostHash = if ($sourceProofFields.ContainsKey($name)) {
            $consumer.source_proof[$sourceProofFields[$name]]
        } else { $null }
        $row = [ordered]@{
            path = $name
            archive_status = 'NOT_INCLUDED_IN_COMPACT_ARTIFACT'
            host_status = $hostJson.status
            sha256 = if ($hostJson.status -eq 'READ') { $hostJson.identity.sha256 } else { $null }
            size_bytes = if ($hostJson.status -eq 'READ') { $hostJson.identity.size_bytes } else { $null }
            consumer_source_proof_sha256 = $expectedHostHash
            host_matches_consumer_source_proof = if ($hostJson.status -eq 'READ' -and $expectedHostHash) {
                $hostJson.identity.sha256 -ceq $expectedHostHash
            } else { $null }
        }
        $receipt.additional_host_json += $row
        Write-CheckpointLine ('YACS_ACCEPTED363_HOST_JSON ' + ($row | ConvertTo-Json -Compress -Depth 8))
    }
    if ($consumer.assets -isnot [Collections.IList] -or $consumer.assets.Count -gt 256) {
        throw 'Accepted consumer asset metadata exceeds the fixed discovery bound.'
    }
    $receipt.consumer_assets = $consumer.assets
    foreach ($asset in $consumer.assets) {
        Write-CheckpointLine ('YACS_ACCEPTED363_ASSET ' + ($asset | ConvertTo-Json -Compress -Depth 16))
    }
    $consumerMetadata = [ordered]@{}
    foreach ($key in @('status', 'exact_sha', 'map_package', 'map_sha256', 'producer_sha256_lf',
        'canonical_map_package', 'canonical_map_sha256', 'component_count', 'geometry_mutation',
        'geometry_snapshot_sha256', 'material_recipe_sha256', 'expected_material_parent',
        'expected_material_instance', 'source_proof', 'fresh_render_receipt')) {
        $consumerMetadata[$key] = $consumer[$key]
    }
    $receipt.consumer_metadata = $consumerMetadata
    Write-CheckpointLine ('YACS_ACCEPTED363_CONSUMER ' + ($consumerMetadata | ConvertTo-Json -Compress -Depth 16))
    foreach ($name in @('saved-material-consumer/reload-receipt.json',
        'saved-material-consumer/fresh-render-receipt.json', 'checkout-restoration.json',
        'checkout-restoration-post-material.json')) {
        $value = $values[$name]
        $consoleReceipt = [ordered]@{}
        foreach ($key in @('status', 'exact_sha', 'map_package', 'map_sha256',
            'component_count', 'fresh_process', 'material_reapplied',
            'saved_assets_unchanged', 'capture_settings_restored', 'geometry_mutation',
            'canonical_map_saved', 'audit_phase', 'tracked_checkout_unchanged',
            'retained_source_unchanged', 'prepared_bundle_unchanged', 'initial_receipt_sha256')) {
            if ($value.Contains($key)) { $consoleReceipt[$key] = $value[$key] }
        }
        if ($value.Contains('errors')) {
            $allErrors = @($value['errors'])
            $consoleReceipt['errors'] = @($allErrors | Select-Object -First 4 | ForEach-Object {
                $errorText = [string]$_
                if ($errorText.Length -gt 512) { $errorText.Substring(0, 512) + '[TRUNCATED]' }
                else { $errorText }
            })
            $consoleReceipt['errors_count'] = $allErrors.Count
            $consoleReceipt['errors_truncated'] = $allErrors.Count -gt 4 -or @($allErrors | Where-Object { ([string]$_).Length -gt 512 }).Count -gt 0
        }
        Write-CheckpointLine ('YACS_ACCEPTED363_RECEIPT ' + $name + ' ' + ($consoleReceipt | ConvertTo-Json -Compress -Depth 8))
    }
    $receipt.status = 'ACCEPTED_CHECKPOINT_METADATA_READ'
}
catch {
    # Network errors may contain signed redirect URLs. Retain only our fixed
    # phase label; never serialize the exception, request headers or token.
    $receipt.status = 'READ_BLOCKED'
    $receipt.error = "Accepted checkpoint discovery failed during $phase."
    if ($phase -ceq 'retained metadata') {
        # Only this fixed local-file phase has diagnostic details. Never emit
        # arbitrary exception text, which could expose a signed network URL.
        $receipt.local_exception_type = $_.Exception.GetType().FullName
        $receipt.error_code = switch ($_.Exception.Message) {
            'Retained checkpoint JSON exceeds its bound.' { 'JSON_SIZE_LIMIT' }
            'Retained checkpoint JSON changed during read.' { 'JSON_CHANGED_DURING_READ' }
            'Accepted checkpoint paths cannot use symlinks or junctions.' { 'REPARSE_PATH' }
            default { 'LOCAL_RETAINED_METADATA_FAILURE' }
        }
        $receipt.error = "Accepted checkpoint discovery failed during $phase at $($receipt.retained_metadata_path): $($receipt.error_code)."
    }
    throw $receipt.error
}
finally {
    $receiptPath = Join-Path $output 'accepted-read.json'
    Assert-NoCheckpointAlias $receiptPath
    $raw = [Text.UTF8Encoding]::new($false).GetBytes(($receipt | ConvertTo-Json -Depth 32))
    $writer = [IO.FileStream]::new($receiptPath, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
    try { $writer.Write($raw, 0, $raw.Length) }
    finally { $writer.Dispose() }
    $summary = [ordered]@{
        status = $receipt.status
        source_exact_sha = $SourceSha
        source_run_id = $SourceRun
        source_run_attempt = $SourceAttempt
        artifact_id = $ArtifactId
        zip_verified = $receipt.zip_verified
        consumer_admission = $receipt.consumer_admission
        native_runtime_verified = $false
        official_mcp_admitted = $false
        restoration_performed = $false
        retained_metadata_path = $receipt.retained_metadata_path
        retained_metadata_observed_bytes = $receipt.retained_metadata_observed_bytes
        error_code = $receipt.error_code
        local_exception_type = $receipt.local_exception_type
        error = $receipt.error
    }
    Write-CheckpointLine ('YACS_ACCEPTED363_READ ' + ($summary | ConvertTo-Json -Compress -Depth 8))
}
