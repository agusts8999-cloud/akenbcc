# BCC Windows backup config — placeholder tokens replaced on export
$BccConfig = @{
    SourceHost   = "{{SOURCE_HOST}}"
    RemoteHost   = "{{REMOTE_HOST}}"
    RemoteUser   = "{{REMOTE_USER}}"
    RemoteBase   = "{{REMOTE_BASE}}"
    RemotePort   = 22
    # Folder lokal yang di-backup (sesuaikan)
    Paths        = @(
        "$env:USERPROFILE\Documents",
        "$env:USERPROFILE\Desktop"
    )
    StagingDir   = "$env:LOCALAPPDATA\BCC-Backup\staging"
    LogDir       = "$env:LOCALAPPDATA\BCC-Backup\logs"
    RetentionDays = 7
    # Path OpenSSH scp (Windows optional feature)
    ScpPath      = "scp"
    SshPath      = "ssh"
    # Key ke server backup (setelah setup)
    SshKeyPath   = "$env:USERPROFILE\.ssh\id_ed25519_bcc_backup"
}
