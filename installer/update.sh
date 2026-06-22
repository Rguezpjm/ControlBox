#!/usr/bin/env bash

set -euo pipefail

CONTROLBOX_INSTALL_DIR="${CONTROLBOX_INSTALL_DIR:-/opt/controlbox}"
CONTROLBOX_CONFIG_DIR="${CONTROLBOX_CONFIG_DIR:-/etc/controlbox}"
CONTROLBOX_STATE_DIR="${CONTROLBOX_STATE_DIR:-/var/lib/controlbox/state}"
CONTROLBOX_INSTALL_URL="${CONTROLBOX_INSTALL_URL:-https://install.grodtech.com}"
CONTROLBOX_VERSION="${CONTROLBOX_VERSION:-1.1.0}"

if [[ -f "${CONTROLBOX_INSTALL_DIR}/lib/common.sh" ]]; then
    CONTROLBOX_INSTALLER_ROOT="${CONTROLBOX_INSTALL_DIR}"
else
    CONTROLBOX_INSTALLER_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fi

source "${CONTROLBOX_INSTALLER_ROOT}/lib/common.sh"
source "${CONTROLBOX_INSTALLER_ROOT}/lib/docker.sh"
source "${CONTROLBOX_INSTALLER_ROOT}/lib/rollback.sh"
source "${CONTROLBOX_INSTALLER_ROOT}/lib/config.sh"

cb_require_root
cb_init_logging
cb_acquire_lock
cb_setup_traps
cb_load_config

cb_banner
cb_step "Actualizando ControlBox"

cb_rollback_create_snapshot "pre-update"

local_version="$(cb_get_install_state "VERSION" || echo "unknown")"
cb_info "Versión actual: ${local_version}"
cb_info "Versión objetivo: ${CONTROLBOX_VERSION}"

if [[ -d "${CONTROLBOX_INSTALLER_ROOT}/templates" ]]; then
    cb_config_deploy_templates
fi

source "${CONTROLBOX_INSTALLER_ROOT}/lib/bootstrap-fixes.sh"
cb_compose_ensure_docker_proxy

if [[ -f "${CONTROLBOX_INSTALL_DIR}/docker-compose.yml" ]]; then
    cd "${CONTROLBOX_INSTALL_DIR}"
    docker compose --env-file "${CONTROLBOX_CONFIG_DIR}/platform.env" pull
    docker compose --env-file "${CONTROLBOX_CONFIG_DIR}/platform.env" up -d --remove-orphans
fi

cb_save_install_state "VERSION" "${CONTROLBOX_VERSION}"
cb_save_install_state "LAST_UPDATE" "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"

cb_rollback_clear_active
cb_success "ControlBox actualizado a v${CONTROLBOX_VERSION}"

cb_docker_stack_status
