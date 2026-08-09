#!/bin/bash
# Fungsi bersama untuk skrip backup

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/config.sh"

log() {
  local level="$1"
  shift
  local msg="$*"
  local ts
  ts="$(date '+%Y-%m-%d %H:%M:%S')"
  echo "[${ts}] [${level}] ${msg}"
}

die() {
  log "ERROR" "$*"
  exit 1
}

ensure_dirs() {
  mkdir -p "${LOCAL_STAGING}/webs" "${LOCAL_STAGING}/dbs" "${LOCAL_LOG_DIR}"
  mkdir -p "${SSH_KEY_DIR}"
  chmod 700 "${SSH_KEY_DIR}" 2>/dev/null || true
}

resolve_mysql_bins() {
  if [[ -z "${MYSQL_BIN}" ]]; then
    if [[ -x /www/server/mysql/bin/mysql ]]; then
      MYSQL_BIN="/www/server/mysql/bin/mysql"
    else
      MYSQL_BIN="$(command -v mysql || true)"
    fi
  fi
  if [[ -z "${MYSQLDUMP_BIN}" ]]; then
    if [[ -x /www/server/mysql/bin/mysqldump ]]; then
      MYSQLDUMP_BIN="/www/server/mysql/bin/mysqldump"
    else
      MYSQLDUMP_BIN="$(command -v mysqldump || true)"
    fi
  fi
  [[ -n "${MYSQL_BIN}" && -x "${MYSQL_BIN}" ]] || die "mysql client tidak ditemukan"
  [[ -n "${MYSQLDUMP_BIN}" && -x "${MYSQLDUMP_BIN}" ]] || die "mysqldump tidak ditemukan"
}

mysql_exec() {
  resolve_mysql_bins
  MYSQL_PWD="${MYSQL_PASSWORD}" "${MYSQL_BIN}" \
    -h "${MYSQL_HOST}" -P "${MYSQL_PORT}" -u "${MYSQL_USER}" \
    --batch --skip-column-names "$@"
}

ssh_cmd() {
  # shellcheck disable=SC2086
  ssh ${SSH_OPTS} "${REMOTE_USER}@${REMOTE_HOST}" "$@"
}

rsync_to_remote() {
  local src="$1"
  local dest_rel="$2" # path relatif di bawah REMOTE_BASE
  local dest="${REMOTE_BASE}/${dest_rel}"

  # Pastikan folder remote ada
  ssh_cmd "mkdir -p '${dest}'"

  # shellcheck disable=SC2086
  rsync -az --delete-after \
    -e "ssh ${SSH_OPTS}" \
    "${src}" \
    "${REMOTE_USER}@${REMOTE_HOST}:${dest}/"
}

upload_file() {
  local local_file="$1"
  local dest_subdir="$2" # webs | dbs
  local dest_dir="${REMOTE_BASE}/${dest_subdir}"
  local base
  base="$(basename "${local_file}")"

  [[ -f "${local_file}" ]] || die "File tidak ada: ${local_file}"

  ssh_cmd "mkdir -p '${dest_dir}'"
  # shellcheck disable=SC2086
  rsync -az \
    -e "ssh ${SSH_OPTS}" \
    "${local_file}" \
    "${REMOTE_USER}@${REMOTE_HOST}:${dest_dir}/${base}"
}

prune_local() {
  local dir="$1"
  find "${dir}" -type f \( -name '*.tar.gz' -o -name '*.sql.gz' \) -mtime "+${RETENTION_DAYS}" -print -delete 2>/dev/null || true
}

prune_remote() {
  local subdir="$1"
  ssh_cmd "find '${REMOTE_BASE}/${subdir}' -type f \( -name '*.tar.gz' -o -name '*.sql.gz' \) -mtime +${RETENTION_DAYS} -print -delete 2>/dev/null || true"
}

check_ssh_ready() {
  if [[ ! -f "${SSH_KEY}" ]]; then
    die "SSH key belum ada: ${SSH_KEY}. Jalankan dulu: ${SCRIPT_DIR}/setup-ssh.sh"
  fi
  # shellcheck disable=SC2086
  if ! ssh ${SSH_OPTS} -o BatchMode=yes -o ConnectTimeout=15 \
    "${REMOTE_USER}@${REMOTE_HOST}" "echo ok" >/dev/null 2>&1; then
    die "SSH ke ${REMOTE_USER}@${REMOTE_HOST} gagal. Cek setup-ssh.sh / firewall / key."
  fi
}

timestamp() {
  date '+%Y%m%d_%H%M%S'
}

safe_name() {
  # Ganti karakter yang merusak nama file
  echo "$1" | sed 's/[^A-Za-z0-9._-]/_/g'
}
