#!/usr/bin/env bash

cb_ssl_fix_acme_permissions() {
    local le_dir="${CONTROLBOX_DATA_DIR:-/var/lib/controlbox}/letsencrypt"
    local acme_file="${le_dir}/acme.json"
    local cb_user="${CONTROLBOX_USER:-controlbox}"

    mkdir -p "${le_dir}"
    touch "${acme_file}"
    chmod 755 "${le_dir}"
    chmod 600 "${acme_file}"
    chown root:root "${le_dir}" "${acme_file}" 2>/dev/null || true
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

    local traefik_cfg="${CONTROLBOX_CONFIG_DIR}/traefik/traefik.yml"
    local traefik_dynamic="${CONTROLBOX_CONFIG_DIR}/traefik/dynamic/tls.yml"
    local middlewares_cfg="${CONTROLBOX_CONFIG_DIR}/traefik/dynamic/middlewares.yml"
    mkdir -p "$(dirname "${traefik_dynamic}")"

    if [[ -f "${traefik_cfg}" ]]; then
        sed -i "s/email: admin@localhost/email: ${admin_email}/" "${traefik_cfg}" 2>/dev/null || true
        sed -i '/redirections:/,/scheme: https/d' "${traefik_cfg}" 2>/dev/null || true
    fi

    if [[ -f "${CONTROLBOX_INSTALL_DIR}/templates/traefik/dynamic/middlewares.yml" ]] \
        && [[ ! -f "${middlewares_cfg}" || ! -s "${middlewares_cfg}" ]]; then
        cp -f "${CONTROLBOX_INSTALL_DIR}/templates/traefik/dynamic/middlewares.yml" "${middlewares_cfg}"
    fi

    cat > "${traefik_dynamic}" <<EOF
# Dynamic TLS options (certificates resolved via static traefik.yml ACME)
tls:
  options:
    default:
      minVersion: VersionTLS12
      sniStrict: true
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

cb_traefik_fix_letsencrypt() {
    local config_dir="${CONTROLBOX_CONFIG_DIR:-/etc/controlbox}"
    local install_dir="${CONTROLBOX_INSTALL_DIR:-/opt/controlbox}"
    local traefik_cfg="${config_dir}/traefik/traefik.yml"
    local middlewares_cfg="${config_dir}/traefik/dynamic/middlewares.yml"
    local template_mw="${install_dir}/templates/traefik/dynamic/middlewares.yml"
    local template_traefik="${install_dir}/templates/traefik/traefik.yml"
    local changed=0

    cb_ssl_fix_acme_permissions

    if [[ -f "${traefik_cfg}" ]]; then
        if grep -q 'redirections:' "${traefik_cfg}" 2>/dev/null; then
            sed -i '/redirections:/,/scheme: https/d' "${traefik_cfg}" 2>/dev/null || true
            cb_info "Traefik: eliminado redirect HTTP global (necesario para ACME HTTP-01)"
            changed=1
        fi
        if grep -q 'email: admin@localhost' "${traefik_cfg}" 2>/dev/null; then
            local admin_email="${CONTROLBOX_ADMIN_EMAIL:-}"
            if [[ -z "${admin_email}" && -f "${config_dir}/domains.conf" ]]; then
                cb_load_env_file "${config_dir}/domains.conf"
                admin_email="${ADMIN_EMAIL:-}"
            fi
            if [[ -n "${admin_email}" ]]; then
                sed -i "s/email: admin@localhost/email: ${admin_email}/" "${traefik_cfg}" 2>/dev/null || true
                cb_info "Traefik: email ACME actualizado a ${admin_email}"
                changed=1
            fi
        fi
    elif [[ -f "${template_traefik}" ]]; then
        mkdir -p "$(dirname "${traefik_cfg}")"
        cp -f "${template_traefik}" "${traefik_cfg}"
        cb_info "Traefik: traefik.yml restaurado desde plantilla"
        changed=1
    fi

    if [[ -f "${template_mw}" ]]; then
        if [[ ! -f "${middlewares_cfg}" ]] || ! grep -q 'https-redirect:' "${middlewares_cfg}" 2>/dev/null; then
            mkdir -p "$(dirname "${middlewares_cfg}")"
            cp -f "${template_mw}" "${middlewares_cfg}"
            cb_info "Traefik: middleware https-redirect instalado"
            changed=1
        fi
    fi

    local tls_dynamic="${config_dir}/traefik/dynamic/tls.yml"
    if [[ -f "${tls_dynamic}" ]] && grep -q 'certificates:' "${tls_dynamic}" 2>/dev/null; then
        cat > "${tls_dynamic}" <<'EOF'
# Dynamic TLS options (certificates resolved via static traefik.yml ACME)
tls:
  options:
    default:
      minVersion: VersionTLS12
      sniStrict: true
EOF
        cb_info "Traefik: tls.yml corregido (ACME no usa dynamic certificates)"
        changed=1
    fi

    if [[ -f "${config_dir}/domains.conf" ]] && declare -f cb_domains_apply_labels >/dev/null 2>&1; then
        cb_load_env_file "${config_dir}/domains.conf"
        cb_domains_apply_labels
        cb_info "Traefik: labels del panel/API regenerados con redirect por servicio"
        changed=1
    fi

    if [[ "${changed}" -eq 1 ]]; then
        local env_file="${config_dir}/platform.env"
        if [[ -f "${env_file}" ]] && declare -f cb_docker_compose_run >/dev/null 2>&1; then
            cb_docker_compose_run "${env_file}" up -d traefik 2>/dev/null \
                || docker compose --env-file "${env_file}" -f "${install_dir}/docker-compose.yml" up -d traefik 2>/dev/null \
                || true
            cb_success "Traefik reiniciado — Let's Encrypt debería emitir certificados en unos minutos"
        fi
    fi
}
