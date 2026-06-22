#!/usr/bin/env bash

cb_setup_pick_panel_port() {
    local port="${CONTROLBOX_PANEL_PORT:-}"
    if [[ -n "${port}" ]]; then
        echo "${port}"
        return 0
    fi

    local candidate
    for _ in $(seq 1 50); do
        candidate=$((8000 + RANDOM % 2000))
        if ! ss -tln 2>/dev/null | grep -q ":${candidate} " && ! netstat -tln 2>/dev/null | grep -q ":${candidate} "; then
            echo "${candidate}"
            return 0
        fi
    done

    echo "8475"
}

cb_setup_slugify() {
    local value="$1"
    value="$(echo "${value}" | tr '[:upper:]' '[:lower:]')"
    value="$(echo "${value}" | sed -E 's/[^a-z0-9]+/-/g; s/^-+|-+$//g')"
    if [[ -z "${value}" ]]; then
        value="main"
    fi
    echo "${value}"
}

cb_setup_validate_password() {
    local password="$1"
    if [[ ${#password} -lt 12 ]]; then
        cb_warn "La contraseña debe tener al menos 12 caracteres."
        return 1
    fi
    return 0
}

cb_setup_prompt_install() {
    cb_step "Configuración inicial del panel"

    if cb_is_noninteractive_install; then
        export CONTROLBOX_ASSUME_YES=true
    fi

    if cb_step_is_done "prompt_install" && [[ -f "${CONTROLBOX_STATE_DIR}/install.state" ]] \
        && [[ "${CONTROLBOX_REINSTALL:-}" != "true" ]]; then
        cb_info "Configuración de instalación ya recopilada"
        cb_setup_load_state
        return 0
    fi

    echo ""
    echo -e "${CB_BOLD}Asistente de instalación ControlBox${CB_NC}"
    echo "Configure el dominio (opcional), la cuenta administradora y el puerto del panel."
    echo "Sin dominio, el panel queda en http://IP:PUERTO (estilo aaPanel / HPanel)."
    echo ""

    local primary_domain="${CONTROLBOX_PRIMARY_DOMAIN:-}"
    local admin_email="${CONTROLBOX_ADMIN_EMAIL:-}"

    if [[ -z "${primary_domain}" ]] && [[ "${CONTROLBOX_ASSUME_YES:-}" != "true" ]]; then
        read -r -p "Dominio principal (opcional, Enter para omitir): " primary_domain
        if [[ -n "${primary_domain}" ]]; then
            read -r -p "Email para Let's Encrypt [admin@${primary_domain}]: " admin_email
            admin_email="${admin_email:-admin@${primary_domain}}"
        fi
    fi

    if [[ -z "${primary_domain}" ]] && [[ "${CONTROLBOX_ASSUME_YES:-}" == "true" ]]; then
        primary_domain="${CONTROLBOX_PRIMARY_DOMAIN:-}"
    fi

    export CONTROLBOX_PRIMARY_DOMAIN="${primary_domain}"
    export CONTROLBOX_ADMIN_EMAIL="${admin_email}"

    local tenant_name="${CONTROLBOX_TENANT_NAME:-}"
    local tenant_slug="${CONTROLBOX_TENANT_SLUG:-}"
    local tenant_admin_email="${CONTROLBOX_TENANT_ADMIN_EMAIL:-}"
    local tenant_admin_password="${CONTROLBOX_TENANT_ADMIN_PASSWORD:-}"
    local tenant_admin_full_name="${CONTROLBOX_TENANT_ADMIN_FULL_NAME:-}"

    if [[ -z "${tenant_name}" ]] && [[ "${CONTROLBOX_ASSUME_YES:-}" != "true" ]]; then
        read -r -p "Nombre de la organización [Mi Organización]: " tenant_name
        tenant_name="${tenant_name:-Mi Organización}"
        read -r -p "Slug del tenant (identificador) [$(cb_setup_slugify "${tenant_name}")]: " tenant_slug
        tenant_slug="${tenant_slug:-$(cb_setup_slugify "${tenant_name}")}"
        read -r -p "Email del administrador: " tenant_admin_email
        while true; do
            read -r -s -p "Contraseña del administrador (mín. 12 caracteres): " tenant_admin_password
            echo ""
            if cb_setup_validate_password "${tenant_admin_password}"; then
                break
            fi
        done
        read -r -p "Nombre completo del administrador [Administrador]: " tenant_admin_full_name
        tenant_admin_full_name="${tenant_admin_full_name:-Administrador}"
    fi

    if [[ -z "${tenant_name}" ]]; then
        tenant_name="${CONTROLBOX_TENANT_NAME:-Mi Organización}"
    fi
    if [[ -z "${tenant_slug}" ]]; then
        tenant_slug="${CONTROLBOX_TENANT_SLUG:-$(cb_setup_slugify "${tenant_name}")}"
    fi
    if [[ -z "${tenant_admin_email}" ]]; then
        if [[ -n "${primary_domain}" ]]; then
            tenant_admin_email="${CONTROLBOX_TENANT_ADMIN_EMAIL:-admin@${primary_domain}}"
        else
            tenant_admin_email="${CONTROLBOX_TENANT_ADMIN_EMAIL:-admin@controlbox.local}"
        fi
    fi
    if [[ -z "${tenant_admin_password}" ]]; then
        tenant_admin_password="${CONTROLBOX_TENANT_ADMIN_PASSWORD:-$(cb_generate_admin_password 16)}"
        cb_info "Contraseña de administrador generada automáticamente"
    fi
    tenant_admin_password="$(cb_sanitize_admin_password "${tenant_admin_password}")"
    if [[ -z "${tenant_admin_full_name}" ]]; then
        tenant_admin_full_name="${CONTROLBOX_TENANT_ADMIN_FULL_NAME:-Administrador}"
    fi

    if cb_is_noninteractive_install && [[ ${#tenant_admin_password} -lt 12 ]]; then
        tenant_admin_password="$(cb_generate_admin_password 16)"
        cb_info "Contraseña ajustada para instalación automática"
    fi

    tenant_slug="$(cb_setup_slugify "${tenant_slug}")"

    local panel_port="${CONTROLBOX_PANEL_PORT:-}"
    if [[ -z "${panel_port}" ]] && [[ "${CONTROLBOX_ASSUME_YES:-}" != "true" ]]; then
        local suggested_port
        suggested_port="$(cb_setup_pick_panel_port)"
        read -r -p "Puerto del panel en el VPS [${suggested_port}]: " panel_port
        panel_port="${panel_port:-${suggested_port}}"
    fi
    if [[ -z "${panel_port}" ]]; then
        panel_port="$(cb_setup_pick_panel_port)"
    fi
    panel_port="$(cb_sanitize_port "${panel_port}" "8475")"

    export CONTROLBOX_TENANT_NAME="${tenant_name}"
    export CONTROLBOX_TENANT_SLUG="${tenant_slug}"
    export CONTROLBOX_TENANT_ADMIN_EMAIL="${tenant_admin_email}"
    export CONTROLBOX_TENANT_ADMIN_PASSWORD="${tenant_admin_password}"
    export CONTROLBOX_TENANT_ADMIN_FULL_NAME="${tenant_admin_full_name}"
    export CONTROLBOX_PANEL_PORT="${panel_port}"
    export CONTROLBOX_PANEL_BASE_PATH="${CONTROLBOX_PANEL_BASE_PATH:-}"
    export INSTALLER_BOOTSTRAP_TOKEN="${INSTALLER_BOOTSTRAP_TOKEN:-$(cb_generate_secret 48)}"

    cb_setup_persist_state
    cb_step_done "prompt_install"
    cb_success "Configuración de instalación guardada"
}

cb_setup_load_state() {
    export CONTROLBOX_PRIMARY_DOMAIN="${CONTROLBOX_PRIMARY_DOMAIN:-$(cb_get_install_state PRIMARY_DOMAIN)}"
    export CONTROLBOX_ADMIN_EMAIL="${CONTROLBOX_ADMIN_EMAIL:-$(cb_get_install_state ADMIN_EMAIL)}"
    export CONTROLBOX_TENANT_NAME="${CONTROLBOX_TENANT_NAME:-$(cb_get_install_state TENANT_NAME)}"
    export CONTROLBOX_TENANT_SLUG="${CONTROLBOX_TENANT_SLUG:-$(cb_get_install_state TENANT_SLUG)}"
    export CONTROLBOX_TENANT_ADMIN_EMAIL="${CONTROLBOX_TENANT_ADMIN_EMAIL:-$(cb_get_install_state TENANT_ADMIN_EMAIL)}"
    export CONTROLBOX_TENANT_ADMIN_PASSWORD="$(cb_sanitize_admin_password "${CONTROLBOX_TENANT_ADMIN_PASSWORD:-$(cb_get_install_state TENANT_ADMIN_PASSWORD)}")"
    export CONTROLBOX_TENANT_ADMIN_FULL_NAME="${CONTROLBOX_TENANT_ADMIN_FULL_NAME:-$(cb_get_install_state TENANT_ADMIN_FULL_NAME)}"
    export CONTROLBOX_PANEL_PORT="$(cb_sanitize_port "${CONTROLBOX_PANEL_PORT:-$(cb_get_install_state PANEL_PORT)}" "")"
    if [[ -z "${CONTROLBOX_PANEL_PORT}" ]]; then
        export CONTROLBOX_PANEL_PORT="$(cb_sanitize_port "$(cb_setup_pick_panel_port)" "8475")"
    fi
    export CONTROLBOX_PANEL_BASE_PATH="${CONTROLBOX_PANEL_BASE_PATH:-$(cb_get_install_state PANEL_BASE_PATH)}"
    export CONTROLBOX_SERVER_IP="${CONTROLBOX_SERVER_IP:-$(cb_get_install_state SERVER_IP)}"
    export INSTALLER_BOOTSTRAP_TOKEN="${INSTALLER_BOOTSTRAP_TOKEN:-$(cb_get_install_state INSTALLER_BOOTSTRAP_TOKEN)}"
}

cb_setup_persist_state() {
    cb_save_install_state "PRIMARY_DOMAIN" "${CONTROLBOX_PRIMARY_DOMAIN:-}"
    cb_save_install_state "ADMIN_EMAIL" "${CONTROLBOX_ADMIN_EMAIL:-}"
    cb_save_install_state "TENANT_NAME" "${CONTROLBOX_TENANT_NAME}"
    cb_save_install_state "TENANT_SLUG" "${CONTROLBOX_TENANT_SLUG}"
    cb_save_install_state "TENANT_ADMIN_EMAIL" "${CONTROLBOX_TENANT_ADMIN_EMAIL}"
    cb_save_install_state "TENANT_ADMIN_PASSWORD" "${CONTROLBOX_TENANT_ADMIN_PASSWORD}"
    cb_save_install_state "TENANT_ADMIN_FULL_NAME" "${CONTROLBOX_TENANT_ADMIN_FULL_NAME}"
    cb_save_install_state "PANEL_PORT" "${CONTROLBOX_PANEL_PORT}"
    cb_save_install_state "PANEL_BASE_PATH" "${CONTROLBOX_PANEL_BASE_PATH}"
    cb_save_install_state "SERVER_IP" "${CONTROLBOX_SERVER_IP:-$(cb_setup_get_server_ip)}"
    cb_save_install_state "INSTALLER_BOOTSTRAP_TOKEN" "${INSTALLER_BOOTSTRAP_TOKEN}"

    local installer_env="${CONTROLBOX_CONFIG_DIR}/installer.env"
    mkdir -p "${CONTROLBOX_CONFIG_DIR}"
    {
        cb_env_emit "CONTROLBOX_PRIMARY_DOMAIN" "${CONTROLBOX_PRIMARY_DOMAIN:-}"
        cb_env_emit "CONTROLBOX_ADMIN_EMAIL" "${CONTROLBOX_ADMIN_EMAIL:-}"
        cb_env_emit "CONTROLBOX_TENANT_NAME" "${CONTROLBOX_TENANT_NAME}"
        cb_env_emit "CONTROLBOX_TENANT_SLUG" "${CONTROLBOX_TENANT_SLUG}"
        cb_env_emit "CONTROLBOX_TENANT_ADMIN_EMAIL" "${CONTROLBOX_TENANT_ADMIN_EMAIL}"
        cb_env_emit "CONTROLBOX_TENANT_ADMIN_PASSWORD" "${CONTROLBOX_TENANT_ADMIN_PASSWORD}"
        cb_env_emit "CONTROLBOX_TENANT_ADMIN_FULL_NAME" "${CONTROLBOX_TENANT_ADMIN_FULL_NAME}"
        cb_env_emit "CONTROLBOX_PANEL_PORT" "${CONTROLBOX_PANEL_PORT}"
        cb_env_emit "CONTROLBOX_PANEL_BASE_PATH" "${CONTROLBOX_PANEL_BASE_PATH}"
        cb_env_emit "INSTALLER_BOOTSTRAP_TOKEN" "${INSTALLER_BOOTSTRAP_TOKEN}"
    } > "${installer_env}"
    cb_secure_file "${installer_env}" 600
}

cb_setup_format_os_label() {
    local os_id="${1:-$(cb_get_install_state OS_ID 2>/dev/null || true)}"
    local os_version="${2:-$(cb_get_install_state OS_VERSION 2>/dev/null || true)}"
    os_id="${os_id//\"/}"
    os_version="${os_version//\"/}"
    case "${os_id}" in
        ubuntu) echo "Ubuntu ${os_version%%.*}" ;;
        debian) echo "Debian ${os_version}" ;;
        centos) echo "CentOS ${os_version%%.*}" ;;
        rocky) echo "Rocky ${os_version%%.*}" ;;
        almalinux) echo "AlmaLinux ${os_version%%.*}" ;;
        rhel) echo "RHEL ${os_version%%.*}" ;;
        fedora) echo "Fedora ${os_version%%.*}" ;;
        "") echo "Linux" ;;
        *) echo "${os_id^} ${os_version}" ;;
    esac
}

cb_setup_normalize_panel_base_path() {
    local path="${1:-}"
    path="${path//\"/}"
    path="${path//\'/}"
    path="${path%/}"
    path="${path#/}"
    echo "${path}"
}

cb_setup_panel_url() {
    local server_ip="${1:-$(cb_setup_get_server_ip)}"
    local panel_port="${2:-${CONTROLBOX_PANEL_PORT:-8475}}"
    local panel_path
    panel_path="$(cb_setup_normalize_panel_base_path "${3:-${CONTROLBOX_PANEL_BASE_PATH:-}}")"

    if [[ -n "${panel_path}" ]]; then
        echo "http://${server_ip}:${panel_port}/${panel_path}"
    else
        echo "http://${server_ip}:${panel_port}"
    fi
}

cb_setup_detect_local_ip() {
    local ip=""

    if command -v ip >/dev/null 2>&1; then
        ip="$(ip -4 addr show scope global 2>/dev/null | awk '
            /inet / {
                split($2, parts, "/")
                addr = parts[1]
                if (addr ~ /^127\./) next
                if (addr ~ /^10\./ || addr ~ /^192\.168\./ || addr ~ /^172\.(1[6-9]|2[0-9]|3[0-1])\./) {
                    print addr
                    exit
                }
                if (public == "") public = addr
            }
            END {
                if (public != "") print public
            }
        ' | head -1)"
    fi

    if [[ -z "${ip}" ]] && command -v ip >/dev/null 2>&1; then
        ip="$(ip -4 route get 1.1.1.1 2>/dev/null | awk '{for (i=1;i<=NF;i++) if ($i=="src") {print $(i+1); exit}}')"
    fi

    if [[ -z "${ip}" ]]; then
        ip="$(hostname -I 2>/dev/null | awk '{for (i=1;i<=NF;i++) if ($i !~ /^127\./) {print $i; exit}}')"
    fi

    echo "${ip}"
}

cb_setup_get_server_ip() {
    local ip="${CONTROLBOX_SERVER_IP:-}"
    local config_dir="${CONTROLBOX_CONFIG_DIR:-/etc/controlbox}"

    ip="${ip//\"/}"
    ip="${ip//\'/}"
    ip="${ip//[[:space:]]/}"
    if [[ -n "${ip}" ]]; then
        echo "${ip}"
        return 0
    fi

    if [[ -f "${config_dir}/platform.env" ]]; then
        ip="$(grep '^CONTROLBOX_SERVER_IP=' "${config_dir}/platform.env" 2>/dev/null | tail -1 | cut -d'=' -f2- | tr -d '"'"'"'"' | tr -d "'")"
        ip="${ip//[[:space:]]/}"
        if [[ -n "${ip}" ]]; then
            echo "${ip}"
            return 0
        fi
    fi

    ip="$(cb_get_install_state SERVER_IP 2>/dev/null || true)"
    ip="${ip//[[:space:]]/}"
    if [[ -n "${ip}" ]]; then
        echo "${ip}"
        return 0
    fi

    ip="$(cb_setup_detect_local_ip)"
    ip="${ip//[[:space:]]/}"
    if [[ -n "${ip}" ]]; then
        echo "${ip}"
        return 0
    fi

    ip="$(curl -fsSL -4 --max-time 5 ifconfig.me 2>/dev/null || curl -fsSL -4 --max-time 5 icanhazip.com 2>/dev/null || true)"
    ip="${ip//$'\r'/}"
    ip="${ip//[[:space:]]/}"
    if [[ -n "${ip}" ]]; then
        echo "${ip}"
        return 0
    fi

    echo "127.0.0.1"
}
