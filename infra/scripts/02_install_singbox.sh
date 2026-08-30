#!/usr/bin/env bash
# ==============================================================================
# Sing-Box Core & Inbound Deployer (VLESS Reality + Hysteria 2)
# ==============================================================================
set -euo pipefail

echo "========================================================="
echo " [2/5] Installing and Configuring sing-box v1.11+"
echo "========================================================="

# Fetch latest sing-box
ARCH="amd64"
LATEST_VER=$(curl -s "https://api.github.com/repos/SagerNet/sing-box/releases/latest" | jq -r '.tag_name' | sed 's/^v//')
if [ -z "$LATEST_VER" ] || [ "$LATEST_VER" = "null" ]; then
    LATEST_VER="1.11.0"
fi

echo "[+] Downloading sing-box v${LATEST_VER}..."
curl -Lo sing-box.tar.gz "https://github.com/SagerNet/sing-box/releases/download/v${LATEST_VER}/sing-box-${LATEST_VER}-linux-${ARCH}.tar.gz"
tar -xzf sing-box.tar.gz
mv "sing-box-${LATEST_VER}-linux-${ARCH}/sing-box" /usr/local/bin/
rm -rf sing-box.tar.gz "sing-box-${LATEST_VER}-linux-${ARCH}"
chmod +x /usr/local/bin/sing-box

mkdir -p /etc/sing-box

# Generate Reality Keys
echo "[+] Generating Reality Keys..."
KEYPAIR=$(sing-box generate reality-keypair)
PRIVATE_KEY=$(echo "$KEYPAIR" | grep "PrivateKey" | awk '{print $2}')
PUBLIC_KEY=$(echo "$KEYPAIR" | grep "PublicKey" | awk '{print $2}')
UUID=$(sing-box generate uuid)
SHORT_ID=$(openssl rand -hex 8)
HY2_PASS=$(openssl rand -base64 16 | tr -dc 'a-zA-Z0-9')
HY2_OBFS_PASS=$(openssl rand -hex 8)

# Target SNI for stealth masking
SNI_DOMAIN="dl.google.com"

# Generate sing-box server config
# Fix notes applied (v1.13+):
#   1. dns block with ipv4_only strategy — prevents hangs on broken IPv6 at hoster
#   2. sniff + sniff_override_destination on VLESS inbound — enables domain routing
#   3. domain_strategy ipv4_only on inbound — resolved destination is always A record
#   4. domain_strategy ipv4_only on direct outbound — outbound never dials AAAA
#   5. route block with auto_detect_interface — binds egress to the default NIC
cat <<EOF > /etc/sing-box/config.json
{
  "log": {
    "level": "info",
    "timestamp": true
  },
  "dns": {
    "servers": [
      {
        "tag": "cf-doh",
        "address": "https://1.1.1.1/dns-query",
        "strategy": "ipv4_only",
        "detour": "direct"
      },
      {
        "tag": "google-doh",
        "address": "https://8.8.8.8/dns-query",
        "strategy": "ipv4_only",
        "detour": "direct"
      }
    ],
    "final": "cf-doh",
    "fallback_delay": "1s",
    "independent_cache": true,
    "strategy": "ipv4_only"
  },
  "inbounds": [
    {
      "type": "vless",
      "tag": "vless-reality-in",
      "listen": "::",
      "listen_port": 443,
      "sniff": true,
      "sniff_override_destination": true,
      "domain_strategy": "ipv4_only",
      "users": [
        {
          "uuid": "${UUID}",
          "flow": "xtls-rprx-vision"
        }
      ],
      "tls": {
        "enabled": true,
        "server_name": "${SNI_DOMAIN}",
        "reality": {
          "enabled": true,
          "handshake": {
            "server": "${SNI_DOMAIN}",
            "server_port": 443
          },
          "private_key": "${PRIVATE_KEY}",
          "short_id": [
            "${SHORT_ID}"
          ]
        }
      }
    },
    {
      "type": "hysteria2",
      "tag": "hy2-in",
      "listen": "::",
      "listen_port": 443,
      "sniff": true,
      "sniff_override_destination": true,
      "domain_strategy": "ipv4_only",
      "users": [
        {
          "password": "${HY2_PASS}"
        }
      ],
      "obfs": {
        "type": "salamander",
        "password": "${HY2_OBFS_PASS}"
      },
      "masquerade": "https://${SNI_DOMAIN}"
    }
  ],
  "outbounds": [
    {
      "type": "direct",
      "tag": "direct",
      "domain_strategy": "ipv4_only"
    },
    {
      "type": "block",
      "tag": "block"
    }
  ],
  "route": {
    "auto_detect_interface": true,
    "final": "direct"
  }
}
EOF

# Setup systemd service
cat <<'EOF' > /etc/systemd/system/sing-box.service
[Unit]
Description=sing-box service
Documentation=https://sing-box.sagernet.org
After=network.target nss-lookup.target

[Service]
CapabilityBoundingSet=CAP_NET_ADMIN CAP_NET_BIND_SERVICE CAP_NET_RAW
AmbientCapabilities=CAP_NET_ADMIN CAP_NET_BIND_SERVICE CAP_NET_RAW
ExecStart=/usr/local/bin/sing-box run -c /etc/sing-box/config.json
Restart=on-failure
RestartSec=3s
LimitNOFILE=65535

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable sing-box
systemctl restart sing-box

# Save credentials locally on server with strict permissions
cat <<EOF > /etc/sing-box/credentials.json
{
  "uuid": "${UUID}",
  "public_key": "${PUBLIC_KEY}",
  "short_id": "${SHORT_ID}",
  "sni": "${SNI_DOMAIN}",
  "hy2_password": "${HY2_PASS}",
  "hy2_obfs_password": "${HY2_OBFS_PASS}"
}
EOF

chmod 600 /etc/sing-box/config.json
chmod 600 /etc/sing-box/credentials.json

echo "sing-box core setup completed successfully."
