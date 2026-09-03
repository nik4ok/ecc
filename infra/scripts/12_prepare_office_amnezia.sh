#!/usr/bin/env bash
# Prepare the OFFICE VPS so the official Amnezia app can finish AmneziaWG.
# Error 202 "docker container missing" on 1 GB Ubuntu is usually AppArmor, no swap, or OOM.
#
# Run on 72.56.118.39 as root, not on the door (89.19.217.190).
#   bash infra/scripts/12_prepare_office_amnezia.sh
set -euo pipefail

UDP_PORT="${NOVA_TEMP_AWG_PORT:-41820}"

if docker ps --format '{{.Names}}' 2>/dev/null | grep -qx 'amnezia-awg2'; then
  echo "Это похоже на дверь: крутится amnezia-awg2. Скрипт только для офиса. Выхожу."
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y docker.io containerd apparmor apparmor-utils ufw curl

systemctl enable --now containerd docker
aa-status >/dev/null 2>&1 || true

if [ ! -f /swapfile ]; then
  echo "Делаю swap 1 ГБ — без него Docker на 1 ГБ RAM часто убивает контейнер."
  fallocate -l 1G /swapfile || dd if=/dev/zero of=/swapfile bs=1M count=1024
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  grep -q '/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

sysctl -w net.ipv4.ip_forward=1 >/dev/null
mkdir -p /etc/sysctl.d
if ! grep -q 'net.ipv4.ip_forward=1' /etc/sysctl.d/99-nova-office-amnezia.conf 2>/dev/null; then
  echo 'net.ipv4.ip_forward=1' > /etc/sysctl.d/99-nova-office-amnezia.conf
fi

# Leftovers from a failed Amnezia app install (container starts and vanishes).
if command -v docker >/dev/null 2>&1; then
  mapfile -t stale < <(docker ps -a --format '{{.Names}}' | grep -E '^amnezia-' || true)
  if ((${#stale[@]})); then
    echo "Снимаю недоставленные контейнеры Amnezia: ${stale[*]}"
    docker rm -f "${stale[@]}" >/dev/null
  fi
fi

if command -v ufw >/dev/null 2>&1; then
  ufw allow 22/tcp comment 'SSH' >/dev/null 2>&1 || true
  ufw allow "${UDP_PORT}/udp" comment 'temp AmneziaWG on office' >/dev/null 2>&1 || true
  ufw allow 8090/tcp comment 'NOVA cashier' >/dev/null 2>&1 || true
  ufw --force enable >/dev/null 2>&1 || true
fi

echo
echo "Готово. Docker, AppArmor и swap на месте."
echo "Кассу и бота не трогал."
echo
echo "Дальше только из Amnezia на телефоне, который УЖЕ в другом VPN"
echo "(NOVA на двери 89.19.217.190, не этот офис):"
echo
echo "  1. Добавить сервер: 72.56.118.39, пользователь root, ваш SSH-ключ или пароль."
echo "  2. Протокол один: AmneziaWG. Не ставить Xray/OpenVPN/SS — памяти не хватит."
echo "  3. Порт UDP ${UDP_PORT}, не 443 и не 39783."
echo "  4. Дождаться зелёного контейнера: docker ps | grep amnezia-awg"
echo "  5. Поделиться ключом vpn:// с гостями. Потом этот VPN снести."
echo
echo "Проверка сейчас:"
systemctl is-active docker
free -h | head -2
docker ps -a --format 'table {{.Names}}\t{{.Status}}' || true
echo
echo "Снести позже:"
echo "  docker ps -a --format '{{.Names}}' | grep '^amnezia-' | xargs -r docker rm -f"
echo "  ufw delete allow ${UDP_PORT}/udp"
echo "  Кассу и бота не удалять."
