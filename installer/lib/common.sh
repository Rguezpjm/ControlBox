#!/usr/bin/env bash

set -euo pipefail

CONTROLBOX_LOG_DIR="${CONTROLBOX_LOG_DIR:-/var/log/controlbox}"
CONTROLBOX_STATE_DIR="${CONTROLBOX_STATE_DIR:-/var/lib/controlbox/state}"
CONTROLBOX_INSTALL_DIR="${CONTROLBOX_INSTALL_DIR:-/opt/controlbox}"

CB_LOG_FILE="${CONTROLBOX_LOG_DIR}/installer.log"
CB_ROLLBACK_DIR="${CONTROLBOX_STATE_DIR}/rollback"
CB_STEPS_DIR="${CONTROLBOX_STATE_DIR}/steps"
CB_LOCK_FILE="${CONTROLBOX_STATE_DIR}/installer.lock"

CB_RED='\033[0;31m'
CB_GREEN='\033[0;32m'
CB_YELLOW='\033[1;33m'
CB_BLUE='\033[0;34m'
CB_CYAN='\033[0;36m'
CB_BOLD='\033[1m'
CB_NC='\033[0m'

cb_env_safe_date() {
    env -i PATH="/usr/bin:/bin:/usr/local/bin" date "$@" 2>/dev/null \
        || /usr/bin/date "$@" 2>/dev/null \
        || date "$@"
}

cb_init_logging() {
    mkdir -p "${CONTROLBOX_LOG_DIR}" "${CONTROLBOX_STATE_DIR}" "${CB_STEPS_DIR}" "${CB_ROLLBACK_DIR}"
    touch "${CB_LOG_FILE}"
    chmod 640 "${CB_LOG_FILE}" 2>/dev/null || true
}

cb_log() {
    local level="$1"
    shift
    local message="$*"
    local timestamp
    timestamp="$(cb_env_safe_date -u '+%Y-%m-%dT%H:%M:%SZ')"
    echo "[${timestamp}] [${level}] ${message}" >> "${CB_LOG_FILE}"
}

cb_info() {
    cb_log "INFO" "$@"
    echo -e "${CB_BLUE}[INFO]${CB_NC} $*"
}

cb_success() {
    cb_log "SUCCESS" "$@"
    echo -e "${CB_GREEN}[OK]${CB_NC} $*"
}

cb_warn() {
    cb_log "WARN" "$@"
    echo -e "${CB_YELLOW}[WARN]${CB_NC} $*"
}

cb_error() {
    cb_log "ERROR" "$@"
    echo -e "${CB_RED}[ERROR]${CB_NC} $*" >&2
}

cb_step() {
    cb_log "STEP" "$@"
    if declare -f cb_progress_step >/dev/null 2>&1; then
        cb_progress_step "$*"
    fi
    echo -e "\n${CB_BOLD}${CB_CYAN}==>${CB_NC} ${CB_BOLD}$*${CB_NC}\n"
}

cb_require_root() {
    if [[ "${EUID}" -ne 0 ]]; then
        cb_error "Este instalador debe ejecutarse como root o con sudo."
        exit 1
    fi
}

cb_acquire_lock() {
    if [[ -f "${CB_LOCK_FILE}" ]]; then
        local pid
        pid="$(cat "${CB_LOCK_FILE}" 2>/dev/null || echo "")"
        if [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null; then
            cb_error "Otro proceso de instalación está en ejecución (PID: ${pid})."
            exit 1
        fi
        env -i PATH="/usr/bin:/bin:/usr/local/bin" rm -f "${CB_LOCK_FILE}" 2>/dev/null \
            || rm -f "${CB_LOCK_FILE}" 2>/dev/null || true
    fi
    echo "$$" > "${CB_LOCK_FILE}"
}

cb_release_lock() {
    env -i PATH="/usr/bin:/bin:/usr/local/bin" rm -f "${CB_LOCK_FILE}" 2>/dev/null \
        || rm -f "${CB_LOCK_FILE}" 2>/dev/null \
        || true
}

cb_step_done() {
    local step="$1"
    touch "${CB_STEPS_DIR}/${step}.done"
    cb_log "STEP_DONE" "${step}"
}

cb_step_is_done() {
    local step="$1"
    [[ -f "${CB_STEPS_DIR}/${step}.done" ]]
}

cb_generate_secret() {
    local length="${1:-32}"
    openssl rand -hex "$((length + 1))" | head -c "${length}"
}

CB_ADMIN_PASSWORD_MIN="${CB_ADMIN_PASSWORD_MIN:-12}"

cb_generate_admin_password() {
    local length="${1:-${CB_ADMIN_PASSWORD_MIN}}"
    if [[ "${length}" -lt "${CB_ADMIN_PASSWORD_MIN}" ]]; then
        length="${CB_ADMIN_PASSWORD_MIN}"
    fi
    local password=""
    while [[ ${#password} -lt ${length} ]]; do
        password="${password}$(openssl rand -hex 16 | tr -dc '0-9')"
    done
    echo "${password:0:${length}}"
}

cb_sanitize_admin_password() {
    local value="${1:-}"
    value="${value//\"/}"
    value="${value//\'/}"
    value="${value//$'\r'/}"
    value="${value//$'\n'/}"
    value="${value//[[:space:]]/}"
    if [[ ${#value} -gt 64 ]]; then
        value="${value:0:64}"
    fi
    if [[ ${#value} -lt ${CB_ADMIN_PASSWORD_MIN} ]]; then
        cb_generate_admin_password "${CB_ADMIN_PASSWORD_MIN}"
        return 0
    fi
    echo "${value}"
}

cb_sanitize_env_secret() {
    local value="${1:-}"
    local max="${2:-256}"
    local gen_len="${3:-32}"
    value="${value//\"/}"
    value="${value//\'/}"
    value="${value//$'\r'/}"
    value="${value//$'\n'/}"
    value="${value//[[:space:]]/}"
    if [[ -z "${value}" ]] || [[ ${#value} -gt ${max} ]]; then
        cb_generate_secret "${gen_len}"
        return 0
    fi
    echo "${value}"
}

cb_env_emit() {
    local key="$1"
    local value="${2-}"
    value="${value//\\/\\\\}"
    value="${value//\"/\\\"}"
    value="${value//$'\r'/}"
    value="${value//$'\n'/\\n}"
    printf '%s="%s"\n' "${key}" "${value}"
}

cb_env_patch_key() {
    local file="$1"
    local key="$2"
    local value="$3"
    value="${value//\\/\\\\}"
    value="${value//\"/\\\"}"
    value="${value//$'\r'/}"
    value="${value//$'\n'/\\n}"
    if [[ ! -f "${file}" ]]; then
        cb_env_emit "${key}" "${value}" >> "${file}"
        return 0
    fi
    local tmp
    tmp="$(mktemp)"
    grep -v "^${key}=" "${file}" > "${tmp}" 2>/dev/null || true
    cb_env_emit "${key}" "${value}" >> "${tmp}"
    mv -f "${tmp}" "${file}"
}

cb_env_read_key() {
    local file="$1"
    local key="$2"
    local line raw
    [[ -f "${file}" ]] || return 1
    line="$(grep "^${key}=" "${file}" 2>/dev/null | tail -1)" || return 1
    raw="${line#*=}"
    raw="${raw//$'\r'/}"
    if [[ "${raw}" =~ ^\"(.*)\"$ ]]; then
        raw="${BASH_REMATCH[1]}"
        raw="${raw//\\\"/\"}"
        raw="${raw//\\\\/\\}"
    fi
    printf '%s' "${raw}"
}

cb_platform_env_dedupe_keys() {
    local env_file="${1:-${CONTROLBOX_CONFIG_DIR}/platform.env}"
    [[ -f "${env_file}" ]] || return 0

    local key value count
    for key in MYSQL_ADMIN_PASSWORD MSSQL_ADMIN_PASSWORD REDIS_PASSWORD POSTGRES_PASSWORD SUPABASE_DB_PASSWORD SUPABASE_DB_ADMIN_PASSWORD; do
        count="$(grep -c "^${key}=" "${env_file}" 2>/dev/null || echo 0)"
        if [[ "${count}" -gt 1 ]]; then
            value="$(cb_env_read_key "${env_file}" "${key}" 2>/dev/null || true)"
            if [[ -n "${value}" ]]; then
                cb_env_patch_key "${env_file}" "${key}" "${value}"
                cb_info "platform.env: ${key} unificado (último valor)"
            fi
        fi
    done
}

cb_platform_env_repair() {
    local env_file="${1:-${CONTROLBOX_CONFIG_DIR}/platform.env}"
    [[ -f "${env_file}" ]] || return 0

    cb_platform_env_dedupe_keys "${env_file}"

    local tmp changed=0
    tmp="$(mktemp)"
    while IFS= read -r line || [[ -n "${line}" ]]; do
        if [[ "${line}" =~ ^[^=]*@redis:6379/[0-9]+\"?$ ]]; then
            changed=1
            continue
        fi
        printf '%s\n' "${line}"
    done < "${env_file}" > "${tmp}"
    if [[ "${changed}" -eq 1 ]]; then
        mv -f "${tmp}" "${env_file}"
        cb_info "platform.env: eliminadas líneas corruptas (CELERY/Redis sin comillas)"
    else
        rm -f "${tmp}"
    fi

    local redis_pass
    redis_pass="$(cb_env_read_key "${env_file}" "REDIS_PASSWORD" 2>/dev/null || true)"
    [[ -n "${redis_pass}" ]] || return 0

    cb_env_patch_key "${env_file}" "CELERY_BROKER_URL" "redis://:${redis_pass}@redis:6379/1"
    cb_env_patch_key "${env_file}" "CELERY_RESULT_BACKEND" "redis://:${redis_pass}@redis:6379/2"
}

cb_sanitize_port() {
    local value="${1:-}"
    local default="${2:-}"
    value="${value//\"/}"
    value="${value//\'/}"
    value="${value//$'\r'/}"
    value="${value//$'\n'/}"
    value="${value//[[:space:]]/}"
    if [[ "${value}" =~ ^[0-9]+$ ]] && (( value >= 1 && value <= 65535 )); then
        echo "${value}"
        return 0
    fi
    if [[ -n "${default}" ]]; then
        echo "${default}"
    fi
}

cb_resolve_panel_port() {
    local port=""

    port="$(cb_sanitize_port "${CONTROLBOX_PANEL_PORT:-}" "")"
    if [[ -z "${port}" ]]; then
        port="$(cb_sanitize_port "$(cb_get_install_state PANEL_PORT 2>/dev/null || true)" "")"
    fi
    if [[ -z "${port}" ]] && [[ -f "${CONTROLBOX_CONFIG_DIR}/platform.env" ]]; then
        port="$(cb_sanitize_port "$(grep '^PANEL_PORT=' "${CONTROLBOX_CONFIG_DIR}/platform.env" | tail -1 | cut -d'=' -f2-)" "")"
    fi
    if [[ -z "${port}" ]]; then
        port="$(cb_sanitize_port "$(cb_setup_pick_panel_port 2>/dev/null || echo 8475)" "8475")"
    fi
    echo "${port}"
}

cb_load_platform_env() {
    local file="$1"
    local host_install="${CONTROLBOX_INSTALL_DIR:-/opt/controlbox}"
    local host_config="${CONTROLBOX_CONFIG_DIR:-/etc/controlbox}"
    local host_data="${CONTROLBOX_DATA_DIR:-/var/lib/controlbox}"

    cb_load_env_file "${file}"

    if [[ "${CONTROLBOX_INSTALL_DIR:-}" == /host/* ]] || [[ -z "${CONTROLBOX_INSTALL_DIR:-}" ]]; then
        CONTROLBOX_INSTALL_DIR="${host_install}"
    fi
    if [[ "${CONTROLBOX_CONFIG_DIR:-}" == /host/* ]] || [[ -z "${CONTROLBOX_CONFIG_DIR:-}" ]]; then
        CONTROLBOX_CONFIG_DIR="${host_config}"
    fi
    if [[ "${CONTROLBOX_DATA_DIR:-}" == /host/* ]] || [[ -z "${CONTROLBOX_DATA_DIR:-}" ]]; then
        CONTROLBOX_DATA_DIR="${host_data}"
    fi

    export CONTROLBOX_INSTALL_DIR CONTROLBOX_CONFIG_DIR CONTROLBOX_DATA_DIR
}

cb_is_noninteractive_install() {
    [[ ! -t 0 ]] || [[ "${CONTROLBOX_ASSUME_YES:-}" == "true" ]]
}

cb_generate_uuid() {
    if command -v uuidgen >/dev/null 2>&1; then
        uuidgen | tr '[:upper:]' '[:lower:]'
    else
        cat /proc/sys/kernel/random/uuid 2>/dev/null || openssl rand -hex 16 | sed 's/\(........\)\(....\)\(xxxx\)\(xxxx\)\(xxxxxxxxxxxx\)/\1-\2-4\3-\4\5/'
    fi
}

cb_command_exists() {
    command -v "$1" >/dev/null 2>&1
}

cb_retry() {
    local max_attempts="$1"
    local delay="$2"
    shift 2
    local attempt=1
    while [[ ${attempt} -le ${max_attempts} ]]; do
        if "$@"; then
            return 0
        fi
        cb_warn "Intento ${attempt}/${max_attempts} fallido. Reintentando en ${delay}s..."
        sleep "${delay}"
        attempt=$((attempt + 1))
    done
    return 1
}

cb_confirm() {
    local prompt="${1:-¿Continuar?}"
    if [[ "${CONTROLBOX_ASSUME_YES:-}" == "true" ]]; then
        return 0
    fi
    if [[ ! -t 0 ]]; then
        cb_info "Instalación no interactiva (curl | bash): continuando automáticamente"
        return 0
    fi
    read -r -p "${prompt} [y/N]: " response
    [[ "${response}" =~ ^[Yy]$ ]]
}

cb_die() {
    cb_error "$@"
    exit 1
}

cb_on_error() {
    local exit_code=$?
    local line="${BASH_LINENO[0]:-unknown}"
    cb_error "Error en línea ${line} (código: ${exit_code})"
    if [[ "${CB_INSTALL_DEPLOYED:-}" == "1" ]] && [[ "${CB_INSTALL_SUMMARY_SHOWN:-}" != "1" ]]; then
        cb_warn "Mostrando credenciales de acceso al panel..."
        if [[ -f "${CONTROLBOX_INSTALLER_ROOT:-}/lib/credentials-display.sh" ]]; then
            # shellcheck source=lib/credentials-display.sh
            source "${CONTROLBOX_INSTALLER_ROOT}/lib/credentials-display.sh"
        fi
        if declare -f cb_print_post_install_summary >/dev/null 2>&1; then
            cb_print_post_install_summary "${CB_INSTALL_STARTED_AT:-$(date +%s)}" || true
        fi
    elif [[ -f "${CONTROLBOX_STATE_DIR}/rollback/active" ]]; then
        cb_warn "Iniciando restauración del estado anterior..."
        # shellcheck source=lib/rollback.sh
        source "${CONTROLBOX_INSTALLER_ROOT}/lib/rollback.sh"
        cb_rollback_execute || cb_error "Restauración falló. Revise ${CB_LOG_FILE}"
    fi
    cb_release_lock
    exit "${exit_code}"
}

cb_setup_traps() {
    trap cb_on_error ERR
    trap 'cb_release_lock' EXIT
}

cb_load_env_file() {
    local file="$1"
    [[ -f "${file}" ]] || return 0

    local file_size
    file_size="$(wc -c < "${file}" 2>/dev/null || echo 0)"
    if [[ "${file_size}" -gt 524288 ]]; then
        cb_warn "Archivo de entorno demasiado grande (${file_size} bytes): ${file}"
        return 1
    fi

    while IFS= read -r line || [[ -n "${line}" ]]; do
        line="${line%%#*}"
        line="${line#"${line%%[![:space:]]*}"}"
        line="${line%"${line##*[![:space:]]}"}"
        [[ -z "${line}" ]] && continue
        [[ "${line}" == *=* ]] || continue

        local key="${line%%=*}"
        local value="${line#*=}"
        key="${key#"${key%%[![:space:]]*}"}"
        key="${key%"${key##*[![:space:]]}"}"

        if [[ ! "${key}" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]; then
            echo "[WARN] Clave inválida omitida en ${file}: ${key}" >&2
            continue
        fi

        if [[ "${value}" =~ ^\"(.*)\"$ ]]; then
            value="${BASH_REMATCH[1]}"
        elif [[ "${value}" =~ ^\'(.*)\'$ ]]; then
            value="${BASH_REMATCH[1]}"
        fi

        if [[ ${#value} -gt 8192 ]]; then
            echo "[WARN] Valor omitido por tamaño (${key} en ${file})" >&2
            continue
        fi

        printf -v "${key}" '%s' "${value}"
        export "${key}"
    done < "${file}"
}

cb_load_defaults() {
    cb_load_env_file "${CONTROLBOX_INSTALLER_ROOT}/config/defaults.conf"
}

cb_load_installer_env() {
    cb_load_env_file "${CONTROLBOX_CONFIG_DIR}/installer.env"
}

cb_load_config() {
    cb_load_defaults
    cb_load_installer_env
}

cb_banner() {
    echo -e "${CB_BOLD}${CB_CYAN}"
    cat <<'BANNER'
   _____            _            _ ____            
  / ____|          | |          | |  _ \           
 | |     ___   __ _| | ___ _   _| | |_) | _____  __
 | |    / _ \ / _` | |/ __| | | | |  _ < / _ \ \/ /
 | |___| (_) | (_| | | (__| |_| | | |_) | (_) >  < 
  \_____\___/ \__,_|_|\___|\__,_|_|____/ \___/_/\_\
                                                   
        ControlBox Platform Installer
BANNER
    echo -e "${CB_NC}"
    echo -e "  Versión: ${CONTROLBOX_VERSION:-unknown}"
    echo -e "  URL: ${CONTROLBOX_INSTALL_URL:-https://install.grodtech.com}"
    echo ""
}

cb_save_install_state() {
    local key="$1"
    local value="$2"
    local state_file="${CONTROLBOX_STATE_DIR}/install.state"
    mkdir -p "${CONTROLBOX_STATE_DIR}"
    if [[ ${#value} -gt 8192 ]]; then
        cb_warn "Estado ${key} demasiado grande, omitiendo guardado"
        return 0
    fi
    if [[ -f "${state_file}" ]]; then
        grep -v "^${key}=" "${state_file}" > "${state_file}.tmp" 2>/dev/null || true
        mv "${state_file}.tmp" "${state_file}"
    fi
    echo "${key}=${value}" >> "${state_file}"
    chmod 640 "${state_file}"
    if id controlbox >/dev/null 2>&1; then
        chown controlbox:controlbox "${state_file}" 2>/dev/null || true
    fi
}

cb_get_install_state() {
    local key="$1"
    local state_file="${CONTROLBOX_STATE_DIR}/install.state"
    local value=""
    if [[ -f "${state_file}" ]]; then
        value="$(grep "^${key}=" "${state_file}" | tail -1 | cut -d'=' -f2-)"
        value="${value//\"/}"
        value="${value//\'/}"
        value="${value//$'\r'/}"
        value="${value//$'\n'/}"
        if [[ "${key}" =~ (PASSWORD|TOKEN|SECRET|KEY)$ ]] && [[ ${#value} -gt 512 ]]; then
            value=""
        fi
    fi
    echo "${value}"
}

cb_render_template() {
    local template="$1"
    local output="$2"
    local content
    content="$(cat "${template}")"
    local placeholders
    placeholders="$(grep -oE '\{\{[A-Z0-9_]+\}\}' "${template}" | sort -u || true)"
    while IFS= read -r placeholder; do
        [[ -z "${placeholder}" ]] && continue
        local var_name="${placeholder//\{\{/}"
        var_name="${var_name//\}\}/}"
        local var_value="${!var_name:-}"
        content="${content//\{\{${var_name}\}\}/${var_value}}"
    done <<< "${placeholders}"
    echo "${content}" > "${output}"
}

cb_secure_file() {
    local file="$1"
    local mode="${2:-600}"
    chmod "${mode}" "${file}"
    if id controlbox >/dev/null 2>&1; then
        chown controlbox:controlbox "${file}" 2>/dev/null || true
    fi
}

cb_wait_for_service() {
    local name="$1"
    local check_cmd="$2"
    local timeout="${3:-120}"
    local diagnose_cmd="${4:-}"
    local elapsed=0
    cb_info "Esperando servicio: ${name}..."
    while [[ ${elapsed} -lt ${timeout} ]]; do
        if eval "${check_cmd}"; then
            echo ""
            cb_success "Servicio ${name} disponible (${elapsed}s)"
            return 0
        fi
        printf "\r  ${CB_CYAN}Esperando %s... %ds / %ds${CB_NC}" "${name}" "${elapsed}" "${timeout}"
        sleep 5
        elapsed=$((elapsed + 5))
    done
    echo ""
    cb_error "Timeout esperando servicio: ${name}"
    if [[ -n "${diagnose_cmd}" ]]; then
        eval "${diagnose_cmd}" || true
    fi
    return 1
}
