#!/usr/bin/env bash
# Install the NOVA Telegram shop bot as a systemd service.
# Run on the VPS from the ecc repo:
#   bash infra/scripts/11_install_bot.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SRC="$ROOT/infra/bot"
DEST=/opt/nova-bot
DATADIR=/var/lib/nova-bot
ENV_FILE=/etc/nova-bot.env

mkdir -p "$DEST" "$DATADIR"
chmod 700 "$DATADIR"
cp -a "$SRC/shop.py" "$SRC/handlers.py" "$SRC/telegram_api.py" "$SRC/bot.py" "$SRC/messages.py" "$DEST/"
install -m 644 "$SRC/nova-bot.service" /etc/systemd/system/nova-bot.service

if [[ ! -f "$ENV_FILE" ]]; then
  umask 077
  cat > "$ENV_FILE" <<'EOF'
NOVA_BOT_TOKEN=
NOVA_PAYMENTS=off
NOVA_STARS_PRICE=250
EOF
  chmod 600 "$ENV_FILE"
  echo "Заполните токен: $ENV_FILE"
else
  echo "Оставляю существующий $ENV_FILE"
fi

if [[ ! -f "$DATADIR/NOVA.apk" ]]; then
  echo "Положите APK в $DATADIR/NOVA.apk — без файла бот примет оплату, но не сможет отдать приложение."
else
  chmod 600 "$DATADIR/NOVA.apk"
fi

systemctl daemon-reload
systemctl enable nova-bot.service
if grep -q '^NOVA_BOT_TOKEN=.\+' "$ENV_FILE"; then
  systemctl restart nova-bot.service
  sleep 1
  systemctl --no-pager --full status nova-bot.service | head -20
else
  echo "Токен пустой — службу не стартую. Впишите NOVA_BOT_TOKEN и: systemctl start nova-bot"
fi

echo "Журнал: journalctl -u nova-bot -f"
