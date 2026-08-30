#!/usr/bin/env bash
# ==============================================================================
# One-Click Full Server Provisioning Script
# Server: Node 1 Netherlands (92.51.46.12)
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🚀 Starting Full Provisioning for VPN Edge Node..."
bash "${SCRIPT_DIR}/01_system_hardening.sh"
bash "${SCRIPT_DIR}/02_install_singbox.sh"

SERVER_IP=$(curl -s -4 https://icanhazip.com || echo "92.51.46.12")
CREDS="/etc/sing-box/credentials.json"

if [ -f "$CREDS" ]; then
    UUID=$(jq -r '.uuid' "$CREDS")
    PUB_KEY=$(jq -r '.public_key' "$CREDS")
    SHORT_ID=$(jq -r '.short_id' "$CREDS")
    SNI=$(jq -r '.sni' "$CREDS")
    HY2_PASS=$(jq -r '.hy2_password' "$CREDS")
    HY2_OBFS=$(jq -r '.hy2_obfs_password' "$CREDS")

    VLESS_URI="vless://${UUID}@${SERVER_IP}:443?encryption=none&flow=xtls-rprx-vision&security=reality&sni=${SNI}&fp=chrome&pbk=${PUB_KEY}&sid=${SHORT_ID}&type=tcp#NL-Amsterdam-Reality"
    HY2_URI="hysteria2://${HY2_PASS}@${SERVER_IP}:443?sni=${SNI}&obfs=salamander&obfs-password=${HY2_OBFS}#NL-Amsterdam-Hysteria2"

    echo ""
    echo "========================================================="
    echo " 🎉 VPN NODE IS FULLY CONFIGURED AND RUNNING!"
    echo "========================================================="
    echo ""
    echo "1. VLESS XTLS Reality URI (Primary Stealth):"
    echo "$VLESS_URI"
    echo ""
    echo "2. Hysteria 2 URI (UDP Obfuscation):"
    echo "$HY2_URI"
    echo ""
    echo "========================================================="
fi
