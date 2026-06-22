#!/usr/bin/env bash

cb_panel_apply_config() {
    cb_step "Aplicando configuración del panel"

    local env_file="${CONTROLBOX_CONFIG_DIR}/platform.env"
    local compose_file="${CONTROLBOX_INSTALL_DIR}/docker-compose.yml"

    if [[ ! -f "${env_file}" ]]; then
        cb_die "platform.env no encontrado"
    fi

    cb_load_platform_env "${env_file}"

    local panel_port="${PANEL_PORT:-8475}"
    cb_setup_load_state 2>/dev/null || true
    panel_port="${CONTROLBOX_PANEL_PORT:-${panel_port}}"

    cb_firewall_open_port "${panel_port}" || true

    cd "${CONTROLBOX_INSTALL_DIR}"
    local compose_args
    compose_args="$(cb_docker_compose_files)"

    cb_info "Reconstruyendo panel (ruta: /${PANEL_BASE_PATH:-}, puerto: ${panel_port})"

    # shellcheck disable=SC2086
    docker compose --env-file "${env_file}" ${compose_args} build panel 2>/dev/null || true
    # shellcheck disable=SC2086
    docker compose --env-file "${env_file}" ${compose_args} up -d --force-recreate panel

    cb_success "Panel actualizado en puerto ${panel_port}"
    cb_save_install_state "PANEL_PORT" "${panel_port}"
}
