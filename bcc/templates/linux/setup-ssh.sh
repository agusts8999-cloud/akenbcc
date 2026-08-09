#!/bin/bash
# Setup SSH key dari server aaPanel ke server backup (sekali jalan)
# Jalankan di server aaPanel sebagai user yang menjalankan cron (mis. root / ubuntu)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/config.sh"

echo "=== Setup SSH key → ${REMOTE_USER}@${REMOTE_HOST} ==="

mkdir -p "${SSH_KEY_DIR}"
chmod 700 "${SSH_KEY_DIR}"

if [[ ! -f "${SSH_KEY}" ]]; then
  ssh-keygen -t ed25519 -f "${SSH_KEY}" -N "" -C "aapanel-backup-${SOURCE_IP}"
  echo "[OK] Key dibuat: ${SSH_KEY}"
else
  echo "[OK] Key sudah ada: ${SSH_KEY}"
fi

chmod 600 "${SSH_KEY}" 2>/dev/null || true
chmod 644 "${SSH_KEY}.pub" 2>/dev/null || true
# Cron aaPanel biasanya root — pastikan readable
if [[ "$(id -u)" -eq 0 ]]; then
  chown -R root:root "${SSH_KEY_DIR}" 2>/dev/null || true
fi

PUB="${SSH_KEY}.pub"
[[ -f "${PUB}" ]] || { echo "[ERROR] Public key tidak ada: ${PUB}"; exit 1; }

if ! command -v sshpass >/dev/null 2>&1; then
  echo "[INFO] Menginstall sshpass (sekali, untuk copy key dengan password)..."
  if command -v apt-get >/dev/null 2>&1; then
    if [[ "$(id -u)" -eq 0 ]]; then
      apt-get update -qq
      apt-get install -y sshpass
    else
      sudo apt-get update -qq
      sudo apt-get install -y sshpass
    fi
  else
    echo "[ERROR] Install sshpass manual, lalu jalankan ulang script ini."
    exit 1
  fi
fi

export SSHPASS="${REMOTE_PASSWORD}"

echo "[INFO] Memasang public key di server backup..."
# shellcheck disable=SC2029
sshpass -e ssh -o StrictHostKeyChecking=accept-new -p "${REMOTE_PORT}" \
  "${REMOTE_USER}@${REMOTE_HOST}" \
  "mkdir -p ~/.ssh && chmod 700 ~/.ssh && touch ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"

# Pipe public key; remote menambahkan jika belum ada
# shellcheck disable=SC2029
cat "${PUB}" | sshpass -e ssh -o StrictHostKeyChecking=accept-new -p "${REMOTE_PORT}" \
  "${REMOTE_USER}@${REMOTE_HOST}" \
  "KEY=\$(cat); grep -qxF \"\$KEY\" ~/.ssh/authorized_keys 2>/dev/null || echo \"\$KEY\" >> ~/.ssh/authorized_keys"

# Buat struktur direktori backup
# shellcheck disable=SC2029
sshpass -e ssh -o StrictHostKeyChecking=accept-new -p "${REMOTE_PORT}" \
  "${REMOTE_USER}@${REMOTE_HOST}" \
  "mkdir -p '${REMOTE_BASE}/webs' '${REMOTE_BASE}/dbs' '${REMOTE_BASE}/logs' && chmod -R u+rwX '${REMOTE_BASE}'"

echo "[INFO] Uji login tanpa password..."
# shellcheck disable=SC2086
if ssh ${SSH_OPTS} -o BatchMode=yes "${REMOTE_USER}@${REMOTE_HOST}" "echo 'SSH backup OK' && ls -la '${REMOTE_BASE}'"; then
  echo
  echo "=== SUKSES ==="
  echo "SSH key authentication siap."
  echo "Lanjut: ./backup-all.sh"
else
  echo "[ERROR] Uji SSH gagal. Periksa password, firewall, atau PermitRootLogin/AuthorizedKeysFile."
  exit 1
fi
