#!/usr/bin/env bash
# Parches críticos aplicados sobre paquetes antiguos del CDN (curl | bash).

cb_platform_port_read() {
    local env_file="${1:-${CONTROLBOX_CONFIG_DIR}/platform.env}"
    local port=""

    port="$(cb_sanitize_port "${CONTROLBOX_PANEL_PORT:-}" "")"
    if [[ -n "${port}" ]]; then
        echo "${port}"
        return 0
    fi

    if [[ -f "${env_file}" ]]; then
        port="$(grep '^PANEL_PORT=' "${env_file}" | tail -1 | cut -d'=' -f2- | tr -d '"'"'"'"' | tr -d "'")"
        port="$(cb_sanitize_port "${port}" "")"
        if [[ -n "${port}" ]]; then
            echo "${port}"
            return 0
        fi
    fi

    cb_resolve_panel_port
}

cb_compose_is_corrupt() {
    local compose_file="$1"
    [[ -f "${compose_file}" ]] || return 1

    if grep -qE '^(#!/|source |cb_)' "${compose_file}" 2>/dev/null; then
        return 0
    fi
    if grep -qE '\$\{CONTROLBOX_INSTALLER_ROOT\}' "${compose_file}" 2>/dev/null; then
        return 0
    fi
    if ! grep -q '^services:' "${compose_file}" 2>/dev/null; then
        return 0
    fi
    return 1
}

cb_compose_repair_compose_ports() {
    local install_dir="${CONTROLBOX_INSTALL_DIR:-/opt/controlbox}"
    local compose_file="${install_dir}/docker-compose.yml"
    local template_file="${install_dir}/templates/docker-compose.platform.yml"
    if [[ ! -f "${template_file}" ]] && [[ -n "${CONTROLBOX_INSTALLER_ROOT:-}" ]]; then
        template_file="${CONTROLBOX_INSTALLER_ROOT}/templates/docker-compose.platform.yml"
    fi
    local panel_port
    panel_port="$(cb_platform_port_read)"

    if cb_compose_is_corrupt "${compose_file}"; then
        cb_warn "docker-compose.yml corrupto (script o rutas de instalador), restaurando plantilla"
        rm -f "${compose_file}"
    fi

    if [[ ! -f "${compose_file}" ]] && [[ -f "${template_file}" ]]; then
        cp -f "${template_file}" "${compose_file}"
    fi

    if [[ -f "${compose_file}" ]]; then
        sed -i \
            -e '/PANEL_PORT/d' \
            -e '/^source /d' \
            -e '/^\s*- "\${PANEL_PORT/d' \
            -e '/^\s*- ${PANEL_PORT/d' \
            "${compose_file}" 2>/dev/null || true
    fi

    local build_file="${install_dir}/docker-compose.build.yml"
    if [[ -f "${build_file}" ]] && grep -q 'CONTROLBOX_INSTALLER_ROOT' "${build_file}" 2>/dev/null; then
        cb_warn "docker-compose.build.yml obsoleto, regenerando"
        rm -f "${build_file}"
    fi

    cb_compose_write_port_override "${panel_port}"
    cb_compose_fix_api_letsencrypt_mount
    cb_ssl_fix_acme_permissions 2>/dev/null || true
    if declare -f cb_traefik_fix_letsencrypt >/dev/null 2>&1; then
        cb_traefik_fix_letsencrypt 2>/dev/null || true
    fi
}

cb_compose_fix_api_letsencrypt_mount() {
    local install_dir="${CONTROLBOX_INSTALL_DIR:-/opt/controlbox}"
    local compose_file="${install_dir}/docker-compose.yml"
    local template_file="${install_dir}/templates/docker-compose.platform.yml"
    local entrypoint="${install_dir}/src/backend/docker-entrypoint.sh"
    local needs_api_rebuild=0

    for file in "${compose_file}" "${template_file}"; do
        [[ -f "${file}" ]] || continue
        if grep -q '/var/lib/controlbox/letsencrypt' "${file}" 2>/dev/null; then
            sed -i \
                's|${CONTROLBOX_DATA_DIR}/letsencrypt:/var/lib/controlbox/letsencrypt:ro|${CONTROLBOX_DATA_DIR}/letsencrypt:/etc/controlbox/letsencrypt:ro|g' \
                "${file}" 2>/dev/null || true
            cb_info "Montaje letsencrypt corregido en $(basename "${file}")"
        fi
    done

    if [[ -f "${entrypoint}" ]] && grep -q 'chown -R controlbox:controlbox /var/lib/controlbox' "${entrypoint}" 2>/dev/null; then
        cat > "${entrypoint}" << 'EOF'
#!/bin/sh
set -e

writable_dirs="/var/lib/controlbox/sites /var/lib/controlbox/backups /var/lib/controlbox/backups/databases"

for dir in $writable_dirs; do
  mkdir -p "$dir"
done

if [ "$(id -u)" = "0" ]; then
  for dir in $writable_dirs; do
    chown -R controlbox:controlbox "$dir" 2>/dev/null || true
  done
  if [ -d /var/log/pure-ftpd ]; then
    chown -R controlbox:controlbox /var/log/pure-ftpd 2>/dev/null || true
  fi
  exec gosu controlbox "$@"
fi

exec "$@"
EOF
        chmod +x "${entrypoint}"
        cb_info "docker-entrypoint.sh del API actualizado"
        needs_api_rebuild=1
    fi

    if [[ "${needs_api_rebuild}" -eq 1 ]]; then
        export CB_API_ENTRYPOINT_PATCHED=1
    fi
}

cb_fix_platform_env_permissions() {
    # El contenedor Docker usa UID/GID 1000 (hardcoded en Dockerfile).
    # El host puede tener el grupo controlbox con un GID distinto.
    # IMPORTANTE: groupmod solo cambia /etc/group; los inodos en disco conservan
    # el GID antiguo. Hay que rechownear los archivos DESPUÉS del groupmod.
    local config_dir="${CONTROLBOX_CONFIG_DIR:-/etc/controlbox}"
    local install_dir="${CONTROLBOX_INSTALL_DIR:-/opt/controlbox}"
    local target_gid=1000

    # 1. Ajustar GID del grupo controlbox al del contenedor (1000)
    if getent group controlbox >/dev/null 2>&1; then
        local current_gid
        current_gid="$(getent group controlbox | cut -d: -f3)"
        if [[ "${current_gid}" != "${target_gid}" ]]; then
            cb_info "Ajustando GID grupo controlbox: ${current_gid} → ${target_gid}..."
            if ! groupmod -g "${target_gid}" controlbox 2>/dev/null; then
                cb_info "No se pudo ajustar GID del grupo controlbox a ${target_gid}; continuando con permisos compatibles"
            fi
        fi
    fi

    # 2. Rechownear config dir y archivos clave con el GID actualizado
    #    (groupmod NO actualiza los inodos en disco; este paso es CRÍTICO)
    chown controlbox:controlbox "${config_dir}" 2>/dev/null || true
    chmod 775 "${config_dir}" 2>/dev/null || true

    for f in \
        "${config_dir}/platform.env" \
        "${config_dir}/credentials.env" \
        "${config_dir}/domains.json" \
        "${install_dir}/.env"; do
        if [[ -f "${f}" ]]; then
            chown controlbox:controlbox "${f}" 2>/dev/null || true
            chmod 640 "${f}" 2>/dev/null || true
        fi
    done

    # 3. Otros subdirectorios del config (traefik, ssl, etc.) — al menos accesibles
    find "${config_dir}" -maxdepth 1 -mindepth 1 -type d \
        -exec chown -R controlbox:controlbox {} \; 2>/dev/null || true

    # 4. State dir: install.state necesario para /health del contenedor
    local state_dir="${CONTROLBOX_STATE_DIR:-/var/lib/controlbox/state}"
    if [[ -d "${state_dir}" ]]; then
        chown controlbox:controlbox "${state_dir}" 2>/dev/null || true
        chmod 755 "${state_dir}" 2>/dev/null || true
        if [[ -f "${state_dir}/install.state" ]]; then
            chown controlbox:controlbox "${state_dir}/install.state" 2>/dev/null || true
            chmod 640 "${state_dir}/install.state" 2>/dev/null || true
        fi
    fi

    # 5. Overrides dinámicos del panel (FTP, etc.) en config dir — UID 1000 del contenedor API
    mkdir -p "${config_dir}/ftp" 2>/dev/null || true
    chown -R controlbox:controlbox "${config_dir}/ftp" 2>/dev/null || true
    chmod 750 "${config_dir}/ftp" 2>/dev/null || true

    local ftp_override="${config_dir}/docker-compose.ftp.yml"
    touch "${ftp_override}" 2>/dev/null || true
    chown controlbox:controlbox "${ftp_override}" 2>/dev/null || true
    chmod 664 "${ftp_override}" 2>/dev/null || true

    local legacy_ftp="${install_dir}/docker-compose.ftp.yml"
    if [[ -f "${legacy_ftp}" ]] && [[ ! -s "${ftp_override}" ]]; then
        cp -f "${legacy_ftp}" "${ftp_override}" 2>/dev/null || true
        chown controlbox:controlbox "${ftp_override}" 2>/dev/null || true
    fi

    cb_info "Permisos de configuración ajustados (GID=${target_gid}, archivos env=640)"
}

cb_compose_ensure_docker_proxy() {
    local install_dir="${CONTROLBOX_INSTALL_DIR:-/opt/controlbox}"
    local compose_file="${install_dir}/docker-compose.yml"
    local template_file="${install_dir}/templates/docker-compose.platform.yml"
    local env_file="${CONTROLBOX_CONFIG_DIR:-/etc/controlbox}/platform.env"

    if [[ ! -f "${template_file}" ]] && [[ -n "${CONTROLBOX_INSTALLER_ROOT:-}" ]]; then
        template_file="${CONTROLBOX_INSTALLER_ROOT}/templates/docker-compose.platform.yml"
    fi

    if [[ -f "${compose_file}" ]] && [[ -f "${template_file}" ]]; then
        if ! grep -q 'docker-socket-proxy' "${compose_file}" 2>/dev/null; then
            cb_warn "Actualizando docker-compose.yml para acceso Docker seguro (docker-socket-proxy)"
            cp -f "${template_file}" "${compose_file}"
            cb_compose_repair_compose_ports
        fi
    fi

    if [[ -f "${env_file}" ]] && ! grep -q '^DOCKER_HOST=' "${env_file}" 2>/dev/null; then
        echo "DOCKER_HOST=tcp://docker-socket-proxy:2375" >> "${env_file}"
        cb_info "DOCKER_HOST configurado en platform.env"
    fi

    if [[ -f "${env_file}" ]] && ! grep -q '^CONTROLBOX_ENABLED_RUNTIMES=' "${env_file}" 2>/dev/null; then
        echo "CONTROLBOX_ENABLED_RUNTIMES=php:8.2,php:8.3,nodejs:22,python:3.13,flutter:3.44.2" >> "${env_file}"
        cb_info "CONTROLBOX_ENABLED_RUNTIMES configurado en platform.env"
    fi

    if [[ -f "${compose_file}" ]] && ! grep -q '/certs:/certs' "${compose_file}" 2>/dev/null; then
        cb_warn "Actualizando docker-compose.yml para certificados SSL personalizados"
        cp -f "${template_file}" "${compose_file}"
        cb_compose_repair_compose_ports
    fi

    # Asegurar que el tmpfs de docker-socket-proxy incluya /run (necesario para haproxy.pid).
    # Si el compose existente no tiene /run en tmpfs, actualizamos desde el template.
    if [[ -f "${compose_file}" ]] && [[ -f "${template_file}" ]]; then
        if ! awk '
            /container_name: controlbox-docker-proxy/{proxy=1}
            proxy && /- \/run/{found=1; exit}
            /^  [a-z]/ && !/controlbox-docker-proxy/ && proxy{exit}
            END{exit (found ? 0 : 1)}
        ' "${compose_file}" 2>/dev/null; then
            cb_warn "Actualizando docker-compose.yml: falta /run en tmpfs de docker-socket-proxy (haproxy.pid)"
            cp -f "${template_file}" "${compose_file}"
            cb_compose_repair_compose_ports
        fi
    fi

    if [[ -f "${env_file}" ]] && grep -q '^REDIS_PASSWORD=' "${env_file}" 2>/dev/null; then
        local redis_pass
        redis_pass="$(cb_env_read_key "${env_file}" "REDIS_PASSWORD" 2>/dev/null || true)"
        if [[ -n "${redis_pass}" ]]; then
            local broker backend
            broker="$(cb_env_read_key "${env_file}" "CELERY_BROKER_URL" 2>/dev/null || true)"
            backend="$(cb_env_read_key "${env_file}" "CELERY_RESULT_BACKEND" 2>/dev/null || true)"
            if [[ "${broker}" != "redis://:${redis_pass}@redis:6379/1" ]] \
                || [[ "${backend}" != "redis://:${redis_pass}@redis:6379/2" ]]; then
                cb_warn "Actualizando CELERY_BROKER_URL con contraseña de Redis (comillas)"
                cb_env_patch_key "${env_file}" "CELERY_BROKER_URL" "redis://:${redis_pass}@redis:6379/1"
                cb_env_patch_key "${env_file}" "CELERY_RESULT_BACKEND" "redis://:${redis_pass}@redis:6379/2"
            fi
        fi
    fi

    cb_platform_env_repair "${env_file}" 2>/dev/null || true

    cb_compose_ensure_host_metrics
}

cb_compose_ensure_host_metrics() {
    local install_dir="${CONTROLBOX_INSTALL_DIR:-/opt/controlbox}"
    local compose_file="${install_dir}/docker-compose.yml"
    local template_file="${install_dir}/templates/docker-compose.platform.yml"
    local env_file="${CONTROLBOX_CONFIG_DIR:-/etc/controlbox}/platform.env"

    if [[ ! -f "${template_file}" ]] && [[ -n "${CONTROLBOX_INSTALLER_ROOT:-}" ]]; then
        template_file="${CONTROLBOX_INSTALLER_ROOT}/templates/docker-compose.platform.yml"
    fi

    if [[ -f "${compose_file}" ]] && [[ -f "${template_file}" ]]; then
        if ! grep -q '/host/proc' "${compose_file}" 2>/dev/null; then
            cb_warn "Actualizando docker-compose.yml para métricas del host (HOST_PROC)"
            cp -f "${template_file}" "${compose_file}"
            cb_compose_repair_compose_ports
        fi
    fi

    if [[ ! -f "${env_file}" ]]; then
        return 0
    fi

    if ! grep -q '^HOST_PROC=' "${env_file}" 2>/dev/null; then
        echo "HOST_PROC=/host/proc" >> "${env_file}"
        cb_info "HOST_PROC configurado en platform.env"
    fi
    if ! grep -q '^HOST_ROOT=' "${env_file}" 2>/dev/null; then
        echo "HOST_ROOT=/host/root" >> "${env_file}"
        cb_info "HOST_ROOT configurado en platform.env"
    fi

    if ! grep -q '^SUPABASE_DB_ADMIN_PASSWORD=' "${env_file}" 2>/dev/null; then
        local db_pass
        db_pass="$(grep '^SUPABASE_DB_PASSWORD=' "${env_file}" 2>/dev/null | tail -1 | cut -d'=' -f2- | tr -d '"'"'"'"' | tr -d "'")"
        if [[ -z "${db_pass}" ]]; then
            db_pass="$(grep '^POSTGRES_PASSWORD=' "${env_file}" 2>/dev/null | tail -1 | cut -d'=' -f2- | tr -d '"'"'"'"' | tr -d "'")"
        fi
        if [[ -n "${db_pass}" ]]; then
            echo "SUPABASE_DB_ADMIN_PASSWORD=${db_pass}" >> "${env_file}"
            cb_info "SUPABASE_DB_ADMIN_PASSWORD sincronizado en platform.env"
        fi
    fi
}

cb_app_source_available() {
    [[ -f "${CONTROLBOX_INSTALL_DIR:-/opt/controlbox}/src/backend/Dockerfile" ]] \
        && [[ -f "${CONTROLBOX_INSTALL_DIR}/src/frontend/Dockerfile" ]]
}

cb_docker_registry_login() {
    local token="${CONTROLBOX_GHCR_TOKEN:-${GITHUB_TOKEN:-}}"
    local user="${CONTROLBOX_GHCR_USER:-${GITHUB_USER:-grodtech}}"
    [[ -n "${token}" ]] || return 0
    cb_info "Autenticando en ghcr.io..."
    echo "${token}" | docker login ghcr.io -u "${user}" --password-stdin >/dev/null 2>&1 \
        || cb_warn "Login en ghcr.io falló (continuando...)"
}

cb_docker_registry_image_ok() {
    local image="$1"
    docker manifest inspect "${image}" >/dev/null 2>&1
}

cb_config_deploy_app_build_override() {
    local install_dir="${CONTROLBOX_INSTALL_DIR:-/opt/controlbox}"
    local version="${CONTROLBOX_VERSION:-4.11.9}"
    local panel_base="${CONTROLBOX_PANEL_BASE_PATH:-}"
    panel_base="$(cb_setup_normalize_panel_base_path "${panel_base}")"
    local panel_base_arg=""
    if [[ -n "${panel_base}" ]]; then
        panel_base_arg="/${panel_base}"
    fi

    cb_app_source_available || return 1

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
        NEXT_PUBLIC_BASE_PATH: ${panel_base_arg}
        API_PROXY_URL: http://api:8000
    image: controlbox-panel:${version}
  migrate:
    image: controlbox-api:${version}
  bootstrap-tenant:
    image: controlbox-api:${version}
EOF
    cb_info "Build local configurado (API + Panel desde src/)"
    return 0
}

cb_docker_compose_files() {
    local compose_file="${CONTROLBOX_INSTALL_DIR}/docker-compose.yml"
    local files=(-f "${compose_file}")
    if [[ -f "${CONTROLBOX_INSTALL_DIR}/docker-compose.ports.yml" ]]; then
        files+=(-f "${CONTROLBOX_INSTALL_DIR}/docker-compose.ports.yml")
    fi
    if [[ -f "${CONTROLBOX_INSTALL_DIR}/docker-compose.build.yml" ]]; then
        files+=(-f "${CONTROLBOX_INSTALL_DIR}/docker-compose.build.yml")
    fi
    if [[ -f "${CONTROLBOX_INSTALL_DIR}/docker-compose.override.yml" ]]; then
        files+=(-f "${CONTROLBOX_INSTALL_DIR}/docker-compose.override.yml")
    fi
    if [[ -f "${CONTROLBOX_INSTALL_DIR}/docker-compose.panel-build.yml" ]]; then
        files+=(-f "${CONTROLBOX_INSTALL_DIR}/docker-compose.panel-build.yml")
    fi
    echo "${files[@]}"
}

cb_compose_service_container_id() {
    local env_file="$1"
    local service="$2"
    cb_docker_compose_run "${env_file}" ps --status running -q "${service}" 2>/dev/null | head -1
}

cb_compose_service_is_running() {
    local env_file="$1"
    local service="$2"
    local cid
    cid="$(cb_compose_service_container_id "${env_file}" "${service}")"
    [[ -n "${cid}" ]]
}

cb_compose_service_is_healthy() {
    local env_file="$1"
    local service="$2"
    local cid health

    cid="$(cb_compose_service_container_id "${env_file}" "${service}")"
    [[ -n "${cid}" ]] || return 1

    health="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}healthy{{end}}' "${cid}" 2>/dev/null || echo unknown)"
    [[ "${health}" == "healthy" ]]
}

cb_docker_proxy_ready() {
    local env_file="$1"
    local cid="${2:-controlbox-docker-proxy}"

    if ! docker inspect "${cid}" >/dev/null 2>&1; then
        cid="$(cb_compose_service_container_id "${env_file}" "docker-socket-proxy")"
        [[ -n "${cid}" ]] || return 1
    fi

    if [[ "$(docker inspect --format '{{.State.Running}}' "${cid}" 2>/dev/null || echo false)" != "true" ]]; then
        return 1
    fi

    if cb_docker_compose_run "${env_file}" exec -T docker-socket-proxy \
        sh -c 'wget -qO- http://127.0.0.1:2375/_ping 2>/dev/null | grep -q OK || wget -q --spider http://127.0.0.1:2375/_ping >/dev/null 2>&1' \
        2>/dev/null; then
        return 0
    fi

    local health
    health="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "${cid}" 2>/dev/null || echo unknown)"
    [[ "${health}" == "healthy" || "${health}" == "none" ]]
}

cb_docker_diagnose_proxy() {
    local env_file="${1:-${CONTROLBOX_CONFIG_DIR}/platform.env}"
    cb_error "Diagnóstico docker-socket-proxy (últimas 40 líneas):"
    docker logs controlbox-docker-proxy --tail 40 2>&1 || true
    echo ""
    cb_error "Estado del contenedor:"
    docker inspect controlbox-docker-proxy \
        --format 'Status={{.State.Status}} Running={{.State.Running}} Health={{if .State.Health}}{{.State.Health.Status}}{{else}}n/a{{end}} ExitCode={{.State.ExitCode}} Error={{.State.Error}}' \
        2>/dev/null || true
    echo ""
    cb_docker_compose_run "${env_file}" ps -a docker-socket-proxy 2>&1 || true
}

cb_docker_compose_run() {
    local env_file="$1"
    shift
    local compose_args
    compose_args="$(cb_docker_compose_files)"
    local install_dir="${CONTROLBOX_INSTALL_DIR:-/opt/controlbox}"

    if [[ ! -f "${install_dir}/docker-compose.yml" ]]; then
        cb_die "docker-compose.yml no encontrado en ${install_dir}"
    fi

    cb_compose_repair_compose_ports 2>/dev/null || true
    if cb_app_source_available && [[ ! -f "${install_dir}/docker-compose.build.yml" ]]; then
        cb_config_deploy_app_build_override 2>/dev/null || true
    fi

    (
        cd "${install_dir}" || exit 1
        # shellcheck disable=SC2086
        env -i PATH="${PATH}" HOME="${HOME:-/root}" USER="${USER:-root}" \
            CONTROLBOX_INSTALLER_ROOT="${install_dir}" \
            docker compose --env-file "${env_file}" ${compose_args} "$@"
    )
}

cb_docker_compose_run_verbose() {
    local env_file="$1"
    shift
    local compose_args
    compose_args="$(cb_docker_compose_files)"
    local install_dir="${CONTROLBOX_INSTALL_DIR:-/opt/controlbox}"

    if [[ ! -f "${install_dir}/docker-compose.yml" ]]; then
        cb_die "docker-compose.yml no encontrado en ${install_dir}"
    fi

    cb_compose_repair_compose_ports 2>/dev/null || true
    if cb_app_source_available && [[ ! -f "${install_dir}/docker-compose.build.yml" ]]; then
        cb_config_deploy_app_build_override 2>/dev/null || true
    fi

    local -a cmd=(docker compose --env-file "${env_file}")
    # shellcheck disable=SC2206
    cmd+=(${compose_args})
    cmd+=("$@")

    (
        cd "${install_dir}" || exit 1
        env -i PATH="${PATH}" HOME="${HOME:-/root}" USER="${USER:-root}" \
            CONTROLBOX_INSTALLER_ROOT="${install_dir}" \
            "${cmd[@]}"
    )
}

cb_compose_write_port_override() {
    local panel_port
    panel_port="$(cb_sanitize_port "${1:-$(cb_platform_port_read)}" "8475")"
    local override_file="${CONTROLBOX_INSTALL_DIR}/docker-compose.ports.yml"

    cat > "${override_file}" <<EOF
services:
  panel:
    ports:
      - "0.0.0.0:${panel_port}:3000"
EOF
    cb_info "Puerto del panel en Docker: ${panel_port}"
}

cb_compose_validate_env_file() {
    local env_file="$1"
    [[ -f "${env_file}" ]] || cb_die "platform.env no encontrado: ${env_file}"

    if grep -qE '^(source |#!/|cb_)' "${env_file}" 2>/dev/null; then
        cb_warn "platform.env corrupto, será regenerado"
        rm -f "${env_file}"
        return 1
    fi

    if ! grep -q '^CONTROLBOX_INSTALLER_ROOT=' "${env_file}" 2>/dev/null; then
        echo "CONTROLBOX_INSTALLER_ROOT=${CONTROLBOX_INSTALL_DIR:-/opt/controlbox}" >> "${env_file}"
    fi

    local panel_port
    panel_port="$(cb_platform_port_read "${env_file}")"
    if [[ -z "${panel_port}" ]]; then
        cb_warn "PANEL_PORT inválido en platform.env"
        return 1
    fi
    return 0
}

cb_docker_pull_images() {
    cb_step "Descargando imágenes Docker"
    local env_file="${CONTROLBOX_CONFIG_DIR}/platform.env"
    local version="${CONTROLBOX_VERSION:-4.11.9}"
    local api_image="ghcr.io/grodtech/controlbox-api:${version}"

    if ! cb_compose_validate_env_file "${env_file}"; then
        cb_die "platform.env inválido. Ejecute de nuevo el instalador para regenerarlo."
    fi

    cb_compose_repair_compose_ports

    if cb_config_deploy_app_build_override 2>/dev/null || cb_app_source_available; then
        cb_info "Código fuente incluido: construyendo API y Panel en el servidor"
        cb_progress_note "Fase 1/2: descargando imágenes base (postgres, redis, traefik...)"
        local -a pull_services=(postgres redis traefik docker-socket-proxy)
        local profiles="${CONTROLBOX_ENABLED_PROFILES:-databases,backups}"
        [[ "${profiles}" == *databases* ]] && pull_services+=(mysql)
        [[ "${profiles}" == *backups* ]] && pull_services+=(minio)
        if [[ "${profiles}" == *supabase* ]]; then
            pull_services+=(
                supabase-db supabase-kong supabase-auth supabase-rest
                supabase-realtime supabase-storage supabase-meta supabase-studio
            )
        fi
        [[ "${profiles}" == *ftp* ]] && pull_services+=(pureftpd sftp)
        cb_docker_compose_run "${env_file}" pull "${pull_services[@]}" --progress=plain 2>/dev/null \
            || cb_docker_compose_run_verbose "${env_file}" pull "${pull_services[@]}" \
            || true
        rm -f "${CONTROLBOX_INSTALL_DIR}/src/frontend/src/app/icon.png" 2>/dev/null || true
        cb_progress_note "Fase 2/2: compilando API (backend Python)..."
        local api_build_args=(build --progress=plain api)
        if [[ "${CB_API_ENTRYPOINT_PATCHED:-}" == "1" ]]; then
            api_build_args=(build --no-cache --progress=plain api)
            cb_info "Recompilando API sin caché (entrypoint corregido)"
        fi
        cb_run_stream "Build Docker: API" \
            cb_docker_compose_run_verbose "${env_file}" "${api_build_args[@]}"
        cb_progress_note "Compilando Panel (frontend Next.js) — suele ser la fase más lenta..."
        local -a panel_build_args=(build --progress=plain panel)
        if [[ "${CONTROLBOX_REINSTALL:-}" == "true" ]]; then
            panel_build_args=(build --no-cache --progress=plain panel)
        fi
        cb_run_stream "Build Docker: Panel" \
            cb_docker_compose_run_verbose "${env_file}" "${panel_build_args[@]}"
        cb_success "Imágenes base descargadas y API/Panel construidos"
        return 0
    fi

    cb_docker_registry_login
    if ! cb_docker_registry_image_ok "${api_image}"; then
        echo ""
        cb_error "No se puede acceder a ${api_image} (denied / no existe)"
        cb_error "Soluciones:"
        cb_error "  • GitHub → Packages → controlbox-api → Change visibility → Public"
        cb_error "  • O: CONTROLBOX_GHCR_TOKEN=ghp_xxx curl -fsSL ... | bash"
        cb_error "  • O: suba un paquete instalador con src/ (build 20250621-11+)"
        cb_die "Imágenes Docker no disponibles en GHCR"
    fi

    cb_run_stream "Descargando imágenes Docker" \
        cb_docker_compose_run_verbose "${env_file}" pull --progress=plain
    cb_success "Imágenes descargadas"
}

cb_docker_diagnose_api() {
    cb_error "Diagnóstico controlbox-api (últimas 80 líneas):"
    docker logs controlbox-api --tail 80 2>&1 || true
    echo ""
    cb_error "Estado del contenedor:"
    docker inspect controlbox-api --format 'Status={{.State.Status}} Health={{if .State.Health}}{{.State.Health.Status}}{{else}}n/a{{end}} ExitCode={{.State.ExitCode}} OOMKilled={{.State.OOMKilled}}' 2>/dev/null || true
}

cb_wait_for_api() {
    local env_file="$1"
    local timeout="${2:-300}"
    local elapsed=0

    cb_info "Esperando servicio: api..."
    while [[ ${elapsed} -lt ${timeout} ]]; do
        local api_status
        api_status="$(docker inspect controlbox-api --format '{{.State.Status}}' 2>/dev/null || echo missing)"

        if [[ "${api_status}" == "exited" ]] || [[ "${api_status}" == "dead" ]]; then
            echo ""
            cb_error "controlbox-api detenido (status=${api_status})"
            cb_docker_diagnose_api
            return 1
        fi

        if cb_docker_compose_run "${env_file}" exec -T api curl -fsS http://localhost:8000/health >/dev/null 2>&1; then
            echo ""
            cb_success "Servicio api disponible (${elapsed}s)"
            return 0
        fi

        if (( elapsed > 0 && elapsed % 30 == 0 )); then
            echo ""
            cb_info "API aún iniciando (${elapsed}s) — log reciente:"
            docker logs controlbox-api --tail 6 2>&1 | sed 's/^/  /' || true
        fi

        printf "\r  ${CB_CYAN}Esperando api... %ds / %ds${CB_NC}" "${elapsed}" "${timeout}"
        sleep 5
        elapsed=$((elapsed + 5))
    done

    echo ""
    cb_error "Timeout esperando servicio: api"
    cb_docker_diagnose_api
    return 1
}

cb_docker_compose_profile_args() {
    local profiles="${CONTROLBOX_ENABLED_PROFILES:-}"
    if [[ -z "${profiles}" ]] && [[ -f "${CONTROLBOX_CONFIG_DIR}/platform.env" ]]; then
        profiles="$(grep '^CONTROLBOX_ENABLED_PROFILES=' "${CONTROLBOX_CONFIG_DIR}/platform.env" 2>/dev/null | tail -1 | cut -d'=' -f2- | tr -d '"'"'"'"' | tr -d "'")"
    fi
    profiles="${profiles:-databases,backups}"
    profiles="${profiles// /}"
    local args=()
    local p
    IFS=',' read -ra parts <<< "${profiles}"
    for p in "${parts[@]}"; do
        [[ -n "${p}" ]] && args+=(--profile "${p}")
    done
    echo "${args[@]}"
}

cb_docker_deploy_stack() {
    cb_step "Desplegando stack ControlBox"

    local env_file="${CONTROLBOX_CONFIG_DIR}/platform.env"

    if ! cb_compose_validate_env_file "${env_file}"; then
        cb_die "platform.env inválido"
    fi

    cb_compose_repair_compose_ports
    cb_compose_ensure_docker_proxy
    cb_fix_platform_env_permissions
    cb_platform_env_repair "${CONTROLBOX_CONFIG_DIR}/platform.env" 2>/dev/null || true
    cb_ssl_fix_acme_permissions 2>/dev/null || true
    if declare -f cb_traefik_fix_letsencrypt >/dev/null 2>&1; then
        cb_traefik_fix_letsencrypt 2>/dev/null || true
    fi
    cb_progress_note "Validando docker-compose.yml..."
    cb_docker_compose_run "${env_file}" config >/dev/null

    cb_progress_note "Fase 1/3: PostgreSQL y Redis..."
    cb_docker_compose_run "${env_file}" up -d postgres redis

    local pg_user="${POSTGRES_USER:-controlbox}"
    local redis_pass="${REDIS_PASSWORD:-}"

    if [[ -z "${redis_pass}" ]] && [[ -f "${env_file}" ]]; then
        redis_pass="$(grep '^REDIS_PASSWORD=' "${env_file}" | tail -1 | cut -d'=' -f2- | tr -d '"'"'"'"' | tr -d "'")"
    fi

    cb_wait_for_service "postgres" \
        "cb_docker_compose_run '${env_file}' exec -T postgres pg_isready -U ${pg_user}" 120

    cb_wait_for_service "redis" \
        "cb_docker_compose_run '${env_file}' exec -T redis redis-cli -a '${redis_pass}' ping 2>/dev/null | grep -q PONG" 60

    cb_progress_note "Fase 2/3: migraciones de base de datos..."
    if ! cb_run_stream "Ejecutando migraciones Alembic" \
        cb_docker_compose_run "${env_file}" --profile migrate run --rm migrate; then
        cb_error "Migración falló. Revise el SQL/traceback arriba (p. ej. palabra reservada, esquema corrupto)."
        cb_error "Si fue contraseña PostgreSQL: reinstalación limpia borra ${CONTROLBOX_DATA_DIR:-/var/lib/controlbox}/postgres"
        cb_docker_diagnose_api
        cb_die "Las migraciones de base de datos fallaron"
    fi

    cb_progress_note "Fase 3/4: proxy Docker y API..."
    if ! cb_run_stream "Iniciando docker-socket-proxy" \
        cb_docker_compose_run "${env_file}" up -d docker-socket-proxy; then
        cb_die "No se pudo iniciar docker-socket-proxy"
    fi

    cb_wait_for_service "docker-socket-proxy" \
        "cb_docker_proxy_ready '${env_file}'" 120 \
        "cb_docker_diagnose_proxy '${env_file}'"

    if ! cb_run_stream "Iniciando controlbox-api" \
        cb_docker_compose_run "${env_file}" up -d api; then
        cb_docker_diagnose_api
        cb_die "No se pudo iniciar controlbox-api"
    fi

    if ! cb_wait_for_api "${env_file}" 300; then
        cb_die "controlbox-api no responde en /health"
    fi

    cb_progress_note "Fase 4/4: Traefik, Panel y servicios seleccionados..."
    local -a profile_args=()
    # shellcheck disable=SC2206
    profile_args=($(cb_docker_compose_profile_args))
    if ! cb_run_stream "Iniciando resto de contenedores" \
        cb_docker_compose_run_verbose "${env_file}" "${profile_args[@]}" up -d --remove-orphans; then
        cb_docker_diagnose_api
        cb_die "Iniciando contenedores falló. Revise los logs arriba y ${CB_LOG_FILE}"
    fi

    cb_wait_for_service "traefik" \
        "cb_compose_service_is_healthy '${env_file}' traefik || cb_compose_service_is_running '${env_file}' traefik" 90

    cb_wait_for_service "panel" \
        "cb_compose_service_is_running '${env_file}' panel" 180

    cb_mysql_ensure_remote_root "${env_file}" || true
    cb_mssql_ensure_env_keys "${env_file}" || true
    cb_mssql_ensure_running "${env_file}" || true
    cb_supabase_ensure_running "${env_file}" || true
    cb_ftp_ensure_running "${env_file}" || true

    cb_step_done "deploy_stack"
    cb_success "Stack desplegado correctamente"
}

cb_mysql_ensure_remote_root() {
    local env_file="${1:-${CONTROLBOX_CONFIG_DIR}/platform.env}"
    [[ -f "${env_file}" ]] || return 0

    cb_platform_env_dedupe_keys "${env_file}" 2>/dev/null || true

    docker ps --format '{{.Names}}' 2>/dev/null | grep -qx 'controlbox-mysql' || return 0

    local mysql_data_dir
    mysql_data_dir="$(docker inspect -f '{{range .Mounts}}{{if eq .Destination "/var/lib/mysql"}}{{.Source}}{{end}}{{end}}' controlbox-mysql 2>/dev/null || true)"
    if [[ -z "${mysql_data_dir}" ]]; then
        mysql_data_dir="$(cb_env_read_key "${env_file}" "CONTROLBOX_DATA_DIR" 2>/dev/null || true)"
        mysql_data_dir="${mysql_data_dir:-${CONTROLBOX_DATA_DIR:-/var/lib/controlbox}}/mysql"
    fi
    mkdir -p "${mysql_data_dir}" 2>/dev/null || true
    chmod 755 "${mysql_data_dir}" 2>/dev/null || true

    local mysql_pass
    mysql_pass="$(cb_env_read_key "${env_file}" "MYSQL_ADMIN_PASSWORD" 2>/dev/null || true)"
    [[ -n "${mysql_pass}" ]] || return 0

    cb_info "Verificando acceso MySQL remoto (root@'%')..."

    local sql_pass="${mysql_pass//\'/\'\'}"
    local sql="
CREATE USER IF NOT EXISTS 'root'@'%' IDENTIFIED BY '${sql_pass}';
ALTER USER 'root'@'%' IDENTIFIED BY '${sql_pass}';
GRANT ALL PRIVILEGES ON *.* TO 'root'@'%' WITH GRANT OPTION;
CREATE USER IF NOT EXISTS 'root'@'localhost' IDENTIFIED BY '${sql_pass}';
ALTER USER 'root'@'localhost' IDENTIFIED BY '${sql_pass}';
GRANT ALL PRIVILEGES ON *.* TO 'root'@'localhost' WITH GRANT OPTION;
FLUSH PRIVILEGES;
"

    if MYSQL_PWD="${mysql_pass}" docker exec -e MYSQL_PWD controlbox-mysql \
        mysql -h 127.0.0.1 -uroot -e "${sql}" >/dev/null 2>&1; then
        cb_success "MySQL: root@'%' listo para el panel y WordPress"
        return 0
    fi

    cb_warn "MySQL rechazó root; resincronizando contraseña con platform.env..."
    if cb_mysql_resync_root_password "${env_file}"; then
        if MYSQL_PWD="${mysql_pass}" docker exec -e MYSQL_PWD controlbox-mysql \
            mysql -h127.0.0.1 -uroot -e "${sql}" >/dev/null 2>&1; then
            cb_success "MySQL: contraseña resincronizada y root@'%' listo"
            return 0
        fi
    fi

    cb_warn "No se pudo configurar root@'%' en MySQL (revise MYSQL_ADMIN_PASSWORD en platform.env)"
    return 1
}

cb_mysql_resync_root_password() {
    local env_file="${1:-${CONTROLBOX_CONFIG_DIR}/platform.env}"
    [[ -f "${env_file}" ]] || return 1

    docker ps -a --format '{{.Names}}' 2>/dev/null | grep -qx 'controlbox-mysql' || return 1

    local mysql_pass data_dir
    mysql_pass="$(cb_env_read_key "${env_file}" "MYSQL_ADMIN_PASSWORD" 2>/dev/null || true)"
    [[ -n "${mysql_pass}" ]] || return 1

    data_dir="$(docker inspect -f '{{range .Mounts}}{{if eq .Destination "/var/lib/mysql"}}{{.Source}}{{end}}{{end}}' controlbox-mysql 2>/dev/null || true)"
    if [[ -z "${data_dir}" ]]; then
        data_dir="$(cb_env_read_key "${env_file}" "CONTROLBOX_DATA_DIR" 2>/dev/null || true)"
        data_dir="${data_dir:-${CONTROLBOX_DATA_DIR:-/var/lib/controlbox}}"
        data_dir="${data_dir}/mysql"
    fi
    mkdir -p "${data_dir}" 2>/dev/null || true
    chmod 755 "${data_dir}" 2>/dev/null || true

    local sql_pass="${mysql_pass//\'/\'\'}"
    local mysql_image="mysql:8.4"

    cb_warn "Resincronizando contraseña root de MySQL (volumen ${data_dir})..."

    docker stop controlbox-mysql >/dev/null 2>&1 || true

    if ! docker run --rm \
        -v "${data_dir}:/var/lib/mysql:rw" \
        --entrypoint bash \
        "${mysql_image}" \
        -c "
set -e
mysqld --user=mysql --skip-grant-tables --skip-networking &
pid=\$!
ready=0
for i in \$(seq 1 90); do
  if mysqladmin ping --silent 2>/dev/null; then
    ready=1
    break
  fi
  sleep 1
done
if [ \"\$ready\" != \"1\" ]; then
  echo 'MySQL no arrancó en modo skip-grant-tables' >&2
  exit 1
fi
mysql -uroot --protocol=socket <<EOSQL
FLUSH PRIVILEGES;
ALTER USER 'root'@'localhost' IDENTIFIED BY '${sql_pass}';
GRANT ALL PRIVILEGES ON *.* TO 'root'@'localhost' WITH GRANT OPTION;
CREATE USER IF NOT EXISTS 'root'@'%' IDENTIFIED BY '${sql_pass}';
ALTER USER 'root'@'%' IDENTIFIED BY '${sql_pass}';
CREATE USER IF NOT EXISTS 'root'@'127.0.0.1' IDENTIFIED BY '${sql_pass}';
ALTER USER 'root'@'127.0.0.1' IDENTIFIED BY '${sql_pass}';
GRANT ALL PRIVILEGES ON *.* TO 'root'@'127.0.0.1' WITH GRANT OPTION;
GRANT ALL PRIVILEGES ON *.* TO 'root'@'%' WITH GRANT OPTION;
FLUSH PRIVILEGES;
EOSQL
kill \"\$pid\" 2>/dev/null || true
wait \"\$pid\" 2>/dev/null || true
"; then
        cb_error "No se pudo resincronizar la contraseña root de MySQL"
        docker start controlbox-mysql >/dev/null 2>&1 || true
        return 1
    fi

    docker start controlbox-mysql >/dev/null 2>&1 || true

    local i
    for i in $(seq 1 45); do
        if docker exec controlbox-mysql mysqladmin ping -h127.0.0.1 --silent >/dev/null 2>&1; then
            cb_success "MySQL: contraseña root alineada con platform.env"
            return 0
        fi
        sleep 2
    done

    cb_error "MySQL no respondió tras resincronizar la contraseña root"
    return 1
}

cb_mssql_ensure_env_keys() {
    local env_file="${1:-${CONTROLBOX_CONFIG_DIR}/platform.env}"
    [[ -f "${env_file}" ]] || return 0

    if ! grep -q '^MSSQL_ADMIN_PASSWORD=' "${env_file}" 2>/dev/null; then
        local mssql_pass="Cb$(cb_generate_secret 16)!9"
        cb_env_patch_key "${env_file}" "MSSQL_ADMIN_PASSWORD" "${mssql_pass}"
        cb_info "MSSQL_ADMIN_PASSWORD generado en platform.env"
    fi
    grep -q '^MSSQL_HOST=' "${env_file}" 2>/dev/null \
        || echo "MSSQL_HOST=mssql" >> "${env_file}"
    grep -q '^MSSQL_PORT=' "${env_file}" 2>/dev/null \
        || echo "MSSQL_PORT=1433" >> "${env_file}"
    grep -q '^MSSQL_ADMIN_USER=' "${env_file}" 2>/dev/null \
        || echo "MSSQL_ADMIN_USER=sa" >> "${env_file}"
}

cb_mssql_ensure_running() {
    local env_file="${1:-${CONTROLBOX_CONFIG_DIR}/platform.env}"
    [[ -f "${env_file}" ]] || return 0

    local profiles
    profiles="$(grep '^CONTROLBOX_ENABLED_PROFILES=' "${env_file}" 2>/dev/null | tail -1 | cut -d'=' -f2- | tr -d '"'"'"'"' | tr -d "'")"
    profiles="${profiles:-databases,backups}"
    [[ ",${profiles}," == *",databases,"* ]] || return 0

    if ! grep -q '^  mssql:' "${CONTROLBOX_INSTALL_DIR}/docker-compose.yml" 2>/dev/null; then
        cb_warn "SQL Server no está en docker-compose.yml. Ejecute: controlbox update"
        return 1
    fi

    cb_mssql_ensure_env_keys "${env_file}"

    local mssql_pass
    mssql_pass="$(cb_env_read_key "${env_file}" "MSSQL_ADMIN_PASSWORD" 2>/dev/null || true)"
    [[ -n "${mssql_pass}" ]] || return 1

    if docker ps --format '{{.Names}}' 2>/dev/null | grep -qx 'controlbox-mssql'; then
        if docker exec controlbox-mssql \
            /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P "${mssql_pass}" -C -Q "SELECT 1" >/dev/null 2>&1; then
            cb_success "SQL Server: servicio en ejecución"
            return 0
        fi
    fi

    local data_dir="${CONTROLBOX_DATA_DIR:-/var/lib/controlbox}/mssql"
    mkdir -p "${data_dir}" 2>/dev/null || true
    # SQL Server runs as the non-root "mssql" user (UID 10001); the data dir must be owned by it
    chown -R 10001:0 "${data_dir}" 2>/dev/null || true
    chmod -R 770 "${data_dir}" 2>/dev/null || true

    cb_info "Iniciando SQL Server (Microsoft SQL)..."
    cd "${CONTROLBOX_INSTALL_DIR:-/opt/controlbox}"
    local -a compose_args=(--env-file "${env_file}" -f docker-compose.yml --profile databases)
    [[ -f docker-compose.override.yml ]] && compose_args+=(-f docker-compose.override.yml)
    [[ -f docker-compose.ports.yml ]] && compose_args+=(-f docker-compose.ports.yml)
    [[ -f docker-compose.build.yml ]] && compose_args+=(-f docker-compose.build.yml)
    [[ -f "${CONTROLBOX_CONFIG_DIR}/docker-compose.ftp.yml" ]] && compose_args+=(-f "${CONTROLBOX_CONFIG_DIR}/docker-compose.ftp.yml")

    # If a crash-looping container already exists, recreate it so the permission fix takes effect
    if docker ps -a --format '{{.Names}}' 2>/dev/null | grep -qx 'controlbox-mssql'; then
        docker compose "${compose_args[@]}" up -d --force-recreate --remove-orphans mssql 2>/dev/null \
            || cb_warn "No se pudo recrear SQL Server automáticamente"
    else
        docker compose "${compose_args[@]}" up -d --remove-orphans mssql 2>/dev/null \
            || cb_warn "No se pudo levantar SQL Server automáticamente"
    fi

    local i
    for i in $(seq 1 60); do
        if docker exec controlbox-mssql \
            /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P "${mssql_pass}" -C -Q "SELECT 1" >/dev/null 2>&1; then
            cb_success "SQL Server: servicio en ejecución"
            return 0
        fi
        sleep 3
    done

    cb_warn "SQL Server no respondió a tiempo. Revise: docker logs controlbox-mssql"
    return 1
}

cb_supabase_ensure_running() {
    local env_file="${1:-${CONTROLBOX_CONFIG_DIR}/platform.env}"
    [[ -f "${env_file}" ]] || return 0

    local profiles
    profiles="$(grep '^CONTROLBOX_ENABLED_PROFILES=' "${env_file}" 2>/dev/null | tail -1 | cut -d'=' -f2- | tr -d '"'"'"'"' | tr -d "'")"
    [[ "${profiles}" == *supabase* ]] || return 0

    local install_dir="${CONTROLBOX_INSTALL_DIR:-/opt/controlbox}"
    local config_dir="${CONTROLBOX_CONFIG_DIR:-/etc/controlbox}"
    local data_dir="${CONTROLBOX_DATA_DIR:-/var/lib/controlbox}"
    local templates_dir="${install_dir}/templates/supabase"

    if [[ ! -f "${config_dir}/supabase/kong.yml" ]] && [[ -d "${templates_dir}" ]]; then
        mkdir -p "${config_dir}/supabase"
        cp -f "${templates_dir}/"* "${config_dir}/supabase/" 2>/dev/null || true
        cb_info "Plantillas Supabase copiadas a ${config_dir}/supabase"
    fi

    mkdir -p "${data_dir}/supabase/db"
    chmod 777 "${data_dir}/supabase/db" 2>/dev/null || true

    if ! docker ps --format '{{.Names}}' 2>/dev/null | grep -qx 'controlbox-supabase-db'; then
        cb_info "Iniciando stack Supabase (requiere MinIO/backups)..."
        cd "${install_dir}"
        docker compose --env-file "${env_file}" \
            --profile databases --profile backups --profile supabase \
            up -d --remove-orphans \
            minio supabase-db supabase-meta supabase-kong supabase-auth \
            supabase-rest supabase-realtime supabase-storage supabase-studio \
            2>/dev/null || cb_warn "No se pudo levantar Supabase automáticamente"
    fi

    local attempt=0
    while [[ ${attempt} -lt 36 ]]; do
        if docker ps --format '{{.Names}}' 2>/dev/null | grep -qx 'controlbox-supabase-db'; then
            cb_success "Supabase: supabase-db en ejecución"
            return 0
        fi
        attempt=$((attempt + 1))
        sleep 5
    done

    cb_warn "Supabase no arrancó. Revise: docker logs controlbox-supabase-db"
    return 1
}

cb_ftp_ensure_running() {
    local env_file="${1:-${CONTROLBOX_CONFIG_DIR}/platform.env}"
    [[ -f "${env_file}" ]] || return 0

    local enabled profiles protocol port passive_min passive_max install_dir
    enabled="$(grep '^PUREFTPD_ENABLED=' "${env_file}" 2>/dev/null | tail -1 | cut -d'=' -f2- | tr -d '"'"'"'"' | tr -d "'")"
    [[ "${enabled}" == "true" ]] || return 0

    profiles="$(grep '^CONTROLBOX_ENABLED_PROFILES=' "${env_file}" 2>/dev/null | tail -1 | cut -d'=' -f2- | tr -d '"'"'"'"' | tr -d "'")"
    if [[ "${profiles}" != *ftp* ]]; then
        profiles="${profiles},ftp"
        profiles="${profiles#,}"
        cb_info "Añadiendo perfil ftp a CONTROLBOX_ENABLED_PROFILES"
        if grep -q '^CONTROLBOX_ENABLED_PROFILES=' "${env_file}"; then
            sed -i "s|^CONTROLBOX_ENABLED_PROFILES=.*|CONTROLBOX_ENABLED_PROFILES=${profiles}|" "${env_file}"
        else
            echo "CONTROLBOX_ENABLED_PROFILES=${profiles}" >> "${env_file}"
        fi
    fi

    install_dir="${CONTROLBOX_INSTALL_DIR:-/opt/controlbox}"
    local config_dir="${CONTROLBOX_CONFIG_DIR:-/etc/controlbox}"
    protocol="$(grep '^PUREFTPD_PROTOCOL=' "${env_file}" 2>/dev/null | tail -1 | cut -d'=' -f2- | tr -d '"'"'"'"' | tr -d "'")"
    protocol="${protocol:-ftp}"
    port="$(grep '^PUREFTPD_PORT=' "${env_file}" 2>/dev/null | tail -1 | cut -d'=' -f2- | tr -d '"'"'"'"' | tr -d "'")"
    port="${port:-21}"
    passive_min="$(grep '^PUREFTPD_PASSIVE_MIN=' "${env_file}" 2>/dev/null | tail -1 | cut -d'=' -f2- | tr -d '"'"'"'"' | tr -d "'")"
    passive_min="${passive_min:-30000}"
    passive_max="$(grep '^PUREFTPD_PASSIVE_MAX=' "${env_file}" 2>/dev/null | tail -1 | cut -d'=' -f2- | tr -d '"'"'"'"' | tr -d "'")"
    passive_max="${passive_max:-30009}"

    local override_file="${config_dir}/docker-compose.ftp.yml"
    local legacy_override="${install_dir}/docker-compose.ftp.yml"
    if [[ -f "${legacy_override}" ]] && [[ ! -f "${override_file}" ]]; then
        cp -f "${legacy_override}" "${override_file}" 2>/dev/null || true
    fi
    touch "${override_file}" 2>/dev/null || true
    chown controlbox:controlbox "${override_file}" 2>/dev/null || true
    chmod 664 "${override_file}" 2>/dev/null || true
    if [[ "${protocol}" == "sftp" ]]; then
        cat > "${override_file}" <<EOF
services:
  sftp:
    ports:
      - "${port}:22"
EOF
    else
        cat > "${override_file}" <<EOF
services:
  pureftpd:
    ports:
      - "${port}:21"
      - "${passive_min}-${passive_max}:${passive_min}-${passive_max}"
EOF
    fi

    if docker ps --format '{{.Names}}' 2>/dev/null | grep -qx 'controlbox-pureftpd' \
        || docker ps --format '{{.Names}}' 2>/dev/null | grep -qx 'controlbox-sftp'; then
        cb_success "FTP: servicio ya en ejecución"
        return 0
    fi

    cb_info "Iniciando servicio FTP (${protocol})..."
    cd "${install_dir}"
    local -a compose_args=(--env-file "${env_file}" -f docker-compose.yml --profile ftp)
    [[ -f docker-compose.override.yml ]] && compose_args+=(-f docker-compose.override.yml)
    [[ -f docker-compose.ports.yml ]] && compose_args+=(-f docker-compose.ports.yml)
    [[ -f "${config_dir}/docker-compose.ftp.yml" ]] && compose_args+=(-f "${config_dir}/docker-compose.ftp.yml")
    [[ -f docker-compose.ftp.yml ]] && compose_args+=(-f docker-compose.ftp.yml)

    if [[ "${protocol}" == "sftp" ]]; then
        docker compose "${compose_args[@]}" up -d --remove-orphans sftp 2>/dev/null \
            || cb_warn "No se pudo levantar SFTP automáticamente"
    else
        docker compose "${compose_args[@]}" up -d --remove-orphans pureftpd 2>/dev/null \
            || cb_warn "No se pudo levantar Pure-FTPd automáticamente"
    fi

    if docker ps --format '{{.Names}}' 2>/dev/null | grep -qx 'controlbox-pureftpd' \
        || docker ps --format '{{.Names}}' 2>/dev/null | grep -qx 'controlbox-sftp'; then
        cb_success "FTP: servicio en ejecución"
        return 0
    fi

    cb_warn "FTP no arrancó. Revise: docker logs controlbox-pureftpd"
    return 1
}

cb_docker_stack_status() {
    local env_file="${CONTROLBOX_CONFIG_DIR}/platform.env"
    cb_docker_compose_run "${env_file}" ps
}

cb_docker_stack_restart() {
    local env_file="${CONTROLBOX_CONFIG_DIR}/platform.env"
    cb_docker_compose_run "${env_file}" restart
}

cb_docker_stack_down() {
    local env_file="${CONTROLBOX_CONFIG_DIR}/platform.env"
    cb_docker_compose_run "${env_file}" down --remove-orphans
}
