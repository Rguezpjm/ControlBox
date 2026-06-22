#!/usr/bin/env bash

cb_firewall_configure() {
    cb_step "Configurando firewall"

    cb_setup_load_state 2>/dev/null || true

    if cb_step_is_done "configure_firewall"; then
        cb_info "Firewall ya configurado, verificando reglas"
        cb_firewall_verify
        return 0
    fi

    local ssh_port http_port https_port panel_port
    ssh_port="$(cb_sanitize_port "${CONTROLBOX_SSH_PORT:-}" "22")"
    http_port="$(cb_sanitize_port "${CONTROLBOX_HTTP_PORT:-}" "80")"
    https_port="$(cb_sanitize_port "${CONTROLBOX_HTTPS_PORT:-}" "443")"
    panel_port="$(cb_resolve_panel_port)"

    export CONTROLBOX_PANEL_PORT="${panel_port}"
    cb_info "Puertos firewall: SSH=${ssh_port} HTTP=${http_port} HTTPS=${https_port} Panel=${panel_port}"

    case "${CB_FIREWALL_TYPE}" in
        ufw)
            if ! command -v ufw >/dev/null 2>&1; then
                cb_os_install_packages ufw
            fi
            ufw --force disable 2>/dev/null || true
            ufw default deny incoming
            ufw default allow outgoing
            ufw allow "${ssh_port}/tcp" comment "SSH"
            ufw allow "${http_port}/tcp" comment "HTTP"
            ufw allow "${https_port}/tcp" comment "HTTPS"
            ufw allow "${panel_port}/tcp" comment "ControlBox Panel"
            ufw --force enable
            cb_success "UFW configurado"
            ;;
        firewalld)
            if ! systemctl is-active firewalld >/dev/null 2>&1; then
                systemctl enable --now firewalld
            fi
            firewall-cmd --permanent --add-service=ssh
            firewall-cmd --permanent --add-service=http
            firewall-cmd --permanent --add-service=https
            firewall-cmd --permanent --add-port="${http_port}/tcp"
            firewall-cmd --permanent --add-port="${https_port}/tcp"
            firewall-cmd --permanent --add-port="${panel_port}/tcp"
            firewall-cmd --reload
            cb_success "Firewalld configurado"
            ;;
        *)
            cb_warn "Tipo de firewall desconocido, omitiendo configuración automática"
            ;;
    esac

    cb_save_install_state "FIREWALL_CONFIGURED" "true"
    cb_save_install_state "PANEL_PORT" "${panel_port}"
    cb_step_done "configure_firewall"
}

cb_firewall_verify() {
    case "${CB_FIREWALL_TYPE}" in
        ufw)
            ufw status | head -20
            ;;
        firewalld)
            firewall-cmd --list-all
            ;;
    esac
}

cb_firewall_open_port() {
    local port
    port="$(cb_sanitize_port "${1:-}" "")"
    [[ -z "${port}" ]] && return 0
    local protocol="${2:-tcp}"
    case "${CB_FIREWALL_TYPE}" in
        ufw) ufw allow "${port}/${protocol}" ;;
        firewalld) firewall-cmd --permanent --add-port="${port}/${protocol}" && firewall-cmd --reload ;;
    esac
}
