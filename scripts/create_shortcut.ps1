param(
    [Parameter(Mandatory = $true)][string]$ExePath,
    [Parameter(Mandatory = $false)][string]$IconPath = "",
    [Parameter(Mandatory = $false)][string]$ShortcutName = "Backup Control Center"
)

$ErrorActionPreference = "Stop"
if (-not (Test-Path -LiteralPath $ExePath)) {
    throw "EXE not found: $ExePath"
}

$desktop = [Environment]::GetFolderPath("Desktop")
$lnkPath = Join-Path $desktop ($ShortcutName + ".lnk")

if (-not $IconPath -or -not (Test-Path -LiteralPath $IconPath)) {
    $IconPath = $ExePath
}

$wsh = New-Object -ComObject WScript.Shell
$sc = $wsh.CreateShortcut($lnkPath)
$sc.TargetPath = (Resolve-Path -LiteralPath $ExePath).Path
$sc.WorkingDirectory = Split-Path -Parent $sc.TargetPath
$sc.IconLocation = ((Resolve-Path -LiteralPath $IconPath).Path) + ",0"
$sc.Description = "Backup Control Center — support & monitoring"
$sc.Save()

Write-Host "Shortcut: $lnkPath"
Write-Host "Icon: $IconPath"
