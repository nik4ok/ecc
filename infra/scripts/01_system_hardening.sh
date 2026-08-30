#!/usr/bin/env bash
# ==============================================================================
# VPN Node Provisioning & Hardening Script (Ubuntu / Debian)
# Targets: Node 1 (Netherlands - 92.51.46.12)
# ==============================================================================
set -euo pipefail

echo "========================================================="
echo " [1/5] Starting System Hardening & TCP Tuning on $(hostname)"
echo "========================================================="

export DEBIAN_FRONTEND=noninteractive

# Update system
apt-get update && apt-get upgrade -y
apt-get install -y curl wget git tar ufw fail2ban jq openssl iproute2 qrencode

# Setup 1GB Swap to prevent OOM on 1GB RAM
if [ ! -f /swapfile ]; then
    echo "[+] Creating 1GB Swap file..."
    fallocate -l 1G /swapfile || dd if=/dev/zero of=/swapfile bs=1M count=1024
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

# Enable TCP BBR & Kernel Performance Optimizations
cat <<'EOF' > /etc/sysctl.d/99-vpn-tuning.conf
# Network buffer & BBR settings
net.core.default_qdisc = fq
net.ipv4.tcp_congestion_control = bbr
net.ipv4.tcp_fastopen = 3
net.ipv4.ip_forward = 1
net.ipv6.conf.all.forwarding = 1
net.ipv4.tcp_fin_timeout = 20
net.ipv4.tcp_tw_reuse = 1
net.core.rmem_max = 67108864
net.core.wmem_max = 67108864
net.ipv4.tcp_rmem = 4096 87380 33554432
net.ipv4.tcp_wmem = 4096 65536 33554432
vm.swappiness = 10

# Anti-Spoofing & Syn-Flood Protection
net.ipv4.conf.all.rp_filter = 1
net.ipv4.conf.default.rp_filter = 1
net.ipv4.tcp_syncookies = 1
net.ipv4.conf.all.accept_redirects = 0
net.ipv4.conf.all.send_redirects = 0
EOF
sysctl --system

# Restrict systemd journal to prevent disk filling on 15GB NVMe
mkdir -p /etc/systemd/journald.conf.d/
cat <<'EOF' > /etc/systemd/journald.conf.d/size.conf
[Journal]
SystemMaxUse=200M
EOF
systemctl restart systemd-journald

# UFW Firewall configuration
echo "[+] Configuring UFW Firewall..."
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp comment 'SSH'
ufw allow 443/tcp comment 'VLESS Reality (TCP)'
ufw allow 443/udp comment 'Hysteria 2 (UDP)'
echo "y" | ufw enable || true

# Fail2ban configuration
echo "[+] Configuring Fail2ban..."
cat <<'EOF' > /etc/fail2ban/jail.local
[DEFAULT]
bantime = 1d
findtime = 10m
maxretry = 5

[sshd]
enabled = true
port = ssh
EOF
systemctl restart fail2ban || true

echo "System hardening & optimization completed successfully."
