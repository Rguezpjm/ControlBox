#!/usr/bin/env bash
set -euo pipefail

CDN_URL="${1:-https://install.grodtech.com}"
EXPECTED_BUILD="${2:-20250621-5}"
EXPECTED_INSTALL_BYTES_MIN="${3:-9500}"
EXPECTED_TAR_TOP="${4:-controlbox-installer/}"

echo "Verificando CDN: ${CDN_URL}"
echo ""

tmp_dir="$(mktemp -d)"
trap 'rm -rf "${tmp_dir}"' EXIT

install_file="${tmp_dir}/install.sh"
tar_file="${tmp_dir}/installer.tar.gz"

echo "==> install.sh"
if ! curl -fsSL "${CDN_URL}/install.sh" -o "${install_file}"; then
    echo "FALLO: install.sh no accesible (HTTP error o 404)"
    exit 1
fi

install_bytes="$(wc -c < "${install_file}")"
echo "    Tamaño: ${install_bytes} bytes (esperado >= ${EXPECTED_INSTALL_BYTES_MIN})"

if ! head -1 "${install_file}" | grep -q '^#!/usr/bin/env bash'; then
    echo "FALLO: install.sh no parece un script bash (¿HTML de error?)"
    head -5 "${install_file}"
    exit 1
fi

if grep -q 'cb_patch_legacy_package\|CONTROLBOX_BOOTSTRAP_BUILD' "${install_file}"; then
    build_id="$(grep 'CONTROLBOX_BOOTSTRAP_BUILD=' "${install_file}" | head -1 | cut -d'"' -f2 || true)"
    echo "    Build: ${build_id:-detectado}"
else
    echo "FALLO: install.sh es una versión antigua (sin parches de bootstrap)"
    exit 1
fi

echo ""
echo "==> controlbox-installer-1.1.0.tar.gz"
if ! curl -fsSL "${CDN_URL}/controlbox-installer-1.1.0.tar.gz" -o "${tar_file}"; then
    echo "FALLO: tar.gz no accesible"
    exit 1
fi

tar_bytes="$(wc -c < "${tar_file}")"
echo "    Tamaño: ${tar_bytes} bytes"

tar_top="$(tar tzf "${tar_file}" | head -1)"
echo "    Carpeta raíz: ${tar_top}"
if [[ "${tar_top}" != "${EXPECTED_TAR_TOP}" ]]; then
    echo "    AVISO: se esperaba ${EXPECTED_TAR_TOP} (paquete antiguo, bootstrap lo parcheará)"
fi

cron_line="$(tar xOzf "${tar_file}" "${tar_top}config/defaults.conf" 2>/dev/null | grep BACKUP_CRON || true)"
echo "    Cron config: ${cron_line:-no encontrado}"
if [[ "${cron_line}" == *'BACKUP_CRON_SCHEDULE=0 3'* && "${cron_line}" != *'"'* ]]; then
    echo "    AVISO: cron sin comillas en tar (bootstrap lo parcheará si install.sh es nuevo)"
fi

echo ""
echo "OK: CDN accesible. Si el build es ${EXPECTED_BUILD} y tamaño >= ${EXPECTED_INSTALL_BYTES_MIN}, puede instalar."
echo ""
echo "curl -fsSL ${CDN_URL}/install.sh | bash"
