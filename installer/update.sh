#!/usr/bin/env bash

set -euo pipefail

CONTROLBOX_INSTALL_DIR="${CONTROLBOX_INSTALL_DIR:-/opt/controlbox}"
CONTROLBOX_CONFIG_DIR="${CONTROLBOX_CONFIG_DIR:-/etc/controlbox}"
CONTROLBOX_STATE_DIR="${CONTROLBOX_STATE_DIR:-/var/lib/controlbox/state}"
CONTROLBOX_INSTALL_URL="${CONTROLBOX_INSTALL_URL:-https://install.grodtech.com}"
CONTROLBOX_VERSION="${CONTROLBOX_VERSION:-4.11.2}"
CONTROLBOX_RELEASE_TARBALL="${CONTROLBOX_RELEASE_TARBALL:-}"

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

cb_update_apply_release_package() {
    local tarball_url="$1"
    local tmp_dir
    tmp_dir="$(mktemp -d /tmp/controlbox-update.XXXXXX)"

    cb_info "Descargando release desde GitHub..."
    if ! curl -fsSL "${tarball_url}" -o "${tmp_dir}/installer.tar.gz"; then
        cb_warn "No se pudo descargar el paquete del release"
        rm -rf "${tmp_dir}"
        return 1
    fi

    tar xzf "${tmp_dir}/installer.tar.gz" -C "${tmp_dir}"
    local package_root=""
    if [[ -d "${tmp_dir}/controlbox-installer" ]]; then
        package_root="${tmp_dir}/controlbox-installer"
    elif [[ -f "${tmp_dir}/lib/common.sh" ]]; then
        package_root="${tmp_dir}"
    else
        package_root="$(find "${tmp_dir}" -mindepth 1 -maxdepth 2 -type f -name common.sh -path '*/lib/common.sh' -print -quit | sed 's|/lib/common.sh||')"
    fi

    if [[ -z "${package_root}" ]] || [[ ! -f "${package_root}/lib/common.sh" ]]; then
        cb_warn "Estructura del paquete del release no reconocida"
        rm -rf "${tmp_dir}"
        return 1
    fi

    cb_info "Sincronizando instalador desde el release..."
    for item in lib templates update.sh repair.sh install.sh config; do
        if [[ -e "${package_root}/${item}" ]]; then
            cp -a "${package_root}/${item}" "${CONTROLBOX_INSTALL_DIR}/"
        fi
    done
    if [[ -d "${package_root}/src" ]]; then
        cp -a "${package_root}/src" "${CONTROLBOX_INSTALL_DIR}/"
    fi

    CONTROLBOX_INSTALLER_ROOT="${CONTROLBOX_INSTALL_DIR}"
    rm -rf "${tmp_dir}"
    return 0
}

if [[ -n "${CONTROLBOX_RELEASE_TARBALL}" ]]; then
    cb_update_apply_release_package "${CONTROLBOX_RELEASE_TARBALL}" || true
fi

if [[ -d "${CONTROLBOX_INSTALLER_ROOT}/templates" ]]; then
    cb_config_deploy_templates
fi

source "${CONTROLBOX_INSTALLER_ROOT}/lib/bootstrap-fixes.sh"
cb_compose_ensure_docker_proxy

env_file="${CONTROLBOX_CONFIG_DIR}/platform.env"
if [[ -f "${env_file}" ]]; then
    cb_env_patch_key "${env_file}" "CONTROLBOX_VERSION" "${CONTROLBOX_VERSION}"
fi

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
