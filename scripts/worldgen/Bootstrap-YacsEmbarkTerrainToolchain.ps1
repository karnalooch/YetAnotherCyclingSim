<#
.SYNOPSIS
    Bootstrap or validate the external DCC prerequisites for the Passo Giau Embark-mode pipeline.

.DESCRIPTION
    This script never stores credentials or license keys in Git. Install mode requires
    caller-supplied local installer/settings/license paths. Validate mode is the default.
#>
[CmdletBinding()]
param(
    [ValidateSet('Validate','Install')] [string] $Mode = 'Validate',

    [string] $HoudiniInstallerExe = 'C:\Program Files\Side Effects Software\Launcher\bin\houdini_installer.exe',
    [string] $HoudiniVersion,
    [string] $HoudiniSettingsFile,
    [string] $HoudiniEula,
    [string] $HoudiniInstallDir,
    [string] $SideFxLabsPackageName,

    [string] $GaeaInstaller,
    [string] $GaeaLicenseFile,
    [string] $GaeaInstallDir = (Join-Path $env:LOCALAPPDATA 'Programs\Gaea 2.0'),

    [string] $ReportPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Resolve-ExistingFile([string] $Path, [string] $Label) {
    if (-not $Path) { return $null }
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "$Label does not exist: $Path"
    }
    return (Resolve-Path -LiteralPath $Path).Path
}

function Find-FirstFile([string[]] $Candidates) {
    foreach ($Candidate in $Candidates) {
        if ($Candidate -and (Test-Path -LiteralPath $Candidate -PathType Leaf)) {
            return (Resolve-Path -LiteralPath $Candidate).Path
        }
    }
    return $null
}

if (-not $ReportPath) {
    $ReportPath = Join-Path $PSScriptRoot '../../Saved/RuntimeProof/CI/M3/EmbarkTerrain/toolchain-bootstrap.json'
}
$ReportPath = [System.IO.Path]::GetFullPath($ReportPath)
New-Item -ItemType Directory -Path (Split-Path -Parent $ReportPath) -Force | Out-Null

$Actions = [System.Collections.Generic.List[object]]::new()

if ($Mode -eq 'Install') {
    $HoudiniInstallerExe = Resolve-ExistingFile $HoudiniInstallerExe 'Houdini Installer CLI'
    $HoudiniSettingsFile = Resolve-ExistingFile $HoudiniSettingsFile 'SideFX settings file'
    if (-not $HoudiniVersion) { throw 'Install mode requires -HoudiniVersion.' }
    if (-not $HoudiniEula) { throw 'Install mode requires -HoudiniEula (SideFX-YYYY-MM-DD).' }
    if (-not $HoudiniInstallDir) { throw 'Install mode requires -HoudiniInstallDir.' }

    $HoudiniArgs = @(
        '--quiet',
        '--settings-file', $HoudiniSettingsFile,
        'install',
        '--product', 'Houdini',
        '--version', $HoudiniVersion,
        '--accept-EULA', $HoudiniEula,
        '--installdir', $HoudiniInstallDir
    )
    & $HoudiniInstallerExe @HoudiniArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Houdini scripted installation failed with exit code $LASTEXITCODE."
    }
    $Actions.Add([ordered]@{ action='install_houdini'; status='PASS'; version=$HoudiniVersion })

    if ($SideFxLabsPackageName) {
        & $HoudiniInstallerExe '--quiet' '--settings-file' $HoudiniSettingsFile 'install-package' '--package-name' $SideFxLabsPackageName '--installdir' $HoudiniInstallDir
        if ($LASTEXITCODE -ne 0) {
            throw "SideFX Labs package installation failed with exit code $LASTEXITCODE."
        }
        $Actions.Add([ordered]@{ action='install_sidefx_labs'; status='PASS'; package=$SideFxLabsPackageName })
    }

    $GaeaInstaller = Resolve-ExistingFile $GaeaInstaller 'Gaea installer'
    $GaeaInstallArgs = @(
        '/VERYSILENT',
        '/SUPPRESSMSGBOXES',
        '/NORESTART',
        '/SP-',
        '/CURRENTUSER',
        ('/DIR="' + $GaeaInstallDir + '"')
    )
    & $GaeaInstaller @GaeaInstallArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Gaea unattended installation failed with exit code $LASTEXITCODE."
    }
    $Actions.Add([ordered]@{ action='install_gaea'; status='PASS'; install_dir=$GaeaInstallDir })

    if ($GaeaLicenseFile) {
        $GaeaLicenseFile = Resolve-ExistingFile $GaeaLicenseFile 'Gaea activation file'
        $GaeaExeForActivation = Find-FirstFile @(
            (Join-Path $GaeaInstallDir 'Gaea.exe'),
            (Join-Path $GaeaInstallDir 'Gaea 2.0\Gaea.exe')
        )
        if (-not $GaeaExeForActivation) {
            throw 'Gaea.exe is unavailable after installation; cannot activate supplied license.'
        }
        & $GaeaExeForActivation '-Activate' $GaeaLicenseFile '-NoStart'
        if ($LASTEXITCODE -ne 0) {
            throw "Gaea activation failed with exit code $LASTEXITCODE."
        }
        $Actions.Add([ordered]@{ action='activate_gaea'; status='PASS' })
    }
}

$Hython = Find-FirstFile @(
    $env:YACS_HYTHON,
    $(if ($HoudiniInstallDir) { Join-Path $HoudiniInstallDir 'bin\hython.exe' } else { $null }),
    $(Get-ChildItem 'C:\Program Files\Side Effects Software' -Filter hython.exe -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty FullName)
)
$GaeaExe = Find-FirstFile @(
    $env:YACS_GAEA_EXE,
    (Join-Path $GaeaInstallDir 'Gaea.exe'),
    $(Get-ChildItem (Split-Path $GaeaInstallDir -Parent) -Filter Gaea.exe -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty FullName)
)
$GaeaSwarm = Find-FirstFile @(
    $env:YACS_GAEA_SWARM,
    (Join-Path $GaeaInstallDir 'Gaea.Swarm.exe'),
    $(Get-ChildItem (Split-Path $GaeaInstallDir -Parent) -Filter Gaea.Swarm.exe -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty FullName)
)

$Checks = @(
    [ordered]@{ name='hython'; status=$(if ($Hython) {'PASS'} else {'FAIL'}); path=$Hython },
    [ordered]@{ name='gaea'; status=$(if ($GaeaExe) {'PASS'} else {'FAIL'}); path=$GaeaExe },
    [ordered]@{ name='gaea_swarm'; status=$(if ($GaeaSwarm) {'PASS'} else {'FAIL'}); path=$GaeaSwarm }
)

if ($Hython) {
    $env:YACS_HYTHON = $Hython
}
if ($GaeaExe) {
    $env:YACS_GAEA_EXE = $GaeaExe
}
if ($GaeaSwarm) {
    $env:YACS_GAEA_SWARM = $GaeaSwarm
}

$Failed = @($Checks | Where-Object { $_.status -ne 'PASS' })
$Report = [ordered]@{
    schema_version = 1
    mode = $Mode
    status = $(if ($Failed.Count -eq 0) {'PASS'} else {'FAIL'})
    checks = $Checks
    actions = $Actions
    secrets_persisted = $false
    note = 'SideFX/Gaea credentials and licenses are caller-owned local inputs and are never written to the repository.'
}
$Report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $ReportPath -Encoding UTF8

if ($Failed.Count -gt 0) {
    $Names = ($Failed | ForEach-Object { $_.name }) -join ', '
    throw "Embark terrain toolchain bootstrap validation failed: $Names"
}

Write-Host "Embark terrain DCC bootstrap validation: PASS" -ForegroundColor Green
Write-Host "YACS_HYTHON=$Hython"
Write-Host "YACS_GAEA_EXE=$GaeaExe"
Write-Host "YACS_GAEA_SWARM=$GaeaSwarm"
