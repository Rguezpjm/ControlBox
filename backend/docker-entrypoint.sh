#!/bin/sh
set -e

writable_dirs="/var/lib/controlbox/sites /var/lib/controlbox/backups /var/lib/controlbox/backups/databases"

for dir in $writable_dirs; do
  mkdir -p "$dir"
done

if [ "$(id -u)" = "0" ]; then
  for dir in $writable_dirs; do
    chown -R controlbox:controlbox "$dir" 2>/dev/null || true
  done
  if [ -d /var/log/pure-ftpd ]; then
    chown -R controlbox:controlbox /var/log/pure-ftpd 2>/dev/null || true
  fi
  exec gosu controlbox "$@"
fi

exec "$@"
