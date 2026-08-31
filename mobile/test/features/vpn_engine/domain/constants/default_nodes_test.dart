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

  test('server endpoint is 89.19.217.190:39783', () {
    expect(node.serverAddress, '89.19.217.190');
    expect(node.serverPort, 39783);
  });

  test('publicKey is the server key and is unchanged', () {
    expect(node.publicKey, 's1bBvq1mlFNu+VeAJSP3lD4PGz/SJhAM9Jw3HPNuekw=');
  });
}
