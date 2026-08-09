#Requires -Version 5.1
<#
.SYNOPSIS
  Backup folder lokal ke ZIP per path, push ke server backup via scp.
#>
$ErrorActionPreference = "Stop"
. "$PSScriptRoot\Config.ps1"

function Write-BccLog([string]$Level, [string]$Msg) {
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$ts] [$Level] $Msg"
    Write-Host $line
    $logFile = Join-Path $BccConfig.LogDir ("backup-files_{0:yyyyMMdd}.log" -f (Get-Date))
    New-Item -ItemType Directory -Force -Path $BccConfig.LogDir | Out-Null
    Add-Content -Path $logFile -Value $line
}

New-Item -ItemType Directory -Force -Path $BccConfig.StagingDir, $BccConfig.LogDir | Out-Null
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$ok = 0
$fail = 0

foreach ($p in $BccConfig.Paths) {
    if (-not (Test-Path -LiteralPath $p)) {
        Write-BccLog "WARN" "Skip missing: $p"
        continue
    }
    $name = (Split-Path -Leaf $p) -replace '[^\w\.-]', '_'
    $zip = Join-Path $BccConfig.StagingDir "${name}_${stamp}.zip"
    Write-BccLog "INFO" "Packing $p -> $zip"
    try {
        if (Test-Path $zip) { Remove-Item $zip -Force }
        Compress-Archive -Path (Join-Path $p '*') -DestinationPath $zip -CompressionLevel Optimal -Force
        & $BccConfig.ScpPath -i $BccConfig.SshKeyPath -P $BccConfig.RemotePort -o StrictHostKeyChecking=accept-new `
            $zip ("{0}@{1}:{2}/files/" -f $BccConfig.RemoteUser, $BccConfig.RemoteHost, $BccConfig.RemoteBase)
        if ($LASTEXITCODE -ne 0) { throw "scp exit $LASTEXITCODE" }
        Write-BccLog "INFO" "OK: $name"
        $ok++
        Remove-Item $zip -Force -ErrorAction SilentlyContinue
    }
    catch {
        Write-BccLog "ERROR" "$_"
        $fail++
    }
}

Write-BccLog "INFO" "Selesai files: sukses=$ok gagal=$fail"
if ($fail -gt 0) { exit 1 }
