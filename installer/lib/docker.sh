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

            # Evitar que el gestor de paquetes intente iniciar servicios durante la instalación/actualización.
            # Esto previene fallos si systemd no está completamente funcional (p.ej. LXC) o si hay errores de configuración previos.
            local policy_rc_existed=0
            if [[ -f /usr/sbin/policy-rc.d ]]; then
                policy_rc_existed=1
                mv /usr/sbin/policy-rc.d /usr/sbin/policy-rc.d.bak
            fi
            echo -e '#!/bin/sh\nexit 101' > /usr/sbin/policy-rc.d
            chmod +x /usr/sbin/policy-rc.d

            apt-get update -qq
            apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

            # Restaurar policy-rc.d original
            rm -f /usr/sbin/policy-rc.d
            if [[ ${policy_rc_existed} -eq 1 ]]; then
                mv /usr/sbin/policy-rc.d.bak /usr/sbin/policy-rc.d
            fi
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

    # Intentar iniciar/reiniciar Docker.
    if ! systemctl restart docker >/dev/null 2>&1; then
        cb_warn "No se pudo iniciar Docker con la configuración estándar."

        # Solución 1: Corrupción de base de datos de red o de BuildKit/builder de Docker.
        # Esto ocurre tras apagados abruptos o crasheos y causa pánico de Go en dockerd (kvstore/boltdb o bbolt freelist).
        if [[ -d /var/lib/docker/network ]] || [[ -d /var/lib/docker/builder ]] || [[ -d /var/lib/docker/buildkit ]]; then
            cb_warn "Detectada posible corrupción de base de datos en Docker (red o cache de construcción). Limpiando..."
            if [[ -d /var/lib/docker/network ]]; then
                rm -rf /var/lib/docker/network.bak 2>/dev/null || true
                mv /var/lib/docker/network /var/lib/docker/network.bak 2>/dev/null || rm -rf /var/lib/docker/network
            fi
            if [[ -d /var/lib/docker/builder ]]; then
                rm -rf /var/lib/docker/builder.bak 2>/dev/null || true
                mv /var/lib/docker/builder /var/lib/docker/builder.bak 2>/dev/null || rm -rf /var/lib/docker/builder
            fi
            if [[ -d /var/lib/docker/buildkit ]]; then
                rm -rf /var/lib/docker/buildkit.bak 2>/dev/null || true
                mv /var/lib/docker/buildkit /var/lib/docker/buildkit.bak 2>/dev/null || rm -rf /var/lib/docker/buildkit
            fi
            cb_info "Reintentando iniciar Docker tras la limpieza..."
            if systemctl restart docker >/dev/null 2>&1; then
                cb_success "Docker iniciado con éxito tras limpiar bases de datos corruptas"
                if id controlbox >/dev/null 2>&1; then
                    usermod -aG docker controlbox 2>/dev/null || true
                fi
                return 0
            fi
        fi

        # Solución 2: Fallback de almacenamiento (p.ej. incompatibilidad de overlay2 o live-restore en LXC/ZFS)
        cb_warn "Aplicando fallback de configuración en daemon.json..."
        cat > "${daemon_json}" <<EOF
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "${log_max_size}",
    "max-file": "${log_max_file}"
  },
  "userland-proxy": false
}
EOF

        # Reintentar limpiar red/builder una vez más por si acaso
        if [[ -d /var/lib/docker/network ]] || [[ -d /var/lib/docker/builder ]] || [[ -d /var/lib/docker/buildkit ]]; then
            rm -rf /var/lib/docker/network.bak /var/lib/docker/builder.bak /var/lib/docker/buildkit.bak 2>/dev/null || true
            [[ -d /var/lib/docker/network ]] && (mv /var/lib/docker/network /var/lib/docker/network.bak 2>/dev/null || rm -rf /var/lib/docker/network)
            [[ -d /var/lib/docker/builder ]] && (mv /var/lib/docker/builder /var/lib/docker/builder.bak 2>/dev/null || rm -rf /var/lib/docker/builder)
            [[ -d /var/lib/docker/buildkit ]] && (mv /var/lib/docker/buildkit /var/lib/docker/buildkit.bak 2>/dev/null || rm -rf /var/lib/docker/buildkit)
        fi

        cb_info "Reintentando iniciar Docker con configuración de fallback..."
        if ! systemctl restart docker; then
            cb_error "ERROR CRÍTICO: Docker no se pudo iniciar después de todos los intentos de recuperación."
            cb_error "==> systemctl status docker.service <=="
            systemctl status docker.service --no-pager || true
            cb_error "==> journalctl -xeu docker.service (últimas 40 líneas) <=="
            journalctl -xeu docker.service --no-pager -n 40 || true
            cb_die "La instalación no puede continuar porque el servicio Docker no está activo. Verifique los logs anteriores."
        fi
        cb_success "Docker iniciado con éxito usando configuración de fallback"
    else
        cb_success "Docker configurado e iniciado correctamente"
    fi

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
if [[ -f "${BASH_SOURCE[0]%/*}/credentials-display.sh" ]]; then
    # shellcheck source=lib/credentials-display.sh
    source "${BASH_SOURCE[0]%/*}/credentials-display.sh"
fi
