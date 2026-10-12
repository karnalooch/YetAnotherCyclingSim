#requires -Version 7.4
[CmdletBinding()]
param([string]$WorkspaceConfig = $env:YACS_WORKSPACE_CONFIG)
$ErrorActionPreference = 'Stop'

function Assert-RetentionPath {
    param([string]$Path, [string]$Root)
    $absolute = [IO.Path]::GetFullPath($Path)
    $base = [IO.Path]::GetFullPath($Root).TrimEnd('\','/')
    if (-not $absolute.StartsWith($base + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Retention path escaped declared root: $absolute"
    }
    $cursor = $absolute
    while ($cursor) {
        if (Test-Path -LiteralPath $cursor) {
            $item = Get-Item -LiteralPath $cursor -Force -ErrorAction Stop
            if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "Reparse path refused: $cursor" }
        }
        if ([string]::Equals($cursor.TrimEnd('\','/'), $base, [StringComparison]::OrdinalIgnoreCase)) { break }
        $cursor = Split-Path -Parent $cursor
    }
    return $absolute
}

function Get-RetentionInventory {
    param([string]$Path)
    $root = [IO.Path]::GetFullPath($Path).TrimEnd('\','/')
    $rootItem = Get-Item -LiteralPath $root -Force -ErrorAction Stop
    if (-not $rootItem.PSIsContainer -or ($rootItem.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        throw 'Inventory root must be a real directory.'
    }
    $queue = [Collections.Generic.Queue[string]]::new()
    $queue.Enqueue($root)
    $files = [Collections.Generic.List[object]]::new()
    $directories = [Collections.Generic.List[string]]::new()
    while ($queue.Count) {
        $directory = $queue.Dequeue()
        foreach ($item in Get-ChildItem -LiteralPath $directory -Force -ErrorAction Stop) {
            if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "Reparse inventory refused: $($item.FullName)" }
            $relative = [IO.Path]::GetRelativePath($root, $item.FullName).Replace('\','/')
            if ($item.Name -eq '.git') {
                if (-not $item.PSIsContainer) { throw 'Nested/root linked .git file cannot be relocated.' }
                foreach ($shared in @('commondir','objects/info/alternates','worktrees')) {
                    $sharedPath = Join-Path $item.FullName $shared
                    if (Test-Path -LiteralPath $sharedPath) {
                        $sharedItem = Get-Item -LiteralPath $sharedPath -Force -ErrorAction Stop
                        if ($sharedItem.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Shared Git metadata reparse point.' }
                        if ($shared -ne 'worktrees' -or @(Get-ChildItem -LiteralPath $sharedPath -Force -ErrorAction Stop).Count -gt 0) {
                            throw 'Shared Git commondir/alternates/live worktrees cannot be relocated.'
                        }
                    }
                }
            }
            if ($item.PSIsContainer) { $directories.Add($relative); $queue.Enqueue($item.FullName) }
            else {
                $files.Add([ordered]@{path=$relative;bytes=[long]$item.Length;sha256=(Get-FileHash -LiteralPath $item.FullName -Algorithm SHA256 -ErrorAction Stop).Hash.ToLowerInvariant()})
            }
        }
    }
    return [ordered]@{directories=@($directories | Sort-Object -CaseSensitive);files=@($files | Sort-Object -Property path -CaseSensitive)}
}

function Invoke-RetentionGit {
    param([string]$Path, [string[]]$Arguments)
    $result = @(& git -C $Path @Arguments 2>&1)
    if ($LASTEXITCODE -ne 0) { throw "Cannot verify Git retention protection at $Path (exit=$LASTEXITCODE)" }
    return @($result | ForEach-Object { [string]$_ })
}

function Assert-RetentionGitProtection {
    param([string]$Path, [string]$Repository)
    $gitPath = Join-Path $Path '.git'
    if (-not (Test-Path -LiteralPath $gitPath)) { return }
    if (-not (Get-Item -LiteralPath $gitPath -Force).PSIsContainer) { throw "Linked worktree must not be relocated: $Path" }
    $head = (Invoke-RetentionGit $Path @('rev-parse','--verify','HEAD')) -join ''
    if ($head -notmatch '^[0-9a-f]{40}$') { throw 'Unknown Git HEAD identity.' }
    $branch = (Invoke-RetentionGit $Path @('rev-parse','--abbrev-ref','HEAD')) -join ''
    if ($branch -in @('main','v0.3.1')) { throw "Protected branch: $branch" }
    foreach ($protectedNames in @(
        @('refs/heads/main','refs/remotes/origin/main'),
        @('refs/heads/v0.3.1','refs/tags/v0.3.1')
    )) {
        $known = Invoke-RetentionGit $Repository (@('for-each-ref','--format=%(objectname)') + $protectedNames)
        if (@($known).Count -eq 0) { throw 'Canonical main AND v0.3.1 identities must be known.' }
    }
    foreach ($repo in @($Path,$Repository) | Select-Object -Unique) {
        if (-not (Test-Path -LiteralPath (Join-Path $repo '.git'))) { throw "Cannot verify canonical Git refs: $repo" }
        $refs = Invoke-RetentionGit $repo @('for-each-ref','--format=%(objectname)','refs/heads/main','refs/remotes/origin/main','refs/heads/v0.3.1','refs/tags/v0.3.1')
        if ($repo -eq $Repository -and @($refs).Count -eq 0) {
            throw 'Canonical protected refs are unavailable; preserve candidate.'
        }
        foreach ($ref in $refs) {
            # Peel annotated tags as well as direct branch/tag commits.
            if ($ref -notmatch '^[0-9a-f]{40}$') { throw 'Malformed protected Git ref.' }
            $commit = (Invoke-RetentionGit $repo @('rev-parse',"${ref}^{commit}")) -join ''
            if ($head -eq $commit) { throw "HEAD matches protected main/v0.3.1 ref: $Path" }
        }
    }
}

function Assert-RetentionProcesses {
    param([string]$Candidate)
    $processes = @(Get-CimInstance Win32_Process -ErrorAction Stop)
    foreach ($process in $processes) {
        if ($process.Name -match '^(UnrealEditor(?:-Cmd)?|ShaderCompileWorker|CrashReportClient|blender|UnrealBuildTool|AutomationTool|MSBuild|cl|link|dotnet|pythonw?|cmake|ninja)\.exe$' -and -not $process.CommandLine) {
            throw "Cannot read native process command line: $($process.Name) pid=$($process.ProcessId)"
        }
        if ($process.CommandLine -and $process.CommandLine.IndexOf($Candidate, [StringComparison]::OrdinalIgnoreCase) -ge 0) {
            throw "Candidate has an active process: $($process.Name) pid=$($process.ProcessId)"
        }
    }
}

function Invoke-YacsCurrentJobRetention {
    param([string]$Configuration)
    if (-not $IsWindows) { throw 'Job retention is supported only on Windows.' }
    if ($env:GITHUB_ACTIONS -cne 'true' -or $env:GITHUB_RUN_ID -notmatch '^[1-9][0-9]*$' -or $env:GITHUB_RUN_ATTEMPT -notmatch '^[1-9][0-9]*$') {
        throw 'Exact current Actions run/attempt required.'
    }
    if (-not $Configuration) { throw 'YACS_WORKSPACE_CONFIG is required.' }
    $configPath = (Resolve-Path -LiteralPath $Configuration -ErrorAction Stop).Path
    $workspace = Split-Path -Parent $configPath
    $config = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
    if ($config.schema_version -ne 1 -or $config.runner -isnot [string] -or [IO.Path]::IsPathRooted($config.runner) -or $config.runner -match '(^|[\\/])\.\.([\\/]|$)') { throw 'Invalid runner configuration.' }
    $runner = Assert-RetentionPath (Join-Path $workspace $config.runner) $workspace
    $work = Assert-RetentionPath (Join-Path $runner '_work') $runner
    $repository = Assert-RetentionPath (Join-Path $work 'YetAnotherCyclingSim/YetAnotherCyclingSim') $work
    $pointerPath = Join-Path $repository '_yacs-unreal-ci/active.json'
    [void](Assert-RetentionPath $pointerPath $repository)
    if (Test-Path -LiteralPath $pointerPath) {
        $pointer = Get-Content -LiteralPath $pointerPath -Raw | ConvertFrom-Json
        if ($pointer.schema_version -ne 1 -or $pointer.worktree -isnot [string] -or
            $pointer.worktree -notmatch '^(_unreal-ci-warm|_unreal-build-[0-9]+-[0-9]+)$') {
            throw 'Unknown active-cache pointer; preserve all candidates.'
        }
        $active = Assert-RetentionPath (Join-Path $repository $pointer.worktree) $repository
        if (-not (Test-Path -LiteralPath $active -PathType Container)) { throw 'Active cache is missing.' }
    }
    $job = $env:GITHUB_RUN_ID + '-' + $env:GITHUB_RUN_ATTEMPT
    $retention = Assert-RetentionPath (Join-Path $workspace "work/runner-retention/$job") $workspace
    if (Test-Path -LiteralPath $retention) { throw 'Preserve prior retention receipt/destination.' }
    $specs = @(
        @{path="s384/$job";root=$work},
        @{path="b384/$job-session-project";root=$work},
        @{path="_official-mcp-source-probe-$job";root=$repository},
        @{path="_road-material-source-proof-$job";root=$repository},
        @{path="_road-material-native-$job";root=$repository},
        @{path="rm-$job";root=$repository}
    )
    $plans = [Collections.Generic.List[object]]::new()
    foreach ($spec in $specs) {
        $candidate = Assert-RetentionPath (Join-Path $spec.root $spec.path) $spec.root
        if (-not (Test-Path -LiteralPath $candidate)) { continue }
        if (-not (Get-Item -LiteralPath $candidate -Force).PSIsContainer) { throw 'Retention candidate is not a directory.' }
        Assert-RetentionGitProtection $candidate $repository
        Assert-RetentionProcesses $candidate
        $plans.Add([ordered]@{source=$candidate;relative=$spec.path;inventory=(Get-RetentionInventory $candidate);status='PLANNED'})
    }
    # No broad sweep: only the six exact current-job paths are considered.
    [void][IO.Directory]::CreateDirectory($retention)
    $receipt = [ordered]@{schema_version=1;run_id=$env:GITHUB_RUN_ID;run_attempt=$env:GITHUB_RUN_ATTEMPT;scope='CURRENT_JOB_QUARANTINE_ONLY';bytes_deleted=0;status='RUNNING';entries=$plans}
    $receiptPath = Join-Path $retention 'retention-receipt.json'
    try {
        foreach ($plan in $plans) {
            [void](Assert-RetentionPath $plan.source $work)
            Assert-RetentionProcesses $plan.source
            Assert-RetentionGitProtection $plan.source $repository
            $again = Get-RetentionInventory $plan.source
            if (($again | ConvertTo-Json -Depth 20 -Compress) -cne ($plan.inventory | ConvertTo-Json -Depth 20 -Compress)) { throw 'Candidate changed before relocation.' }
            $destination = Assert-RetentionPath (Join-Path $retention $plan.relative) $retention
            if (Test-Path -LiteralPath $destination) { throw 'Retention destination exists.' }
            [void][IO.Directory]::CreateDirectory((Split-Path -Parent $destination))
            # Same workspace volume; no deletion, reset, clean or shell composition.
            Move-Item -LiteralPath $plan.source -Destination $destination -ErrorAction Stop
            $plan.destination = $destination
            $plan.status = 'MOVED_NOT_YET_VERIFIED'
            $after = Get-RetentionInventory $destination
            $plan.after_inventory = $after
            if (($after | ConvertTo-Json -Depth 20 -Compress) -cne ($plan.inventory | ConvertTo-Json -Depth 20 -Compress)) { throw 'Retained file inventory/hash differs.' }
            $plan.status = 'RETAINED_BYTES_VERIFIED'
        }
        $receipt.status = 'COMPLETED_NO_BYTES_DELETED'
    } catch {
        $receipt.status = 'FAILED_RETAIN_ALL_BYTES'
        $receipt.error = $_.Exception.Message
        throw
    } finally {
        $receipt | ConvertTo-Json -Depth 30 | Set-Content -LiteralPath $receiptPath -Encoding utf8
    }
    Write-Output "Current-job quarantine completed; all bytes retained: $receiptPath"
}

if ($MyInvocation.InvocationName -ne '.') { Invoke-YacsCurrentJobRetention $WorkspaceConfig }
