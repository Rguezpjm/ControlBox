#!/usr/bin/env bash

cb_install_detect_existing() {
    [[ -f "${CONTROLBOX_STATE_DIR}/installed" ]] && return 0
    [[ -f "${CONTROLBOX_INSTALL_DIR}/docker-compose.yml" ]] && return 0
    [[ -f "${CONTROLBOX_CONFIG_DIR}/platform.env" ]] && return 0
    docker ps -a --format '{{.Names}}' 2>/dev/null | grep -q '^controlbox-' && return 0
    return 1
}

cb_install_purge_corrupt_env() {
    local config_dir="${CONTROLBOX_CONFIG_DIR:-/etc/controlbox}"
    local f size

    for f in "${config_dir}/installer.env" "${config_dir}/platform.env"; do
        [[ -f "${f}" ]] || continue
        size="$(wc -c < "${f}" 2>/dev/null || echo 0)"
        if [[ "${size}" -gt 524288 ]]; then
            echo "[WARN] Eliminando ${f} (${size} bytes, corrupto)" >&2
            env -i PATH="/usr/bin:/bin:/usr/local/bin" rm -f "${f}" 2>/dev/null \
                || rm -f "${f}" 2>/dev/null || true
            continue
        fi
        if grep -qE '^(source |#!/|cb_)' "${f}" 2>/dev/null; then
            echo "[WARN] Eliminando ${f} (contenido inválido)" >&2
            env -i PATH="/usr/bin:/bin:/usr/local/bin" rm -f "${f}" 2>/dev/null \
                || rm -f "${f}" 2>/dev/null || true
        fi
    done
}

cb_install_reset_database_volumes() {
    local data_dir="${CONTROLBOX_DATA_DIR:-/var/lib/controlbox}"
    local -a db_dirs=(
        "${data_dir}/postgres"
        "${data_dir}/supabase/db"
    )
    local removed=false

    for dir in "${db_dirs[@]}"; do
        if [[ -d "${dir}" ]]; then
            cb_warn "Eliminando datos antiguos: ${dir}"
            rm -rf "${dir}"
            removed=true
        fi
    done

    if [[ "${removed}" == "true" ]]; then
        cb_info "Volúmenes PostgreSQL reiniciados (nuevas contraseñas en platform.env)"
    fi
}

cb_install_clean_for_reinstall() {
    cb_step "Reinstalación limpia (curl | bash)"

    export CONTROLBOX_REINSTALL=true
    export CONTROLBOX_ASSUME_YES=true

    if [[ -f "${CONTROLBOX_INSTALL_DIR}/docker-compose.yml" ]]; then
        cb_info "Deteniendo stack Docker existente..."
        if [[ -f "${CONTROLBOX_CONFIG_DIR}/platform.env" ]] \
            && ! grep -qE '^(source |#!/|cb_)' "${CONTROLBOX_CONFIG_DIR}/platform.env" 2>/dev/null \
            && declare -f cb_docker_compose_run >/dev/null 2>&1; then
            cb_docker_compose_run "${CONTROLBOX_CONFIG_DIR}/platform.env" down --remove-orphans 2>/dev/null || true
        else
            (
                cd "${CONTROLBOX_INSTALL_DIR}" || exit 0
                docker compose down --remove-orphans 2>/dev/null || true
            )
        fi
    fi

    if [[ -f "${CONTROLBOX_INSTALL_DIR}/docker-compose.yml" ]] \
        && grep -qE 'PANEL_PORT|^(source |#!/|cb_)' "${CONTROLBOX_INSTALL_DIR}/docker-compose.yml" 2>/dev/null; then
        cb_warn "docker-compose.yml con puerto variable o corrupto, será restaurado"
        rm -f "${CONTROLBOX_INSTALL_DIR}/docker-compose.yml"
    fi

    if docker ps -a --format '{{.Names}}' 2>/dev/null | grep -q '^controlbox-'; then
        cb_info "Eliminando contenedores ControlBox..."
        docker ps -a --filter "name=controlbox" -q | xargs -r docker rm -f 2>/dev/null || true
    fi

    docker network rm controlbox controlbox_default 2>/dev/null || true

    cb_info "Limpiando estado de instalación parcial..."
    rm -f "${CONTROLBOX_STATE_DIR}/installed"
    rm -f "${CONTROLBOX_STATE_DIR}/install.state"
    rm -rf "${CONTROLBOX_STATE_DIR}/steps"
    mkdir -p "${CONTROLBOX_STATE_DIR}/steps"

    rm -f "${CONTROLBOX_CONFIG_DIR}/platform.env"
    rm -f "${CONTROLBOX_CONFIG_DIR}/installer.env"
    rm -f "${CONTROLBOX_INSTALL_DIR}/.env"
    rm -f "${CONTROLBOX_INSTALL_DIR}/docker-compose.override.yml"
    rm -f "${CONTROLBOX_INSTALL_DIR}/docker-compose.ports.yml"
    rm -f "${CONTROLBOX_INSTALL_DIR}/docker-compose.panel-build.yml"
    rm -f "${CONTROLBOX_INSTALL_DIR}/docker-compose.build.yml"
    rm -f "${CONTROLBOX_INSTALL_DIR}/docker-compose.yml"

    cb_install_reset_database_volumes

    cb_success "Entorno preparado para instalación limpia"
}
