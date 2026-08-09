#!/bin/bash
# Jalankan di server aaPanel setelah folder di-upload ke /www/backup-scripts
# Usage: sudo bash install-on-aapanel.sh

set -euo pipefail

TARGET="/www/backup-scripts"
SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== Install backup scripts ke ${TARGET} ==="

if [[ "${SELF_DIR}" != "${TARGET}" ]]; then
  mkdir -p "${TARGET}"
  cp -a "${SELF_DIR}/." "${TARGET}/"
fi

cd "${TARGET}"
chmod 700 setup-ssh.sh backup-webs.sh backup-dbs.sh backup-all.sh install-on-aapanel.sh lib.sh 2>/dev/null || true
chmod 600 config.sh
chmod 644 exclude-web.list README.md 2>/dev/null || true
mkdir -p logs staging/webs staging/dbs .ssh
chmod 700 .ssh

echo "[INFO] Install paket (rsync, sshpass, tar, gzip)..."
if command -v apt-get >/dev/null 2>&1; then
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq
  apt-get install -y rsync openssh-client tar gzip sshpass
fi

echo
echo "=== Langkah berikutnya ==="
echo "1) Setup SSH (sekali):  ${TARGET}/setup-ssh.sh"
echo "2) Uji:                 ${TARGET}/backup-all.sh"
echo "3) Cron aaPanel Plan Task:"
echo "     Shell: bash ${TARGET}/backup-all.sh"
echo "     Jadwal contoh: 0 2 * * *  (setiap hari jam 02:00)"
echo
echo "Atau 2 cron terpisah:"
echo "     0 2 * * *  bash ${TARGET}/backup-webs.sh"
echo "     0 3 * * *  bash ${TARGET}/backup-dbs.sh"
