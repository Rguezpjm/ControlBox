#!/usr/bin/env bash

CB_ROLLBACK_SNAPSHOT=""

cb_rollback_create_snapshot() {
    local reason="${1:-pre-install}"
    local timestamp
    timestamp="$(date +%Y%m%d_%H%M%S)"
    CB_ROLLBACK_SNAPSHOT="${CB_ROLLBACK_DIR}/${timestamp}_${reason}"

    cb_info "Creando snapshot de rollback: ${CB_ROLLBACK_SNAPSHOT}"
    mkdir -p "${CB_ROLLBACK_SNAPSHOT}"

    if [[ -f "${CONTROLBOX_INSTALL_DIR}/docker-compose.yml" ]]; then
        cp -a "${CONTROLBOX_INSTALL_DIR}/docker-compose.yml" "${CB_ROLLBACK_SNAPSHOT}/"
    fi
    if [[ -f "${CONTROLBOX_INSTALL_DIR}/docker-compose.override.yml" ]]; then
        cp -a "${CONTROLBOX_INSTALL_DIR}/docker-compose.override.yml" "${CB_ROLLBACK_SNAPSHOT}/"
    fi
    if [[ -f "${CONTROLBOX_CONFIG_DIR}/platform.env" ]]; then
        cp -a "${CONTROLBOX_CONFIG_DIR}/platform.env" "${CB_ROLLBACK_SNAPSHOT}/"
    fi
    if [[ -d "${CONTROLBOX_CONFIG_DIR}/traefik" ]]; then
        cp -a "${CONTROLBOX_CONFIG_DIR}/traefik" "${CB_ROLLBACK_SNAPSHOT}/"
    fi
    if [[ -d "${CONTROLBOX_CONFIG_DIR}/prometheus" ]]; then
        cp -a "${CONTROLBOX_CONFIG_DIR}/prometheus" "${CB_ROLLBACK_SNAPSHOT}/"
    fi

    echo "${CB_ROLLBACK_SNAPSHOT}" > "${CONTROLBOX_STATE_DIR}/rollback/active"
    echo "${reason}" > "${CB_ROLLBACK_SNAPSHOT}/reason.txt"
    echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "${CB_ROLLBACK_SNAPSHOT}/timestamp.txt"

    cb_log "ROLLBACK_SNAPSHOT" "${CB_ROLLBACK_SNAPSHOT}"
}

cb_rollback_clear_active() {
    rm -f "${CONTROLBOX_STATE_DIR}/rollback/active"
}

cb_rollback_execute() {
    local snapshot="${1:-}"

    if [[ -z "${snapshot}" ]]; then
        if [[ -f "${CONTROLBOX_STATE_DIR}/rollback/active" ]]; then
            snapshot="$(cat "${CONTROLBOX_STATE_DIR}/rollback/active")"
        else
            snapshot="$(ls -1dt "${CB_ROLLBACK_DIR}"/*/ 2>/dev/null | head -1)"
        fi
    fi

    if [[ -z "${snapshot}" ]] || [[ ! -d "${snapshot}" ]]; then
        cb_error "No hay snapshot de rollback disponible"
        return 1
    fi

    cb_warn "Ejecutando rollback desde: ${snapshot}"

    if [[ -f "${CONTROLBOX_INSTALLER_ROOT}/lib/docker.sh" ]]; then
        # shellcheck source=lib/docker.sh
        source "${CONTROLBOX_INSTALLER_ROOT}/lib/docker.sh"
    fi

    if docker info >/dev/null 2>&1; then
        cb_docker_stack_down 2>/dev/null || true
    fi

    if [[ -f "${snapshot}/docker-compose.yml" ]]; then
        cp -a "${snapshot}/docker-compose.yml" "${CONTROLBOX_INSTALL_DIR}/"
    fi
    if [[ -f "${snapshot}/docker-compose.override.yml" ]]; then
        cp -a "${snapshot}/docker-compose.override.yml" "${CONTROLBOX_INSTALL_DIR}/"
    fi
    if [[ -f "${snapshot}/platform.env" ]]; then
        cp -a "${snapshot}/platform.env" "${CONTROLBOX_CONFIG_DIR}/"
    fi
    if [[ -d "${snapshot}/traefik" ]]; then
        rm -rf "${CONTROLBOX_CONFIG_DIR}/traefik"
        cp -a "${snapshot}/traefik" "${CONTROLBOX_CONFIG_DIR}/"
    fi

    if [[ -f "${CONTROLBOX_INSTALL_DIR}/docker-compose.yml" ]]; then
        if [[ "${CB_INSTALL_DEPLOYED:-}" == "1" ]]; then
            cb_docker_deploy_stack 2>/dev/null || true
        else
            cb_info "Archivos de configuración restaurados (sin redespliegue durante instalación)"
        fi
    fi

    cb_rollback_clear_active
    cb_success "Estado anterior restaurado"
}

cb_rollback_list() {
    if [[ -d "${CB_ROLLBACK_DIR}" ]]; then
        ls -lht "${CB_ROLLBACK_DIR}" 2>/dev/null
    else
        cb_info "No hay snapshots de rollback"
    fi
}
