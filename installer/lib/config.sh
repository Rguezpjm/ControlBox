#!/usr/bin/env bash

cb_config_prepare_variables() {
    DASHBOARD_AUTH_USER="${DASHBOARD_AUTH_USER:-${TRAEFIK_DASHBOARD_USER:-admin}}"
    DASHBOARD_AUTH_PASSWORD="${DASHBOARD_AUTH_PASSWORD:-${TRAEFIK_DASHBOARD_PASSWORD:-}}"
    MINIO_ROOT_USER="${MINIO_ROOT_USER:-controlbox}"

    if [[ -z "${POSTGRES_PASSWORD:-}" ]]; then POSTGRES_PASSWORD="$(cb_generate_secret 32)"; fi
    if [[ -z "${REDIS_PASSWORD:-}" ]]; then REDIS_PASSWORD="$(cb_generate_secret 32)"; fi
    if [[ -z "${APP_SECRET_KEY:-}" ]]; then APP_SECRET_KEY="$(cb_generate_secret 64)"; fi
    if [[ -z "${MINIO_ROOT_PASSWORD:-}" ]]; then MINIO_ROOT_PASSWORD="$(cb_generate_secret 24)"; fi
    if [[ -z "${GRAFANA_ADMIN_PASSWORD:-}" ]]; then GRAFANA_ADMIN_PASSWORD="$(cb_generate_secret 16)"; fi
    if [[ -z "${SUPABASE_JWT_SECRET:-}" ]]; then SUPABASE_JWT_SECRET="$(cb_generate_secret 64)"; fi
    if [[ -z "${SUPABASE_ANON_KEY:-}" ]]; then SUPABASE_ANON_KEY="$(cb_generate_secret 32)"; fi
    if [[ -z "${SUPABASE_SERVICE_KEY:-}" ]]; then SUPABASE_SERVICE_KEY="$(cb_generate_secret 32)"; fi
    if [[ -z "${DASHBOARD_AUTH_PASSWORD:-}" ]]; then DASHBOARD_AUTH_PASSWORD="$(cb_generate_secret 16)"; fi
    if [[ -z "${INSTALLER_BOOTSTRAP_TOKEN:-}" ]]; then INSTALLER_BOOTSTRAP_TOKEN="$(cb_generate_secret 48)"; fi
    if [[ -z "${MYSQL_ADMIN_PASSWORD:-}" ]]; then MYSQL_ADMIN_PASSWORD="$(cb_generate_secret 24)"; fi

    POSTGRES_PASSWORD="$(cb_sanitize_env_secret "${POSTGRES_PASSWORD}" 128 32)"
    REDIS_PASSWORD="$(cb_sanitize_env_secret "${REDIS_PASSWORD}" 128 32)"
    APP_SECRET_KEY="$(cb_sanitize_env_secret "${APP_SECRET_KEY}" 256 64)"
    MINIO_ROOT_PASSWORD="$(cb_sanitize_env_secret "${MINIO_ROOT_PASSWORD}" 128 24)"
    GRAFANA_ADMIN_PASSWORD="$(cb_sanitize_env_secret "${GRAFANA_ADMIN_PASSWORD}" 128 16)"
    SUPABASE_JWT_SECRET="$(cb_sanitize_env_secret "${SUPABASE_JWT_SECRET}" 256 64)"
    SUPABASE_ANON_KEY="$(cb_sanitize_env_secret "${SUPABASE_ANON_KEY}" 128 32)"
    SUPABASE_SERVICE_KEY="$(cb_sanitize_env_secret "${SUPABASE_SERVICE_KEY}" 128 32)"
    DASHBOARD_AUTH_PASSWORD="$(cb_sanitize_env_secret "${DASHBOARD_AUTH_PASSWORD}" 128 16)"
    INSTALLER_BOOTSTRAP_TOKEN="$(cb_sanitize_env_secret "${INSTALLER_BOOTSTRAP_TOKEN}" 256 48)"
    MYSQL_ADMIN_PASSWORD="$(cb_sanitize_env_secret "${MYSQL_ADMIN_PASSWORD}" 128 24)"

    CONTROLBOX_TENANT_NAME="${CONTROLBOX_TENANT_NAME:-Mi Organización}"
    CONTROLBOX_TENANT_SLUG="${CONTROLBOX_TENANT_SLUG:-main}"
    CONTROLBOX_TENANT_ADMIN_EMAIL="${CONTROLBOX_TENANT_ADMIN_EMAIL:-admin@controlbox.local}"
    CONTROLBOX_TENANT_ADMIN_FULL_NAME="${CONTROLBOX_TENANT_ADMIN_FULL_NAME:-Administrador}"
    if [[ -z "${CONTROLBOX_TENANT_ADMIN_PASSWORD:-}" ]]; then
        CONTROLBOX_TENANT_ADMIN_PASSWORD="$(cb_generate_admin_password)"
    fi
    CONTROLBOX_TENANT_ADMIN_PASSWORD="$(cb_sanitize_admin_password "${CONTROLBOX_TENANT_ADMIN_PASSWORD}")"

    export DASHBOARD_AUTH_USER DASHBOARD_AUTH_PASSWORD MINIO_ROOT_USER
    export POSTGRES_PASSWORD REDIS_PASSWORD APP_SECRET_KEY MINIO_ROOT_PASSWORD
    export GRAFANA_ADMIN_PASSWORD SUPABASE_JWT_SECRET SUPABASE_ANON_KEY SUPABASE_SERVICE_KEY
    export INSTALLER_BOOTSTRAP_TOKEN
    export MYSQL_ADMIN_PASSWORD
    export CONTROLBOX_TENANT_NAME CONTROLBOX_TENANT_SLUG CONTROLBOX_TENANT_ADMIN_EMAIL
    export CONTROLBOX_TENANT_ADMIN_PASSWORD CONTROLBOX_TENANT_ADMIN_FULL_NAME
}

cb_config_generate() {
    cb_step "Generando configuración óptima"

    local host_install_dir="${CONTROLBOX_INSTALL_DIR:-/opt/controlbox}"
    local host_config_dir="${CONTROLBOX_CONFIG_DIR:-/etc/controlbox}"
    local host_data_dir="${CONTROLBOX_DATA_DIR:-/var/lib/controlbox}"
    local env_file="${host_config_dir}/platform.env"

    export CONTROLBOX_INSTALL_DIR="${host_install_dir}"
    export CONTROLBOX_CONFIG_DIR="${host_config_dir}"
    export CONTROLBOX_DATA_DIR="${host_data_dir}"

    mkdir -p "${host_install_dir}" "${host_config_dir}" "${host_data_dir}"

    if [[ -f "${env_file}" ]] && grep -qE 'CONTROLBOX_(INSTALL|CONFIG)_DIR="/host/' "${env_file}" 2>/dev/null; then
        cb_warn "platform.env corrupto (rutas /host). Regenerando..."
        rm -f "${env_file}"
        rm -f "${CB_STEPS_DIR}/generate_config.done"
    fi

    if [[ -f "${env_file}" ]] && grep -qE '^(source |#!/|cb_)' "${env_file}" 2>/dev/null; then
        cb_warn "platform.env corrupto (contenido inválido). Regenerando..."
        rm -f "${env_file}"
        rm -f "${CB_STEPS_DIR}/generate_config.done"
    fi

    if [[ -f "${env_file}" ]]; then
        local env_size
        env_size="$(wc -c < "${env_file}" 2>/dev/null || echo 0)"
        if [[ "${env_size}" -gt 524288 ]]; then
            cb_warn "platform.env demasiado grande (${env_size} bytes). Regenerando..."
            rm -f "${env_file}"
            rm -f "${CB_STEPS_DIR}/generate_config.done"
        fi
    fi

    if cb_step_is_done "generate_config" && [[ -f "${env_file}" ]] \
        && [[ "${CONTROLBOX_REINSTALL:-}" != "true" ]] \
        && ! cb_is_noninteractive_install; then
        cb_info "Configuración ya generada, omitiendo"
        cb_load_platform_env "${env_file}"
        return 0
    fi

    cb_resources_get_limits
    cb_setup_load_state

    if [[ ! -f "${env_file}" ]] && [[ -d "${host_data_dir}/postgres" ]]; then
        cb_warn "PostgreSQL existente con platform.env nuevo: reiniciando volumen de datos"
        cb_install_reset_database_volumes 2>/dev/null || rm -rf "${host_data_dir}/postgres" "${host_data_dir}/supabase/db"
    fi

    if [[ ! -f "${env_file}" ]]; then
        POSTGRES_PASSWORD="$(cb_generate_secret 32)"
        REDIS_PASSWORD="$(cb_generate_secret 32)"
        APP_SECRET_KEY="$(cb_generate_secret 64)"
        MINIO_ROOT_USER="controlbox"
        MINIO_ROOT_PASSWORD="$(cb_generate_secret 24)"
        GRAFANA_ADMIN_PASSWORD="$(cb_generate_secret 16)"
        SUPABASE_JWT_SECRET="$(cb_generate_secret 64)"
        SUPABASE_ANON_KEY="$(cb_generate_secret 32)"
        SUPABASE_SERVICE_KEY="$(cb_generate_secret 32)"
        DASHBOARD_AUTH_USER="admin"
        DASHBOARD_AUTH_PASSWORD="$(cb_generate_secret 16)"
    else
        cb_load_platform_env "${env_file}"
    fi

    cb_config_prepare_variables

    if declare -f cb_services_load_state >/dev/null 2>&1; then
        cb_services_load_state 2>/dev/null || true
    fi
    export CONTROLBOX_ENABLED_PROFILES="${CONTROLBOX_ENABLED_PROFILES:-databases,backups}"

    local server_ip
    server_ip="$(cb_setup_get_server_ip)"
    local panel_port
    panel_port="$(cb_sanitize_port "$(cb_resolve_panel_port)" "8475")"
    export CONTROLBOX_PANEL_PORT="${panel_port}"
    local panel_base_path
    panel_base_path="$(cb_setup_normalize_panel_base_path "${CONTROLBOX_PANEL_BASE_PATH:-}")"
    local os_label
    os_label="$(cb_setup_format_os_label)"
    local cors_origins webauthn_origin
    if cb_setup_is_ip_only_mode 2>/dev/null; then
        cors_origins="http://${server_ip}"
        webauthn_origin="http://${server_ip}"
        if [[ -n "${panel_base_path}" ]]; then
            cors_origins="http://${server_ip}/${panel_base_path}"
            webauthn_origin="http://${server_ip}/${panel_base_path}"
        fi
    else
        cors_origins="http://${server_ip}:${panel_port}"
        if [[ -n "${panel_base_path}" ]]; then
            cors_origins="http://${server_ip}:${panel_port}/${panel_base_path}"
        fi
        webauthn_origin="http://${server_ip}:${panel_port}"
        if [[ -n "${panel_base_path}" ]]; then
            webauthn_origin="http://${server_ip}:${panel_port}/${panel_base_path}"
        fi
    fi
    if [[ -n "${CONTROLBOX_PRIMARY_DOMAIN:-}" ]]; then
        cors_origins="${cors_origins},https://panel.${CONTROLBOX_PRIMARY_DOMAIN}"
    fi

    local cookie_secure="false"
    if [[ -n "${CONTROLBOX_PRIMARY_DOMAIN:-}" ]]; then
        cookie_secure="true"
    fi

    {
        cb_env_emit "CONTROLBOX_VERSION" "${CONTROLBOX_VERSION}"
        cb_env_emit "CONTROLBOX_GITHUB_REPO" "${CONTROLBOX_GITHUB_REPO:-Rguezpjm/ControlBox}"
        cb_env_emit "CONTROLBOX_INSTALL_URL" "${CONTROLBOX_INSTALL_URL:-https://install.grodtech.com}"
        cb_env_emit "CONTROLBOX_PROFILE" "${CB_PROFILE}"
        cb_env_emit "CONTROLBOX_OS_LABEL" "${os_label}"
        cb_env_emit "CONTROLBOX_INSTALL_DATE" "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
        cb_env_emit "CONTROLBOX_CONFIG_DIR" "${host_config_dir}"
        cb_env_emit "CONTROLBOX_DATA_DIR" "${host_data_dir}"
        cb_env_emit "CONTROLBOX_INSTALL_DIR" "${host_install_dir}"
        cb_env_emit "CONTROLBOX_INSTALLER_ROOT" "${host_install_dir}"
        cb_env_emit "TRAEFIK_VERSION" "${TRAEFIK_VERSION:-v3.2}"
        cb_env_emit "POSTGRES_VERSION" "${POSTGRES_VERSION:-16-alpine}"
        cb_env_emit "REDIS_VERSION" "${REDIS_VERSION:-7-alpine}"
        cb_env_emit "MINIO_VERSION" "${MINIO_VERSION:-RELEASE.2024-12-18T13-15-44Z}"
        cb_env_emit "PROMETHEUS_VERSION" "${PROMETHEUS_VERSION:-v2.55.1}"
        cb_env_emit "GRAFANA_VERSION" "${GRAFANA_VERSION:-11.4.0}"
        cb_env_emit "LOKI_VERSION" "${LOKI_VERSION:-3.3.2}"
        cb_env_emit "PROMTAIL_VERSION" "${PROMTAIL_VERSION:-3.3.2}"
        cb_env_emit "APP_NAME" "ControlBox"
        cb_env_emit "APP_ENV" "production"
        cb_env_emit "APP_DEBUG" "false"
        cb_env_emit "APP_SECRET_KEY" "${APP_SECRET_KEY}"
        cb_env_emit "APP_API_PREFIX" "/api/v1"
        cb_env_emit "POSTGRES_HOST" "postgres"
        cb_env_emit "POSTGRES_PORT" "5432"
        cb_env_emit "POSTGRES_DB" "controlbox"
        cb_env_emit "POSTGRES_USER" "controlbox"
        cb_env_emit "POSTGRES_PASSWORD" "${POSTGRES_PASSWORD}"
        cb_env_emit "POSTGRES_MAX_CONNECTIONS" "${POSTGRES_MAX_CONNECTIONS}"
        cb_env_emit "POSTGRES_SHARED_BUFFERS" "${POSTGRES_SHARED_BUFFERS}"
        cb_env_emit "POSTGRES_EFFECTIVE_CACHE" "${POSTGRES_EFFECTIVE_CACHE}"
        cb_env_emit "REDIS_HOST" "redis"
        cb_env_emit "REDIS_PORT" "6379"
        cb_env_emit "REDIS_PASSWORD" "${REDIS_PASSWORD}"
        cb_env_emit "REDIS_MAXMEMORY" "${REDIS_MAXMEMORY}"
        cb_env_emit "REDIS_DB" "0"
        cb_env_emit "JWT_ACCESS_TOKEN_EXPIRE_MINUTES" "15"
        cb_env_emit "JWT_REFRESH_TOKEN_EXPIRE_DAYS" "7"
        cb_env_emit "JWT_ALGORITHM" "HS256"
        cb_env_emit "MINIO_ROOT_USER" "${MINIO_ROOT_USER}"
        cb_env_emit "MINIO_ROOT_PASSWORD" "${MINIO_ROOT_PASSWORD}"
        cb_env_emit "MINIO_BUCKET" "controlbox"
        cb_env_emit "GRAFANA_ADMIN_USER" "admin"
        cb_env_emit "GRAFANA_ADMIN_PASSWORD" "${GRAFANA_ADMIN_PASSWORD}"
        cb_env_emit "SUPABASE_JWT_SECRET" "${SUPABASE_JWT_SECRET}"
        cb_env_emit "SUPABASE_ANON_KEY" "${SUPABASE_ANON_KEY}"
        cb_env_emit "SUPABASE_SERVICE_KEY" "${SUPABASE_SERVICE_KEY}"
        cb_env_emit "SUPABASE_DB_PASSWORD" "${POSTGRES_PASSWORD}"
        cb_env_emit "SUPABASE_DB_ADMIN_PASSWORD" "${POSTGRES_PASSWORD}"
        cb_env_emit "TRAEFIK_DASHBOARD_USER" "${DASHBOARD_AUTH_USER}"
        cb_env_emit "TRAEFIK_DASHBOARD_PASSWORD" "${DASHBOARD_AUTH_PASSWORD}"
        cb_env_emit "PROMETHEUS_RETENTION" "${PROMETHEUS_RETENTION}"
        cb_env_emit "LOKI_RETENTION" "${LOKI_RETENTION}"
        cb_env_emit "API_WORKERS" "${API_WORKERS}"
        cb_env_emit "UVICORN_WORKERS" "${API_WORKERS:-1}"
        cb_env_emit "BACKGROUND_TASKS_ENABLED" "true"
        cb_env_emit "MYSQL_HOST" "mysql"
        cb_env_emit "MYSQL_PORT" "3306"
        cb_env_emit "MYSQL_ADMIN_USER" "root"
        cb_env_emit "MYSQL_ADMIN_PASSWORD" "${MYSQL_ADMIN_PASSWORD}"
        cb_env_emit "SITES_BASE_PATH" "/var/lib/controlbox/sites"
        cb_env_emit "BACKUPS_BASE_PATH" "/var/lib/controlbox/backups"
        cb_env_emit "DATABASE_BACKUPS_PATH" "/var/lib/controlbox/backups/databases"
        cb_env_emit "CELERY_BROKER_URL" "redis://:${REDIS_PASSWORD}@redis:6379/1"
        cb_env_emit "CELERY_RESULT_BACKEND" "redis://:${REDIS_PASSWORD}@redis:6379/2"
        cb_env_emit "DOCKER_HOST" "tcp://docker-socket-proxy:2375"
        cb_env_emit "HOST_PROC" "/host/proc"
        cb_env_emit "HOST_ROOT" "/host/root"
        cb_env_emit "REGISTRATION_ENABLED" "false"
        cb_env_emit "INSTALLER_BOOTSTRAP_TOKEN" "${INSTALLER_BOOTSTRAP_TOKEN}"
        cb_env_emit "TENANT_NAME" "${CONTROLBOX_TENANT_NAME}"
        cb_env_emit "TENANT_SLUG" "${CONTROLBOX_TENANT_SLUG}"
        cb_env_emit "TENANT_ADMIN_EMAIL" "${CONTROLBOX_TENANT_ADMIN_EMAIL}"
        cb_env_emit "TENANT_ADMIN_PASSWORD" "${CONTROLBOX_TENANT_ADMIN_PASSWORD}"
        cb_env_emit "TENANT_ADMIN_FULL_NAME" "${CONTROLBOX_TENANT_ADMIN_FULL_NAME}"
        cb_env_emit "PANEL_PORT" "${panel_port}"
        cb_env_emit "PANEL_BASE_PATH" "${panel_base_path}"
        cb_env_emit "CONTROLBOX_SERVER_IP" "${server_ip}"
        cb_env_emit "INSTALLER_TENANT_NAME" "${CONTROLBOX_TENANT_NAME}"
        cb_env_emit "INSTALLER_TENANT_SLUG" "${CONTROLBOX_TENANT_SLUG}"
        cb_env_emit "INSTALLER_TENANT_ADMIN_EMAIL" "${CONTROLBOX_TENANT_ADMIN_EMAIL}"
        cb_env_emit "INSTALLER_TENANT_ADMIN_PASSWORD" "${CONTROLBOX_TENANT_ADMIN_PASSWORD}"
        cb_env_emit "INSTALLER_TENANT_ADMIN_FULL_NAME" "${CONTROLBOX_TENANT_ADMIN_FULL_NAME}"
        cb_env_emit "CORS_ORIGINS" "${cors_origins}"
        cb_env_emit "COOKIE_SECURE" "${cookie_secure}"
        cb_env_emit "WEBAUTHN_ORIGIN" "${webauthn_origin}"
        cb_env_emit "WEBAUTHN_RP_ID" "${CONTROLBOX_PRIMARY_DOMAIN:-${server_ip}}"
        cb_env_emit "CONTROLBOX_ENABLED_PROFILES" "${CONTROLBOX_ENABLED_PROFILES:-databases,backups}"
        cb_env_emit "CONTROLBOX_ENABLED_RUNTIMES" "${CONTROLBOX_ENABLED_RUNTIMES:-php:8.2,php:8.3,nodejs:22,python:3.13,flutter:3.44.2}"
        cb_env_emit "CONTROLBOX_FEATURE_DNS" "${CONTROLBOX_FEATURE_DNS:-false}"
        cb_env_emit "CONTROLBOX_FEATURE_MAIL" "${CONTROLBOX_FEATURE_MAIL:-false}"
        cb_env_emit "CONTROLBOX_FEATURE_FTP" "${CONTROLBOX_FEATURE_FTP:-false}"
        cb_env_emit "PUREFTPD_ENABLED" "${CONTROLBOX_FEATURE_FTP:-false}"
        cb_env_emit "PUREFTPD_HOST" "pureftpd"
        cb_env_emit "PUREFTPD_PORT" "21"
        cb_env_emit "PUREFTPD_PROTOCOL" "ftp"
        cb_env_emit "PUREFTPD_PUBLIC_HOST" "${CONTROLBOX_PRIMARY_DOMAIN:-${server_ip}}"
        cb_env_emit "PUREFTPD_PASSIVE_MIN" "30000"
        cb_env_emit "PUREFTPD_PASSIVE_MAX" "30009"
        cb_env_emit "PUREFTPD_TLS" "0"
        cb_env_emit "LOG_LEVEL" "INFO"
    } > "${env_file}"

    export CONTROLBOX_INSTALL_DIR="${host_install_dir}"
    export CONTROLBOX_CONFIG_DIR="${host_config_dir}"
    export CONTROLBOX_DATA_DIR="${host_data_dir}"

    cb_secure_file "${env_file}" 640
    cp -f "${env_file}" "${host_install_dir}/.env"
    cb_secure_file "${host_install_dir}/.env" 640

    cb_save_install_state "SERVER_IP" "${server_ip}"
    cb_config_deploy_templates
    if cb_setup_is_ip_only_mode 2>/dev/null && declare -f cb_panel_prepare_ip_access_files >/dev/null 2>&1; then
        cb_panel_prepare_ip_access_files
    fi
    cb_config_deploy_app_build_override 2>/dev/null || cb_config_deploy_panel_override
    cb_compose_repair_compose_ports 2>/dev/null || cb_compose_write_port_override "${panel_port}" 2>/dev/null || true
    cp -f "${env_file}" "${host_install_dir}/.env"
    cb_config_save_credentials
    cb_ssl_fix_acme_permissions 2>/dev/null || true

    cb_step_done "generate_config"
    cb_success "Configuración generada en ${env_file}"
}

cb_config_deploy_templates() {
    local templates_dir="${CONTROLBOX_INSTALLER_ROOT}/templates"
    local host_install_dir="${CONTROLBOX_INSTALL_DIR:-/opt/controlbox}"
    local host_config_dir="${CONTROLBOX_CONFIG_DIR:-/etc/controlbox}"

    cp -f "${templates_dir}/docker-compose.platform.yml" "${host_install_dir}/docker-compose.yml"

    cp -rf "${templates_dir}/traefik/"* "${host_config_dir}/traefik/" 2>/dev/null || true
    cp -rf "${templates_dir}/prometheus/"* "${host_config_dir}/prometheus/" 2>/dev/null || true
    cp -rf "${templates_dir}/grafana/"* "${host_config_dir}/grafana/" 2>/dev/null || true
    cp -rf "${templates_dir}/loki/"* "${host_config_dir}/loki/" 2>/dev/null || true
    cp -rf "${templates_dir}/promtail/"* "${host_config_dir}/promtail/" 2>/dev/null || true
    cp -rf "${templates_dir}/supabase/"* "${host_config_dir}/supabase/" 2>/dev/null || true

    chown -R controlbox:controlbox "${host_install_dir}" "${host_config_dir}" 2>/dev/null || true
}

cb_config_deploy_app_build_override() {
    local install_dir="${CONTROLBOX_INSTALL_DIR:-/opt/controlbox}"
    local version="${CONTROLBOX_VERSION:-4.11.7}"
    local panel_base="${CONTROLBOX_PANEL_BASE_PATH:-}"

    [[ -f "${install_dir}/src/backend/Dockerfile" ]] \
        && [[ -f "${install_dir}/src/frontend/Dockerfile" ]] || return 1

    cat > "${install_dir}/docker-compose.build.yml" <<EOF
services:
  api:
    build:
      context: ${install_dir}/src/backend
      dockerfile: Dockerfile
    image: controlbox-api:${version}
  panel:
    build:
      context: ${install_dir}/src/frontend
      dockerfile: Dockerfile
      args:
        NEXT_PUBLIC_BASE_PATH: ${panel_base}
        API_PROXY_URL: http://api:8000
    image: controlbox-panel:${version}
  migrate:
    image: controlbox-api:${version}
  bootstrap-tenant:
    image: controlbox-api:${version}
  worker:
    image: controlbox-api:${version}
EOF
    cb_info "Build local: API y Panel desde ${install_dir}/src/"
    return 0
}

cb_config_deploy_panel_override() {
    local frontend_dir="${CONTROLBOX_INSTALLER_ROOT}/../frontend"
    if [[ ! -f "${frontend_dir}/Dockerfile" ]]; then
        return 0
    fi

    cb_info "Frontend local detectado, configurando build del panel"
    local override_file="${CONTROLBOX_INSTALL_DIR}/docker-compose.panel-build.yml"
    cat > "${override_file}" <<EOF
services:
  panel:
    build:
      context: ${frontend_dir}
      dockerfile: Dockerfile
      args:
        NEXT_PUBLIC_BASE_PATH: ${CONTROLBOX_PANEL_BASE_PATH:-}
        API_PROXY_URL: http://api:8000
    image: controlbox-panel:local
EOF
}

cb_config_save_credentials() {
    local cred_file="${CONTROLBOX_CONFIG_DIR}/credentials.txt"
    local generated_at
    generated_at="$(cb_env_safe_date -u '+%Y-%m-%dT%H:%M:%SZ')"

    local postgres_user="${POSTGRES_USER:-controlbox}"
    local postgres_db="${POSTGRES_DB:-controlbox}"
    local grafana_user="${GRAFANA_ADMIN_USER:-admin}"
    local traefik_user="${TRAEFIK_DASHBOARD_USER:-${DASHBOARD_AUTH_USER:-admin}}"

    env -i PATH="/usr/bin:/bin:/usr/local/bin" HOME="${HOME:-/root}" \
        cat > "${cred_file}" <<EOF
ControlBox Platform Credentials
Generated: ${generated_at}
================================

PostgreSQL:
  User:     ${postgres_user}
  Password: ${POSTGRES_PASSWORD}
  Database: ${postgres_db}

Redis:
  Password: ${REDIS_PASSWORD}

MinIO:
  User:     ${MINIO_ROOT_USER}
  Password: ${MINIO_ROOT_PASSWORD}

Grafana:
  User:     ${grafana_user}
  Password: ${GRAFANA_ADMIN_PASSWORD}

Traefik Dashboard:
  User:     ${traefik_user}
  Password: ${DASHBOARD_AUTH_PASSWORD}

Supabase:
  JWT Secret:   ${SUPABASE_JWT_SECRET}
  Anon Key:     ${SUPABASE_ANON_KEY}
  Service Key:  ${SUPABASE_SERVICE_KEY}

App Secret Key: ${APP_SECRET_KEY}

MySQL (WordPress / managed databases):
  Host:     mysql
  Port:     3306
  User:     root
  Password: ${MYSQL_ADMIN_PASSWORD}

Panel Admin:
  Email:    ${CONTROLBOX_TENANT_ADMIN_EMAIL}
  Password: ${CONTROLBOX_TENANT_ADMIN_PASSWORD}
  Role:     Owner (full sysadmin)
EOF

    cb_secure_file "${cred_file}" 600
    cb_warn "Credenciales guardadas en ${cred_file} (permisos 600)"
}

cb_config_install_scripts() {
    cp -f "${CONTROLBOX_INSTALLER_ROOT}/update.sh" "${CONTROLBOX_INSTALL_DIR}/update.sh"
    cp -f "${CONTROLBOX_INSTALLER_ROOT}/repair.sh" "${CONTROLBOX_INSTALL_DIR}/repair.sh"
    cp -f "${CONTROLBOX_INSTALLER_ROOT}/uninstall.sh" "${CONTROLBOX_INSTALL_DIR}/uninstall.sh"
    cp -rf "${CONTROLBOX_INSTALLER_ROOT}/lib" "${CONTROLBOX_INSTALL_DIR}/"
    cp -rf "${CONTROLBOX_INSTALLER_ROOT}/config" "${CONTROLBOX_INSTALL_DIR}/"
    cp -rf "${CONTROLBOX_INSTALLER_ROOT}/templates" "${CONTROLBOX_INSTALL_DIR}/"
    if [[ -d "${CONTROLBOX_INSTALLER_ROOT}/src" ]]; then
        rm -rf "${CONTROLBOX_INSTALL_DIR}/src"
        cp -a "${CONTROLBOX_INSTALLER_ROOT}/src" "${CONTROLBOX_INSTALL_DIR}/"
        rm -f "${CONTROLBOX_INSTALL_DIR}/src/frontend/src/app/icon.png" 2>/dev/null || true
    fi
    chmod +x "${CONTROLBOX_INSTALL_DIR}/update.sh" "${CONTROLBOX_INSTALL_DIR}/repair.sh" "${CONTROLBOX_INSTALL_DIR}/uninstall.sh"
    chmod +x "${CONTROLBOX_INSTALLER_ROOT}/controlbox" 2>/dev/null || true

    install -m 0755 "${CONTROLBOX_INSTALLER_ROOT}/controlbox" /usr/local/bin/controlbox
    ln -sf /usr/local/bin/controlbox /usr/local/bin/cb
}
