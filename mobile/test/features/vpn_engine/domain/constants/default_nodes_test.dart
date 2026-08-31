import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:vpn_app/features/vpn_engine/domain/constants/default_nodes.dart';

void main() {
  const node = DefaultNodes.netherlandsAmneziaWg;

  test('clientAddress is the client tunnel IP, not the server', () {
    expect(node.clientAddress, '10.8.1.2/32');
  });

  test('clientPrivateKey base64-decodes to 32 bytes', () {
    final key = node.clientPrivateKey;
    expect(key, isNotNull);
    expect(key, isNotEmpty);
    final bytes = base64Decode(key!);
    expect(bytes.length, 32);
  });

  test('server endpoint is 92.51.46.12:38037', () {
    expect(node.serverAddress, '92.51.46.12');
    expect(node.serverPort, 38037);
  });

  test('publicKey is the server key and is unchanged', () {
    expect(node.publicKey, 'dn+S2ksWUSFdjL69a8Q2rk+cBhV6Nt+YOAM2QVwmpAQ=');
  });
}
