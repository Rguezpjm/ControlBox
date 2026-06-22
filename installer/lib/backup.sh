#!/usr/bin/env bash

cb_backup_configure() {
    cb_step "Configurando backups automáticos"

    if cb_step_is_done "configure_backups"; then
        cb_info "Backups ya configurados"
        return 0
    fi

    local backup_script="${CONTROLBOX_INSTALL_DIR}/scripts/backup.sh"
    local cron_schedule="${BACKUP_CRON_SCHEDULE:-0 3 * * *}"
    local retention="${BACKUP_RETENTION_DAYS:-14}"

    mkdir -p "${CONTROLBOX_INSTALL_DIR}/scripts"

    cat > "${backup_script}" <<'BACKUP_SCRIPT'
#!/usr/bin/env bash
set -euo pipefail

CONTROLBOX_CONFIG_DIR="${CONTROLBOX_CONFIG_DIR:-/etc/controlbox}"
CONTROLBOX_DATA_DIR="${CONTROLBOX_DATA_DIR:-/var/lib/controlbox}"
CONTROLBOX_BACKUP_DIR="${CONTROLBOX_BACKUP_DIR:-/var/lib/controlbox/backups}"
CONTROLBOX_INSTALL_DIR="${CONTROLBOX_INSTALL_DIR:-/opt/controlbox}"
CONTROLBOX_LOG_DIR="${CONTROLBOX_LOG_DIR:-/var/log/controlbox}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"

source "${CONTROLBOX_CONFIG_DIR}/platform.env" 2>/dev/null || true

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_PATH="${CONTROLBOX_BACKUP_DIR}/${TIMESTAMP}"
LOG_FILE="${CONTROLBOX_LOG_DIR}/backup.log"

log() {
    echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] $*" >> "${LOG_FILE}"
}

mkdir -p "${BACKUP_PATH}"
log "Iniciando backup ${TIMESTAMP}"

cd "${CONTROLBOX_INSTALL_DIR}"

if docker compose --env-file "${CONTROLBOX_CONFIG_DIR}/platform.env" ps postgres 2>/dev/null | grep -q Up; then
    docker compose --env-file "${CONTROLBOX_CONFIG_DIR}/platform.env" exec -T postgres \
        pg_dumpall -U "${POSTGRES_USER:-controlbox}" | gzip > "${BACKUP_PATH}/postgres.sql.gz"
    log "PostgreSQL backup completado"
fi

if docker compose --env-file "${CONTROLBOX_CONFIG_DIR}/platform.env" ps redis 2>/dev/null | grep -q Up; then
    docker compose --env-file "${CONTROLBOX_CONFIG_DIR}/platform.env" exec -T redis \
        redis-cli -a "${REDIS_PASSWORD}" --rdb /data/dump.rdb 2>/dev/null || true
    docker cp "$(docker compose --env-file ${CONTROLBOX_CONFIG_DIR}/platform.env ps -q redis):/data/dump.rdb" \
        "${BACKUP_PATH}/redis.rdb" 2>/dev/null || true
    log "Redis backup completado"
fi

tar czf "${BACKUP_PATH}/config.tar.gz" -C /etc controlbox 2>/dev/null || true
tar czf "${BACKUP_PATH}/traefik_certs.tar.gz" -C "${CONTROLBOX_DATA_DIR}" letsencrypt 2>/dev/null || true

if docker compose --env-file "${CONTROLBOX_CONFIG_DIR}/platform.env" ps minio 2>/dev/null | grep -q Up; then
    docker run --rm --network controlbox \
        -v "${BACKUP_PATH}:/backup" \
        minio/mc:latest \
        mirror local/controlbox /backup/minio 2>/dev/null || log "MinIO mirror omitido"
fi

echo "${TIMESTAMP}" > "${BACKUP_PATH}/backup.meta"
log "Backup completado: ${BACKUP_PATH}"

find "${CONTROLBOX_BACKUP_DIR}" -maxdepth 1 -type d -mtime +${RETENTION_DAYS} -exec rm -rf {} + 2>/dev/null || true
log "Limpieza de backups > ${RETENTION_DAYS} días"
BACKUP_SCRIPT

    chmod +x "${backup_script}"
    chown controlbox:controlbox "${backup_script}" 2>/dev/null || true

    local cron_file="/etc/cron.d/controlbox-backup"
    cat > "${cron_file}" <<EOF
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin
${cron_schedule} root ${backup_script} >> ${CONTROLBOX_LOG_DIR}/backup.log 2>&1
EOF
    chmod 644 "${cron_file}"

    cb_save_install_state "BACKUP_CONFIGURED" "true"
    cb_save_install_state "BACKUP_RETENTION_DAYS" "${retention}"
    cb_step_done "configure_backups"
    cb_success "Backups automáticos configurados (${cron_schedule})"
}

cb_backup_run_now() {
    local backup_script="${CONTROLBOX_INSTALL_DIR}/scripts/backup.sh"
    if [[ -f "${backup_script}" ]]; then
        bash "${backup_script}"
        cb_success "Backup manual completado"
    else
        cb_error "Script de backup no encontrado"
        return 1
    fi
}

cb_backup_list() {
    local backup_dir="${CONTROLBOX_BACKUP_DIR:-/var/lib/controlbox/backups}"
    if [[ -d "${backup_dir}" ]]; then
        ls -lht "${backup_dir}" 2>/dev/null | head -20
    else
        cb_warn "Directorio de backups no encontrado"
    fi
}

cb_backup_restore() {
    local backup_id="$1"
    local backup_path="${CONTROLBOX_BACKUP_DIR}/${backup_id}"

    if [[ ! -d "${backup_path}" ]]; then
        cb_die "Backup no encontrado: ${backup_id}"
    fi

    cb_step "Restaurando backup ${backup_id}"

    if [[ -f "${backup_path}/postgres.sql.gz" ]]; then
        gunzip -c "${backup_path}/postgres.sql.gz" | \
            docker compose --env-file "${CONTROLBOX_CONFIG_DIR}/platform.env" exec -T postgres \
            psql -U "${POSTGRES_USER:-controlbox}"
        cb_success "PostgreSQL restaurado"
    fi

    if [[ -f "${backup_path}/config.tar.gz" ]]; then
        tar xzf "${backup_path}/config.tar.gz" -C /
        cb_success "Configuración restaurada"
    fi

    cb_docker_stack_restart
}
