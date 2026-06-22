#!/usr/bin/env bash

set -euo pipefail

CONTROLBOX_VERSION="${CONTROLBOX_VERSION:-1.1.0}"
CONTROLBOX_INSTALL_URL="${CONTROLBOX_INSTALL_URL:-https://install.grodtech.com}"
CONTROLBOX_INSTALLER_ROOT="${CONTROLBOX_INSTALLER_ROOT:-}"
CONTROLBOX_BOOTSTRAP_BUILD="20250621-41"

cb_resolve_installer_root() {
    local tmp_dir="$1"
    local candidate=""

    for candidate in \
        "${tmp_dir}/controlbox-installer" \
        "${tmp_dir}/controlbox-installer-${CONTROLBOX_VERSION}"; do
        if [[ -f "${candidate}/lib/common.sh" ]]; then
            echo "${candidate}"
            return 0
        fi
    done

    candidate="$(find "${tmp_dir}" -mindepth 1 -maxdepth 1 -type d -name 'controlbox-installer*' | head -1)"
    if [[ -n "${candidate}" ]] && [[ -f "${candidate}/lib/common.sh" ]]; then
        echo "${candidate}"
        return 0
    fi

    return 1
}

cb_normalize_package_files() {
    local root="$1"
    find "${root}" -type f \( \
        -name '*.sh' -o -name '*.conf' -o -name '*.yml' -o -name '*.yaml' \
        -o -name '*.tpl' -o -name '*.env' -o -name '*.json' \
    \) -exec sed -i 's/\r$//' {} +
}

cb_patch_copy_from_script_dir() {
    local root="$1"
    local rel="$2"
    local script_dir=""

    if [[ -n "${BASH_SOURCE[0]:-}" ]] && [[ "${BASH_SOURCE[0]}" != "-" ]] && [[ -f "${BASH_SOURCE[0]}" ]]; then
        script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
        if [[ -f "${script_dir}/${rel}" ]]; then
            mkdir -p "$(dirname "${root}/${rel}")"
            cp -f "${script_dir}/${rel}" "${root}/${rel}"
            return 0
        fi
    fi
    return 1
}

cb_patch_embed_bootstrap_fixes() {
    local root="$1"
    local dest="${root}/lib/bootstrap-fixes.sh"
    [[ -f "${dest}" ]] && return 0
    mkdir -p "${root}/lib"
    echo '__BOOTSTRAP_FIXES_B64__' | base64 -d > "${dest}" 2>/dev/null || return 1
}

cb_patch_embed_reinstall() {
    local root="$1"
    local dest="${root}/lib/reinstall.sh"
    [[ -f "${dest}" ]] && return 0
    mkdir -p "${root}/lib"
    echo '__REINSTALL_B64__' | base64 -d > "${dest}" 2>/dev/null || return 1
    chmod +x "${dest}" 2>/dev/null || true
}

cb_patch_sync_hotfix_file() {
    local root="$1"
    local rel="$2"
    local dest="${root}/${rel}"
    local src=""

    for src in \
        "${CONTROLBOX_LOCAL_INSTALLER:-}/${rel}" \
        "${dest}"; do
        if [[ -n "${CONTROLBOX_LOCAL_INSTALLER:-}" ]] && [[ -f "${CONTROLBOX_LOCAL_INSTALLER}/${rel}" ]]; then
            mkdir -p "$(dirname "${dest}")"
            cp -f "${CONTROLBOX_LOCAL_INSTALLER}/${rel}" "${dest}"
            return 0
        fi
    done

    if curl -fsSL "${CONTROLBOX_INSTALL_URL}/${rel}" -o "${dest}.tmp" 2>/dev/null; then
        mkdir -p "$(dirname "${dest}")"
        mv -f "${dest}.tmp" "${dest}"
        return 0
    fi

    rm -f "${dest}.tmp" 2>/dev/null || true
    return 1
}

cb_patch_legacy_package() {
    local root="$1"
    local defaults="${root}/config/defaults.conf"
    local common="${root}/lib/common.sh"
    local compose="${root}/templates/docker-compose.platform.yml"
    local docker_sh="${root}/lib/docker.sh"
    local tar_build=""

    if [[ -f "${defaults}" ]]; then
        sed -i 's/^BACKUP_CRON_SCHEDULE=0 3 \* \* \*$/BACKUP_CRON_SCHEDULE="0 3 * * *"/' "${defaults}"
    fi

    if [[ -f "${common}" ]] && ! grep -q 'cb_load_env_file' "${common}"; then
        cat >> "${common}" <<'EOF'

cb_load_env_file() {
    local file="$1"
    [[ -f "${file}" ]] || return 0
    while IFS= read -r line || [[ -n "${line}" ]]; do
        line="${line%%#*}"
        line="${line#"${line%%[![:space:]]*}"}"
        line="${line%"${line##*[![:space:]]}"}"
        [[ -z "${line}" ]] && continue
        [[ "${line}" == *=* ]] || continue
        local key="${line%%=*}"
        local value="${line#*=}"
        key="${key#"${key%%[![:space:]]*}"}"
        key="${key%"${key##*[![:space:]]}"}"
        if [[ "${value}" =~ ^\"(.*)\"$ ]]; then
            value="${BASH_REMATCH[1]}"
        elif [[ "${value}" =~ ^\'(.*)\'$ ]]; then
            value="${BASH_REMATCH[1]}"
        fi
        printf -v "${key}" '%s' "${value}"
        export "${key}"
    done < "${file}"
}

cb_load_config() {
    cb_load_env_file "${CONTROLBOX_INSTALLER_ROOT}/config/defaults.conf"
    cb_load_env_file "${CONTROLBOX_CONFIG_DIR}/installer.env"
}
EOF
    fi

    cb_patch_sync_hotfix_file "${root}" "lib/bootstrap-fixes.sh" \
        || cb_patch_copy_from_script_dir "${root}" "lib/bootstrap-fixes.sh" \
        || cb_patch_embed_bootstrap_fixes "${root}" \
        || true
    cb_patch_sync_hotfix_file "${root}" "lib/reinstall.sh" \
        || cb_patch_copy_from_script_dir "${root}" "lib/reinstall.sh" \
        || cb_patch_embed_reinstall "${root}" \
        || true

    if [[ ! -f "${root}/lib/bootstrap-fixes.sh" ]]; then
        echo "[ControlBox] ERROR: No se pudo obtener lib/bootstrap-fixes.sh"
        echo "Suba install.sh actualizado (build ${CONTROLBOX_BOOTSTRAP_BUILD}) al CDN."
        exit 1
    fi

    if [[ -f "${docker_sh}" ]] && ! grep -q 'bootstrap-fixes.sh' "${docker_sh}"; then
        cat >> "${docker_sh}" <<'EOF'

if [[ -f "${BASH_SOURCE[0]%/*}/bootstrap-fixes.sh" ]]; then
    # shellcheck source=lib/bootstrap-fixes.sh
    source "${BASH_SOURCE[0]%/*}/bootstrap-fixes.sh"
fi
EOF
    fi

    if [[ -f "${compose}" ]]; then
        sed -i \
            -e '/PANEL_PORT/d' \
            -e '/^\s*- "\${PANEL_PORT/d' \
            -e '/^\s*- ${PANEL_PORT/d' \
            "${compose}" 2>/dev/null || true
    fi

    if [[ -f "${root}/install.sh" ]]; then
        tar_build="$(grep '^CONTROLBOX_BOOTSTRAP_BUILD=' "${root}/install.sh" | head -1 | cut -d'"' -f2)"
        if [[ -n "${tar_build}" ]] && [[ "${tar_build}" != "${CONTROLBOX_BOOTSTRAP_BUILD}" ]]; then
            echo "[ControlBox] AVISO: paquete tar=${tar_build}, bootstrap=${CONTROLBOX_BOOTSTRAP_BUILD}"
            echo "[ControlBox] Aplicando parches hotfix. Suba también controlbox-installer-${CONTROLBOX_VERSION}.tar.gz al CDN."
        fi
    fi
}

cb_bootstrap_download_package() {
    local tmp_dir="$1"
    local -a package_urls=()
    local package_url=""

    package_urls+=("${CONTROLBOX_INSTALL_URL}/controlbox-installer-${CONTROLBOX_VERSION}.tar.gz")
    if [[ "${CONTROLBOX_VERSION}" != "1.0.0" ]]; then
        package_urls+=("${CONTROLBOX_INSTALL_URL}/controlbox-installer-1.0.0.tar.gz")
    fi

    for package_url in "${package_urls[@]}"; do
        echo "[ControlBox] Descargando instalador desde ${package_url}..."
        if curl -fsSL "${package_url}" -o "${tmp_dir}/installer.tar.gz" 2>/dev/null; then
            echo "[ControlBox] Paquete descargado correctamente"
            return 0
        fi
        echo "[ControlBox] No disponible: ${package_url}"
    done

    return 1
}

cb_bootstrap_package_missing_error() {
    echo "[ControlBox] ERROR: No se pudo descargar el paquete del instalador."
    echo ""
    echo "El script install.sh está en el CDN, pero falta el archivo .tar.gz."
    echo "Suba al mismo directorio web de install.grodtech.com:"
    echo "  controlbox-installer-${CONTROLBOX_VERSION}.tar.gz"
    echo ""
    echo "Verifique en el VPS CDN (debe responder 200, no 404):"
    echo "  curl -fsI ${CONTROLBOX_INSTALL_URL}/controlbox-installer-${CONTROLBOX_VERSION}.tar.gz"
    echo ""
    echo "Tras subir, purgue caché de Cloudflare y vuelva a ejecutar:"
    echo "  curl -fsSL ${CONTROLBOX_INSTALL_URL}/install.sh | bash"
}

cb_bootstrap() {
    if [[ -n "${CONTROLBOX_INSTALLER_ROOT}" ]] && [[ -f "${CONTROLBOX_INSTALLER_ROOT}/lib/common.sh" ]]; then
        return 0
    fi

    local script_path=""
    if [[ -n "${BASH_SOURCE[0]:-}" ]] && [[ "${BASH_SOURCE[0]}" != "-" ]] && [[ -f "${BASH_SOURCE[0]}" ]]; then
        script_path="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
        if [[ -f "${script_path}/lib/common.sh" ]]; then
            CONTROLBOX_INSTALLER_ROOT="${script_path}"
            export CONTROLBOX_INSTALLER_ROOT
            return 0
        fi
    fi

    local tmp_dir
    tmp_dir="$(mktemp -d /tmp/controlbox-installer.XXXXXX)"

    echo "[ControlBox] Bootstrap build ${CONTROLBOX_BOOTSTRAP_BUILD}"

    if ! cb_bootstrap_download_package "${tmp_dir}"; then
        if [[ -n "${script_path}" ]] && [[ -d "${script_path}" ]] && [[ -f "${script_path}/lib/common.sh" ]]; then
            echo "[ControlBox] Paquete remoto no disponible, usando instalador local..."
            cp -a "${script_path}/." "${tmp_dir}/controlbox-installer/"
            CONTROLBOX_INSTALLER_ROOT="${tmp_dir}/controlbox-installer"
            export CONTROLBOX_LOCAL_INSTALLER="${script_path}"
            cb_normalize_package_files "${CONTROLBOX_INSTALLER_ROOT}"
            cb_patch_legacy_package "${CONTROLBOX_INSTALLER_ROOT}"
        else
            cb_bootstrap_package_missing_error
            rm -rf "${tmp_dir}"
            exit 1
        fi
    else
        tar xzf "${tmp_dir}/installer.tar.gz" -C "${tmp_dir}"
        if ! CONTROLBOX_INSTALLER_ROOT="$(cb_resolve_installer_root "${tmp_dir}")"; then
            echo "[ControlBox] ERROR: Estructura del paquete inválida tras extraer el .tar.gz"
            echo "[ControlBox] Contenido extraído:"
            find "${tmp_dir}" -maxdepth 2 -type f -o -type d | sed 's/^/  /'
            rm -rf "${tmp_dir}"
            exit 1
        fi
    fi

    cb_normalize_package_files "${CONTROLBOX_INSTALLER_ROOT}"
    cb_patch_legacy_package "${CONTROLBOX_INSTALLER_ROOT}"

    export CONTROLBOX_INSTALLER_ROOT
    export CONTROLBOX_BOOTSTRAP_TMP="${tmp_dir}"

    cb_run_installer "$@"
    local exit_code=$?
    rm -rf "${tmp_dir}"
    exit "${exit_code}"
}

cb_main_install() {
    local install_started_at
    install_started_at="$(cb_env_safe_date +%s 2>/dev/null || date +%s)"

    cb_banner
    cb_require_root
    cb_init_logging
    cb_acquire_lock
    cb_setup_traps

    cb_load_defaults
    export CONTROLBOX_CONFIG_DIR="${CONTROLBOX_CONFIG_DIR:-/etc/controlbox}"
    export CONTROLBOX_DATA_DIR="${CONTROLBOX_DATA_DIR:-/var/lib/controlbox}"
    export CONTROLBOX_INSTALL_DIR="${CONTROLBOX_INSTALL_DIR:-/opt/controlbox}"

    cb_install_purge_corrupt_env

    if cb_is_noninteractive_install; then
        export CONTROLBOX_ASSUME_YES=true
        cb_install_clean_for_reinstall
    elif cb_install_detect_existing; then
        cb_warn "ControlBox ya está instalado en ${CONTROLBOX_INSTALL_DIR}"
        if cb_is_noninteractive_install; then
            export CONTROLBOX_REINSTALL=true
            cb_info "Reinstalación/actualización automática (curl | bash)"
        else
            cb_confirm "¿Desea reinstalar/actualizar?" || exit 0
            export CONTROLBOX_REINSTALL=true
        fi
    fi

    cb_load_installer_env

    cb_info "Iniciando instalación ControlBox v${CONTROLBOX_VERSION} (build ${CONTROLBOX_BOOTSTRAP_BUILD})"
    cb_info "Log: ${CB_LOG_FILE}"
    cb_progress_init 16

    cb_rollback_create_snapshot "pre-install"

    cb_os_detect
    cb_resources_detect
    cb_resources_print_summary

    cb_os_install_prerequisites
    cb_os_create_user
    cb_os_create_directories

    cb_setup_prompt_install

    cb_config_install_scripts

    cb_docker_install
    cb_compose_install

    cb_config_generate
    cb_setup_load_state
    cb_firewall_configure
    cb_docker_pull_images
    cb_docker_deploy_stack
    cb_domains_configure
    cb_ssl_configure
    cb_tenant_bootstrap
    cb_backup_configure

    cb_rollback_clear_active
    touch "${CONTROLBOX_STATE_DIR}/installed"
    echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "${CONTROLBOX_STATE_DIR}/installed"

    cb_print_post_install_summary "${install_started_at}"
    cb_progress_render "Instalación completada"
    echo ""
}

cb_print_post_install_summary() {
    local install_started_at="${1:-$(date +%s)}"
    cb_setup_load_state

    local server_ip
    server_ip="$(cb_setup_get_server_ip)"
    local panel_url
    panel_url="$(cb_setup_panel_url "${server_ip}" "${CONTROLBOX_PANEL_PORT}")"

    if [[ -f "${CONTROLBOX_CONFIG_DIR}/domains.conf" ]]; then
        cb_load_env_file "${CONTROLBOX_CONFIG_DIR}/domains.conf"
        if [[ -n "${PANEL_DOMAIN:-}" ]]; then
            panel_url="https://${PANEL_DOMAIN}/${panel_path}"
        fi
    fi

    local elapsed=$(( $(date +%s) - install_started_at ))
    local elapsed_min=$(( elapsed / 60 ))
    local firewall_ports="${CONTROLBOX_PANEL_PORT}|80|443"

    echo ""
    echo "=================================================================="
    echo -e "${CB_GREEN}${CB_BOLD}Congratulations! ControlBox installed successfully!${CB_NC}"
    echo "=================================================================="
    echo ""
    echo -e "${CB_BOLD}Panel:${CB_NC}     ${panel_url}"
    echo -e "${CB_BOLD}Username:${CB_NC}  ${CONTROLBOX_TENANT_ADMIN_EMAIL}"
    echo -e "${CB_BOLD}Password:${CB_NC}  ${CONTROLBOX_TENANT_ADMIN_PASSWORD}"
    echo ""
    echo -e "${CB_YELLOW}${CB_BOLD}Warning:${CB_NC}"
    echo "If you cannot access the panel, release the following ports"
    echo "in your security group / firewall: ${firewall_ports}"
    echo ""
    echo "=================================================================="
    echo -e "${CB_BOLD}Time consumed:${CB_NC} ${elapsed_min} Minute(s)!"
    echo "=================================================================="
    echo ""
    echo -e "  ${CB_BOLD}Detalles adicionales:${CB_NC}"
    echo -e "  IP del servidor:     ${server_ip}"
    echo -e "  Puerto del panel:    ${CONTROLBOX_PANEL_PORT}"
    echo -e "  Directorio:          ${CONTROLBOX_INSTALL_DIR}"
    echo -e "  Configuración:       ${CONTROLBOX_CONFIG_DIR}"
    echo -e "  Credenciales:        ${CONTROLBOX_CONFIG_DIR}/credentials.txt"
    echo -e "  Logs:                ${CB_LOG_FILE}"
    echo ""
    echo -e "  ${CB_BOLD}Comandos útiles:${CB_NC}"
    echo "    controlbox status"
    echo "    controlbox update"
    echo "    controlbox repair"
    echo "    controlbox backup"
    echo "    controlbox domains <dominio> <email>"
    echo ""
    if [[ -f "${CONTROLBOX_CONFIG_DIR}/domains.conf" ]]; then
        cb_load_env_file "${CONTROLBOX_CONFIG_DIR}/domains.conf"
        echo -e "  ${CB_BOLD}URLs por dominio:${CB_NC}"
        echo "    Panel:    https://${PANEL_DOMAIN:-panel.example.com}"
        echo "    API:      https://${API_DOMAIN:-api.example.com}"
        echo "    Grafana:  https://${GRAFANA_DOMAIN:-grafana.example.com}"
        echo "    MinIO:    https://${MINIO_DOMAIN:-minio.example.com}"
        echo "    Supabase: https://${SUPABASE_DOMAIN:-supabase.example.com}"
    fi
    echo ""
    cb_warn "Guarde estas credenciales. También están en ${CONTROLBOX_CONFIG_DIR}/credentials.txt"
    echo ""
    echo -e "  ${CB_BOLD}Siguiente paso:${CB_NC} Inicie sesión y complete Settings → Producción (secretos, TOTP, alertas)"
    cb_success "Instalación completada"
}

cb_run_installer() {
    source "${CONTROLBOX_INSTALLER_ROOT}/lib/common.sh"
    source "${CONTROLBOX_INSTALLER_ROOT}/lib/progress.sh"
    source "${CONTROLBOX_INSTALLER_ROOT}/lib/os.sh"
    source "${CONTROLBOX_INSTALLER_ROOT}/lib/resources.sh"
    source "${CONTROLBOX_INSTALLER_ROOT}/lib/docker.sh"
    source "${CONTROLBOX_INSTALLER_ROOT}/lib/firewall.sh"
    source "${CONTROLBOX_INSTALLER_ROOT}/lib/ssl.sh"
    source "${CONTROLBOX_INSTALLER_ROOT}/lib/domains.sh"
    source "${CONTROLBOX_INSTALLER_ROOT}/lib/setup.sh"
    source "${CONTROLBOX_INSTALLER_ROOT}/lib/tenant.sh"
    source "${CONTROLBOX_INSTALLER_ROOT}/lib/backup.sh"
    source "${CONTROLBOX_INSTALLER_ROOT}/lib/rollback.sh"
    source "${CONTROLBOX_INSTALLER_ROOT}/lib/config.sh"
    if [[ -f "${CONTROLBOX_INSTALLER_ROOT}/lib/reinstall.sh" ]]; then
        # shellcheck source=lib/reinstall.sh
        source "${CONTROLBOX_INSTALLER_ROOT}/lib/reinstall.sh"
    fi

    case "${1:-install}" in
        install) cb_main_install ;;
        --help|-h)
            echo "Uso: curl -fsSL https://install.grodtech.com/install.sh | bash"
            echo ""
            echo "Variables de entorno:"
            echo "  CONTROLBOX_PRIMARY_DOMAIN   Dominio principal"
            echo "  CONTROLBOX_ADMIN_EMAIL      Email para Let's Encrypt"
            echo "  CONTROLBOX_TENANT_NAME        Nombre de la organización"
            echo "  CONTROLBOX_TENANT_SLUG        Slug del tenant"
            echo "  CONTROLBOX_TENANT_ADMIN_EMAIL Email del administrador"
            echo "  CONTROLBOX_TENANT_ADMIN_PASSWORD Contraseña del administrador"
            echo "  CONTROLBOX_TENANT_ADMIN_FULL_NAME Nombre completo del administrador"
            echo "  CONTROLBOX_PANEL_PORT       Puerto del panel (ej. 8475)"
            echo "  CONTROLBOX_SERVER_IP        IP del VPS (auto-detecta LAN; evita ifconfig.me)"
            echo "  CONTROLBOX_ASSUME_YES=true  Sin confirmaciones interactivas"
            echo "  CONTROLBOX_FORCE_INSTALL    Omitir confirmaciones de recursos bajos"
            echo "  CONTROLBOX_REINSTALL=true   Reinstalar si ya existe"
            ;;
        *) cb_main_install ;;
    esac
}

if [[ "${CONTROLBOX_INSTALLER_ROOT}" == "" ]] || [[ ! -f "${CONTROLBOX_INSTALLER_ROOT}/lib/common.sh" ]]; then
    cb_bootstrap "$@"
else
    cb_run_installer "$@"
fi
