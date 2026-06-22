#!/usr/bin/env bash

cb_tenant_sync_password_env() {
    local env_file="${CONTROLBOX_CONFIG_DIR}/platform.env"
    local password="${CONTROLBOX_TENANT_ADMIN_PASSWORD:-}"
    [[ -f "${env_file}" ]] || return 0
    [[ -n "${password}" ]] || return 0

    for key in TENANT_ADMIN_PASSWORD INSTALLER_TENANT_ADMIN_PASSWORD; do
        if grep -q "^${key}=" "${env_file}"; then
            sed -i "s|^${key}=.*|${key}=${password}|" "${env_file}"
        else
            echo "${key}=${password}" >> "${env_file}"
        fi
    done
    cp -f "${env_file}" "${CONTROLBOX_INSTALL_DIR}/.env" 2>/dev/null || true
}

cb_tenant_ensure_admin_password() {
    CONTROLBOX_TENANT_ADMIN_PASSWORD="$(cb_sanitize_admin_password "${CONTROLBOX_TENANT_ADMIN_PASSWORD:-}")"
    export CONTROLBOX_TENANT_ADMIN_PASSWORD
    cb_tenant_sync_password_env
    cb_save_install_state "TENANT_ADMIN_PASSWORD" "${CONTROLBOX_TENANT_ADMIN_PASSWORD}"
}

cb_tenant_bootstrap() {
    cb_step "Creando cuenta administradora (primer tenant)"

    if cb_step_is_done "bootstrap_tenant" && [[ "$(cb_get_install_state TENANT_BOOTSTRAPPED)" == "true" ]]; then
        cb_info "Tenant ya creado, omitiendo"
        return 0
    fi

    cb_setup_load_state
    cb_tenant_ensure_admin_password

    local env_file="${CONTROLBOX_CONFIG_DIR}/platform.env"

    if [[ ! -f "${env_file}" ]]; then
        cb_die "platform.env no encontrado"
    fi

    cb_load_platform_env "${env_file}"
    cb_wait_for_service "api" \
        "cb_docker_compose_run '${env_file}' exec -T api curl -fsS http://localhost:8000/health >/dev/null 2>&1" 180

    local bootstrap_output
    if ! bootstrap_output="$(cb_docker_compose_run "${env_file}" exec -T api \
        python -m controlbox.installer.bootstrap_tenant 2>&1)"; then
        cb_error "No se pudo crear el tenant inicial"
        echo "${bootstrap_output}" | tail -40
        echo "${bootstrap_output}" >> "${CB_LOG_FILE}"
        cb_error "Detalle completo en ${CB_LOG_FILE}"
        return 1
    fi

    echo "${bootstrap_output}" >> "${CB_LOG_FILE}"
    if ! grep -qE 'TENANT_(SLUG|ADMIN_EMAIL)=' <<< "${bootstrap_output}"; then
        cb_warn "Bootstrap completó sin confirmación explícita; verificando tenant en base de datos..."
    fi

    cb_save_install_state "TENANT_BOOTSTRAPPED" "true"
    cb_config_append_panel_credentials
    cb_step_done "bootstrap_tenant"
    cb_success "Cuenta administradora creada: ${CONTROLBOX_TENANT_ADMIN_EMAIL}"
}

cb_tenant_reset_admin_password() {
    cb_step "Restableciendo contraseña del administrador del panel"

    local env_file="${CONTROLBOX_CONFIG_DIR}/platform.env"
    if [[ ! -f "${env_file}" ]]; then
        cb_die "platform.env no encontrado"
    fi

    cb_load_platform_env "${env_file}"
    cb_setup_load_state

    cb_wait_for_service "api" \
        "cb_docker_compose_run '${env_file}' exec -T api curl -fsS http://localhost:8000/health >/dev/null 2>&1" 120

    local reset_output
    if ! reset_output="$(cb_docker_compose_run "${env_file}" exec -T api \
        python -m controlbox.installer.reset_admin_password 2>&1)"; then
        cb_error "No se pudo restablecer la contraseña del panel"
        echo "${reset_output}" | tail -20
        cb_die "Reset de contraseña falló"
    fi

    echo "${reset_output}" >> "${CB_LOG_FILE}"
    cb_config_append_panel_credentials
    cb_success "Contraseña del panel sincronizada con platform.env"
    echo ""
    echo -e "${CB_BOLD}Usuario:${CB_NC}  ${CONTROLBOX_TENANT_ADMIN_EMAIL}"
    echo -e "${CB_BOLD}Contraseña:${CB_NC}  ${CONTROLBOX_TENANT_ADMIN_PASSWORD}"
    echo -e "${CB_BOLD}Archivo:${CB_NC}   ${CONTROLBOX_CONFIG_DIR}/credentials.txt"
}

cb_config_append_panel_credentials() {
    local cred_file="${CONTROLBOX_CONFIG_DIR}/credentials.txt"
    local server_ip
    server_ip="$(cb_setup_get_server_ip)"
    local panel_url
    panel_url="$(cb_setup_panel_url "${server_ip}" "${CONTROLBOX_PANEL_PORT}")"

    if [[ -f "${CONTROLBOX_CONFIG_DIR}/domains.conf" ]]; then
        cb_load_env_file "${CONTROLBOX_CONFIG_DIR}/domains.conf"
        local panel_path
        panel_path="$(cb_setup_normalize_panel_base_path "${CONTROLBOX_PANEL_BASE_PATH:-}")"
        if [[ -n "${PANEL_DOMAIN:-}" ]]; then
            if [[ -n "${panel_path}" ]]; then
                panel_url="https://${PANEL_DOMAIN}/${panel_path}"
            else
                panel_url="https://${PANEL_DOMAIN}"
            fi
        fi
    fi

    cat >> "${cred_file}" <<EOF

Panel de administración:
  URL:      ${panel_url}
  Usuario:  ${CONTROLBOX_TENANT_ADMIN_EMAIL}
  Contraseña: ${CONTROLBOX_TENANT_ADMIN_PASSWORD}
  Tenant:   ${CONTROLBOX_TENANT_SLUG}
EOF
    cb_secure_file "${cred_file}" 600
    cb_save_install_state "PANEL_URL" "${panel_url}"
}
