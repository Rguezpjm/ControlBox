#!/bin/sh
set -e

writable_dirs="/var/lib/controlbox/sites /var/lib/controlbox/backups /var/lib/controlbox/backups/databases"

for dir in $writable_dirs; do
  mkdir -p "$dir"
done

cb_wait_for_docker() {
  [ -n "${DOCKER_HOST:-}" ] || return 0
  [ "${REQUIRE_DOCKER_API:-0}" = "1" ] || return 0

  echo "Esperando API Docker en ${DOCKER_HOST}..."
  attempt=0
  while [ "${attempt}" -lt 45 ]; do
    if docker info >/dev/null 2>&1; then
      echo "API Docker disponible en ${DOCKER_HOST}"
      return 0
    fi

    case "${DOCKER_HOST}" in
      *docker-socket-proxy*)
        export DOCKER_HOST="tcp://controlbox-docker-proxy:2375"
        if docker info >/dev/null 2>&1; then
          echo "API Docker disponible en ${DOCKER_HOST}"
          return 0
        fi
        export DOCKER_HOST="tcp://docker-socket-proxy:2375"
        ;;
      *controlbox-docker-proxy*)
        export DOCKER_HOST="tcp://docker-socket-proxy:2375"
        if docker info >/dev/null 2>&1; then
          echo "API Docker disponible en ${DOCKER_HOST}"
          return 0
        fi
        export DOCKER_HOST="tcp://controlbox-docker-proxy:2375"
        ;;
    esac

    attempt=$((attempt + 1))
    sleep 2
  done

  echo "AVISO: API Docker no disponible en ${DOCKER_HOST}. Sitios web y contenedores pueden fallar." >&2
  return 0
}

if [ "$(id -u)" = "0" ]; then
  for dir in $writable_dirs; do
    chown -R controlbox:controlbox "$dir" 2>/dev/null || true
  done
  if [ -d /var/log/pure-ftpd ]; then
    chown -R controlbox:controlbox /var/log/pure-ftpd 2>/dev/null || true
  fi

  # Asegurar que platform.env y otros archivos montados sean legibles por controlbox.
  # El entrypoint corre como root antes del gosu — oportunidad para corregir permisos.
  _cb_uid="$(id -u controlbox 2>/dev/null || echo 1000)"
  _cb_gid="$(id -g controlbox 2>/dev/null || echo 1000)"

  # platform.env
  _platform_env="${PLATFORM_CONFIG_DIR:-/host/etc/controlbox}/platform.env"
  if [ -f "${_platform_env}" ]; then
    chmod 640 "${_platform_env}" 2>/dev/null || true
    chown "${_cb_uid}:${_cb_gid}" "${_platform_env}" 2>/dev/null || true
    chmod o+x "${PLATFORM_CONFIG_DIR:-/host/etc/controlbox}" 2>/dev/null || true
    chmod g+rx "${PLATFORM_CONFIG_DIR:-/host/etc/controlbox}" 2>/dev/null || true
  fi

  # install.state — contiene VERSION, PANEL_PORT, etc.; necesario para /health
  _state_file="/host/root/var/lib/controlbox/state/install.state"
  if [ -f "${_state_file}" ]; then
    chmod 640 "${_state_file}" 2>/dev/null || true
    chown "${_cb_uid}:${_cb_gid}" "${_state_file}" 2>/dev/null || true
    chmod o+x "/host/root/var/lib/controlbox" 2>/dev/null || true
    chmod o+x "/host/root/var/lib/controlbox/state" 2>/dev/null || true
  fi

  cb_wait_for_docker
  exec gosu controlbox "$@"
fi

cb_wait_for_docker
exec "$@"
