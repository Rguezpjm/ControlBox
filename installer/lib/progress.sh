#!/usr/bin/env bash

CB_PROGRESS_ENABLED="${CB_PROGRESS_ENABLED:-1}"
CB_PROGRESS_TOTAL="${CB_PROGRESS_TOTAL:-16}"
CB_PROGRESS_CURRENT="${CB_PROGRESS_CURRENT:-0}"
CB_PROGRESS_START="${CB_PROGRESS_START:-0}"

cb_progress_init() {
    CB_PROGRESS_TOTAL="${1:-16}"
    CB_PROGRESS_CURRENT=0
    CB_PROGRESS_START="$(date +%s)"
    echo ""
    echo -e "${CB_BOLD}Progreso de instalación ControlBox${CB_NC}"
    cb_progress_render ""
}

cb_progress_elapsed() {
    local now elapsed mins secs
    now="$(date +%s)"
    elapsed=$(( now - CB_PROGRESS_START ))
    mins=$(( elapsed / 60 ))
    secs=$(( elapsed % 60 ))
    printf '%02d:%02d' "${mins}" "${secs}"
}

cb_progress_render() {
    local label="${1:-}"
    [[ "${CB_PROGRESS_ENABLED}" == "1" ]] || return 0

    local pct=0 width=36 filled empty bar
    if (( CB_PROGRESS_TOTAL > 0 )); then
        pct=$(( CB_PROGRESS_CURRENT * 100 / CB_PROGRESS_TOTAL ))
    fi
    filled=$(( pct * width / 100 ))
    empty=$(( width - filled ))
    bar="[$(printf '%*s' "${filled}" '' | tr ' ' '#')$(printf '%*s' "${empty}" '' | tr ' ' '-')]"

    echo ""
    echo -e "${CB_CYAN}${bar}${CB_NC} ${pct}% · paso ${CB_PROGRESS_CURRENT}/${CB_PROGRESS_TOTAL} · $(cb_progress_elapsed)"
    if [[ -n "${label}" ]]; then
        echo -e "  ${CB_BOLD}${label}${CB_NC}"
    fi
}

cb_progress_step() {
    local label="${1:-}"
    CB_PROGRESS_CURRENT=$((CB_PROGRESS_CURRENT + 1))
    cb_progress_render "${label}"
}

cb_progress_note() {
    cb_log "PROGRESS" "$@"
    echo -e "  ${CB_BLUE}→${CB_NC} $*"
}

cb_progress_long_hint() {
    cb_progress_note "Esta fase puede tardar varios minutos (build Docker: ~5-20 min)."
    cb_progress_note "La instalación sigue activa. Log completo: ${CB_LOG_FILE}"
    cb_progress_note "Otra terminal: tail -f ${CB_LOG_FILE}"
}

cb_run_stream() {
    local description="${1:-Ejecutando...}"
    shift
    cb_progress_long_hint
    cb_log "STREAM" "${description}: $*"
    echo -e "  ${CB_BOLD}${description}${CB_NC}"
    echo ""

    set -o pipefail
    if "$@" 2>&1 | tee -a "${CB_LOG_FILE}"; then
        echo ""
        return 0
    fi
    local rc=${PIPESTATUS[0]}
    echo ""
    cb_error "${description} falló (código ${rc}). Revise ${CB_LOG_FILE}"
    return "${rc}"
}
