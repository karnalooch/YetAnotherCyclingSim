#requires -Version 7.4
<#
.SYNOPSIS
Request the latest PR #470 UE Remote session through the existing GitHub workflow.
.DESCRIPTION
Requires GitHub CLI (gh) authenticated as the repository owner with repository write
access. Can run on an operator computer; no Unreal installation is needed there.
The remote workflow waits for exact-SHA CI and Blender proof, arbitrates the home
host, prepares the retained scene and leaves its owned Editor open. Close a prior
Editor normally before requesting a new session. This script never stops it.
Creates one content-identical checkpoint commit on the current PR branch with
the existing [level-editor-review] push trigger. No file content changes. The
branch must be free of an active owner session before publishing this checkpoint.
No local checkout is needed. An uncertain write is never automatically retried.
.EXAMPLE
pwsh -NoProfile -File ./scripts/ue/Start-YacsRemoteFromGitHub.ps1
.EXAMPLE
pwsh -NoProfile -File ./scripts/ue/Start-YacsRemoteFromGitHub.ps1 -CheckOnly
#>
[CmdletBinding()]
param([switch]$CheckOnly)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$repository = 'karnalooch/YetAnotherCyclingSim'
$branch = 'codex/364-road-surface-materials'
$workflow = 'level-editor-review.yml'

function Invoke-GitHubJson([string]$Endpoint) {
    $raw = & gh api --hostname github.com $Endpoint
    if ($LASTEXITCODE -ne 0) { throw "GitHub read failed: $Endpoint (exit $LASTEXITCODE)." }
    return ($raw | ConvertFrom-Json -Depth 64)
}

function Write-GitHubJson([string]$Method, [string]$Endpoint, [hashtable]$Body) {
    $json = $Body | ConvertTo-Json -Depth 8 -Compress
    $raw = $json | & gh api --hostname github.com --method $Method $Endpoint --input -
    if ($LASTEXITCODE -ne 0) {
        throw "GitHub write failed or its result is uncertain: $Method $Endpoint (exit $LASTEXITCODE). Inspect the remote branch before retrying; this script will not retry."
    }
    return ($raw | ConvertFrom-Json -Depth 64)
}

$null = Get-Command gh -ErrorAction Stop
$identity = Invoke-GitHubJson 'user'
if ($identity.login -cne 'karnalooch') {
    throw 'The existing review workflow admits only the repository owner karnalooch. Authenticate gh as that owner.'
}
$pr = Invoke-GitHubJson "repos/$repository/pulls/470"
if ($pr.state -cne 'open' -or $pr.head.repo.full_name -cne $repository -or $pr.head.ref -cne $branch) {
    throw 'PR #470 no longer identifies the approved open review branch. No checkpoint was created.'
}
$head = [string]$pr.head.sha
if ($head -cnotmatch '^[0-9a-f]{40}$') { throw 'GitHub returned an invalid source SHA.' }
$definition = Invoke-GitHubJson "repos/$repository/actions/workflows/$workflow"
if ($definition.state -cne 'active' -or $definition.path -cne ".github/workflows/$workflow") {
    throw 'The remote review workflow is unavailable or inactive. No checkpoint was created.'
}
$source = Invoke-GitHubJson "repos/$repository/git/commits/$head"
$tree = [string]$source.tree.sha
if ($source.sha -cne $head -or $tree -cnotmatch '^[0-9a-f]{40}$') {
    throw 'The source commit/tree identity is invalid. No checkpoint was created.'
}
Write-Host "Latest PR #470 source: $head"
Write-Host "Remote workflow: https://github.com/$repository/actions/workflows/$workflow"
Write-Host 'This creates a content-identical checkpoint commit with [level-editor-review] on the PR branch.'
Write-Host 'The new checkpoint requires its own matching CI and Blender proof before remote launch.'
Write-Host 'Close any prior owned Editor normally before running this script; an active session freezes this branch.'
if ($CheckOnly) {
    Write-Host 'CHECK ONLY: no checkpoint created, branch updated or Editor launched.'
    return
}

# gh handles authentication; never embed a token or download-and-execute code.
# The supported branch-push trigger avoids unproven draft workflow dispatch.
$current = Invoke-GitHubJson "repos/$repository/git/ref/heads/$branch"
if ($current.object.sha -cne $head) { throw 'The PR branch moved. No checkpoint was created; inspect the new head.' }
$checkpoint = Write-GitHubJson 'POST' "repos/$repository/git/commits" @{
    message = 'chore(ue): request remote review [level-editor-review]'
    tree = $tree
    parents = @($head)
}
$checkpointSha = [string]$checkpoint.sha
if ($checkpointSha -cnotmatch '^[0-9a-f]{40}$' -or $checkpoint.tree.sha -cne $tree -or
    @($checkpoint.parents).Count -ne 1 -or $checkpoint.parents[0].sha -cne $head) {
    throw 'Created checkpoint did not match the requested source tree/parent. Branch was not updated.'
}
Write-Host "Created unchanged-tree checkpoint: $checkpointSha"
$current = Invoke-GitHubJson "repos/$repository/git/ref/heads/$branch"
if ($current.object.sha -cne $head) {
    throw "The PR branch moved; checkpoint $checkpointSha remains unattached. No branch update attempted."
}
# A concurrent forward update is not an ancestor of our sibling checkpoint;
# force=false therefore rejects it instead of discarding another writer's work.
$updated = Write-GitHubJson 'PATCH' "repos/$repository/git/refs/heads/$branch" @{
    sha = $checkpointSha
    force = $false
}
if ($updated.object.sha -cne $checkpointSha) {
    throw 'Branch update returned an unexpected SHA. Inspect GitHub before any retry.'
}
Write-Host 'Checkpoint published. This requests remote launch; it does not confirm an Editor or received video.'
Write-Host 'Inspect this checkpoint run and its level-editor-review artifact for the session and observed viewer URL.'
Write-Host "https://github.com/$repository/commit/$checkpointSha"
Write-Host "https://github.com/$repository/actions/workflows/$workflow"
