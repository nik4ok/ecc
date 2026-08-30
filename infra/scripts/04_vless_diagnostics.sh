#!/usr/bin/env bash
# =============================================================================
# VLESS Reality Diagnostic & Auto-Fix Script
# Target: 92.51.46.12 (Amsterdam) — sing-box VLESS Reality + Hysteria2
#
# Zero-BS failure hunt covering:
#   1. Runtime detection (sing-box vs xray/3X-UI conflict)
#   2. Service health & crash loops
#   3. Port 443 TCP/UDP binding verification
#   4. Firewall (UFW) rule audit
#   5. Reality keypair integrity (private → derived public → client match)
#   6. VPS DNS chain (system resolver → DoH)
#   7. VPS outbound HTTPS connectivity
#   8. UDP/xudp + sniff configuration audit
#   9. Extract 100% verified VLESS URI + QR code
#  10. Auto-fix: DNS fallback, config patch, UFW, service restart
# =============================================================================
set -uo pipefail

# ---------------------------------------------------------------------------
# Terminal helpers
# ---------------------------------------------------------------------------
RED='\033[0;31m'; YELLOW='\033[1;33m'; GREEN='\033[0;32m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

ok()   { echo -e "${GREEN}[OK]${RESET}    $*"; }
warn() { echo -e "${YELLOW}[WARN]${RESET}  $*"; WARN_COUNT=$((WARN_COUNT+1)); }
fail() { echo -e "${RED}[FAIL]${RESET}  $*"; FAIL_COUNT=$((FAIL_COUNT+1)); }
info() { echo -e "${CYAN}[INFO]${RESET}  $*"; }
section() { echo -e "\n${BOLD}══════════════════════════════════════════${RESET}"; \
            echo -e "${BOLD} $*${RESET}"; \
            echo -e "${BOLD}══════════════════════════════════════════${RESET}"; }

FAIL_COUNT=0
WARN_COUNT=0
AUTO_FIX=${AUTO_FIX:-0}    # set AUTO_FIX=1 to apply fixes automatically
FIXES_APPLIED=()
DERIVED_PUB=""              # populated in Phase 4; read in Phase 9

# ---------------------------------------------------------------------------
# Helper: patch /etc/resolv.conf with working upstream DNS
# (defined early — called from Phase 5 before being referenced)
# ---------------------------------------------------------------------------
_apply_dns_fix() {
    local backup_resolv="/etc/resolv.conf.bak.$(date +%Y%m%d_%H%M%S)"
    cp /etc/resolv.conf "$backup_resolv" 2>/dev/null || true
    # Break symlink if managed by systemd-resolved
    [ -L /etc/resolv.conf ] && rm /etc/resolv.conf
    cat > /etc/resolv.conf <<'EOF'
# Patched by vless_diagnostics.sh
nameserver 1.1.1.1
nameserver 8.8.8.8
nameserver 9.9.9.9
options timeout:2 attempts:3
EOF
    ok "AUTO-FIX: /etc/resolv.conf patched (1.1.1.1 / 8.8.8.8 / 9.9.9.9). Backup: $backup_resolv"
    FIXES_APPLIED+=("Patched /etc/resolv.conf with working upstream DNS")
}

# Must run as root
if [ "$(id -u)" -ne 0 ]; then
    echo -e "${RED}ERROR: Run as root (sudo bash $0)${RESET}" >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# PHASE 0: Runtime Detection
# ---------------------------------------------------------------------------
section "PHASE 0 — Runtime Detection"

RUNTIME=""
SINGBOX_BIN=""
XRAY_BIN=""

if command -v sing-box &>/dev/null; then
    SINGBOX_BIN=$(command -v sing-box)
    SINGBOX_VER=$(sing-box version 2>/dev/null | head -1 || echo "unknown")
    info "sing-box found: $SINGBOX_BIN ($SINGBOX_VER)"
    RUNTIME="singbox"
fi

if command -v xray &>/dev/null; then
    XRAY_BIN=$(command -v xray)
    XRAY_VER=$(xray version 2>/dev/null | head -1 || echo "unknown")
    info "xray found: $XRAY_BIN ($XRAY_VER)"
    [ "$RUNTIME" = "singbox" ] && RUNTIME="both" || RUNTIME="xray"
fi

if systemctl list-units --type=service 2>/dev/null | grep -q 'x-ui'; then
    info "3X-UI service detected (x-ui.service)"
    [ "$RUNTIME" = "both" ] && true || RUNTIME="${RUNTIME}+3xui"
fi

case "$RUNTIME" in
    singbox)
        ok "Runtime: sing-box only — expected configuration."
        PROXY_CONFIG="/etc/sing-box/config.json"
        PROXY_CREDS="/etc/sing-box/credentials.json"
        PROXY_SERVICE="sing-box"
        PROXY_CMD="sing-box"
        ;;
    xray)
        warn "Runtime: xray only — expected sing-box. Config may differ from infra scripts."
        PROXY_CONFIG="/usr/local/x-ray/config.json"
        PROXY_CREDS=""
        PROXY_SERVICE="xray"
        PROXY_CMD="xray"
        ;;
    *3xui*)
        fail "CONFLICT DETECTED: 3X-UI service running alongside sing-box."
        fail "Both processes may compete for port 443. This is almost certainly your root cause."
        info "Fix: systemctl stop x-ui && systemctl disable x-ui"
        PROXY_CONFIG="/etc/sing-box/config.json"
        PROXY_CREDS="/etc/sing-box/credentials.json"
        PROXY_SERVICE="sing-box"
        PROXY_CMD="sing-box"
        if [ "$AUTO_FIX" = "1" ]; then
            systemctl stop x-ui 2>/dev/null || true
            systemctl disable x-ui 2>/dev/null || true
            warn "AUTO-FIX: 3X-UI stopped and disabled."
            FIXES_APPLIED+=("Stopped 3X-UI to release port 443 conflict")
        fi
        ;;
    both)
        fail "CONFLICT DETECTED: BOTH sing-box AND xray are installed."
        fail "Port 443 collision. Exactly one process owns the socket — the other is silently dead."
        info "Fix: Decide which one to keep. Disable the other."
        PROXY_CONFIG="/etc/sing-box/config.json"
        PROXY_CREDS="/etc/sing-box/credentials.json"
        PROXY_SERVICE="sing-box"
        PROXY_CMD="sing-box"
        ;;
    "")
        fail "FATAL: Neither sing-box nor xray found. Nothing is proxying traffic."
        info "Fix: Run infra/scripts/02_install_singbox.sh"
        exit 1
        ;;
esac

# ---------------------------------------------------------------------------
# PHASE 1: Service Health
# ---------------------------------------------------------------------------
section "PHASE 1 — Service Health (${PROXY_SERVICE})"

SERVICE_STATUS=$(systemctl is-active "${PROXY_SERVICE}" 2>/dev/null || echo "unknown")
info "Service status: $SERVICE_STATUS"

if [ "$SERVICE_STATUS" = "active" ]; then
    ok "${PROXY_SERVICE} is running."
else
    fail "${PROXY_SERVICE} is NOT running (status: $SERVICE_STATUS)."
    info "Last 20 journal lines:"
    journalctl -u "${PROXY_SERVICE}" -n 20 --no-pager 2>/dev/null || true
    if [ "$AUTO_FIX" = "1" ]; then
        systemctl restart "${PROXY_SERVICE}"
        sleep 2
        NEW_STATUS=$(systemctl is-active "${PROXY_SERVICE}" 2>/dev/null || echo "failed")
        if [ "$NEW_STATUS" = "active" ]; then
            ok "AUTO-FIX: ${PROXY_SERVICE} restarted successfully."
            FIXES_APPLIED+=("Restarted ${PROXY_SERVICE}")
        else
            fail "AUTO-FIX: Restart failed. Check journalctl -u ${PROXY_SERVICE} -n 50"
        fi
    fi
fi

# Check for recent restarts (crash loop indicator)
RESTART_COUNT=$(systemctl show "${PROXY_SERVICE}" --property=NRestarts 2>/dev/null | cut -d= -f2 || echo "0")
if [ "${RESTART_COUNT:-0}" -gt 3 ]; then
    warn "Crash loop detected: ${PROXY_SERVICE} has restarted ${RESTART_COUNT} times."
    warn "This means configuration errors are causing silent restarts."
fi

# Check config validity before anything else
if [ -f "${PROXY_CONFIG}" ]; then
    if [ "$PROXY_CMD" = "sing-box" ]; then
        if sing-box check -c "${PROXY_CONFIG}" 2>/dev/null; then
            ok "Config syntax valid: ${PROXY_CONFIG}"
        else
            fail "Config INVALID: ${PROXY_CONFIG}"
            info "sing-box check output:"
            sing-box check -c "${PROXY_CONFIG}" 2>&1 || true
        fi
    fi
else
    fail "Config not found: ${PROXY_CONFIG}"
fi

# ---------------------------------------------------------------------------
# PHASE 2: Port Binding Verification
# ---------------------------------------------------------------------------
section "PHASE 2 — Port 443 Binding"

info "Checking TCP 443..."
TCP_443=$(ss -tlnp 2>/dev/null | grep ':443 ' || echo "")
if echo "$TCP_443" | grep -q ':443'; then
    ok "TCP 443 is listening:"
    echo "$TCP_443" | sed 's/^/         /'
else
    fail "TCP 443 is NOT listening. Service started but didn't bind the port."
    info "Possible: config error, wrong user permissions, or another process crashed while holding the socket."
fi

info "Checking UDP 443 (Hysteria2)..."
UDP_443=$(ss -ulnp 2>/dev/null | grep ':443 ' || echo "")
if echo "$UDP_443" | grep -q ':443'; then
    ok "UDP 443 is listening:"
    echo "$UDP_443" | sed 's/^/         /'
else
    warn "UDP 443 is NOT listening. Hysteria2 may be disabled or crashed."
    info "v2RayTun using VLESS is TCP-only — this may be acceptable."
fi

# Check for competing processes on 443
ALL_443=$(ss -tlnp -ulnp 2>/dev/null | grep ':443' || echo "")
PROC_COUNT=$(echo "$ALL_443" | grep -v '^$' | grep ':443' | wc -l)
if [ "$PROC_COUNT" -gt 2 ]; then
    warn "More than 2 processes on port 443. Possible conflict:"
    echo "$ALL_443" | sed 's/^/         /'
fi

# ---------------------------------------------------------------------------
# PHASE 3: Firewall Audit
# ---------------------------------------------------------------------------
section "PHASE 3 — Firewall (UFW)"

UFW_STATUS=$(ufw status 2>/dev/null || echo "inactive")
if echo "$UFW_STATUS" | grep -q "Status: active"; then
    ok "UFW is active."

    if echo "$UFW_STATUS" | grep -qE "443.*ALLOW.*tcp|443/tcp.*ALLOW"; then
        ok "UFW allows 443/tcp."
    else
        fail "UFW MISSING rule for 443/tcp. Inbound connections are silently dropped."
        if [ "$AUTO_FIX" = "1" ]; then
            ufw allow 443/tcp comment 'VLESS Reality (TCP)'
            ok "AUTO-FIX: Added UFW rule for 443/tcp."
            FIXES_APPLIED+=("Added UFW rule: 443/tcp ALLOW")
        fi
    fi

    if echo "$UFW_STATUS" | grep -qE "443.*ALLOW.*udp|443/udp.*ALLOW"; then
        ok "UFW allows 443/udp."
    else
        warn "UFW MISSING rule for 443/udp. Hysteria2 is blocked."
        if [ "$AUTO_FIX" = "1" ]; then
            ufw allow 443/udp comment 'Hysteria2 (UDP)'
            ok "AUTO-FIX: Added UFW rule for 443/udp."
            FIXES_APPLIED+=("Added UFW rule: 443/udp ALLOW")
        fi
    fi
else
    info "UFW is inactive — no firewall filtering at OS level."
fi

# ---------------------------------------------------------------------------
# PHASE 4: Reality Keypair Integrity
# ---------------------------------------------------------------------------
section "PHASE 4 — Reality Keypair Integrity"

# Portable x25519 public key derivation via OpenSSL DER encoding
# x25519 PKCS#8 DER header (hex): 302e020100300506032b656e04220420
# Structure: SEQUENCE { version=0, AlgorithmID x25519, OCTET STRING { OCTET STRING { <32-byte key> } } }
derive_x25519_pubkey() {
    local priv_b64url="$1"

    # Normalize base64url → base64 standard with padding
    local priv_b64
    priv_b64=$(printf '%s' "$priv_b64url" | tr '_-' '/+')
    # Pad to multiple of 4
    local pad=$(( (4 - (${#priv_b64} % 4)) % 4 ))
    for _ in $(seq 1 $pad); do priv_b64="${priv_b64}="; done

    # Decode raw 32-byte private key, build PKCS#8 DER
    local priv_hex
    priv_hex=$(printf '%s' "$priv_b64" | base64 -d 2>/dev/null | xxd -p -c 64 | tr -d '\n')
    if [ ${#priv_hex} -ne 64 ]; then
        echo "ERROR:invalid_key_length"
        return 1
    fi

    local der_hex="302e020100300506032b656e04220420${priv_hex}"
    local tmpkey
    tmpkey=$(mktemp /tmp/x25519_priv_XXXXXX.der)
    # shellcheck disable=SC2064
    trap "rm -f '$tmpkey'" RETURN

    printf '%s' "$der_hex" | xxd -r -p > "$tmpkey" 2>/dev/null

    # Extract public key from DER output: SubjectPublicKeyInfo ends with 32-byte pubkey
    local pub_raw
    pub_raw=$(openssl pkey -inform DER -in "$tmpkey" -pubout -outform DER 2>/dev/null | tail -c 32)
    if [ -z "$pub_raw" ]; then
        echo "ERROR:openssl_failed"
        return 1
    fi

    # Encode as base64url without padding
    printf '%s' "$pub_raw" | base64 | tr '+/' '-_' | tr -d '='
}

if [ ! -f "${PROXY_CONFIG}" ]; then
    fail "Cannot check keypair: config not found."
else
    CONFIG_PRIV=$(jq -r '
        .inbounds[]?
        | select(.type == "vless")
        | .tls.reality.private_key
    ' "${PROXY_CONFIG}" 2>/dev/null || echo "")

    CONFIG_SHORT_IDS=$(jq -r '
        .inbounds[]?
        | select(.type == "vless")
        | .tls.reality.short_id[]
    ' "${PROXY_CONFIG}" 2>/dev/null | paste -sd ',' || echo "")

    if [ -z "$CONFIG_PRIV" ]; then
        fail "Cannot extract private_key from config. Check .inbounds[].tls.reality.private_key"
    else
        info "Private key found in config (length=${#CONFIG_PRIV})"
        info "short_ids in config: ${CONFIG_SHORT_IDS:-<none found>}"

        DERIVED_PUB=$(derive_x25519_pubkey "$CONFIG_PRIV" 2>/dev/null || echo "ERROR")

        if echo "$DERIVED_PUB" | grep -q "ERROR"; then
            fail "Key derivation failed ($DERIVED_PUB). openssl or xxd may be missing."
            info "Install: apt-get install -y openssl xxd"
        else
            ok "Derived public key: ${DERIVED_PUB}"

            # Compare with credentials.json if present
            if [ -f "${PROXY_CREDS:-/nonexistent}" ]; then
                STORED_PUB=$(jq -r '.public_key' "${PROXY_CREDS}" 2>/dev/null || echo "")
                if [ "$STORED_PUB" = "$DERIVED_PUB" ]; then
                    ok "KEYPAIR MATCH: credentials.json public_key == derived(config private_key)."
                else
                    fail "KEYPAIR MISMATCH DETECTED!"
                    fail "  credentials.json: ${STORED_PUB}"
                    fail "  derived from config: ${DERIVED_PUB}"
                    fail "  → Your VLESS URI has the WRONG public key."
                    fail "  → Client Reality handshake will SILENTLY FAIL."
                    info "  → Use the derived key above in your VLESS URI."
                    if [ "$AUTO_FIX" = "1" ]; then
                        # Update credentials.json with correct public key
                        _creds_tmp=$(mktemp)
                        jq --arg pk "$DERIVED_PUB" '.public_key = $pk' "${PROXY_CREDS}" > "$_creds_tmp"
                        mv "$_creds_tmp" "${PROXY_CREDS}"
                        ok "AUTO-FIX: credentials.json updated with derived public key."
                        FIXES_APPLIED+=("Fixed public key in credentials.json")
                    fi
                fi
            fi

            # Check against servers.json if present
            SERVERS_JSON="/root/servers.json"
            # try common locations
            for loc in /root/servers.json /opt/servers.json ~/.cursor/servers.json; do
                [ -f "$loc" ] && SERVERS_JSON="$loc" && break
            done
            if [ -f "$SERVERS_JSON" ]; then
                SERVERS_PUB=$(jq -r '
                    .servers[0].credentials.vless_reality.public_key // ""
                ' "$SERVERS_JSON" 2>/dev/null || echo "")
                if [ -n "$SERVERS_PUB" ] && [ "$SERVERS_PUB" != "$DERIVED_PUB" ]; then
                    fail "KEYPAIR MISMATCH in servers.json!"
                    fail "  servers.json publicKey: ${SERVERS_PUB}"
                    fail "  actual derived pubkey:   ${DERIVED_PUB}"
                fi
            fi
        fi
    fi
fi

# ---------------------------------------------------------------------------
# PHASE 5: VPS DNS Chain Test
# ---------------------------------------------------------------------------
section "PHASE 5 — DNS Chain (System + DoH)"

# 5a: System DNS
info "System resolver test (resolv.conf):"
SYSTEM_NS=$(grep '^nameserver' /etc/resolv.conf 2>/dev/null | head -3 | awk '{print $2}' | paste -sd ',' || echo "none")
info "  Configured nameservers: ${SYSTEM_NS:-none}"

if dig +short +time=3 google.com A @1.1.1.1 2>/dev/null | grep -qE '^[0-9]+\.[0-9]'; then
    ok "DNS via Cloudflare 1.1.1.1 UDP: working."
else
    fail "DNS via 1.1.1.1 UDP FAILED."
    warn "Hoster may block UDP port 53 egress or rate-limit 1.1.1.1."
fi

if dig +short +time=3 google.com A @8.8.8.8 2>/dev/null | grep -qE '^[0-9]+\.[0-9]'; then
    ok "DNS via Google 8.8.8.8 UDP: working."
else
    fail "DNS via 8.8.8.8 UDP FAILED."
fi

# 5b: DoH (what sing-box actually uses)
info "DoH test (sing-box's actual resolver path):"
DOH_CF=$(curl -s --max-time 5 "https://1.1.1.1/dns-query?name=google.com&type=A" \
    -H "accept: application/dns-json" 2>/dev/null \
    | jq -r '.Answer[]? | select(.type==1) | .data' 2>/dev/null | head -1 || echo "")

if [ -n "$DOH_CF" ]; then
    ok "DoH 1.1.1.1 working — resolved google.com → $DOH_CF"
else
    fail "DoH to 1.1.1.1 FAILED (HTTPS DNS-JSON query returned nothing)."
    fail "  → sing-box cannot resolve any proxied domain names."
    fail "  → THIS IS LIKELY YOUR ROOT CAUSE for 'connected but no pages load'."

    DOH_G=$(curl -s --max-time 5 "https://8.8.8.8/dns-query?name=google.com&type=A" \
        -H "accept: application/dns-json" 2>/dev/null \
        | jq -r '.Answer[]? | select(.type==1) | .data' 2>/dev/null | head -1 || echo "")

    if [ -n "$DOH_G" ]; then
        warn "DoH via 8.8.8.8 works but 1.1.1.1 doesn't — firewall targeting Cloudflare."
    else
        fail "Both DoH resolvers unreachable. VPS has no HTTPS egress to major DNS providers."
        fail "  → Fix: add system DNS fallback in resolv.conf + patch sing-box to use local resolver."
        if [ "$AUTO_FIX" = "1" ]; then
            _apply_dns_fix
        fi
    fi
fi

# 5c: Detect broken/local-only resolv.conf
if grep -qE '^nameserver (127\.|::1)' /etc/resolv.conf 2>/dev/null; then
    LOCALHOST_DNS_PORT=$(ss -ulnp | grep ':53 ' | head -1)
    if [ -z "$LOCALHOST_DNS_PORT" ]; then
        fail "resolv.conf points to localhost but nothing is listening on UDP 53."
        fail "  → All DNS from sing-box system path is dead."
        info "  → Fix: replace with working upstream, e.g.:"
        info "         echo 'nameserver 1.1.1.1' > /etc/resolv.conf"
        info "         echo 'nameserver 8.8.8.8' >> /etc/resolv.conf"
        if [ "$AUTO_FIX" = "1" ]; then
            _apply_dns_fix
        fi
    else
        info "Local DNS stub is listening on 53 — may be systemd-resolved."
    fi
fi

# ---------------------------------------------------------------------------
# PHASE 6: VPS Outbound Connectivity
# ---------------------------------------------------------------------------
section "PHASE 6 — VPS Outbound HTTPS"

info "Testing outbound TCP 443 to google.com..."
if curl -s --max-time 8 -o /dev/null -w "%{http_code}" "https://www.google.com" 2>/dev/null | grep -qE '^[23]'; then
    ok "Outbound HTTPS to google.com: OK."
else
    fail "Outbound HTTPS to google.com FAILED."
    fail "  → VPS cannot reach internet. All proxied HTTPS requests will fail."
    info "  Possible causes: hoster outbound filter, missing default route, broken gateway."
    info "  Check: ip route; ip route get 8.8.8.8"
    ip route 2>/dev/null | head -5 | sed 's/^/         /'
    DEFAULT_ROUTE=$(ip route show default 2>/dev/null || echo "")
    if [ -z "$DEFAULT_ROUTE" ]; then
        fail "  NO DEFAULT ROUTE. VPS has no internet gateway configured."
    fi
fi

info "Testing outbound TCP 443 to dl.google.com (SNI target / masquerade destination)..."
if curl -s --max-time 8 -o /dev/null -w "%{http_code}" "https://dl.google.com" 2>/dev/null | grep -qE '^[23]'; then
    ok "Outbound to dl.google.com: OK. Reality handshake masquerade will work."
else
    fail "Outbound to dl.google.com FAILED."
    fail "  → Reality handshake will fail. Passive probes see a dead server, not dl.google.com."
fi

# ---------------------------------------------------------------------------
# PHASE 7: sing-box Config Deep Audit
# ---------------------------------------------------------------------------
section "PHASE 7 — sing-box Config Audit"

if [ ! -f "${PROXY_CONFIG}" ]; then
    fail "Config not found: ${PROXY_CONFIG}. Skipping audit."
else
    # 7a: sniff + sniff_override_destination on VLESS inbound
    SNIFF=$(jq -r '
        .inbounds[]?
        | select(.type == "vless")
        | .sniff // false
    ' "${PROXY_CONFIG}" 2>/dev/null)
    SNIFF_OVERRIDE=$(jq -r '
        .inbounds[]?
        | select(.type == "vless")
        | .sniff_override_destination // false
    ' "${PROXY_CONFIG}" 2>/dev/null)

    if [ "$SNIFF" = "true" ] && [ "$SNIFF_OVERRIDE" = "true" ]; then
        ok "VLESS inbound: sniff=true, sniff_override_destination=true — DNS/UDP will be properly routed."
    else
        fail "VLESS inbound MISSING sniff config: sniff=$SNIFF, sniff_override_destination=$SNIFF_OVERRIDE"
        fail "  → DNS queries (UDP) from v2RayTun TUN cannot be resolved server-side."
        fail "  → THIS IS A KNOWN ROOT CAUSE for 'connected but no pages load'."
        info "  → Fix: add \"sniff\": true, \"sniff_override_destination\": true to VLESS inbound."
        if [ "$AUTO_FIX" = "1" ]; then
            bash "$(dirname "$0")/03_fix_singbox_routing.sh" && \
                FIXES_APPLIED+=("Ran 03_fix_singbox_routing.sh — patched sniff + domain_strategy")
        fi
    fi

    # 7b: domain_strategy ipv4_only on inbound
    DOMAIN_STRAT=$(jq -r '
        .inbounds[]?
        | select(.type == "vless")
        | .domain_strategy // ""
    ' "${PROXY_CONFIG}" 2>/dev/null)
    if [ "$DOMAIN_STRAT" = "ipv4_only" ]; then
        ok "VLESS inbound: domain_strategy=ipv4_only — no IPv6 destination hangs."
    else
        warn "VLESS inbound domain_strategy='${DOMAIN_STRAT:-not set}'. Should be 'ipv4_only'."
        warn "  → Destinations may be dialed over IPv6 which many hosters don't support."
        warn "  → Requests hang or time out after 30s instead of failing fast."
    fi

    # 7c: domain_strategy ipv4_only on direct outbound
    OUTBOUND_STRAT=$(jq -r '
        .outbounds[]?
        | select(.type == "direct")
        | .domain_strategy // ""
    ' "${PROXY_CONFIG}" 2>/dev/null)
    if [ "$OUTBOUND_STRAT" = "ipv4_only" ]; then
        ok "direct outbound: domain_strategy=ipv4_only."
    else
        warn "direct outbound domain_strategy='${OUTBOUND_STRAT:-not set}'. Should be 'ipv4_only'."
    fi

    # 7d: DNS block present and using DoH
    HAS_DNS=$(jq -r '.dns.servers // [] | length' "${PROXY_CONFIG}" 2>/dev/null)
    if [ "${HAS_DNS:-0}" -gt 0 ]; then
        ok "DNS block present in config with ${HAS_DNS} server(s)."
        DNS_ADDRS=$(jq -r '.dns.servers[].address' "${PROXY_CONFIG}" 2>/dev/null | paste -sd ', ')
        info "  DNS servers: $DNS_ADDRS"
    else
        fail "No DNS block in sing-box config."
        fail "  → sing-box uses system /etc/resolv.conf which may be broken."
        fail "  → Run 03_fix_singbox_routing.sh to inject DoH block."
    fi

    # 7e: route.auto_detect_interface
    AUTO_IFACE=$(jq -r '.route.auto_detect_interface // false' "${PROXY_CONFIG}" 2>/dev/null)
    if [ "$AUTO_IFACE" = "true" ]; then
        ok "route.auto_detect_interface=true — egress bound to default NIC."
    else
        warn "route.auto_detect_interface not set. Egress may bind wrong interface on multi-NIC VPS."
    fi
fi

# ---------------------------------------------------------------------------
# PHASE 8: Local Proxy Smoke Test
# ---------------------------------------------------------------------------
section "PHASE 8 — Local Proxy Smoke Test"

# Check if there's any HTTP proxy inbound in sing-box config
HTTP_PROXY_PORT=$(jq -r '
    .inbounds[]?
    | select(.type == "http" or .type == "mixed")
    | .listen_port
' "${PROXY_CONFIG}" 2>/dev/null | head -1 || echo "")

SOCKS_PROXY_PORT=$(jq -r '
    .inbounds[]?
    | select(.type == "socks" or .type == "mixed")
    | .listen_port
' "${PROXY_CONFIG}" 2>/dev/null | head -1 || echo "")

if [ -n "$HTTP_PROXY_PORT" ]; then
    info "HTTP proxy inbound on port $HTTP_PROXY_PORT — testing..."
    HTTP_CODE=$(curl -s --max-time 8 -x "http://127.0.0.1:${HTTP_PROXY_PORT}" \
        -o /dev/null -w "%{http_code}" "https://www.google.com" 2>/dev/null || echo "000")
    if echo "$HTTP_CODE" | grep -qE '^[23]'; then
        ok "Local HTTP proxy smoke test PASSED (HTTP $HTTP_CODE)."
    else
        fail "Local HTTP proxy smoke test FAILED (HTTP $HTTP_CODE)."
    fi
elif [ -n "$SOCKS_PROXY_PORT" ]; then
    info "SOCKS proxy inbound on port $SOCKS_PROXY_PORT — testing..."
    HTTP_CODE=$(curl -s --max-time 8 --socks5 "127.0.0.1:${SOCKS_PROXY_PORT}" \
        -o /dev/null -w "%{http_code}" "https://www.google.com" 2>/dev/null || echo "000")
    if echo "$HTTP_CODE" | grep -qE '^[23]'; then
        ok "Local SOCKS5 proxy smoke test PASSED (HTTP $HTTP_CODE)."
    else
        fail "Local SOCKS5 proxy smoke test FAILED (HTTP $HTTP_CODE)."
    fi
else
    info "No HTTP/SOCKS inbound in sing-box config (server-only mode — expected for VLESS)."
    info "Smoke test via outbound: direct curl from VPS to www.google.com..."
    HTTP_CODE=$(curl -s --max-time 8 -o /dev/null -w "%{http_code}" "https://www.google.com" 2>/dev/null || echo "000")
    if echo "$HTTP_CODE" | grep -qE '^[23]'; then
        ok "VPS outbound proxy path is functional (HTTP $HTTP_CODE)."
    else
        fail "VPS outbound HTTP FAILED (HTTP $HTTP_CODE). Proxied traffic will not reach internet."
    fi
fi

# Verify VLESS port actually accepts TLS connections (deep-link probe)
info "TCP connectivity probe on 127.0.0.1:443 (3-second timeout)..."
if timeout 3 bash -c 'echo >/dev/tcp/127.0.0.1/443' 2>/dev/null; then
    ok "TCP 443 accepts connections on localhost."
else
    fail "TCP 443 refusing connections. sing-box process crashed or not bound."
fi

# ---------------------------------------------------------------------------
# PHASE 9: Extract Verified VLESS URI + QR Code
# ---------------------------------------------------------------------------
section "PHASE 9 — Verified VLESS URI & QR Code"

# Collect all required fields
if [ -f "${PROXY_CONFIG}" ] && [ -n "${DERIVED_PUB:-}" ] && ! echo "${DERIVED_PUB:-}" | grep -q "ERROR"; then
    V_UUID=$(jq -r '
        .inbounds[]?
        | select(.type == "vless")
        | .users[0].uuid
    ' "${PROXY_CONFIG}" 2>/dev/null || echo "")

    V_FLOW=$(jq -r '
        .inbounds[]?
        | select(.type == "vless")
        | .users[0].flow // "xtls-rprx-vision"
    ' "${PROXY_CONFIG}" 2>/dev/null || echo "xtls-rprx-vision")

    V_SNI=$(jq -r '
        .inbounds[]?
        | select(.type == "vless")
        | .tls.server_name // ""
    ' "${PROXY_CONFIG}" 2>/dev/null || echo "")

    V_SHORT_ID=$(jq -r '
        .inbounds[]?
        | select(.type == "vless")
        | .tls.reality.short_id[0] // ""
    ' "${PROXY_CONFIG}" 2>/dev/null || echo "")

    V_PORT=$(jq -r '
        .inbounds[]?
        | select(.type == "vless")
        | .listen_port
    ' "${PROXY_CONFIG}" 2>/dev/null || echo "443")

    SERVER_IP=$(curl -s --max-time 5 -4 https://icanhazip.com 2>/dev/null | tr -d '\n' || echo "92.51.46.12")

    if [ -z "$V_UUID" ] || [ -z "$V_SNI" ] || [ -z "$V_SHORT_ID" ]; then
        fail "Incomplete config — cannot generate VLESS URI."
        info "Missing: UUID='${V_UUID}' SNI='${V_SNI}' ShortID='${V_SHORT_ID}'"
    else
        VLESS_URI="vless://${V_UUID}@${SERVER_IP}:${V_PORT}?encryption=none&flow=${V_FLOW}&security=reality&sni=${V_SNI}&fp=chrome&pbk=${DERIVED_PUB}&sid=${V_SHORT_ID}&type=tcp#NL-Amsterdam-Reality"

        echo ""
        echo -e "${BOLD}────────────────────────────────────────────────────────────────${RESET}"
        echo -e "${GREEN}${BOLD}✅ 100% VERIFIED VLESS URI (public key derived from active config):${RESET}"
        echo -e "${BOLD}────────────────────────────────────────────────────────────────${RESET}"
        echo ""
        echo "  UUID:      $V_UUID"
        echo "  Server:    $SERVER_IP:$V_PORT"
        echo "  SNI:       $V_SNI"
        echo "  ShortID:   $V_SHORT_ID"
        echo "  Flow:      $V_FLOW"
        echo "  PublicKey: $DERIVED_PUB (derived — not stored)"
        echo ""
        echo -e "${GREEN}${VLESS_URI}${RESET}"
        echo ""

        if command -v qrencode &>/dev/null; then
            echo "QR CODE (scan with v2RayTun / any VLESS client):"
            echo ""
            qrencode -t ANSIUTF8 "$VLESS_URI"
            echo ""
        else
            warn "qrencode not installed. Install: apt-get install -y qrencode"
            info "QR link: https://api.qrserver.com/v1/create-qr-code/?size=400x400&data=$(python3 -c "import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1]))" "$VLESS_URI" 2>/dev/null)"
        fi

        # Also output Hysteria2 URI if credentials present
        if [ -f "${PROXY_CREDS:-/nonexistent}" ]; then
            HY2_PASS=$(jq -r '.hy2_password' "${PROXY_CREDS}" 2>/dev/null || echo "")
            HY2_OBFS=$(jq -r '.hy2_obfs_password' "${PROXY_CREDS}" 2>/dev/null || echo "")
            if [ -n "$HY2_PASS" ] && [ -n "$HY2_OBFS" ]; then
                HY2_URI="hysteria2://${HY2_PASS}@${SERVER_IP}:443?sni=${V_SNI}&obfs=salamander&obfs-password=${HY2_OBFS}#NL-Amsterdam-Hysteria2"
                echo -e "${CYAN}Hysteria2 URI (fallback):${RESET}"
                echo "$HY2_URI"
                echo ""
            fi
        fi
    fi
else
    fail "Keypair derivation failed — cannot produce a verified URI."
    info "Falling back to credentials.json if present..."
    if [ -f "${PROXY_CREDS:-/nonexistent}" ]; then
        UUID_F=$(jq -r '.uuid // ""' "${PROXY_CREDS}" 2>/dev/null || echo "")
        PK_F=$(jq -r '.public_key // ""' "${PROXY_CREDS}" 2>/dev/null || echo "")
        SID_F=$(jq -r '.short_id // ""' "${PROXY_CREDS}" 2>/dev/null || echo "")
        SNI_F=$(jq -r '.sni // "dl.google.com"' "${PROXY_CREDS}" 2>/dev/null || echo "dl.google.com")
        SERVER_IP=$(curl -s --max-time 5 -4 https://icanhazip.com 2>/dev/null | tr -d '\n' || echo "92.51.46.12")
        if [ -n "$UUID_F" ] && [ -n "$PK_F" ]; then
            warn "URI from credentials.json (public key NOT re-verified from config):"
            echo "vless://${UUID_F}@${SERVER_IP}:443?encryption=none&flow=xtls-rprx-vision&security=reality&sni=${SNI_F}&fp=chrome&pbk=${PK_F}&sid=${SID_F}&type=tcp#NL-Amsterdam-Reality"
        fi
    fi
fi

# ---------------------------------------------------------------------------
# PHASE 10: v2RayTun Client Checklist
# ---------------------------------------------------------------------------
section "PHASE 10 — v2RayTun Client-Side Checklist"

echo ""
cat <<'CHECKLIST'
Client-side items that can cause "Connected, but no traffic" (cannot be auto-fixed server-side):

  [ ] Public key in client config matches the DERIVED key printed in Phase 9
      (not the one stored in servers.json which may be stale)

  [ ] ShortID in client matches exactly one entry in the server's short_id array

  [ ] Flow = xtls-rprx-vision on BOTH server (config.json) and client

  [ ] Fingerprint = chrome (fp=chrome in URI). Mismatched fp causes silent TLS failure.

  [ ] v2RayTun → Settings → DNS:
        - Set "Remote DNS" to "https://1.1.1.1/dns-query"
        - Enable "DNS over VLESS" (or "Remote DNS over Proxy")
        - If DNS is set to "System" only, DNS queries bypass the tunnel → zero resolution

  [ ] v2RayTun → Settings → Routing:
        - Ensure "Proxy all traffic" or "Global" mode is selected
        - "Bypass LAN & China" mode might silently exclude your test sites

  [ ] v2RayTun TUN mode:
        - Enable TUN mode (not SOCKS/HTTP only)
        - TUN device must have a default route injected; verify in phone's Wi-Fi settings

  [ ] Test: in v2RayTun, switch protocol to Hysteria2 (same server, port 443).
        If Hysteria2 works but VLESS doesn't → VLESS config/keypair issue.
        If neither works → VPS outbound or DNS issue.
CHECKLIST
echo ""

# ---------------------------------------------------------------------------
# SUMMARY
# ---------------------------------------------------------------------------
section "DIAGNOSTIC SUMMARY"

echo ""
if [ $FAIL_COUNT -eq 0 ] && [ $WARN_COUNT -eq 0 ]; then
    ok "All checks passed. If traffic still doesn't flow, the issue is client-side (see Phase 10)."
else
    echo -e "${RED}${BOLD}FAILURES: ${FAIL_COUNT}${RESET}   ${YELLOW}WARNINGS: ${WARN_COUNT}${RESET}"
    echo ""
    if [ ${#FIXES_APPLIED[@]} -gt 0 ]; then
        echo -e "${GREEN}Auto-fixes applied:${RESET}"
        for fix in "${FIXES_APPLIED[@]}"; do
            echo "  ✔ $fix"
        done
        echo ""
        info "Restarting ${PROXY_SERVICE} to apply all fixes..."
        systemctl restart "${PROXY_SERVICE}" && sleep 2
        if systemctl is-active --quiet "${PROXY_SERVICE}"; then
            ok "${PROXY_SERVICE} restarted and active after fixes."
        else
            fail "${PROXY_SERVICE} failed to restart. Run: journalctl -u ${PROXY_SERVICE} -n 50"
        fi
    else
        echo -e "${YELLOW}Run with AUTO_FIX=1 to automatically apply fixes:${RESET}"
        echo "  sudo AUTO_FIX=1 bash $0"
    fi
fi
echo ""
