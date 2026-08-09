#!/bin/bash
# Jalankan backup website + database berurutan

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/lib.sh"

LOG_FILE="${LOCAL_LOG_DIR}/backup-all_$(date '+%Y%m%d').log"
mkdir -p "${LOCAL_LOG_DIR}"
exec > >(tee -a "${LOG_FILE}") 2>&1

log "INFO" "######## BACKUP ALL START ########"
rc=0

if bash "${SCRIPT_DIR}/backup-webs.sh"; then
  log "INFO" "backup-webs.sh: OK"
else
  log "ERROR" "backup-webs.sh: GAGAL"
  rc=1
fi

if bash "${SCRIPT_DIR}/backup-dbs.sh"; then
  log "INFO" "backup-dbs.sh: OK"
else
  log "ERROR" "backup-dbs.sh: GAGAL"
  rc=1
fi

if [[ "${rc}" -eq 0 ]]; then
  log "INFO" "######## BACKUP ALL SELESAI SUKSES ########"
else
  log "ERROR" "######## BACKUP ALL SELESAI DENGAN ERROR ########"
fi

exit "${rc}"
