#requires -Version 7.4
[CmdletBinding()]
param(
 [Parameter(Mandatory)][ValidatePattern('^[0-9]{8}T[0-9]{6}Z-[a-f0-9]{12}$')][string]$Session,
 [Parameter(Mandatory)][ValidatePattern('^[a-f0-9]{40}$')][string]$RecipeRevision,
 [Parameter(Mandatory)][ValidatePattern('^[a-f0-9]{64}$')][string]$Manifest
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$runtime='D:\yacs\live-host\runtime'
$sessionRoot=Join-Path $runtime "sessions/$Session"
$helper=Join-Path $PSScriptRoot 'live_progress.py'
$python=(Get-Command python -ErrorAction Stop).Source
$lock=$null
function Test-Identity {
 $current=Get-Content -LiteralPath 'D:\yacs\live-host\state\current-session.json' -Raw | ConvertFrom-Json
 if ($current.session -cne $Session) { return $false }
 $beat=Get-Content -LiteralPath (Join-Path $sessionRoot 'live-heartbeat.json') -Raw | ConvertFrom-Json
 $age=((Get-Date).ToUniversalTime() - [DateTime]::Parse($beat.updated_utc).ToUniversalTime()).TotalSeconds
 return ($beat.session -ceq $Session -and $beat.source_sha -ceq $current.source_sha -and $beat.status -ceq 'EDITOR_TICK_ALIVE' -and $age -ge -5 -and $age -lt 30)
}
try {
 $lock=[IO.File]::Open((Join-Path $sessionRoot 'progress-observer.lock'),[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
 while (Test-Identity) {
  try {
   $parameters=@{operation='status';manifest_sha256=$Manifest}|ConvertTo-Json -Compress
   $sent=& (Join-Path $PSScriptRoot 'Send-YacsLiveHostCommand.ps1') -Action run_recipe -Recipe rock_contact_scatter -RecipeRevision $RecipeRevision -Intent preview -ParametersJson $parameters 6>&1
   $message=($sent|Out-String)
   if ($message -notmatch 'sequence=(\d+)') { throw 'Missing submitted sequence' }
   $prefix='{0:D6}-' -f [long]$Matches[1]
   $deadline=[DateTime]::UtcNow.AddSeconds(30)
   do {
    if (-not (Test-Identity)) { throw 'Session unavailable' }
    $receipts=@(Get-ChildItem -LiteralPath (Join-Path $sessionRoot 'commands') -Filter "$prefix*.result.json" -File)
    if ($receipts.Count -eq 1) {
     & $python $helper --session $Session --revision $RecipeRevision --manifest $Manifest --receipt $receipts[0].Name
     if ($LASTEXITCODE -ne 0) { throw 'Projection failed' }
     break
    }
    Start-Sleep -Seconds 1
   } while ([DateTime]::UtcNow -lt $deadline)
  } catch {
   # Existing queue arbitration may be occupied. Preserve last native timestamp.
   [Console]::Error.WriteLine("Progress observer retry: " + $_.Exception.GetType().Name)
  }
  Start-Sleep -Seconds 10
 }
} finally {
 if ($lock) { & $python $helper --session $Session --revision $RecipeRevision --manifest $Manifest --unavailable }
 if ($lock) { $lock.Dispose(); Remove-Item -LiteralPath (Join-Path $sessionRoot 'progress-observer.lock') }
}



