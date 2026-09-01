#!/usr/bin/env bash
# Install NOVA cashier as a systemd service on the Amnezia node.
# Run on the VPS from the ecc repo:
#   bash infra/scripts/10_install_controlplane.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SRC="$ROOT/infra/controlplane"
DEST=/opt/nova-controlplane
DBDIR=/var/lib/nova-controlplane

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is required"
  exit 1
fi
if ! docker ps --format '{{.Names}}' | grep -qx 'amnezia-awg2'; then
  echo "container amnezia-awg2 is not running"
  docker ps -a
  exit 1
fi

mkdir -p "$DEST" "$DBDIR"
cp -a "$SRC"/*.py "$DEST/"
cp -a "$SRC/dashboard.html" "$DEST/"
cp -a "$SRC/demo_awg_show.txt" "$DEST/"
cp -a "$ROOT/infra/servers.json" "$DEST/servers.json"
install -m 644 "$SRC/nova-controlplane.service" /etc/systemd/system/nova-controlplane.service

ENV_FILE=/etc/nova-controlplane.env
if [[ ! -f "$ENV_FILE" ]]; then
  umask 077
  password="$(openssl rand -base64 18 | tr -d '/+=' | head -c 20)"
  printf 'NOVA_DASHBOARD_USER=nova\nNOVA_DASHBOARD_PASSWORD=%s\n' "$password" > "$ENV_FILE"
  chmod 600 "$ENV_FILE"
  echo "Пароль дашборда записан в $ENV_FILE (логин nova). Посмотреть: cat $ENV_FILE"
else
  echo "Оставляю существующий $ENV_FILE"
fi

if command -v ufw >/dev/null 2>&1; then
  ufw allow 8090/tcp comment 'NOVA cashier dashboard' >/dev/null 2>&1 || true
fi

systemctl daemon-reload
systemctl enable nova-controlplane.service
systemctl restart nova-controlplane.service
sleep 1
systemctl --no-pager --full status nova-controlplane.service | head -20
echo
echo "Касса: http://$(hostname -I | awk '{print $1}'):8090"
echo "Журнал: journalctl -u nova-controlplane -f"
