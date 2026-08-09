#Requires -Version 5.1
# Pastikan folder remote ada
$ErrorActionPreference = "Stop"
. "$PSScriptRoot\Config.ps1"

$base = $BccConfig.RemoteBase
& $BccConfig.SshPath -i $BccConfig.SshKeyPath -p $BccConfig.RemotePort -o StrictHostKeyChecking=accept-new `
    ("{0}@{1}" -f $BccConfig.RemoteUser, $BccConfig.RemoteHost) `
    "mkdir -p '$base/files' '$base/dbs' '$base/logs'"
if ($LASTEXITCODE -ne 0) { throw "ssh mkdir gagal" }
Write-Host "Remote dirs ready: $base"
