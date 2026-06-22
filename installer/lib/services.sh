#!/usr/bin/env bash

# aaPanel-style optional service selection during install.
# Profiles map to docker-compose.platform.yml compose profiles.

cb_services_default_profiles() {
    echo "databases"
}

cb_services_parse_profiles() {
    local raw="${1:-}"
    raw="${raw// /}"
    if [[ -z "${raw}" ]]; then
        cb_services_default_profiles
        return 0
    fi
    echo "${raw}"
}

cb_services_profile_args() {
    local profiles
    profiles="$(cb_services_parse_profiles "${CONTROLBOX_ENABLED_PROFILES:-}")"
    local args=()
    local p
    IFS=',' read -ra parts <<< "${profiles}"
    for p in "${parts[@]}"; do
        [[ -z "${p}" ]] && continue
        args+=(--profile "${p}")
    done
    echo "${args[@]}"
}

cb_services_ask_yes_no() {
    local prompt="$1"
    local default="${2:-n}"
    local answer=""
    if [[ "${CONTROLBOX_ASSUME_YES:-}" == "true" ]]; then
        [[ "${default}" == "y" ]] && echo "y" || echo "n"
        return 0
    fi
    read -r -p "${prompt} [$( [[ "${default}" == "y" ]] && echo Y/n || echo y/N )]: " answer
    answer="${answer:-${default}}"
    case "${answer}" in
        y|Y|yes|Yes|s|S|si|Si) echo "y" ;;
        *) echo "n" ;;
    esac
}

cb_services_prompt() {
    cb_step "Paquetes de software recomendados"

    if cb_step_is_done "prompt_services" && [[ -n "${CONTROLBOX_ENABLED_PROFILES:-}" ]]; then
        cb_info "Selección de servicios ya guardada: ${CONTROLBOX_ENABLED_PROFILES}"
        return 0
    fi

    if [[ -n "${CONTROLBOX_ENABLED_PROFILES:-}" ]] && cb_is_noninteractive_install; then
        export CONTROLBOX_ENABLED_PROFILES="$(cb_services_parse_profiles "${CONTROLBOX_ENABLED_PROFILES}")"
        cb_services_persist_state
        cb_step_done "prompt_services"
        return 0
    fi

    echo ""
    echo -e "${CB_BOLD}Paquetes de software (estilo aaPanel)${CB_NC}"
    echo "Elija qué servicios instalar en este servidor. El panel core siempre se instala."
    echo "Desmarque servicios que no necesite para ahorrar RAM y CPU."
    echo ""

    local use_mysql="y"
    local use_monitoring="n"
    local use_backups="y"
    local use_supabase="n"
    local use_dns="n"
    local use_mail="n"
    local use_ftp="n"

    if [[ "${CONTROLBOX_ASSUME_YES:-}" != "true" ]]; then
        echo -e "${CB_BOLD}Stack web LNMP (recomendado)${CB_NC}"
        use_mysql="$(cb_services_ask_yes_no "  MySQL — bases de datos para Websites y WordPress" "y")"
        use_backups="$(cb_services_ask_yes_no "  MinIO — almacenamiento de backups" "y")"
        echo ""
        echo -e "${CB_BOLD}Observabilidad y plataforma${CB_NC}"
        use_monitoring="$(cb_services_ask_yes_no "  Monitoring — Prometheus, Grafana, Loki" "n")"
        use_supabase="$(cb_services_ask_yes_no "  Supabase — stack completo (requiere MinIO)" "n")"
        echo ""
        echo -e "${CB_BOLD}Servicios opcionales (registro para el panel)${CB_NC}"
        echo "  DNS, Mail y FTP se habilitan en el panel cuando estén desplegados."
        use_dns="$(cb_services_ask_yes_no "  DNS Server (PowerDNS)" "n")"
        use_mail="$(cb_services_ask_yes_no "  Mail Server" "n")"
        use_ftp="$(cb_services_ask_yes_no "  FTP (Pure-FTPd)" "n")"
    else
        use_mysql="y"
        use_backups="y"
    fi

    local profiles=()
    [[ "${use_mysql}" == "y" ]] && profiles+=("databases")
    [[ "${use_backups}" == "y" ]] && profiles+=("backups")
    [[ "${use_monitoring}" == "y" ]] && profiles+=("monitoring")
    if [[ "${use_supabase}" == "y" ]]; then
        profiles+=("supabase")
        if [[ "${use_backups}" != "y" ]]; then
            profiles+=("backups")
            cb_info "Supabase requiere MinIO — perfil backups activado"
        fi
    fi

    local joined=""
    local item
    for item in "${profiles[@]}"; do
        [[ -z "${joined}" ]] && joined="${item}" || joined="${joined},${item}"
    done
    export CONTROLBOX_ENABLED_PROFILES="${joined:-$(cb_services_default_profiles)}"

    export CONTROLBOX_FEATURE_DNS="$([[ "${use_dns}" == "y" ]] && echo true || echo false)"
    export CONTROLBOX_FEATURE_MAIL="$([[ "${use_mail}" == "y" ]] && echo true || echo false)"
    export CONTROLBOX_FEATURE_FTP="$([[ "${use_ftp}" == "y" ]] && echo true || echo false)"

    cb_services_persist_state
    cb_step_done "prompt_services"
    cb_success "Servicios seleccionados: ${CONTROLBOX_ENABLED_PROFILES}"
}

cb_services_load_state() {
    export CONTROLBOX_ENABLED_PROFILES="${CONTROLBOX_ENABLED_PROFILES:-$(cb_get_install_state ENABLED_PROFILES)}"
    export CONTROLBOX_ENABLED_PROFILES="$(cb_services_parse_profiles "${CONTROLBOX_ENABLED_PROFILES}")"
    export CONTROLBOX_FEATURE_DNS="${CONTROLBOX_FEATURE_DNS:-$(cb_get_install_state FEATURE_DNS)}"
    export CONTROLBOX_FEATURE_MAIL="${CONTROLBOX_FEATURE_MAIL:-$(cb_get_install_state FEATURE_MAIL)}"
    export CONTROLBOX_FEATURE_FTP="${CONTROLBOX_FEATURE_FTP:-$(cb_get_install_state FEATURE_FTP)}"
    [[ -z "${CONTROLBOX_FEATURE_DNS}" ]] && export CONTROLBOX_FEATURE_DNS="false"
    [[ -z "${CONTROLBOX_FEATURE_MAIL}" ]] && export CONTROLBOX_FEATURE_MAIL="false"
    [[ -z "${CONTROLBOX_FEATURE_FTP}" ]] && export CONTROLBOX_FEATURE_FTP="false"
}

cb_services_persist_state() {
    cb_save_install_state "ENABLED_PROFILES" "${CONTROLBOX_ENABLED_PROFILES}"
    cb_save_install_state "FEATURE_DNS" "${CONTROLBOX_FEATURE_DNS:-false}"
    cb_save_install_state "FEATURE_MAIL" "${CONTROLBOX_FEATURE_MAIL:-false}"
    cb_save_install_state "FEATURE_FTP" "${CONTROLBOX_FEATURE_FTP:-false}"

    local installer_env="${CONTROLBOX_CONFIG_DIR}/installer.env"
    if [[ -f "${installer_env}" ]]; then
        {
            cb_env_emit "CONTROLBOX_ENABLED_PROFILES" "${CONTROLBOX_ENABLED_PROFILES}"
            cb_env_emit "CONTROLBOX_FEATURE_DNS" "${CONTROLBOX_FEATURE_DNS:-false}"
            cb_env_emit "CONTROLBOX_FEATURE_MAIL" "${CONTROLBOX_FEATURE_MAIL:-false}"
            cb_env_emit "CONTROLBOX_FEATURE_FTP" "${CONTROLBOX_FEATURE_FTP:-false}"
        } >> "${installer_env}.services.tmp"
        grep -v '^CONTROLBOX_ENABLED_PROFILES=\|^CONTROLBOX_FEATURE_' "${installer_env}" > "${installer_env}.bak" 2>/dev/null || true
        cat "${installer_env}.bak" "${installer_env}.services.tmp" > "${installer_env}.new" 2>/dev/null || cat "${installer_env}.services.tmp" > "${installer_env}.new"
        mv "${installer_env}.new" "${installer_env}"
        rm -f "${installer_env}.services.tmp" "${installer_env}.bak"
        cb_secure_file "${installer_env}" 600
    fi
}

cb_services_load_from_platform_env() {
    local env_file="${CONTROLBOX_CONFIG_DIR}/platform.env"
    [[ -f "${env_file}" ]] || return 0
    if [[ -z "${CONTROLBOX_ENABLED_PROFILES:-}" ]]; then
        CONTROLBOX_ENABLED_PROFILES="$(grep '^CONTROLBOX_ENABLED_PROFILES=' "${env_file}" 2>/dev/null | tail -1 | cut -d'=' -f2- | tr -d '"'"'"'"' | tr -d "'")"
        export CONTROLBOX_ENABLED_PROFILES="$(cb_services_parse_profiles "${CONTROLBOX_ENABLED_PROFILES}")"
    fi
}
