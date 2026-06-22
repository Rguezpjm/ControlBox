#!/usr/bin/env bash

set -euo pipefail

CONTROLBOX_INSTALL_DIR="${CONTROLBOX_INSTALL_DIR:-/opt/controlbox}"
CONTROLBOX_CONFIG_DIR="${CONTROLBOX_CONFIG_DIR:-/etc/controlbox}"
CONTROLBOX_DATA_DIR="${CONTROLBOX_DATA_DIR:-/var/lib/controlbox}"
CONTROLBOX_LOG_DIR="${CONTROLBOX_LOG_DIR:-/var/log/controlbox}"
CONTROLBOX_STATE_DIR="${CONTROLBOX_STATE_DIR:-/var/lib/controlbox/state}"
CONTROLBOX_BACKUP_DIR="${CONTROLBOX_BACKUP_DIR:-/var/lib/controlbox/backups}"

if [[ -f "${CONTROLBOX_INSTALL_DIR}/lib/common.sh" ]]; then
    CONTROLBOX_INSTALLER_ROOT="${CONTROLBOX_INSTALL_DIR}"
else
    CONTROLBOX_INSTALLER_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fi

source "${CONTROLBOX_INSTALLER_ROOT}/lib/common.sh"
source "${CONTROLBOX_INSTALLER_ROOT}/lib/docker.sh"
source "${CONTROLBOX_INSTALLER_ROOT}/lib/backup.sh"

cb_require_root
cb_init_logging
cb_acquire_lock
cb_setup_traps
cb_load_config

cb_banner

if [[ "${CONTROLBOX_ASSUME_YES:-}" != "true" ]]; then
    echo -e "${CB_RED}${CB_BOLD}ADVERTENCIA: Esta acción eliminará ControlBox del servidor.${CB_NC}"
    echo ""
    echo "Se eliminarán:"
    echo "  - Contenedores y redes Docker de ControlBox"
    echo "  - ${CONTROLBOX_INSTALL_DIR}"
    echo "  - ${CONTROLBOX_CONFIG_DIR}"
    echo "  - Cron jobs y CLI"
    echo ""
    echo "NO se eliminarán (por seguridad):"
    echo "  - ${CONTROLBOX_DATA_DIR} (datos persistentes)"
    echo "  - ${CONTROLBOX_BACKUP_DIR} (backups)"
    echo "  - ${CONTROLBOX_LOG_DIR} (logs)"
    echo ""
    read -r -p "¿Eliminar ControlBox? Escriba 'UNINSTALL' para confirmar: " confirm
    [[ "${confirm}" == "UNINSTALL" ]] || { cb_info "Cancelado"; exit 0; }
fi

cb_step "Creando backup final antes de desinstalar"
if [[ -f "${CONTROLBOX_INSTALL_DIR}/scripts/backup.sh" ]]; then
    bash "${CONTROLBOX_INSTALL_DIR}/scripts/backup.sh" || cb_warn "Backup final falló"
fi

cb_step "Deteniendo servicios"
if [[ -f "${CONTROLBOX_INSTALL_DIR}/docker-compose.yml" ]]; then
    cd "${CONTROLBOX_INSTALL_DIR}"
    docker compose --env-file "${CONTROLBOX_CONFIG_DIR}/platform.env" down -v --remove-orphans 2>/dev/null || true
fi

cb_step "Eliminando contenedores huérfanos ControlBox"
docker ps -a --filter "name=controlbox" -q | xargs -r docker rm -f 2>/dev/null || true
docker network rm controlbox 2>/dev/null || true

cb_step "Eliminando archivos de instalación"
rm -rf "${CONTROLBOX_INSTALL_DIR}"
rm -rf "${CONTROLBOX_CONFIG_DIR}"
rm -f /usr/local/bin/controlbox
rm -f /etc/cron.d/controlbox-backup

if id controlbox >/dev/null 2>&1; then
    userdel controlbox 2>/dev/null || true
fi

rm -f "${CONTROLBOX_STATE_DIR}/installed"
rm -rf "${CONTROLBOX_STATE_DIR}/steps"

cb_step "Limpiando imágenes Docker (opcional)"
if [[ "${CONTROLBOX_PURGE_IMAGES:-}" == "true" ]]; then
    docker images --filter "reference=ghcr.io/grodtech/controlbox*" -q | xargs -r docker rmi -f 2>/dev/null || true
    docker images --filter "reference=supabase/*" -q | xargs -r docker rmi -f 2>/dev/null || true
fi

if [[ "${CONTROLBOX_PURGE_DATA:-}" == "true" ]]; then
    cb_warn "Eliminando datos persistentes..."
    rm -rf "${CONTROLBOX_DATA_DIR}"
    rm -rf "${CONTROLBOX_BACKUP_DIR}"
fi

cb_release_lock

echo ""
cb_success "ControlBox desinstalado"
echo ""
echo "Datos preservados en:"
echo "  ${CONTROLBOX_DATA_DIR}"
echo "  ${CONTROLBOX_BACKUP_DIR}"
echo ""
echo "Para eliminar datos: CONTROLBOX_PURGE_DATA=true bash uninstall.sh"
