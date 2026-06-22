#!/bin/sh
set -e

for dir in /var/lib/controlbox/sites /var/lib/controlbox/backups/databases /var/lib/controlbox/backups; do
  mkdir -p "$dir"
done

if [ "$(id -u)" = "0" ]; then
  chown -R controlbox:controlbox /var/lib/controlbox
  if [ -d /var/log/pure-ftpd ]; then
    chown -R controlbox:controlbox /var/log/pure-ftpd 2>/dev/null || true
  fi
  exec gosu controlbox "$@"
fi

exec "$@"
