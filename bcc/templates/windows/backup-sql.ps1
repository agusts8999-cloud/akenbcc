#Requires -Version 5.1
<#
.SYNOPSIS
  Optional SQL dump via mysqldump (jika tersedia di PATH).
  Set $Mysql* di bawah atau kosongkan untuk no-op.
#>
$ErrorActionPreference = "Stop"
. "$PSScriptRoot\Config.ps1"

$MysqlUser = "root"
$MysqlPassword = ""
$MysqlHost = "127.0.0.1"
$Databases = @()  # e.g. @("mydb")

function Write-BccLog([string]$Level, [string]$Msg) {
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$ts] [$Level] $Msg"
    Write-Host $line
    $logFile = Join-Path $BccConfig.LogDir ("backup-sql_{0:yyyyMMdd}.log" -f (Get-Date))
    New-Item -ItemType Directory -Force -Path $BccConfig.LogDir | Out-Null
    Add-Content -Path $logFile -Value $line
}

if (-not $Databases -or $Databases.Count -eq 0) {
    Write-BccLog "INFO" "Tidak ada database dikonfigurasi — skip"
    exit 0
}

$mysqldump = Get-Command mysqldump -ErrorAction SilentlyContinue
if (-not $mysqldump) {
    Write-BccLog "ERROR" "mysqldump tidak di PATH"
    exit 1
}

New-Item -ItemType Directory -Force -Path $BccConfig.StagingDir | Out-Null
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$ok = 0; $fail = 0
foreach ($db in $Databases) {
    $out = Join-Path $BccConfig.StagingDir "${db}_${stamp}.sql.gz"
    Write-BccLog "INFO" "Dump $db"
    try {
        $env:MYSQL_PWD = $MysqlPassword
        & mysqldump -h $MysqlHost -u $MysqlUser --single-transaction --routines --triggers $db |
            & gzip -c > $out 2>$null
        if (-not (Test-Path $out)) {
            # fallback without gzip
            $out2 = Join-Path $BccConfig.StagingDir "${db}_${stamp}.sql"
            & mysqldump -h $MysqlHost -u $MysqlUser --single-transaction --routines --triggers $db -r $out2
            $out = $out2
        }
        & $BccConfig.ScpPath -i $BccConfig.SshKeyPath -P $BccConfig.RemotePort `
            $out ("{0}@{1}:{2}/dbs/" -f $BccConfig.RemoteUser, $BccConfig.RemoteHost, $BccConfig.RemoteBase)
        $ok++
        Remove-Item $out -Force -ErrorAction SilentlyContinue
    }
    catch {
        Write-BccLog "ERROR" "$_"
        $fail++
    }
    finally {
        Remove-Item Env:MYSQL_PWD -ErrorAction SilentlyContinue
    }
}
Write-BccLog "INFO" "Selesai dbs: sukses=$ok gagal=$fail"
if ($fail -gt 0) { exit 1 }
