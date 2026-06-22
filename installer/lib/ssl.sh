#!/usr/bin/env bash

cb_ssl_fix_acme_permissions() {
    local le_dir="${CONTROLBOX_DATA_DIR:-/var/lib/controlbox}/letsencrypt"
    local acme_file="${le_dir}/acme.json"
    local cb_user="${CONTROLBOX_USER:-controlbox}"

    mkdir -p "${le_dir}"
    touch "${acme_file}"
    chmod 755 "${le_dir}"
    chmod 644 "${acme_file}"
    chown "${cb_user}:${cb_user}" "${le_dir}" "${acme_file}" 2>/dev/null || true
}

cb_ssl_configure() {
    cb_step "Configurando SSL/TLS"

    if cb_step_is_done "configure_ssl"; then
        cb_info "SSL ya configurado"
        return 0
    fi

    local primary_domain="${CONTROLBOX_PRIMARY_DOMAIN:-}"
    local admin_email="${CONTROLBOX_ADMIN_EMAIL:-}"

    if [[ -z "${primary_domain}" ]]; then
        cb_info "SSL omitido: acceso por IP/puerto del panel (configure dominio después con: controlbox domains set ...)"
        cb_step_done "configure_ssl"
        return 0
    fi

    if [[ -z "${admin_email}" ]]; then
        admin_email="admin@${primary_domain}"
        cb_warn "Email no definido, usando ${admin_email}"
    fi

    cb_save_install_state "PRIMARY_DOMAIN" "${primary_domain}"
    cb_save_install_state "ADMIN_EMAIL" "${admin_email}"

    local traefik_dynamic="${CONTROLBOX_CONFIG_DIR}/traefik/dynamic/tls.yml"
    mkdir -p "$(dirname "${traefik_dynamic}")"

    cat > "${traefik_dynamic}" <<EOF
tls:
  certificatesResolvers:
    letsencrypt:
      acme:
        email: ${admin_email}
        storage: /letsencrypt/acme.json
        httpChallenge:
          entryPoint: web
EOF

    local domains_file="${CONTROLBOX_CONFIG_DIR}/domains.conf"
    cat > "${domains_file}" <<EOF
PRIMARY_DOMAIN=${primary_domain}
ADMIN_EMAIL=${admin_email}
PANEL_DOMAIN=panel.${primary_domain}
API_DOMAIN=api.${primary_domain}
GRAFANA_DOMAIN=grafana.${primary_domain}
MINIO_DOMAIN=minio.${primary_domain}
SUPABASE_DOMAIN=supabase.${primary_domain}
EOF
    cb_secure_file "${domains_file}" 600

    cb_ssl_fix_acme_permissions

    cb_domains_apply_labels

    local compose_file="${CONTROLBOX_INSTALL_DIR}/docker-compose.yml"
    local env_file="${CONTROLBOX_CONFIG_DIR}/platform.env"
    cd "${CONTROLBOX_INSTALL_DIR}"
    docker compose --env-file "${env_file}" -f "${compose_file}" up -d traefik

    cb_step_done "configure_ssl"
    cb_success "SSL configurado para ${primary_domain} (Let's Encrypt via Traefik)"
}

cb_ssl_renew_check() {
    local acme_file="${CONTROLBOX_DATA_DIR}/letsencrypt/acme.json"
    if [[ -f "${acme_file}" ]] && [[ -s "${acme_file}" ]]; then
        cb_success "Certificados ACME presentes"
        return 0
    fi
    cb_warn "Certificados ACME aún no emitidos. Verifique DNS y reintente."
    return 1
}

cb_ssl_status() {
    local acme_file="${CONTROLBOX_DATA_DIR}/letsencrypt/acme.json"
    if [[ -f "${acme_file}" ]]; then
        local size
        size="$(wc -c < "${acme_file}")"
        echo "ACME storage: ${acme_file} (${size} bytes)"
        if [[ ${size} -gt 10 ]]; then
            cb_success "Certificados SSL activos"
        else
            cb_warn "Certificados SSL pendientes de emisión"
        fi
    else
        cb_warn "ACME storage no encontrado"
    fi
}
