#!/usr/bin/env bash

set -euo pipefail

CONTROLBOX_INSTALL_DIR="${CONTROLBOX_INSTALL_DIR:-/opt/controlbox}"
CONTROLBOX_CONFIG_DIR="${CONTROLBOX_CONFIG_DIR:-/etc/controlbox}"
CONTROLBOX_LOG_DIR="${CONTROLBOX_LOG_DIR:-/var/log/controlbox}"
CONTROLBOX_STATE_DIR="${CONTROLBOX_STATE_DIR:-/var/lib/controlbox/state}"

if [[ -f "${CONTROLBOX_INSTALL_DIR}/lib/common.sh" ]]; then
    CONTROLBOX_INSTALLER_ROOT="${CONTROLBOX_INSTALL_DIR}"
else
    CONTROLBOX_INSTALLER_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fi

source "${CONTROLBOX_INSTALLER_ROOT}/lib/common.sh"
source "${CONTROLBOX_INSTALLER_ROOT}/lib/os.sh"
source "${CONTROLBOX_INSTALLER_ROOT}/lib/docker.sh"
source "${CONTROLBOX_INSTALLER_ROOT}/lib/firewall.sh"
source "${CONTROLBOX_INSTALLER_ROOT}/lib/ssl.sh"
source "${CONTROLBOX_INSTALLER_ROOT}/lib/domains.sh"
source "${CONTROLBOX_INSTALLER_ROOT}/lib/backup.sh"
source "${CONTROLBOX_INSTALLER_ROOT}/lib/rollback.sh"
source "${CONTROLBOX_INSTALLER_ROOT}/lib/panel.sh"
source "${CONTROLBOX_INSTALLER_ROOT}/lib/setup.sh"
source "${CONTROLBOX_INSTALLER_ROOT}/lib/services.sh"
source "${CONTROLBOX_INSTALLER_ROOT}/lib/bootstrap-fixes.sh"

cb_init_logging
cb_load_config

cb_repair_status() {
    cb_banner
    cb_step "Estado del sistema ControlBox"

    echo -e "${CB_BOLD}Instalación:${CB_NC}"
    if [[ -f "${CONTROLBOX_STATE_DIR}/installed" ]]; then
        cb_success "ControlBox instalado ($(cat "${CONTROLBOX_STATE_DIR}/installed"))"
    else
        cb_warn "ControlBox no instalado o instalación incompleta"
    fi

    echo ""
    echo -e "${CB_BOLD}Recursos:${CB_NC}"
    echo "  CPU:   $(nproc) cores"
    echo "  RAM:   $(awk '/MemTotal/ {print int($2/1024)}' /proc/meminfo) MB"
    echo "  Disco: $(df -h ${CONTROLBOX_DATA_DIR:-/var/lib/controlbox} | awk 'NR==2 {print $4}') libre"

    echo ""
    echo -e "${CB_BOLD}Docker:${CB_NC}"
    if cb_docker_is_installed; then
        docker --version
        docker compose version
    else
        cb_error "Docker no disponible"
    fi

    echo ""
    echo -e "${CB_BOLD}Servicios:${CB_NC}"
    if [[ -f "${CONTROLBOX_INSTALL_DIR}/docker-compose.yml" ]]; then
        cb_docker_stack_status || true
    fi

    echo ""
    echo -e "${CB_BOLD}SSL:${CB_NC}"
    cb_ssl_status

    echo ""
    echo -e "${CB_BOLD}Firewall:${CB_NC}"
    CB_FIREWALL_TYPE="$(cb_get_install_state "FIREWALL_TYPE")"
    cb_firewall_verify 2>/dev/null || cb_warn "Firewall no verificado"

    echo ""
    echo -e "${CB_BOLD}Backups:${CB_NC}"
    cb_backup_list

    echo ""
    echo -e "${CB_BOLD}Logs recientes:${CB_NC}"
    tail -20 "${CB_LOG_FILE}" 2>/dev/null || cb_warn "Sin logs de instalador"
}

cb_repair_fix() {
    cb_require_root
    cb_acquire_lock
    cb_setup_traps

    cb_banner
    cb_step "Reparando ControlBox"

    cb_rollback_create_snapshot "pre-repair"

    if ! cb_docker_is_installed; then
        source "${CONTROLBOX_INSTALLER_ROOT}/lib/docker.sh"
        cb_docker_install
        cb_compose_install
    fi

    if [[ ! -f "${CONTROLBOX_CONFIG_DIR}/platform.env" ]]; then
        source "${CONTROLBOX_INSTALLER_ROOT}/lib/config.sh"
        cb_config_generate
    fi

    source "${CONTROLBOX_INSTALLER_ROOT}/lib/firewall.sh"
    cb_firewall_configure

    if [[ -f "${CONTROLBOX_INSTALL_DIR}/docker-compose.yml" ]]; then
        cb_compose_ensure_docker_proxy
        cb_fix_platform_env_permissions
        cb_compose_fix_api_letsencrypt_mount
        cb_platform_env_repair "${CONTROLBOX_CONFIG_DIR}/platform.env" 2>/dev/null || true
        cb_ssl_fix_acme_permissions 2>/dev/null || true
        cb_traefik_fix_letsencrypt 2>/dev/null || true
        cb_services_load_from_platform_env
        local -a profile_args=()
        # shellcheck disable=SC2206
        profile_args=($(cb_docker_compose_profile_args))
        cd "${CONTROLBOX_INSTALL_DIR}"
        docker compose --env-file "${CONTROLBOX_CONFIG_DIR}/platform.env" up -d docker-socket-proxy 2>/dev/null \
            || cb_warn "No se pudo iniciar docker-socket-proxy (revise docker-compose.yml)"
        cb_info "Iniciando stack con perfiles: ${CONTROLBOX_ENABLED_PROFILES:-databases,backups}"
        docker compose --env-file "${CONTROLBOX_CONFIG_DIR}/platform.env" "${profile_args[@]}" up -d --remove-orphans \
            || cb_die "No se pudo levantar el stack Docker"
        docker compose --env-file "${CONTROLBOX_CONFIG_DIR}/platform.env" "${profile_args[@]}" up -d --force-recreate api worker 2>/dev/null \
            || true

        cb_mysql_ensure_remote_root "${CONTROLBOX_CONFIG_DIR}/platform.env" || true
        cb_mssql_ensure_env_keys "${CONTROLBOX_CONFIG_DIR}/platform.env" || true
        cb_mssql_ensure_running "${CONTROLBOX_CONFIG_DIR}/platform.env" || true
        cb_supabase_ensure_running "${CONTROLBOX_CONFIG_DIR}/platform.env" || true
        cb_ftp_ensure_running "${CONTROLBOX_CONFIG_DIR}/platform.env" || true

        cb_info "Aplicando migraciones de base de datos..."
        docker compose --env-file "${CONTROLBOX_CONFIG_DIR}/platform.env" run --rm migrate 2>/dev/null \
            || docker compose --env-file "${CONTROLBOX_CONFIG_DIR}/platform.env" exec -T api alembic upgrade head 2>/dev/null \
            || cb_warn "No se pudieron ejecutar migraciones automáticamente"

        cb_info "Sincronizando rol Owner del administrador..."
        docker compose --env-file "${CONTROLBOX_CONFIG_DIR}/platform.env" exec -T api \
            python -m controlbox.installer.bootstrap_tenant 2>/dev/null \
            || cb_warn "No se pudo sincronizar el rol Owner (reinicie sesión tras controlbox reset-password)"

        local unhealthy
        unhealthy="$(docker compose --env-file "${CONTROLBOX_CONFIG_DIR}/platform.env" ps --format json 2>/dev/null | grep -c unhealthy || echo 0)"
        if [[ ${unhealthy} -gt 0 ]]; then
            cb_warn "Servicios unhealthy detectados, reiniciando..."
            docker compose --env-file "${CONTROLBOX_CONFIG_DIR}/platform.env" restart
        fi
    fi

    source "${CONTROLBOX_INSTALLER_ROOT}/lib/ssl.sh"
    cb_ssl_renew_check || cb_ssl_configure

    source "${CONTROLBOX_INSTALLER_ROOT}/lib/backup.sh"
    if ! [[ -f /etc/cron.d/controlbox-backup ]]; then
        cb_backup_configure
    fi

    cb_rollback_clear_active
    cb_success "Reparación completada"
    cb_docker_stack_status
}

cb_repair_rollback() {
    cb_require_root
    cb_step "Rollback manual"
    cb_rollback_list
    cb_confirm "¿Ejecutar rollback al último snapshot?" || exit 0
    cb_rollback_execute
}

case "${1:-}" in
    --status|status) cb_repair_status ;;
    --rollback) cb_repair_rollback ;;
    --apply-panel) cb_require_root; cb_panel_apply_config ;;
    --reset-panel-password)
        cb_require_root
        source "${CONTROLBOX_INSTALLER_ROOT}/lib/tenant.sh"
        cb_tenant_reset_admin_password
        ;;
    --help|-h)
        echo "Uso: repair.sh [--status|--rollback|--apply-panel|--reset-panel-password]"
        echo "  repair.sh                      Reparar servicios"
        echo "  repair.sh --status             Mostrar estado"
        echo "  repair.sh --rollback           Restaurar último snapshot"
        echo "  repair.sh --apply-panel        Aplicar puerto/ruta del panel"
        echo "  repair.sh --reset-panel-password  Sincronizar contraseña del panel con platform.env"
        ;;
    *) cb_repair_fix ;;
esac
