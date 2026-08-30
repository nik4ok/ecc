#!/usr/bin/env bash
# ==============================================================================
# Hotfix: sing-box routing/DNS patch for existing running server
# Applies to: sing-box v1.10+ / v1.13+
# Fixes:
#   1. Missing dns block → add DoH with ipv4_only strategy
#   2. Missing domain_strategy on inbounds → prevent IPv6 destination hangs
#   3. Missing sniff / sniff_override_destination → enable domain sniffing
#   4. Missing domain_strategy on direct outbound → outbound always dials A record
#   5. Missing route block → bind egress to the default NIC via auto_detect_interface
# ==============================================================================
set -euo pipefail

CONFIG="/etc/sing-box/config.json"
BACKUP="${CONFIG}.bak.$(date +%Y%m%d_%H%M%S)"

if [ ! -f "$CONFIG" ]; then
    echo "[ERROR] $CONFIG not found. Run 02_install_singbox.sh first." >&2
    exit 1
fi

echo "[*] Backing up current config → $BACKUP"
cp "$CONFIG" "$BACKUP"

# ---------------------------------------------------------------------------
# Step 1: Verify current config is valid JSON and extract credentials
# ---------------------------------------------------------------------------
if ! jq empty "$CONFIG" 2>/dev/null; then
    echo "[ERROR] $CONFIG is not valid JSON. Aborting." >&2
    exit 1
fi

UUID=$(jq -r '.inbounds[] | select(.type=="vless") | .users[0].uuid' "$CONFIG")
FLOW=$(jq -r '.inbounds[] | select(.type=="vless") | .users[0].flow' "$CONFIG")
PRIVATE_KEY=$(jq -r '.inbounds[] | select(.type=="vless") | .tls.reality.private_key' "$CONFIG")
SHORT_IDS=$(jq -c '.inbounds[] | select(.type=="vless") | .tls.reality.short_id' "$CONFIG")
SNI=$(jq -r '.inbounds[] | select(.type=="vless") | .tls.server_name' "$CONFIG")
LISTEN_PORT=$(jq -r '.inbounds[] | select(.type=="vless") | .listen_port' "$CONFIG")

# Hysteria2 fields (may be absent)
HY2_PASS=$(jq -r '(.inbounds[] | select(.type=="hysteria2") | .users[0].password) // ""' "$CONFIG")
HY2_OBFS_PASS=$(jq -r '(.inbounds[] | select(.type=="hysteria2") | .obfs.password) // ""' "$CONFIG")
HY2_PORT=$(jq -r '(.inbounds[] | select(.type=="hysteria2") | .listen_port) // 443' "$CONFIG")

echo "[*] Extracted: UUID=${UUID} SNI=${SNI} port=${LISTEN_PORT}"

# ---------------------------------------------------------------------------
# Step 2: Write patched config
# ---------------------------------------------------------------------------
cat > "$CONFIG" <<JSONEOF
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
      "listen_port": ${LISTEN_PORT},
      "sniff": true,
      "sniff_override_destination": true,
      "domain_strategy": "ipv4_only",
      "users": [
        {
          "uuid": "${UUID}",
          "flow": "${FLOW}"
        }
      ],
      "tls": {
        "enabled": true,
        "server_name": "${SNI}",
        "reality": {
          "enabled": true,
          "handshake": {
            "server": "${SNI}",
            "server_port": 443
          },
          "private_key": "${PRIVATE_KEY}",
          "short_id": ${SHORT_IDS}
        }
      }
    }$([ -n "$HY2_PASS" ] && echo ",
    {
      \"type\": \"hysteria2\",
      \"tag\": \"hy2-in\",
      \"listen\": \"::\",
      \"listen_port\": ${HY2_PORT},
      \"sniff\": true,
      \"sniff_override_destination\": true,
      \"domain_strategy\": \"ipv4_only\",
      \"users\": [{ \"password\": \"${HY2_PASS}\" }],
      \"obfs\": { \"type\": \"salamander\", \"password\": \"${HY2_OBFS_PASS}\" },
      \"masquerade\": \"https://${SNI}\"
    }" || true)
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
JSONEOF

# ---------------------------------------------------------------------------
# Step 3: Validate patched config
# ---------------------------------------------------------------------------
echo "[*] Validating new config..."
if ! sing-box check -c "$CONFIG"; then
    echo "[ERROR] Config validation failed. Restoring backup..." >&2
    cp "$BACKUP" "$CONFIG"
    exit 1
fi
echo "[+] Config is valid."

# ---------------------------------------------------------------------------
# Step 4: Restart sing-box and verify
# ---------------------------------------------------------------------------
echo "[*] Restarting sing-box..."
systemctl restart sing-box
sleep 2

STATUS=$(systemctl is-active sing-box)
if [ "$STATUS" = "active" ]; then
    echo "[+] sing-box is running."
else
    echo "[ERROR] sing-box failed to start. Check: journalctl -u sing-box -n 50" >&2
    cp "$BACKUP" "$CONFIG"
    systemctl restart sing-box
    exit 1
fi

# ---------------------------------------------------------------------------
# Step 5: Quick connectivity smoke test
# ---------------------------------------------------------------------------
echo "[*] Smoke test: IPv4 DNS resolution from server..."
if dig +short +time=3 google.com A @1.1.1.1 | grep -qE '^[0-9]'; then
    echo "[+] IPv4 DNS OK."
else
    echo "[WARN] DNS smoke test failed — check firewall rules for UDP 53 / DoH egress."
fi

echo "[*] Smoke test: IPv6 connectivity..."
if ping6 -c 1 -W 2 2606:4700:4700::1111 &>/dev/null; then
    echo "[INFO] IPv6 reachable (but outbound will still prefer IPv4 via domain_strategy)."
else
    echo "[INFO] IPv6 unreachable on this host — ipv4_only is the correct setting."
fi

echo ""
echo "======================================================="
echo " Patch applied successfully. Backup: $BACKUP"
echo " Monitor live traffic:"
echo "   journalctl -fu sing-box --no-hostname"
echo "======================================================="
