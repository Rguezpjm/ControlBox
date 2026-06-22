#!/usr/bin/env bash

cb_install_resolve_credentials() {
    if declare -f cb_setup_load_state >/dev/null 2>&1; then
        cb_setup_load_state 2>/dev/null || true
    fi

    local server_ip panel_url admin_email admin_password panel_path=""
    server_ip="$(cb_setup_get_server_ip 2>/dev/null || echo "127.0.0.1")"
    panel_url="$(cb_setup_panel_url "${server_ip}" "${CONTROLBOX_PANEL_PORT:-8475}" 2>/dev/null || echo "http://${server_ip}:${CONTROLBOX_PANEL_PORT:-8475}")"

    if [[ -f "${CONTROLBOX_CONFIG_DIR}/platform.env" ]]; then
        # shellcheck source=/dev/null
        cb_load_platform_env "${CONTROLBOX_CONFIG_DIR}/platform.env" 2>/dev/null || true
    fi

    admin_email="${CONTROLBOX_TENANT_ADMIN_EMAIL:-}"
    admin_password="${CONTROLBOX_TENANT_ADMIN_PASSWORD:-}"

    if [[ -z "${admin_email}" ]] && [[ -f "${CONTROLBOX_CONFIG_DIR}/platform.env" ]]; then
        admin_email="$(grep '^TENANT_ADMIN_EMAIL=' "${CONTROLBOX_CONFIG_DIR}/platform.env" 2>/dev/null | tail -1 | cut -d'=' -f2- | tr -d '"'"'"'"' | tr -d "'")"
    fi
    if [[ -z "${admin_password}" ]] && [[ -f "${CONTROLBOX_CONFIG_DIR}/platform.env" ]]; then
        admin_password="$(grep '^TENANT_ADMIN_PASSWORD=' "${CONTROLBOX_CONFIG_DIR}/platform.env" 2>/dev/null | tail -1 | cut -d'=' -f2- | tr -d '"'"'"'"' | tr -d "'")"
    fi

    if [[ -f "${CONTROLBOX_CONFIG_DIR}/domains.conf" ]]; then
        cb_load_env_file "${CONTROLBOX_CONFIG_DIR}/domains.conf" 2>/dev/null || true
        if declare -f cb_setup_normalize_panel_base_path >/dev/null 2>&1; then
            panel_path="$(cb_setup_normalize_panel_base_path "${CONTROLBOX_PANEL_BASE_PATH:-}")"
        fi
        if [[ -n "${PANEL_DOMAIN:-}" ]]; then
            if [[ -n "${panel_path}" ]]; then
                panel_url="https://${PANEL_DOMAIN}/${panel_path}"
            else
                panel_url="https://${PANEL_DOMAIN}"
            fi
        fi
    fi

    admin_email="${admin_email:-admin@controlbox.local}"
    admin_password="${admin_password:-}"

    CB_SUMMARY_PANEL_URL="${panel_url}"
    CB_SUMMARY_ADMIN_EMAIL="${admin_email}"
    CB_SUMMARY_ADMIN_PASSWORD="${admin_password}"
    CB_SUMMARY_SERVER_IP="${server_ip}"
    CB_SUMMARY_PANEL_PORT="${CONTROLBOX_PANEL_PORT:-8475}"
}

cb_print_post_install_summary() {
    if [[ "${CB_INSTALL_SUMMARY_SHOWN:-}" == "1" ]]; then
        return 0
    fi
    local install_started_at="${1:-$(date +%s)}"
    cb_install_resolve_credentials

    local panel_url="${CB_SUMMARY_PANEL_URL:-}"
    local admin_email="${CB_SUMMARY_ADMIN_EMAIL:-admin@controlbox.local}"
    local admin_password="${CB_SUMMARY_ADMIN_PASSWORD:-}"
    local server_ip="${CB_SUMMARY_SERVER_IP:-127.0.0.1}"
    local panel_port="${CB_SUMMARY_PANEL_PORT:-8475}"
    local direct_url=""
    if declare -f cb_setup_panel_direct_url >/dev/null 2>&1; then
        direct_url="$(cb_setup_panel_direct_url "${server_ip}" "${panel_port}")"
    else
        direct_url="http://${server_ip}:${panel_port}"
    fi

    local elapsed=$(( $(date +%s) - install_started_at ))
    local elapsed_min=$(( elapsed / 60 ))
    [[ "${elapsed_min}" -lt 1 ]] && elapsed_min=1
    local firewall_ports="80|443|${panel_port}"

    if declare -f cb_save_install_state >/dev/null 2>&1; then
        cb_save_install_state "PANEL_URL" "${panel_url}" 2>/dev/null || true
    fi

    echo ""
    echo -e "${CB_GREEN}======================================================================${CB_NC}"
    echo -e "${CB_GREEN}======================================================================${CB_NC}"
    echo ""
    echo -e "${CB_BLUE}${CB_BOLD}Congratulations! ControlBox installed successfully!${CB_NC}"
    echo ""
    echo -e "${CB_GREEN}======================================================================${CB_NC}"
    echo -e "${CB_GREEN}======================================================================${CB_NC}"
    echo ""
    echo -e "${CB_BOLD}Panel URL:${CB_NC}  ${panel_url}"
    if cb_setup_is_ip_only_mode 2>/dev/null && [[ -n "${direct_url}" ]] && [[ "${direct_url}" != "${panel_url}" ]]; then
        echo -e "${CB_BOLD}Direct URL:${CB_NC} ${direct_url} (requiere puerto ${panel_port} abierto)"
    fi
    echo -e "${CB_BOLD}username:${CB_NC}   ${admin_email}"
    echo -e "${CB_BOLD}password:${CB_NC}   ${admin_password}"
    echo ""
    echo -e "${CB_YELLOW}${CB_BOLD}Warning:${CB_NC}"
    echo -e "${CB_YELLOW}If you cannot access the panel, release the following ports in the security group${CB_NC}"
    echo -e "${CB_YELLOW}(${firewall_ports})${CB_NC}"
    echo ""
    echo -e "${CB_GREEN}======================================================================${CB_NC}"
    echo -e "${CB_GREEN}======================================================================${CB_NC}"
    echo ""
    echo -e "${CB_BOLD}Time consumed:${CB_NC} ${CB_BLUE}${elapsed_min} Minute(s)!${CB_NC}"
    echo ""
    echo -e "  Credenciales guardadas en: ${CONTROLBOX_CONFIG_DIR}/credentials.txt"
    echo -e "  Ver de nuevo:              controlbox credentials"
    echo ""
    export CB_INSTALL_SUMMARY_SHOWN=1
}
