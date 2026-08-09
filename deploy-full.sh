#!/bin/bash
# Orkestrasi full deploy di server aaPanel (jalankan sebagai root)
# Usage: sudo bash /www/backup-scripts/deploy-full.sh

set -euo pipefail

TARGET="/www/backup-scripts"
SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "[ERROR] Jalankan sebagai root: sudo bash $0"
  exit 1
fi

echo "######## DEPLOY FULL backup aaPanel → Webmin ########"

# 1) Install scripts ke path tetap
if [[ "${SELF_DIR}" != "${TARGET}" ]]; then
  mkdir -p "${TARGET}"
  cp -a "${SELF_DIR}/." "${TARGET}/"
fi

cd "${TARGET}"
chmod 700 setup-ssh.sh backup-webs.sh backup-dbs.sh backup-all.sh install-on-aapanel.sh deploy-full.sh lib.sh 2>/dev/null || true
chmod 600 config.sh
chmod 644 exclude-web.list README.md aapanel-cron-examples.txt 2>/dev/null || true
mkdir -p logs staging/webs staging/dbs .ssh
chmod 700 .ssh

# 2) Paket
echo "[1/5] Install paket..."
export DEBIAN_FRONTEND=noninteractive
if command -v apt-get >/dev/null 2>&1; then
  apt-get update -qq
  apt-get install -y rsync openssh-client tar gzip sshpass
fi

# 3) SSH trust permanen sumber → tujuan (key, tanpa password)
echo "[2/5] Setup SSH key ke server backup..."
bash "${TARGET}/setup-ssh.sh"

# Pastikan ownership root (cron aaPanel = root)
chown -R root:root "${TARGET}"
chmod 700 "${TARGET}/.ssh"
chmod 600 "${TARGET}/.ssh/id_ed25519_backup" 2>/dev/null || true
chmod 600 "${TARGET}/config.sh"

# shellcheck source=/dev/null
source "${TARGET}/config.sh"

echo "[3/5] Uji SSH BatchMode (tanpa password)..."
# shellcheck disable=SC2086
if ! ssh ${SSH_OPTS} -o BatchMode=yes "${REMOTE_USER}@${REMOTE_HOST}" "echo SSH_TRUST_OK && mkdir -p '${REMOTE_BASE}/webs' '${REMOTE_BASE}/dbs' '${REMOTE_BASE}/logs'"; then
  echo "[ERROR] SSH trust gagal. Cron TIDAK dipasang."
  exit 1
fi

# 4) Crontab root (idempotent)
echo "[4/5] Pasang crontab root..."
CRON_MARKER="# aapanel-backup-remote"
CRON_BLOCK="${CRON_MARKER}
0 2 * * * /bin/bash ${TARGET}/backup-webs.sh >> ${TARGET}/logs/cron-webs.log 2>&1
0 3 * * * /bin/bash ${TARGET}/backup-dbs.sh >> ${TARGET}/logs/cron-dbs.log 2>&1"

existing="$(crontab -l 2>/dev/null || true)"
# Hapus block lama jika ada
cleaned="$(printf '%s\n' "${existing}" | sed "/${CRON_MARKER}/,/backup-dbs.sh/d" | sed '/^$/N;/^\n$/D')"
{
  printf '%s\n' "${cleaned}" | sed '/^$/d'
  printf '%s\n' "${CRON_BLOCK}"
} | crontab -

echo "[INFO] crontab root:"
crontab -l | sed -n "/${CRON_MARKER}/,/backup-dbs/p"

# 5) Backup pertama
echo "[5/5] Jalankan backup pertama (bisa lama jika data besar)..."
set +e
bash "${TARGET}/backup-all.sh"
BACKUP_RC=$?
set -e

echo
echo "######## DEPLOY SELESAI ########"
echo "SSH trust:    OK (BatchMode)"
echo "Scripts:      ${TARGET}"
echo "Remote base:  ${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_BASE}"
echo "Cron:         webs 02:00, dbs 03:00"
echo "Backup uji:   exit=${BACKUP_RC}"
echo "Logs:         ${TARGET}/logs/"
exit "${BACKUP_RC}"
