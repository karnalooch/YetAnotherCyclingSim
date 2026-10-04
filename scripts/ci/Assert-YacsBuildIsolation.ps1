function Resolve-YacsPhysicalPath {
    param([Parameter(Mandatory)][string]$Path)
    $absolute = [IO.Path]::GetFullPath($Path)
    $resolved = [IO.Path]::GetPathRoot($absolute)
    foreach ($part in $absolute.Substring($resolved.Length).Split([char[]]@('\', '/'), [StringSplitOptions]::RemoveEmptyEntries)) {
        $resolved = Join-Path $resolved $part
        if (Test-Path -LiteralPath $resolved) {
            $item = Get-Item -LiteralPath $resolved -Force -ErrorAction Stop
            if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
                $link = $item.ResolveLinkTarget($true)
                if ($null -eq $link) { throw "Cannot resolve build path alias: $resolved" }
                $resolved = $link.FullName
            }
        }
    }
    return $resolved
}

function Assert-YacsBuildIsolation {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$ProjectPath,
        [object[]]$EditorProcesses
    )
    if (-not $PSBoundParameters.ContainsKey('EditorProcesses')) {
        $EditorProcesses = @(Get-CimInstance Win32_Process | Where-Object Name -in @('UnrealEditor.exe', 'UnrealEditor-Cmd.exe'))
    }
    $target = Resolve-YacsPhysicalPath $ProjectPath
    foreach ($process in $EditorProcesses) {
        $match = [regex]::Match([string]$process.CommandLine, '"(?<project>[^"]+\.uproject)"|(?<project>[^\s"]+\.uproject)', 'IgnoreCase')
        if (-not $match.Success) { throw 'Cannot establish project ownership of a running Unreal Editor.' }
        $open = Resolve-YacsPhysicalPath $match.Groups['project'].Value
        if ($open -ieq $target) { throw "Close the editor for the build workspace before compiling: $target" }
    }
}
