import 'dart:convert';
import '../entities/vpn_profile.dart';

class SingBoxConfigGenerator {
  static String generateVlessRealityConfig({
    required String serverAddress,
    required int serverPort,
    required String uuid,
    required String publicKey,
    required String shortId,
    required String sni,
  }) {
    final Map<String, dynamic> config = {
      "log": {"level": "warn"},
      "dns": {
        "servers": [
          {
            "tag": "remote-dns",
            "address": "tcp://8.8.8.8",
            "detour": "proxy"
          },
          {
            "tag": "local-dns",
            "address": "local",
            "detour": "direct"
          }
        ],
        "rules": [
          {
            "geoip": ["ru"],
            "server": "local-dns"
          }
        ],
        "strategy": "ipv4_only"
      },
      "inbounds": [
        {
          "type": "tun",
          "tag": "tun-in",
          "interface_name": "tun0",
          "inet4_address": "172.19.0.1/30",
          "auto_route": true,
          "strict_route": true,
          "sniff": true
        }
      ],
      "outbounds": [
        {
          "type": "vless",
          "tag": "proxy",
          "server": serverAddress,
          "server_port": serverPort,
          "uuid": uuid,
          "flow": "xtls-rprx-vision",
          "tls": {
            "enabled": true,
            "server_name": sni,
            "utls": {
              "enabled": true,
              "fingerprint": "chrome"
            },
            "reality": {
              "enabled": true,
              "public_key": publicKey,
              "short_id": shortId
            }
          }
        },
        {
          "type": "direct",
          "tag": "direct"
        },
        {
          "type": "dns",
          "tag": "dns-out"
        }
      ],
      "route": {
        "rules": [
          {
            "protocol": "dns",
            "outbound": "dns-out"
          },
          {
            "ip_is_private": true,
            "outbound": "direct"
          },
          {
            "geoip": ["ru"],
            "outbound": "direct"
          }
        ],
        "auto_detect_interface": true
      }
    };

    return const JsonEncoder.withIndent('  ').convert(config);
  }
}
