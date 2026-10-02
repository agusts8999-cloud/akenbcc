#!/bin/bash
# Backup setiap website di /www/wwwroot secara terpisah → server backup

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/lib.sh"

# Cegah overlap (deploy + cron / cron dobel)
LOCK_FILE="${SCRIPT_DIR}/.lock-webs"
exec 9>"${LOCK_FILE}"
if ! flock -n 9; then
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] [WARN] backup-webs sudah berjalan, skip"
  exit 0
fi

LOG_FILE="${LOCAL_LOG_DIR}/backup-webs_$(date '+%Y%m%d').log"
exec >>"${LOG_FILE}" 2>&1

main() {
  ensure_dirs
  check_ssh_ready

  local ts exclude_file count fail
  ts="$(timestamp)"
  exclude_file="${SCRIPT_DIR}/exclude-web.list"
  count=0
  fail=0

  log "INFO" "==== Mulai backup websites (${SOURCE_LABEL}) ===="
  log "INFO" "Sumber: ${WEB_ROOT} → Remote: ${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_BASE}/webs"

  if [[ ! -d "${WEB_ROOT}" ]]; then
    die "WEB_ROOT tidak ada: ${WEB_ROOT}"
  fi

  shopt -s nullglob
  local sites=("${WEB_ROOT}"/*)
  shopt -u nullglob

  if [[ ${#sites[@]} -eq 0 ]]; then
    log "WARN" "Tidak ada website di ${WEB_ROOT}"
    exit 0
  fi

  local site site_name archive local_dir
  for site in "${sites[@]}"; do
    [[ -d "${site}" ]] || continue
    site_name="$(basename "${site}")"

    # Lewati folder sistem / default yang biasanya bukan site app
    case "${site_name}" in
      .|..|default|phpmyadmin|phpMyAdmin) continue ;;
    esac

    local safe
    safe="$(safe_name "${site_name}")"
    local_dir="${LOCAL_STAGING}/webs"
    archive="${local_dir}/${safe}_${ts}.tar.gz"

    log "INFO" "Packing: ${site_name}"
    if [[ -f "${exclude_file}" ]]; then
      if tar -czf "${archive}" \
        --exclude-from="${exclude_file}" \
        -C "${WEB_ROOT}" \
        "${site_name}"; then
        :
      else
        log "ERROR" "Gagal tar: ${site_name}"
        ((fail++)) || true
        rm -f "${archive}"
        continue
      fi
    else
      tar -czf "${archive}" -C "${WEB_ROOT}" "${site_name}" || {
        log "ERROR" "Gagal tar: ${site_name}"
        ((fail++)) || true
        rm -f "${archive}"
        continue
      }
    fi

    local size
    size="$(du -h "${archive}" | awk '{print $1}')"
    log "INFO" "Upload: ${safe}_${ts}.tar.gz (${size})"
    if upload_file "${archive}" "webs"; then
      log "INFO" "OK: ${site_name}"
      ((count++)) || true
      # Hapus staging lokal setelah sukses upload (hemat disk)
      rm -f "${archive}"
    else
      log "ERROR" "Upload gagal: ${site_name}"
      ((fail++)) || true
    fi
  done

  prune_remote "webs"
  log "INFO" "==== Selesai webs: sukses=${count} gagal=${fail} ===="
  [[ "${fail}" -eq 0 ]] || exit 1
}

main "$@"
