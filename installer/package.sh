#!/usr/bin/env bash

set -euo pipefail

CONTROLBOX_VERSION="${CONTROLBOX_VERSION:-4.11.5}"
CONTROLBOX_INSTALL_URL="${CONTROLBOX_INSTALL_URL:-https://install.grodtech.com}"

echo "ControlBox Installer Packager v${CONTROLBOX_VERSION}"
echo "Este script empaqueta el instalador para distribución en ${CONTROLBOX_INSTALL_URL}"
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_DIR="${SCRIPT_DIR}/dist"
PACKAGE_NAME="controlbox-installer-${CONTROLBOX_VERSION}"
ARCHIVE="${OUTPUT_DIR}/${PACKAGE_NAME}.tar.gz"
STAGING_ROOT="${OUTPUT_DIR}/staging"
STAGING_DIR="${STAGING_ROOT}/controlbox-installer"

cb_normalize_text_files() {
    local root="$1"
    find "${root}" -type f \( \
        -name '*.sh' -o -name '*.conf' -o -name '*.yml' -o -name '*.yaml' \
        -o -name '*.tpl' -o -name '*.env' -o -name '*.json' \
    \) -exec bash -c 'tr -d "\r" < "$1" > "$1.lf" && mv "$1.lf" "$1"' _ {} +
}

cb_verify_no_crlf() {
    local root="$1"
    local bad_files=""

    if [[ "${OSTYPE:-}" == msys* ]] || [[ "${OSTYPE:-}" == mingw* ]] \
        || [[ "${MSYSTEM:-}" == MINGW64* ]] || uname -s 2>/dev/null | grep -qi mingw; then
        echo "AVISO: verificación CRLF omitida en Windows (los archivos se normalizan con LF al copiar)"
        return 0
    fi

    bad_files="$(find "${root}" -type f \( \
        -name '*.sh' -o -name '*.conf' -o -name '*.yml' -o -name '*.yaml' \
        -o -name '*.tpl' -o -name '*.env' -o -name '*.json' \
    \) -exec grep -l $'\r' {} + 2>/dev/null || true)"
    if [[ -n "${bad_files}" ]]; then
        echo "ERROR: Archivos con CRLF detectados (deben usar LF):"
        echo "${bad_files}"
        exit 1
    fi
}

cb_is_binary_asset() {
    local file="$1"
    case "${file,,}" in
        *.png|*.jpg|*.jpeg|*.gif|*.webp|*.ico|*.bmp|*.svg|*.woff|*.woff2|*.ttf|*.eot|*.zip|*.gz|*.br|*.pdf)
            return 0
            ;;
    esac
    return 1
}

cb_copy_file_to_staging() {
    local src="$1"
    local target="$2"
    mkdir -p "$(dirname "${target}")"
    if cb_is_binary_asset "${src}"; then
        cp -f "${src}" "${target}"
    else
        tr -d '\r' < "${src}" > "${target}"
    fi
}

cb_copy_app_source() {
    local repo_root="$(cd "${SCRIPT_DIR}/.." && pwd)"
    local dest="${STAGING_DIR}/src"

    for component in backend frontend; do
        local src="${repo_root}/${component}"
        [[ -d "${src}" ]] || continue
        find "${src}" -type f \
            ! -path '*/node_modules/*' \
            ! -path '*/.next/*' \
            ! -path '*/__pycache__/*' \
            ! -name '*.pyc' \
            -print0 | while IFS= read -r -d '' file; do
            local rel_path="${file#"${src}/"}"
            local target="${dest}/${component}/${rel_path}"
            cb_copy_file_to_staging "${file}" "${target}"
        done
    done
}

cb_copy_installer_tree() {
    local src_dir="$1"
    local dest_dir="$2"

    mkdir -p "${dest_dir}"
    find "${src_dir}" -mindepth 1 -type f \
        ! -path "${src_dir}/dist/*" \
        ! -name 'package.sh' \
        ! -name 'README.md' \
        ! -name 'verify-cdn.sh' \
        -print0 | while IFS= read -r -d '' file; do
        local rel_path="${file#"${src_dir}/"}"
        local target="${dest_dir}/${rel_path}"
        cb_copy_file_to_staging "${file}" "${target}"
    done
}

rm -rf "${STAGING_ROOT}"
mkdir -p "${STAGING_DIR}"

cb_copy_installer_tree "${SCRIPT_DIR}" "${STAGING_DIR}"
cb_copy_app_source
cb_normalize_text_files "${STAGING_DIR}"
cb_verify_no_crlf "${STAGING_DIR}"

chmod +x "${STAGING_DIR}"/*.sh "${STAGING_DIR}/lib"/*.sh

tar czf "${ARCHIVE}" -C "${STAGING_ROOT}" controlbox-installer

sed 's/\r$//' "${SCRIPT_DIR}/install.sh" | tr -d '\r' > "${OUTPUT_DIR}/install.sh"
chmod +x "${OUTPUT_DIR}/install.sh"

repo_root="$(cd "${SCRIPT_DIR}/.." && pwd)"
if [[ -f "${repo_root}/frontend/public/logo.png" ]]; then
    cp -f "${repo_root}/frontend/public/logo.png" "${OUTPUT_DIR}/logo.png"
fi
if [[ -f "${repo_root}/logo.png" ]]; then
    cp -f "${repo_root}/logo.png" "${OUTPUT_DIR}/logo.png"
fi

BOOTSTRAP_FIXES_B64="$(base64 -w0 "${SCRIPT_DIR}/lib/bootstrap-fixes.sh" 2>/dev/null || base64 "${SCRIPT_DIR}/lib/bootstrap-fixes.sh" | tr -d '\n')"
REINSTALL_B64="$(base64 -w0 "${SCRIPT_DIR}/lib/reinstall.sh" 2>/dev/null || base64 "${SCRIPT_DIR}/lib/reinstall.sh" | tr -d '\n')"
sed -i "s|__BOOTSTRAP_FIXES_B64__|${BOOTSTRAP_FIXES_B64}|g" "${OUTPUT_DIR}/install.sh"
sed -i "s|__REINSTALL_B64__|${REINSTALL_B64}|g" "${OUTPUT_DIR}/install.sh"
cb_verify_no_crlf "${OUTPUT_DIR}"

echo "Verificando paquete..."
tar tzf "${ARCHIVE}" | head -5 || true
test -f "${OUTPUT_DIR}/install.sh"
test -f "${STAGING_DIR}/install.sh"
test -f "${STAGING_DIR}/lib/common.sh"
test -f "${STAGING_DIR}/lib/bootstrap-fixes.sh"
test -f "${STAGING_DIR}/lib/reinstall.sh"
test -f "${STAGING_DIR}/src/backend/Dockerfile"
test -f "${STAGING_DIR}/src/frontend/Dockerfile"
test -f "${STAGING_DIR}/src/frontend/public/logo.png"
logo_src="${repo_root}/frontend/public/logo.png"
logo_staged="${STAGING_DIR}/src/frontend/public/logo.png"
if [[ -f "${logo_src}" ]] && [[ -f "${logo_staged}" ]]; then
    src_size="$(wc -c < "${logo_src}" | tr -d ' ')"
    staged_size="$(wc -c < "${logo_staged}" | tr -d ' ')"
    if [[ "${src_size}" != "${staged_size}" ]]; then
        echo "ERROR: logo.png corrupto en el paquete (${staged_size} bytes vs ${src_size} originales)"
        exit 1
    fi
    if ! head -c 8 "${logo_staged}" | grep -q $'PNG'; then
        echo "ERROR: logo.png no tiene cabecera PNG válida"
        exit 1
    fi
fi
test -f "${STAGING_DIR}/config/defaults.conf"

if [[ -f "${STAGING_DIR}/src/frontend/src/app/icon.png" ]]; then
    echo "ERROR: src/frontend/src/app/icon.png no debe incluirse (usar metadata icons en layout.tsx)"
    exit 1
fi

repo_root="$(cd "${SCRIPT_DIR}/.." && pwd)"
if [[ -f "${repo_root}/frontend/package.json" ]] && command -v npm >/dev/null 2>&1; then
    echo "Verificando TypeScript del panel..."
    if [[ ! -d "${repo_root}/frontend/node_modules" ]]; then
        (cd "${repo_root}/frontend" && npm ci --prefer-offline 2>/dev/null) || true
    fi
    if [[ -d "${repo_root}/frontend/node_modules" ]]; then
        (cd "${repo_root}/frontend" && npm run typecheck) || {
            echo "ERROR: typecheck del panel falló. Corrija errores TypeScript antes de empaquetar."
            exit 1
        }
    else
        echo "AVISO: node_modules no disponible; omitiendo typecheck del panel"
    fi
fi

if grep -q 'PANEL_PORT' "${STAGING_DIR}/templates/docker-compose.platform.yml"; then
    echo "ERROR: docker-compose.platform.yml aún contiene PANEL_PORT (debe usar docker-compose.ports.yml)"
    exit 1
fi

dist_build="$(grep '^CONTROLBOX_BOOTSTRAP_BUILD=' "${OUTPUT_DIR}/install.sh" | head -1 | cut -d'"' -f2)"
tar_build="$(grep '^CONTROLBOX_BOOTSTRAP_BUILD=' "${STAGING_DIR}/install.sh" | head -1 | cut -d'"' -f2)"
if [[ "${dist_build}" != "${tar_build}" ]]; then
    echo "ERROR: build dist/install.sh (${dist_build}) != tar/install.sh (${tar_build})"
    exit 1
fi

if grep -q '__BOOTSTRAP_FIXES_B64__' "${OUTPUT_DIR}/install.sh"; then
    echo "ERROR: dist/install.sh no tiene parches embebidos (base64 sin reemplazar)"
    exit 1
fi

echo "Build verificado: ${dist_build}"
echo "Archivos en tar: $(tar tzf "${ARCHIVE}" | wc -l)"

echo "Paquete creado: ${ARCHIVE}"
echo "Bootstrap:      ${OUTPUT_DIR}/install.sh"
mkdir -p "${OUTPUT_DIR}/lib"
cp -f "${SCRIPT_DIR}/lib/bootstrap-fixes.sh" "${OUTPUT_DIR}/lib/bootstrap-fixes.sh"
cp -f "${SCRIPT_DIR}/lib/reinstall.sh" "${OUTPUT_DIR}/lib/reinstall.sh"
(
    cd "${OUTPUT_DIR}"
    sha256sum install.sh "${PACKAGE_NAME}.tar.gz" > CHECKSUMS.txt 2>/dev/null || \
        shasum -a 256 install.sh "${PACKAGE_NAME}.tar.gz" > CHECKSUMS.txt
)
echo "Checksums:      ${OUTPUT_DIR}/CHECKSUMS.txt"
cat "${OUTPUT_DIR}/CHECKSUMS.txt"
echo ""
echo "Despliegue en CDN:"
echo "  ${CONTROLBOX_INSTALL_URL}/install.sh"
echo "  ${CONTROLBOX_INSTALL_URL}/controlbox-installer-${CONTROLBOX_VERSION}.tar.gz"
echo "  ${CONTROLBOX_INSTALL_URL}/lib/bootstrap-fixes.sh"
echo "  ${CONTROLBOX_INSTALL_URL}/lib/reinstall.sh"
