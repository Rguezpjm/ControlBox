#!/usr/bin/env bash
# Interactive server console when the web panel is unavailable.

cb_cli_require_root() {
    if [[ "${EUID}" -ne 0 ]]; then
        echo "[ERROR] Run as root: sudo controlbox"
        exit 1
    fi
}

cb_cli_env_file() {
    echo "${CONTROLBOX_CONFIG_DIR:-/etc/controlbox}/platform.env"
}

cb_cli_compose() {
    local env_file
    env_file="$(cb_cli_env_file)"
    local install_dir="${CONTROLBOX_INSTALL_DIR:-/opt/controlbox}"
    if [[ ! -f "${install_dir}/docker-compose.yml" ]]; then
        echo "[ERROR] docker-compose.yml not found in ${install_dir}"
        return 1
    fi
    local -a args=(compose --env-file "${env_file}" -f "${install_dir}/docker-compose.yml")
    for extra in docker-compose.ports.yml docker-compose.build.yml docker-compose.override.yml docker-compose.panel-build.yml; do
        [[ -f "${install_dir}/${extra}" ]] && args+=(-f "${install_dir}/${extra}")
    done
    local profiles=""
    if [[ -f "${env_file}" ]]; then
        profiles="$(grep '^CONTROLBOX_ENABLED_PROFILES=' "${env_file}" 2>/dev/null | tail -1 | cut -d'=' -f2- | tr -d '"'"'"'"' | tr -d "'")"
    fi
    profiles="${profiles:-databases,backups}"
    local p
    IFS=',' read -ra prof <<< "${profiles// /}"
    for p in "${prof[@]}"; do
        [[ -n "${p}" ]] && args+=(--profile "${p}")
    done
    (cd "${install_dir}" && docker "${args[@]}" "$@")
}

cb_cli_set_env_key() {
    local key="$1"
    local value="$2"
    local env_file
    env_file="$(cb_cli_env_file)"
    [[ -f "${env_file}" ]] || return 1
    if grep -q "^${key}=" "${env_file}"; then
        sed -i "s|^${key}=.*|${key}=${value}|" "${env_file}"
    else
        echo "${key}=${value}" >> "${env_file}"
    fi
}

cb_cli_banner() {
    echo ""
    echo "=================================================="
    echo "       ControlBox Server Console (CLI)"
    echo "=================================================="
    echo "  Use this menu if the web panel is unreachable."
    echo ""
}

cb_cli_show_menu() {
    cb_cli_banner
    cat <<'MENU'
  (1)  Restart panel UI service
  (2)  Stop panel UI service
  (3)  Start panel UI service
  (4)  Reload panel (recreate container)
  (5)  Sync admin password from config file
  (6)  Set new admin password
  (7)  Change panel access port
  (8)  Apply panel port / path changes
  (9)  Show login URL and credentials
  (10) Repair platform stack
  (11) Show panel container logs
  (12) Show API error logs
  (13) Show services status
  (14) Open firewall for panel port
  (15) Follow installer log
  (0)  Exit
MENU
    echo ""
}

cb_cli_panel_restart() {
    echo "Restarting panel..."
    cb_cli_compose restart panel 2>/dev/null || docker restart controlbox-panel 2>/dev/null || true
    echo "[OK] Panel restart requested"
}

cb_cli_panel_stop() {
    echo "Stopping panel (websites and databases keep running)..."
    cb_cli_compose stop panel 2>/dev/null || docker stop controlbox-panel 2>/dev/null || true
    echo "[OK] Panel stopped"
}

cb_cli_panel_start() {
    echo "Starting panel..."
    cb_cli_compose up -d panel 2>/dev/null || docker start controlbox-panel 2>/dev/null || true
    echo "[OK] Panel start requested"
}

cb_cli_panel_reload() {
    echo "Reloading panel container..."
    cb_cli_compose up -d --force-recreate panel 2>/dev/null || docker restart controlbox-panel 2>/dev/null || true
    echo "[OK] Panel reloaded"
}

cb_cli_show_credentials() {
    local cred="${CONTROLBOX_CONFIG_DIR:-/etc/controlbox}/credentials.txt"
    local env_file
    env_file="$(cb_cli_env_file)"

    if [[ -f "${CONTROLBOX_INSTALL_DIR:-/opt/controlbox}/lib/setup.sh" ]]; then
        # shellcheck source=lib/setup.sh
        source "${CONTROLBOX_INSTALL_DIR}/lib/setup.sh"
    fi

    local panel_url=""
    local email=""
    local password=""

    if declare -f cb_setup_load_state >/dev/null 2>&1; then
        cb_setup_load_state 2>/dev/null || true
        email="${CONTROLBOX_TENANT_ADMIN_EMAIL:-}"
        password="${CONTROLBOX_TENANT_ADMIN_PASSWORD:-}"
        if declare -f cb_setup_get_server_ip >/dev/null 2>&1; then
            panel_url="$(cb_setup_panel_url "$(cb_setup_get_server_ip)" "${CONTROLBOX_PANEL_PORT:-8475}")"
        fi
    fi

    if [[ -f "${env_file}" ]]; then
        [[ -z "${email}" ]] && email="$(grep '^TENANT_ADMIN_EMAIL=' "${env_file}" | tail -1 | cut -d'=' -f2- | tr -d '"'"'"'"' | tr -d "'")"
        [[ -z "${password}" ]] && password="$(grep '^TENANT_ADMIN_PASSWORD=' "${env_file}" | tail -1 | cut -d'=' -f2- | tr -d '"'"'"'"' | tr -d "'")"
        if [[ -z "${panel_url}" ]]; then
            local port ip
            port="$(grep '^PANEL_PORT=' "${env_file}" | tail -1 | cut -d'=' -f2- | tr -d '"'"'"'"' | tr -d "'")"
            ip="$(grep '^CONTROLBOX_SERVER_IP=' "${env_file}" | tail -1 | cut -d'=' -f2- | tr -d '"'"'"'"' | tr -d "'")"
            port="${port:-8475}"
            ip="${ip:-127.0.0.1}"
            panel_url="http://${ip}:${port}/"
        fi
    fi

    email="${email:-admin@controlbox.local}"

    echo ""
    echo "=================================================================="
    echo "ControlBox — credenciales de acceso"
    echo "=================================================================="
    echo ""
    echo "  URL del panel:  ${panel_url:-desconocida}"
    echo "  Usuario:        ${email}"
    echo "  Contraseña:     ${password:-(ver platform.env)}"
    echo ""
    if [[ -f "${cred}" ]]; then
        echo "  Archivo completo: ${cred}"
        echo ""
    fi
}

cb_cli_set_password() {
    local env_file
    env_file="$(cb_cli_env_file)"
    local pwd1 pwd2
    read -r -s -p "New admin password (min 12 chars): " pwd1
    echo ""
    read -r -s -p "Confirm password: " pwd2
    echo ""
    if [[ "${pwd1}" != "${pwd2}" ]]; then
        echo "[ERROR] Passwords do not match"
        return 1
    fi
    if [[ ${#pwd1} -lt 12 ]]; then
        echo "[ERROR] Password must be at least 12 characters"
        return 1
    fi
    cb_cli_set_env_key "TENANT_ADMIN_PASSWORD" "${pwd1}"
    cb_cli_set_env_key "INSTALLER_TENANT_ADMIN_PASSWORD" "${pwd1}"
    bash "${CONTROLBOX_INSTALL_DIR}/repair.sh" --reset-panel-password
}

cb_cli_change_port() {
    local env_file
    env_file="$(cb_cli_env_file)"
    local current new_port
    current="$(grep '^PANEL_PORT=' "${env_file}" 2>/dev/null | tail -1 | cut -d'=' -f2- | tr -d '"'"'"'"' | tr -d "'")"
    current="${current:-8475}"
    read -r -p "Panel port [${current}]: " new_port
    new_port="${new_port:-${current}}"
    if ! [[ "${new_port}" =~ ^[0-9]+$ ]] || [[ "${new_port}" -lt 1024 ]] || [[ "${new_port}" -gt 65535 ]]; then
        echo "[ERROR] Invalid port"
        return 1
    fi
    cb_cli_set_env_key "PANEL_PORT" "${new_port}"
    cb_cli_set_env_key "CONTROLBOX_PANEL_PORT" "${new_port}"
    echo "[OK] Port saved. Run option (8) to apply, or: controlbox apply-panel"
}

cb_cli_open_firewall() {
    local lib="${CONTROLBOX_INSTALL_DIR}/lib/firewall.sh"
    if [[ -f "${lib}" ]]; then
        # shellcheck source=lib/firewall.sh
        source "${CONTROLBOX_INSTALL_DIR}/lib/common.sh"
        source "${lib}"
        cb_init_logging 2>/dev/null || true
        cb_load_config 2>/dev/null || true
        local port
        port="$(grep '^PANEL_PORT=' "$(cb_cli_env_file)" 2>/dev/null | tail -1 | cut -d'=' -f2- | tr -d '"'"'"'"' | tr -d "'")"
        port="${port:-8475}"
        cb_firewall_open_port "${port}" && echo "[OK] Firewall updated for port ${port}"
    else
        echo "[WARN] Firewall module not found"
    fi
}

cb_cli_interactive_menu() {
    cb_cli_require_root
    while true; do
        cb_cli_show_menu
        read -r -p "Enter option number: " choice
        echo ""
        case "${choice}" in
            1) cb_cli_panel_restart ;;
            2) cb_cli_panel_stop ;;
            3) cb_cli_panel_start ;;
            4) cb_cli_panel_reload ;;
            5) bash "${CONTROLBOX_INSTALL_DIR}/repair.sh" --reset-panel-password ;;
            6) cb_cli_set_password ;;
            7) cb_cli_change_port ;;
            8) bash "${CONTROLBOX_INSTALL_DIR}/repair.sh" --apply-panel ;;
            9) cb_cli_show_credentials ;;
            10) bash "${CONTROLBOX_INSTALL_DIR}/repair.sh" ;;
            11) docker logs controlbox-panel --tail 100 2>&1 || cb_cli_compose logs --tail 100 panel ;;
            12) docker logs controlbox-api --tail 100 2>&1 || cb_cli_compose logs --tail 100 api ;;
            13) bash "${CONTROLBOX_INSTALL_DIR}/repair.sh" --status ;;
            14) cb_cli_open_firewall ;;
            15) tail -f "${CONTROLBOX_LOG_DIR:-/var/log/controlbox}/installer.log" ;;
            0|q|Q|exit) echo "Bye."; break ;;
            *) echo "[WARN] Unknown option: ${choice}" ;;
        esac
        echo ""
        read -r -p "Press Enter to continue..." _
        echo ""
    done
}
