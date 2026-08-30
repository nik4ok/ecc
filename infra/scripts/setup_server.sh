mkdir -p /etc/sing-box

UUID=$(sing-box generate uuid)
KEYPAIR=$(sing-box generate reality-keypair)
PRIV_KEY=$(echo "$KEYPAIR" | grep "PrivateKey" | awk '{print $2}')
PUB_KEY=$(echo "$KEYPAIR" | grep "PublicKey" | awk '{print $2}')
SHORT_ID=$(openssl rand -hex 8)
HY2_PASS=$(openssl rand -base64 12 | tr -dc 'a-zA-Z0-9')
HY2_OBFS=$(openssl rand -hex 8)

cat <<EOF > /etc/sing-box/config.json
{
  "log": { "level": "warn", "timestamp": true },
  "inbounds": [
    {
      "type": "vless",
      "tag": "vless-reality-in",
      "listen": "::",
      "listen_port": 443,
      "users": [{ "uuid": "${UUID}", "flow": "xtls-rprx-vision" }],
      "tls": {
        "enabled": true,
        "server_name": "dl.google.com",
        "reality": {
          "enabled": true,
          "handshake": { "server": "dl.google.com", "server_port": 443 },
          "private_key": "${PRIV_KEY}",
          "short_id": ["${SHORT_ID}"]
        }
      }
    },
    {
      "type": "hysteria2",
      "tag": "hy2-in",
      "listen": "::",
      "listen_port": 443,
      "users": [{ "password": "${HY2_PASS}" }],
      "obfs": { "type": "salamander", "password": "${HY2_OBFS}" },
      "masquerade": "https://dl.google.com"
    }
  ],
  "outbounds": [{ "type": "direct", "tag": "direct" }]
}
EOF

systemctl enable --now sing-box
systemctl restart sing-box

echo ""
echo "========================================="
echo "🎉 СЕРВЕР УСПЕШНО НАСТРОЕН НА ПОРТ 443!"
echo "========================================="
echo ""
echo "1. VLESS Reality ссылка:"
echo "vless://${UUID}@92.51.46.12:443?encryption=none&flow=xtls-rprx-vision&security=reality&sni=dl.google.com&fp=chrome&pbk=${PUB_KEY}&sid=${SHORT_ID}&type=tcp#NL-Amsterdam-Reality"
echo ""
echo "2. Hysteria 2 ссылка:"
echo "hysteria2://${HY2_PASS}@92.51.46.12:443?sni=dl.google.com&obfs=salamander&obfs-password=${HY2_OBFS}#NL-Amsterdam-Hysteria2"
echo ""
echo "========================================="
