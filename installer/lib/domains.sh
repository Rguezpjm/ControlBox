#!/usr/bin/env bash

cb_domains_http_redirect_labels() {
    local service="$1"
    local router="$2"
    local domain="$3"
    local port="$4"
    cat <<EOF
      - "traefik.http.routers.${router}.rule=Host(\`${domain}\`)"
      - "traefik.http.routers.${router}.entrypoints=websecure"
      - "traefik.http.routers.${router}.tls=true"
      - "traefik.http.routers.${router}.tls.certresolver=letsencrypt"
      - "traefik.http.services.${router}.loadbalancer.server.port=${port}"
      - "traefik.http.routers.${router}-http.rule=Host(\`${domain}\`)"
      - "traefik.http.routers.${router}-http.entrypoints=web"
      - "traefik.http.routers.${router}-http.middlewares=https-redirect@file"
      - "traefik.http.routers.${router}-http.service=${router}"
EOF
}

cb_domains_apply_labels() {
    local domains_file="${CONTROLBOX_CONFIG_DIR}/domains.conf"
    if [[ ! -f "${domains_file}" ]]; then
        return 0
    fi
    cb_load_env_file "${domains_file}"

    local compose_override="${CONTROLBOX_INSTALL_DIR}/docker-compose.override.yml"
    cat > "${compose_override}" <<EOF
services:
  traefik:
    labels:
      - "traefik.enable=true"
  api:
    labels:
      - "traefik.enable=true"
$(cb_domains_http_redirect_labels api controlbox-api "${API_DOMAIN}" 8000)
  panel:
    labels:
      - "traefik.enable=true"
$(cb_domains_http_redirect_labels panel controlbox-panel "${PANEL_DOMAIN}" 3000)
  grafana:
    labels:
      - "traefik.enable=true"
$(cb_domains_http_redirect_labels grafana grafana "${GRAFANA_DOMAIN}" 3000)
  minio:
    labels:
      - "traefik.enable=true"
$(cb_domains_http_redirect_labels minio minio "${MINIO_DOMAIN}" 9001)
  supabase-kong:
    labels:
      - "traefik.enable=true"
$(cb_domains_http_redirect_labels supabase-kong supabase "${SUPABASE_DOMAIN}" 8000)
EOF
}

cb_domains_configure() {
    cb_step "Configurando dominios"

    local primary_domain="${CONTROLBOX_PRIMARY_DOMAIN:-}"
    local admin_email="${CONTROLBOX_ADMIN_EMAIL:-}"

    if [[ -z "${primary_domain}" ]]; then
        if [[ "${CONTROLBOX_ASSUME_YES:-}" != "true" ]]; then
            echo ""
            read -r -p "Dominio principal (ej: grodtech.com, Enter para omitir): " primary_domain
            if [[ -n "${primary_domain}" ]]; then
                read -r -p "Email para Let's Encrypt: " admin_email
            fi
        fi
    fi

    if [[ -z "${primary_domain}" ]]; then
        cb_info "Modo VPS/IP: panel en $(cb_setup_panel_url "$(cb_setup_get_server_ip)" "${CONTROLBOX_PANEL_PORT:-8475}" "${CONTROLBOX_PANEL_BASE_PATH:-}") (puerto 80)"
        if declare -f cb_panel_apply_ip_access >/dev/null 2>&1; then
            cb_panel_apply_ip_access || true
        fi
        cb_step_done "configure_domains"
        return 0
    fi

    export CONTROLBOX_PRIMARY_DOMAIN="${primary_domain}"
    export CONTROLBOX_ADMIN_EMAIL="${admin_email:-admin@${primary_domain}}"

    local domains_file="${CONTROLBOX_CONFIG_DIR}/domains.conf"
    cat > "${domains_file}" <<EOF
PRIMARY_DOMAIN=${CONTROLBOX_PRIMARY_DOMAIN}
ADMIN_EMAIL=${CONTROLBOX_ADMIN_EMAIL}
PANEL_DOMAIN=panel.${CONTROLBOX_PRIMARY_DOMAIN}
API_DOMAIN=api.${CONTROLBOX_PRIMARY_DOMAIN}
GRAFANA_DOMAIN=grafana.${CONTROLBOX_PRIMARY_DOMAIN}
MINIO_DOMAIN=minio.${CONTROLBOX_PRIMARY_DOMAIN}
SUPABASE_DOMAIN=supabase.${CONTROLBOX_PRIMARY_DOMAIN}
STUDIO_DOMAIN=studio.${CONTROLBOX_PRIMARY_DOMAIN}
EOF
    cb_secure_file "${domains_file}" 600

    cb_save_install_state "PRIMARY_DOMAIN" "${CONTROLBOX_PRIMARY_DOMAIN}"
    cb_save_install_state "PANEL_DOMAIN" "panel.${CONTROLBOX_PRIMARY_DOMAIN}"
    cb_save_install_state "API_DOMAIN" "api.${CONTROLBOX_PRIMARY_DOMAIN}"

    cb_domains_print_dns_records
    cb_domains_apply_labels

    cb_step_done "configure_domains"
    cb_success "Dominios configurados para ${CONTROLBOX_PRIMARY_DOMAIN}"
}

cb_domains_print_dns_records() {
    local server_ip
    server_ip="$(cb_setup_get_server_ip)"

    echo ""
    echo -e "${CB_BOLD}Registros DNS requeridos:${CB_NC}"
    echo "  Tipo   Nombre                              Valor"
    echo "  ----   --------------------------------    -----------------"
    echo "  A      ${CONTROLBOX_PRIMARY_DOMAIN}                       ${server_ip}"
    echo "  A      panel.${CONTROLBOX_PRIMARY_DOMAIN}                 ${server_ip}"
    echo "  A      api.${CONTROLBOX_PRIMARY_DOMAIN}                   ${server_ip}"
    echo "  A      grafana.${CONTROLBOX_PRIMARY_DOMAIN}               ${server_ip}"
    echo "  A      minio.${CONTROLBOX_PRIMARY_DOMAIN}                 ${server_ip}"
    echo "  A      supabase.${CONTROLBOX_PRIMARY_DOMAIN}              ${server_ip}"
    echo "  A      studio.${CONTROLBOX_PRIMARY_DOMAIN}                ${server_ip}"
    echo ""
}

cb_domains_set() {
    local domain="$1"
    local email="$2"
    export CONTROLBOX_PRIMARY_DOMAIN="${domain}"
    export CONTROLBOX_ADMIN_EMAIL="${email}"
    cb_domains_configure
    cb_ssl_configure
    local env_file="${CONTROLBOX_CONFIG_DIR}/platform.env"
    if declare -f cb_docker_compose_run >/dev/null 2>&1; then
        cb_docker_compose_run "${env_file}" up -d
    fi
}
