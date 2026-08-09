#!/bin/bash
# Backup setiap database MySQL (kecuali sistem) secara terpisah → server backup

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/lib.sh"

# Cegah overlap
LOCK_FILE="${SCRIPT_DIR}/.lock-dbs"
exec 9>"${LOCK_FILE}"
if ! flock -n 9; then
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] [WARN] backup-dbs sudah berjalan, skip"
  exit 0
fi

LOG_FILE="${LOCAL_LOG_DIR}/backup-dbs_$(date '+%Y%m%d').log"
exec > >(tee -a "${LOG_FILE}") 2>&1

list_databases() {
  mysql_exec -e "SHOW DATABASES;" | grep -Eiv "^(${MYSQL_SKIP_DBS})$" || true
}

main() {
  ensure_dirs
  check_ssh_ready
  resolve_mysql_bins

  local ts count fail db safe archive local_dir
  ts="$(timestamp)"
  count=0
  fail=0
  local_dir="${LOCAL_STAGING}/dbs"

  log "INFO" "==== Mulai backup databases (${SOURCE_LABEL}) ===="
  log "INFO" "Remote: ${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_BASE}/dbs"

  # Uji koneksi MySQL
  if ! mysql_exec -e "SELECT 1;" >/dev/null 2>&1; then
    die "Koneksi MySQL gagal. Cek MYSQL_USER / MYSQL_PASSWORD di config.sh"
  fi

  local dbs
  mapfile -t dbs < <(list_databases)

  if [[ ${#dbs[@]} -eq 0 ]]; then
    log "WARN" "Tidak ada database user untuk di-backup"
    exit 0
  fi

  for db in "${dbs[@]}"; do
    [[ -n "${db}" ]] || continue
    safe="$(safe_name "${db}")"
    archive="${local_dir}/${safe}_${ts}.sql.gz"

    log "INFO" "Dump: ${db}"
    # --single-transaction aman untuk InnoDB tanpa long lock
    if MYSQL_PWD="${MYSQL_PASSWORD}" "${MYSQLDUMP_BIN}" \
      -h "${MYSQL_HOST}" -P "${MYSQL_PORT}" -u "${MYSQL_USER}" \
      --single-transaction \
      --quick \
      --routines \
      --triggers \
      --events \
      --hex-blob \
      --default-character-set=utf8mb4 \
      "${db}" \
      | gzip -"${GZIP_LEVEL}" > "${archive}"; then
      :
    else
      log "ERROR" "mysqldump gagal: ${db}"
      ((fail++)) || true
      rm -f "${archive}"
      continue
    fi

    # File kosong / terlalu kecil = gagal
    if [[ ! -s "${archive}" ]] || [[ "$(stat -c%s "${archive}" 2>/dev/null || echo 0)" -lt 20 ]]; then
      log "ERROR" "Dump kosong/invalid: ${db}"
      ((fail++)) || true
      rm -f "${archive}"
      continue
    fi

    local size
    size="$(du -h "${archive}" | awk '{print $1}')"
    log "INFO" "Upload: ${safe}_${ts}.sql.gz (${size})"
    if upload_file "${archive}" "dbs"; then
      log "INFO" "OK: ${db}"
      ((count++)) || true
      rm -f "${archive}"
    else
      log "ERROR" "Upload gagal: ${db}"
      ((fail++)) || true
    fi
  done

  prune_remote "dbs"
  log "INFO" "==== Selesai dbs: sukses=${count} gagal=${fail} ===="
  [[ "${fail}" -eq 0 ]] || exit 1
}

main "$@"
