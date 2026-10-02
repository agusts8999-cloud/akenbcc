#!/bin/bash
# =============================================================================
# Konfigurasi backup aaPanel → server Webmin
# Permission: chmod 600 config.sh
# Values injected by BCC deploy / deploy_remote.py (placeholders below for template).
# =============================================================================

# --- Sumber (aaPanel) ---
SOURCE_IP="{{SOURCE_IP}}"
SOURCE_LABEL="{{SOURCE_LABEL}}"

# Path website aaPanel
WEB_ROOT="{{WEB_ROOT}}"

# MySQL (root aaPanel)
MYSQL_USER="{{MYSQL_USER}}"
MYSQL_PASSWORD="{{MYSQL_PASSWORD}}"
MYSQL_HOST="127.0.0.1"
MYSQL_PORT="3306"
# Binary aaPanel (fallback ke yang di PATH jika kosong)
MYSQL_BIN=""
MYSQLDUMP_BIN=""

# Database sistem yang tidak di-backup
MYSQL_SKIP_DBS="information_schema|performance_schema|mysql|sys|phpmyadmin"

# --- Tujuan (Webmin / backup server) ---
REMOTE_HOST="{{REMOTE_HOST}}"
REMOTE_USER="{{REMOTE_USER}}"
REMOTE_PASSWORD="{{REMOTE_PASSWORD}}"
REMOTE_BASE="{{REMOTE_BASE}}"
REMOTE_PORT="22"

# SSH key (dibuat oleh setup-ssh.sh)
SSH_KEY_DIR="{{SSH_KEY_DIR}}"
SSH_KEY="{{SSH_KEY}}"
SSH_OPTS="-i ${SSH_KEY} -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=30 -o ServerAliveInterval=15 -o ServerAliveCountMax=4 -p ${REMOTE_PORT}"

# --- Staging lokal (sebelum upload) ---
LOCAL_STAGING="{{LOCAL_STAGING}}"
LOCAL_LOG_DIR="{{LOCAL_LOG_DIR}}"

# --- Retensi (hari) ---
RETENTION_DAYS=7

# --- Kompresi ---
# gzip -1..9 (default 6 balance)
GZIP_LEVEL=6

# --- Notifikasi (opsional, kosongkan jika tidak dipakai) ---
# WEBHOOK_URL=""
