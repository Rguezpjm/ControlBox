#!/usr/bin/env bash

CB_OS_ID=""
CB_OS_VERSION=""
CB_OS_FAMILY=""
CB_OS_ARCH=""
CB_OS_PRETTY=""
CB_PACKAGE_MANAGER=""
CB_FIREWALL_TYPE=""
CB_SUPPORTED=false

cb_os_set_from_family() {
    if [[ "${CB_OS_FAMILY}" == *"debian"* ]] || [[ "${CB_OS_FAMILY}" == *"ubuntu"* ]]; then
        CB_PACKAGE_MANAGER="apt"
        CB_FIREWALL_TYPE="ufw"
        CB_SUPPORTED=true
        cb_info "Derivado Debian/Ubuntu detectado (${CB_OS_ID})"
        return 0
    fi

    if [[ "${CB_OS_FAMILY}" == *"rhel"* ]] || [[ "${CB_OS_FAMILY}" == *"fedora"* ]] || [[ "${CB_OS_FAMILY}" == *"centos"* ]]; then
        CB_PACKAGE_MANAGER="dnf"
        CB_FIREWALL_TYPE="firewalld"
        CB_SUPPORTED=true
        cb_info "Derivado RHEL/CentOS detectado (${CB_OS_ID})"
        return 0
    fi

    return 1
}

cb_os_detect() {
    cb_step "Detectando sistema operativo"

    if [[ -f /etc/os-release ]]; then
        # shellcheck source=/dev/null
        source /etc/os-release
        CB_OS_ID="${ID:-unknown}"
        CB_OS_VERSION="${VERSION_ID:-unknown}"
        CB_OS_PRETTY="${PRETTY_NAME:-unknown}"
        CB_OS_FAMILY="${ID_LIKE:-${ID}}"
    else
        cb_die "No se pudo detectar el sistema operativo (/etc/os-release no encontrado)"
    fi

    CB_OS_ARCH="$(uname -m)"
    case "${CB_OS_ARCH}" in
        x86_64|amd64) CB_OS_ARCH="amd64" ;;
        aarch64|arm64) CB_OS_ARCH="arm64" ;;
        *) cb_warn "Arquitectura no probada: ${CB_OS_ARCH}" ;;
    esac

    case "${CB_OS_ID}" in
        ubuntu|debian|linuxmint|pop|elementary|raspbian|kali|parrot)
            CB_PACKAGE_MANAGER="apt"
            CB_FIREWALL_TYPE="ufw"
            CB_SUPPORTED=true
            ;;
        fedora)
            CB_PACKAGE_MANAGER="dnf"
            CB_FIREWALL_TYPE="firewalld"
            CB_SUPPORTED=true
            ;;
        centos)
            if [[ "${CB_OS_VERSION}" == 7* ]]; then
                CB_PACKAGE_MANAGER="yum"
            else
                CB_PACKAGE_MANAGER="dnf"
            fi
            CB_FIREWALL_TYPE="firewalld"
            CB_SUPPORTED=true
            ;;
        rhel|rocky|almalinux|ol|amzn|alinux|anolis|tencentos|eurolinux|virtuozzo)
            if [[ "${CB_OS_VERSION}" == 7* ]]; then
                CB_PACKAGE_MANAGER="yum"
            else
                CB_PACKAGE_MANAGER="dnf"
            fi
            CB_FIREWALL_TYPE="firewalld"
            CB_SUPPORTED=true
            ;;
        *)
            if ! cb_os_set_from_family; then
                cb_warn "SO no listado (${CB_OS_ID}): se intentará instalar con apt"
                CB_PACKAGE_MANAGER="apt"
                CB_FIREWALL_TYPE="ufw"
                CB_SUPPORTED=true
            fi
            ;;
    esac

    cb_save_install_state "OS_ID" "${CB_OS_ID}"
    cb_save_install_state "OS_VERSION" "${CB_OS_VERSION}"
    cb_save_install_state "OS_ARCH" "${CB_OS_ARCH}"
    cb_save_install_state "OS_FAMILY" "${CB_OS_FAMILY}"
    cb_save_install_state "PACKAGE_MANAGER" "${CB_PACKAGE_MANAGER}"
    cb_save_install_state "FIREWALL_TYPE" "${CB_FIREWALL_TYPE}"

    cb_success "Sistema: ${CB_OS_PRETTY} (${CB_OS_ARCH})"
    cb_info "Gestor de paquetes: ${CB_PACKAGE_MANAGER}"
    cb_info "Firewall: ${CB_FIREWALL_TYPE}"
    cb_info "Compatibilidad: amplia (Ubuntu/Debian/CentOS/Rocky/AlmaLinux y derivados)"

    cb_step_done "detect_os"
}

cb_os_install_packages() {
    local packages=("$@")
    case "${CB_PACKAGE_MANAGER}" in
        apt)
            export DEBIAN_FRONTEND=noninteractive
            apt-get update -qq
            apt-get install -y -qq "${packages[@]}"
            ;;
        dnf)
            dnf install -y -q "${packages[@]}"
            ;;
        yum)
            yum install -y -q "${packages[@]}"
            ;;
        *)
            cb_die "Gestor de paquetes no soportado: ${CB_PACKAGE_MANAGER}"
            ;;
    esac
}

cb_os_install_prerequisites() {
    cb_step "Instalando prerequisitos del sistema"

    if cb_step_is_done "install_prerequisites"; then
        cb_info "Prerequisitos ya instalados, omitiendo"
        return 0
    fi

    case "${CB_PACKAGE_MANAGER}" in
        apt)
            cb_os_install_packages \
                ca-certificates \
                curl \
                gnupg \
                lsb-release \
                jq \
                openssl \
                tar \
                gzip \
                unzip \
                wget \
                cron \
                rsync \
                acl \
                iproute2 \
                net-tools \
                software-properties-common
            ;;
        dnf)
            cb_os_install_packages \
                ca-certificates \
                curl \
                gnupg2 \
                jq \
                openssl \
                tar \
                gzip \
                unzip \
                wget \
                cronie \
                rsync \
                acl \
                iproute \
                net-tools \
                dnf-plugins-core
            systemctl enable --now crond 2>/dev/null || true
            ;;
        yum)
            cb_os_install_packages \
                ca-certificates \
                curl \
                gnupg2 \
                jq \
                openssl \
                tar \
                gzip \
                unzip \
                wget \
                cronie \
                rsync \
                acl \
                iproute \
                net-tools \
                yum-utils
            systemctl enable --now crond 2>/dev/null || true
            ;;
    esac

    cb_step_done "install_prerequisites"
    cb_success "Prerequisitos instalados"
}

cb_os_create_user() {
    if id controlbox >/dev/null 2>&1; then
        cb_info "Usuario controlbox ya existe"
        return 0
    fi
    useradd --system --home-dir "${CONTROLBOX_INSTALL_DIR}" --shell /usr/sbin/nologin controlbox
    cb_success "Usuario controlbox creado"
}

cb_os_create_directories() {
    cb_step "Creando directorios del sistema"

    local dirs=(
        "${CONTROLBOX_INSTALL_DIR}"
        "${CONTROLBOX_DATA_DIR}"
        "${CONTROLBOX_CONFIG_DIR}"
        "${CONTROLBOX_LOG_DIR}"
        "${CONTROLBOX_STATE_DIR}"
        "${CONTROLBOX_BACKUP_DIR}"
        "${CONTROLBOX_INSTALL_DIR}/templates"
        "${CONTROLBOX_INSTALL_DIR}/scripts"
        "${CONTROLBOX_INSTALL_DIR}/lib"
        "${CONTROLBOX_CONFIG_DIR}/traefik"
        "${CONTROLBOX_CONFIG_DIR}/traefik/dynamic"
        "${CONTROLBOX_CONFIG_DIR}/prometheus"
        "${CONTROLBOX_CONFIG_DIR}/grafana/provisioning/datasources"
        "${CONTROLBOX_CONFIG_DIR}/grafana/provisioning/dashboards"
        "${CONTROLBOX_CONFIG_DIR}/loki"
        "${CONTROLBOX_CONFIG_DIR}/promtail"
        "${CONTROLBOX_CONFIG_DIR}/supabase"
        "${CONTROLBOX_CONFIG_DIR}/minio"
        "${CONTROLBOX_DATA_DIR}/postgres"
        "${CONTROLBOX_DATA_DIR}/redis"
        "${CONTROLBOX_DATA_DIR}/minio"
        "${CONTROLBOX_DATA_DIR}/grafana"
        "${CONTROLBOX_DATA_DIR}/prometheus"
        "${CONTROLBOX_DATA_DIR}/loki"
        "${CONTROLBOX_DATA_DIR}/supabase"
        "${CONTROLBOX_DATA_DIR}/traefik"
        "${CONTROLBOX_DATA_DIR}/letsencrypt"
    )

    for dir in "${dirs[@]}"; do
        mkdir -p "${dir}"
    done

    chown -R controlbox:controlbox "${CONTROLBOX_INSTALL_DIR}" "${CONTROLBOX_DATA_DIR}" "${CONTROLBOX_LOG_DIR}" 2>/dev/null || true
    chmod 750 "${CONTROLBOX_CONFIG_DIR}"
    cb_ssl_fix_acme_permissions 2>/dev/null || {
        chmod 755 "${CONTROLBOX_DATA_DIR}/letsencrypt"
        touch "${CONTROLBOX_DATA_DIR}/letsencrypt/acme.json"
        chmod 644 "${CONTROLBOX_DATA_DIR}/letsencrypt/acme.json"
    }

    cb_step_done "create_directories"
    cb_success "Directorios creados"
}
