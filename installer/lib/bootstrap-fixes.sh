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

    if [[ -f "${env_file}" ]] && grep -q '^REDIS_PASSWORD=' "${env_file}" 2>/dev/null; then
        local redis_pass
        redis_pass="$(grep '^REDIS_PASSWORD=' "${env_file}" | tail -1 | cut -d'=' -f2- | tr -d '"'"'"'"' | tr -d "'")"
        if [[ -n "${redis_pass}" ]] && ! grep -q "^CELERY_BROKER_URL=redis://:${redis_pass}@" "${env_file}" 2>/dev/null; then
            cb_warn "Actualizando CELERY_BROKER_URL con contraseña de Redis"
            sed -i '/^CELERY_BROKER_URL=/d' "${env_file}" 2>/dev/null || true
            sed -i '/^CELERY_RESULT_BACKEND=/d' "${env_file}" 2>/dev/null || true
            echo "CELERY_BROKER_URL=redis://:${redis_pass}@redis:6379/1" >> "${env_file}"
            echo "CELERY_RESULT_BACKEND=redis://:${redis_pass}@redis:6379/2" >> "${env_file}"
        fi
    fi

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
    local version="${CONTROLBOX_VERSION:-4.11.1}"
    local panel_base="${CONTROLBOX_PANEL_BASE_PATH:-}"

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
        NEXT_PUBLIC_BASE_PATH: ${panel_base}
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
    local version="${CONTROLBOX_VERSION:-4.11.1}"
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
    cb_ssl_fix_acme_permissions 2>/dev/null || true
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
        "cb_docker_compose_run '${env_file}' ps docker-socket-proxy 2>/dev/null | grep -qE 'Up|running'" 90

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
        "cb_docker_compose_run '${env_file}' ps traefik 2>/dev/null | grep -qE 'healthy|Up'" 90

    cb_wait_for_service "panel" \
        "cb_docker_compose_run '${env_file}' ps panel 2>/dev/null | grep -q Up" 120

    cb_step_done "deploy_stack"
    cb_success "Stack desplegado correctamente"
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
