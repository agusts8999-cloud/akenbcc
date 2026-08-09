#Requires -Version 5.1
#Requires -RunAsAdministrator
<#
.SYNOPSIS
  Daftarkan Task Scheduler untuk backup harian mandiri (tanpa GUI BCC).
#>
$ErrorActionPreference = "Stop"
$ScriptRoot = $PSScriptRoot
$filesTask = "BCC-Backup-Files"
$sqlTask = "BCC-Backup-SQL"

$actionFiles = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$ScriptRoot\backup-files.ps1`""
$triggerFiles = New-ScheduledTaskTrigger -Daily -At 02:00
Register-ScheduledTask -TaskName $filesTask -Action $actionFiles -Trigger $triggerFiles `
    -Description "BCC Windows file backup to remote" -Force | Out-Null

$actionSql = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$ScriptRoot\backup-sql.ps1`""
$triggerSql = New-ScheduledTaskTrigger -Daily -At 03:00
Register-ScheduledTask -TaskName $sqlTask -Action $actionSql -Trigger $triggerSql `
    -Description "BCC Windows SQL backup to remote" -Force | Out-Null

Write-Host "Registered tasks: $filesTask (02:00), $sqlTask (03:00)"
Write-Host "Pastikan SSH key di Config.ps1 sudah trusted di server backup."
