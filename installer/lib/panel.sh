#!/usr/bin/env bash

cb_panel_curl_ok() {
    local url="$1"
    local code=""
    code="$(curl -fsS -o /dev/null -w '%{http_code}' --max-time 6 "${url}" 2>/dev/null || echo "000")"
    [[ "${code}" =~ ^(200|301|302|307|308)$ ]]
}

cb_panel_prepare_ip_access_files() {
    local templates_dir="${CONTROLBOX_INSTALLER_ROOT}/templates"
    local config_dir="${CONTROLBOX_CONFIG_DIR}/traefik"
    local compose_override="${CONTROLBOX_INSTALL_DIR}/docker-compose.override.yml"

    mkdir -p "${config_dir}/dynamic"
    if [[ -f "${templates_dir}/traefik/traefik.ip-only.yml" ]]; then
        cp -f "${templates_dir}/traefik/traefik.ip-only.yml" "${config_dir}/traefik.yml"
    fi

    cat > "${compose_override}" <<'EOF'
services:
  panel:
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.controlbox-panel-ip.rule=HostRegexp(`{host:.+}`)"
      - "traefik.http.routers.controlbox-panel-ip.entrypoints=web"
      - "traefik.http.routers.controlbox-panel-ip.priority=1"
      - "traefik.http.routers.controlbox-panel-ip.service=controlbox-panel-ip"
      - "traefik.http.services.controlbox-panel-ip.loadbalancer.server.port=3000"
EOF
}

cb_panel_apply_ip_access() {
    local env_file="${CONTROLBOX_CONFIG_DIR}/platform.env"
    local server_ip
    server_ip="$(cb_setup_get_server_ip)"

    cb_panel_prepare_ip_access_files

    if [[ ! -f "${env_file}" ]] || ! declare -f cb_docker_compose_run >/dev/null 2>&1; then
        return 0
    fi

    if [[ "$(cb_get_install_state IP_PANEL_ROUTING 2>/dev/null)" == "1" ]] \
        && docker ps --format '{{.Names}}' 2>/dev/null | grep -q '^controlbox-panel$' \
        && docker ps --format '{{.Names}}' 2>/dev/null | grep -q '^controlbox-traefik$'; then
        cb_info "Panel accesible en http://${server_ip}/ (puerto 80)"
        return 0
    fi

    cb_info "Publicando panel en http://${server_ip}/ (Traefik puerto 80)"
    cb_docker_compose_run "${env_file}" up -d traefik panel || {
        cb_warn "No se pudo aplicar routing IP; ejecute: controlbox apply-panel"
        return 1
    }
    cb_save_install_state "IP_PANEL_ROUTING" "1"
    return 0
}

cb_panel_verify_access() {
    local panel_port="${CONTROLBOX_PANEL_PORT:-8475}"
    local timeout="${1:-90}"
    panel_port="$(cb_sanitize_port "${panel_port}" "8475")"
    local elapsed=0
    local ok_traefik=false ok_direct=false

    while [[ ${elapsed} -lt ${timeout} ]]; do
        if cb_panel_curl_ok "http://127.0.0.1/login" || cb_panel_curl_ok "http://127.0.0.1/"; then
            ok_traefik=true
            break
        fi
        if cb_panel_curl_ok "http://127.0.0.1:${panel_port}/login" \
            || cb_panel_curl_ok "http://127.0.0.1:${panel_port}/"; then
            ok_direct=true
            break
        fi
        sleep 3
        elapsed=$((elapsed + 3))
    done

    if [[ "${ok_traefik}" == "true" ]]; then
        cb_success "Panel responde en puerto 80 (http://$(cb_setup_get_server_ip)/)"
        return 0
    fi

    if [[ "${ok_direct}" == "true" ]]; then
        cb_success "Panel responde en puerto ${panel_port} (acceso directo)"
        cb_warn "Use http://$(cb_setup_get_server_ip):${panel_port} o abra el puerto ${panel_port} en el firewall cloud"
        return 0
    fi

    if ss -tln 2>/dev/null | grep -qE ':80 |:8475 '; then
        cb_warn "Puertos 80/8475 en escucha pero el panel aún no responde HTTP; reintente en 1 minuto"
        cb_warn "URL: http://$(cb_setup_get_server_ip)/"
        return 0
    fi

    cb_error "Panel no responde en localhost:80 ni localhost:${panel_port}"
    return 1
}

cb_panel_apply_config() {
    cb_step "Aplicando configuración del panel"

    local env_file="${CONTROLBOX_CONFIG_DIR}/platform.env"
    if [[ ! -f "${env_file}" ]]; then
        cb_die "platform.env no encontrado"
    fi

    cb_load_platform_env "${env_file}"
    cb_setup_load_state 2>/dev/null || true

    local panel_port="${PANEL_PORT:-8475}"
    panel_port="${CONTROLBOX_PANEL_PORT:-${panel_port}}"

    cb_firewall_open_port "${panel_port}" || true

    if cb_setup_is_ip_only_mode 2>/dev/null; then
        cb_panel_apply_ip_access
        cb_panel_verify_access 60 || true
        cb_success "Panel actualizado (http://$(cb_setup_get_server_ip)/)"
        cb_save_install_state "PANEL_PORT" "${panel_port}"
        return 0
    fi

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
