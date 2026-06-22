# ControlBox Installer

Instalador profesional tipo aaPanel para la plataforma ControlBox.

## Instalación rápida

```bash
curl -fsSL https://install.grodtech.com/install.sh | bash
```

El asistente interactivo solicita dominio (opcional), datos del administrador y puerto del panel. Al finalizar muestra:

```
URL PANEL:     IP_VPS:PUERTO/ControlBox_Panel
USUARIO:       email@administrador
CONTRASEÑA:    ********
```

## Instalación no interactiva

```bash
curl -fsSL https://install.grodtech.com/install.sh | \
  CONTROLBOX_PRIMARY_DOMAIN=grodtech.com \
  CONTROLBOX_ADMIN_EMAIL=admin@grodtech.com \
  CONTROLBOX_TENANT_NAME="Mi Empresa" \
  CONTROLBOX_TENANT_SLUG=mi-empresa \
  CONTROLBOX_TENANT_ADMIN_EMAIL=admin@mi-empresa.com \
  CONTROLBOX_TENANT_ADMIN_PASSWORD='ContraseñaSegura123!' \
  CONTROLBOX_TENANT_ADMIN_FULL_NAME="Administrador" \
  CONTROLBOX_PANEL_PORT=8475 \
  CONTROLBOX_ASSUME_YES=true \
  bash
```

## Instalación local (desarrollo)

```bash
cd installer
sudo CONTROLBOX_INSTALLER_ROOT=$(pwd) bash install.sh
```

Si el repositorio incluye `frontend/`, el instalador construye la imagen del panel localmente.

## Componentes instalados

- Docker + Docker Compose
- PostgreSQL
- Redis
- Traefik (SSL automático Let's Encrypt)
- MinIO
- Panel de administración (puerto dedicado + `/ControlBox_Panel`)
- Prometheus
- Grafana
- Loki + Promtail
- Supabase Self-Hosted (Kong, Auth, REST, Realtime, Storage, Studio)

## Primer tenant

El instalador crea automáticamente el primer tenant con `REGISTRATION_ENABLED=false`.
Usa el módulo `controlbox.installer.bootstrap_tenant` y un token `INSTALLER_BOOTSTRAP_TOKEN`.

## Configuración post-instalación (panel)

Tras iniciar sesión, Owner/Administrator completan **Settings**:

- **Producción** — rotación de secretos y checklist
- **Acceso al panel** — puerto y ruta `/ControlBox_Panel`
- **Alertas** — umbrales CPU/RAM/disco (notificaciones en campana)
- **Seguridad** — enlace a TOTP/MFA

```bash
sudo controlbox apply-panel   # tras cambiar ruta del panel
```

## Comandos CLI

```bash
controlbox status
controlbox update
controlbox repair
controlbox backup
controlbox domains grodtech.com admin@grodtech.com
controlbox logs
controlbox uninstall
```

## Scripts

| Script | Descripción |
|--------|-------------|
| `install.sh` | Instalación completa idempotente con asistente |
| `update.sh` | Actualiza imágenes y configuración |
| `repair.sh` | Diagnóstico y reparación de servicios |
| `uninstall.sh` | Desinstalación segura con preservación de datos |

## Variables de entorno

| Variable | Descripción |
|----------|-------------|
| `CONTROLBOX_PRIMARY_DOMAIN` | Dominio principal (opcional) |
| `CONTROLBOX_ADMIN_EMAIL` | Email para Let's Encrypt |
| `CONTROLBOX_TENANT_NAME` | Nombre de la organización |
| `CONTROLBOX_TENANT_SLUG` | Slug del tenant |
| `CONTROLBOX_TENANT_ADMIN_EMAIL` | Email del administrador |
| `CONTROLBOX_TENANT_ADMIN_PASSWORD` | Contraseña (mín. 12 caracteres) |
| `CONTROLBOX_TENANT_ADMIN_FULL_NAME` | Nombre completo del administrador |
| `CONTROLBOX_PANEL_PORT` | Puerto del panel en el VPS |
| `CONTROLBOX_ASSUME_YES` | Omitir confirmaciones |
| `CONTROLBOX_FORCE_INSTALL` | Forzar en OS no certificado |
| `CONTROLBOX_REINSTALL` | Reinstalar si ya existe |
| `CONTROLBOX_PURGE_DATA` | Eliminar datos en uninstall |

## Rutas del sistema

| Ruta | Contenido |
|------|-----------|
| `/opt/controlbox` | Instalación y docker-compose |
| `/etc/controlbox` | Configuración y credenciales |
| `/var/lib/controlbox` | Datos persistentes |
| `/var/log/controlbox` | Logs del instalador y backups |

## Empaquetado para CDN

```bash
cd installer
bash package.sh
```

Genera `dist/controlbox-installer-1.0.0.tar.gz` para hospedar en `install.grodtech.com`.

## Rollback

El instalador crea snapshots automáticos en `/var/lib/controlbox/state/rollback/`.
En caso de error durante la instalación, se ejecuta rollback automático.

```bash
sudo bash /opt/controlbox/repair.sh --rollback
```

## Seguridad

- Credenciales generadas con `openssl rand` (permisos 600)
- Firewall UFW/firewalld configurado automáticamente (SSH, 80, 443, puerto del panel)
- SSL TLS 1.2+ via Traefik
- Registro público deshabilitado por defecto
- Bootstrap del primer tenant con token de instalación
- Sin secretos en logs
- Backup automático diario a las 03:00
