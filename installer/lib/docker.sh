#!/usr/bin/env bash

cb_docker_is_installed() {
    command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1
}

cb_compose_is_installed() {
    docker compose version >/dev/null 2>&1
}

cb_docker_install() {
    cb_step "Instalando Docker"

    if cb_step_is_done "install_docker" && cb_docker_is_installed; then
        cb_info "Docker ya instalado, omitiendo"
        return 0
    fi

    if cb_docker_is_installed; then
        cb_info "Docker detectado en el sistema"
        cb_docker_configure
        cb_step_done "install_docker"
        return 0
    fi

    case "${CB_PACKAGE_MANAGER}" in
        apt)
            install -m 0755 -d /etc/apt/keyrings
            if [[ ! -f /etc/apt/keyrings/docker.gpg ]]; then
                curl -fsSL https://download.docker.com/linux/${CB_OS_ID}/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
                chmod a+r /etc/apt/keyrings/docker.gpg
            fi
            echo \
                "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/${CB_OS_ID} \
                $(. /etc/os-release && echo "${VERSION_CODENAME}") stable" > /etc/apt/sources.list.d/docker.list
            apt-get update -qq
            apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
            ;;
        dnf)
            dnf config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo 2>/dev/null || true
            dnf install -y -q docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
            ;;
    esac

    cb_docker_configure
    cb_step_done "install_docker"
    cb_success "Docker instalado: $(docker --version)"
}

cb_docker_configure() {
    mkdir -p /etc/docker
    local daemon_json="/etc/docker/daemon.json"
    local log_max_size="50m"
    local log_max_file=5
    local storage_driver="overlay2"

    case "${CB_PROFILE:-standard}" in
        enterprise) log_max_size="100m"; log_max_file=10 ;;
        minimal) log_max_size="20m"; log_max_file=3 ;;
    esac

    if [[ ! -f "${daemon_json}" ]]; then
        cat > "${daemon_json}" <<EOF
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "${log_max_size}",
    "max-file": "${log_max_file}"
  },
  "storage-driver": "${storage_driver}",
  "live-restore": true,
  "userland-proxy": false
}
EOF
    fi

    systemctl enable docker
    systemctl restart docker

    if id controlbox >/dev/null 2>&1; then
        usermod -aG docker controlbox 2>/dev/null || true
    fi
}

cb_compose_install() {
    cb_step "Verificando Docker Compose"

    if cb_step_is_done "install_compose" && cb_compose_is_installed; then
        cb_info "Docker Compose ya disponible"
        return 0
    fi

    if cb_compose_is_installed; then
        cb_step_done "install_compose"
        cb_success "Docker Compose disponible: $(docker compose version)"
        return 0
    fi

    local compose_version="${DOCKER_COMPOSE_VERSION:-2.29.7}"
    local compose_url="https://github.com/docker/compose/releases/download/v${compose_version}/docker-compose-linux-$(uname -m)"

    curl -fsSL "${compose_url}" -o /usr/local/lib/docker/cli-plugins/docker-compose
    chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
    mkdir -p /usr/local/lib/docker/cli-plugins

    cb_step_done "install_compose"
    cb_success "Docker Compose instalado"
}

if [[ -f "${BASH_SOURCE[0]%/*}/bootstrap-fixes.sh" ]]; then
    # shellcheck source=lib/bootstrap-fixes.sh
    source "${BASH_SOURCE[0]%/*}/bootstrap-fixes.sh"
fi
