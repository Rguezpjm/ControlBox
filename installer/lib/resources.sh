#!/usr/bin/env bash

CB_CPU_CORES=0
CB_RAM_MB=0
CB_DISK_GB=0
CB_SWAP_MB=0
CB_PROFILE="standard"

cb_resources_detect() {
    cb_step "Detectando recursos del sistema"

    CB_CPU_CORES="$(nproc 2>/dev/null || grep -c ^processor /proc/cpuinfo)"
    CB_RAM_MB="$(awk '/MemTotal/ {print int($2/1024)}' /proc/meminfo)"
    CB_SWAP_MB="$(awk '/SwapTotal/ {print int($2/1024)}' /proc/meminfo)"

    local data_dir="${CONTROLBOX_DATA_DIR:-/var/lib/controlbox}"
    mkdir -p "${data_dir}"
    CB_DISK_GB="$(df -BG "${data_dir}" | awk 'NR==2 {gsub(/G/,"",$4); print $4}')"

    cb_save_install_state "CPU_CORES" "${CB_CPU_CORES}"
    cb_save_install_state "RAM_MB" "${CB_RAM_MB}"
    cb_save_install_state "DISK_GB" "${CB_DISK_GB}"
    cb_save_install_state "SWAP_MB" "${CB_SWAP_MB}"

    cb_info "CPU: ${CB_CPU_CORES} cores"
    cb_info "RAM: ${CB_RAM_MB} MB"
    cb_info "Disco disponible: ${CB_DISK_GB} GB"
    cb_info "Swap: ${CB_SWAP_MB} MB"

    local min_ram="${MIN_RAM_MB:-4096}"
    local min_disk="${MIN_DISK_GB:-40}"
    local min_cpu="${MIN_CPU_CORES:-2}"

    if [[ ${CB_RAM_MB} -lt ${min_ram} ]]; then
        cb_warn "RAM por debajo del recomendado: ${CB_RAM_MB}MB < ${min_ram}MB (perfil minimal)"
    fi

    if [[ ${CB_DISK_GB} -lt ${min_disk} ]]; then
        cb_warn "Disco por debajo del recomendado: ${CB_DISK_GB}GB < ${min_disk}GB"
    fi

    if [[ ${CB_CPU_CORES} -lt ${min_cpu} ]]; then
        cb_warn "CPU insuficiente: ${CB_CPU_CORES} < ${min_cpu} cores recomendado"
    fi

    cb_resources_calculate_profile
    cb_step_done "detect_resources"
}

cb_resources_calculate_profile() {
    if [[ ${CB_RAM_MB} -ge 32768 ]] && [[ ${CB_CPU_CORES} -ge 8 ]]; then
        CB_PROFILE="enterprise"
    elif [[ ${CB_RAM_MB} -ge 16384 ]] && [[ ${CB_CPU_CORES} -ge 4 ]]; then
        CB_PROFILE="professional"
    elif [[ ${CB_RAM_MB} -ge 8192 ]] && [[ ${CB_CPU_CORES} -ge 2 ]]; then
        CB_PROFILE="standard"
    else
        CB_PROFILE="minimal"
    fi

    cb_save_install_state "PROFILE" "${CB_PROFILE}"
    cb_success "Perfil de recursos: ${CB_PROFILE}"
}

cb_resources_get_limits() {
    case "${CB_PROFILE}" in
        enterprise)
            POSTGRES_MAX_CONNECTIONS=300
            POSTGRES_SHARED_BUFFERS="2GB"
            POSTGRES_EFFECTIVE_CACHE="8GB"
            REDIS_MAXMEMORY="2gb"
            PROMETHEUS_RETENTION="60d"
            LOKI_RETENTION="60d"
            API_WORKERS=8
            ;;
        professional)
            POSTGRES_MAX_CONNECTIONS=200
            POSTGRES_SHARED_BUFFERS="1GB"
            POSTGRES_EFFECTIVE_CACHE="4GB"
            REDIS_MAXMEMORY="1gb"
            PROMETHEUS_RETENTION="30d"
            LOKI_RETENTION="30d"
            API_WORKERS=4
            ;;
        standard)
            POSTGRES_MAX_CONNECTIONS=100
            POSTGRES_SHARED_BUFFERS="512MB"
            POSTGRES_EFFECTIVE_CACHE="2GB"
            REDIS_MAXMEMORY="512mb"
            PROMETHEUS_RETENTION="15d"
            LOKI_RETENTION="15d"
            API_WORKERS=2
            ;;
        minimal)
            POSTGRES_MAX_CONNECTIONS=50
            POSTGRES_SHARED_BUFFERS="256MB"
            POSTGRES_EFFECTIVE_CACHE="1GB"
            REDIS_MAXMEMORY="256mb"
            PROMETHEUS_RETENTION="7d"
            LOKI_RETENTION="7d"
            API_WORKERS=2
            ;;
    esac

    export POSTGRES_MAX_CONNECTIONS POSTGRES_SHARED_BUFFERS POSTGRES_EFFECTIVE_CACHE
    export REDIS_MAXMEMORY PROMETHEUS_RETENTION LOKI_RETENTION API_WORKERS
}

cb_resources_print_summary() {
    cb_resources_get_limits
    echo ""
    echo -e "${CB_BOLD}Configuración óptima generada:${CB_NC}"
    echo "  Perfil:              ${CB_PROFILE}"
    echo "  PostgreSQL buffers:  ${POSTGRES_SHARED_BUFFERS}"
    echo "  PostgreSQL conns:    ${POSTGRES_MAX_CONNECTIONS}"
    echo "  Redis maxmemory:     ${REDIS_MAXMEMORY}"
    echo "  Prometheus retención: ${PROMETHEUS_RETENTION}"
    echo "  API workers:         ${API_WORKERS}"
    echo ""
}
