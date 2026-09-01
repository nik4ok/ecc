#!/usr/bin/env bash
# Install NOVA cashier as a systemd service.
# On the office VPS (no Docker): SSH provision to the door.
# On the door itself (legacy): docker exec amnezia-awg2.
# Run from the ecc repo:
#   bash infra/scripts/10_install_controlplane.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SRC="$ROOT/infra/controlplane"
DEST=/opt/nova-controlplane
DBDIR=/var/lib/nova-controlplane
KEYDIR=/etc/nova-controlplane
ENV_FILE=/etc/nova-controlplane.env
SERVERS="$ROOT/infra/servers.json"

if [[ ! -f "$SERVERS" ]]; then
  echo "Нет $SERVERS — на офисе: git sparse-checkout set infra/bot infra/scripts infra/controlplane"
  echo "затем: git checkout HEAD -- infra/servers.json"
  exit 1
fi

MODE=ssh
if command -v docker >/dev/null 2>&1 && docker ps --format '{{.Names}}' 2>/dev/null | grep -qx 'amnezia-awg2'; then
  MODE=docker
fi

mkdir -p "$DEST" "$DBDIR" "$KEYDIR"
chmod 700 "$DBDIR" "$KEYDIR"
cp -a "$SRC"/*.py "$DEST/"
cp -a "$SRC/dashboard.html" "$DEST/"
cp -a "$SRC/demo_awg_show.txt" "$DEST/"
cp -a "$SERVERS" "$DEST/servers.json"
install -m 644 "$SRC/nova-controlplane.service" /etc/systemd/system/nova-controlplane.service

if [[ ! -f "$ENV_FILE" ]]; then
  umask 077
  password="$(openssl rand -base64 18 | tr -d '/+=' | head -c 20)"
  {
    printf 'NOVA_DASHBOARD_USER=nova\n'
    printf 'NOVA_DASHBOARD_PASSWORD=%s\n' "$password"
    printf 'NOVA_PROVISION_MODE=%s\n' "$MODE"
    if [[ "$MODE" == "ssh" ]]; then
      printf 'NOVA_EDGE_SSH=root@89.19.217.190\n'
      printf 'NOVA_EDGE_SSH_KEY=%s/edge_ed25519\n' "$KEYDIR"
    fi
  } > "$ENV_FILE"
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

if [[ "$MODE" == "ssh" && ! -f "$KEYDIR/edge_ed25519" ]]; then
  echo "Режим ssh: положите ключ в $KEYDIR/edge_ed25519 и: systemctl start nova-controlplane"
  echo "Касса скопирована, службу не стартую — без ключа дверь не откроется."
  exit 0
fi

systemctl restart nova-controlplane.service
sleep 1
systemctl --no-pager --full status nova-controlplane.service | head -20
echo
echo "Касса: http://$(hostname -I | awk '{print $1}'):8090"
echo "Журнал: journalctl -u nova-controlplane -f"
