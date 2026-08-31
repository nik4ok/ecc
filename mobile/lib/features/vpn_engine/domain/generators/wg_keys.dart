import 'dart:convert';
import 'dart:math';
import 'dart:typed_data';

import 'x25519.dart';

/// WireGuard/X25519 key helpers. Never log private keys.
class WgKeyPair {
  final String privateKey;
  final String publicKey;

  const WgKeyPair({required this.privateKey, required this.publicKey});
}

class WgKeys {
  const WgKeys._();

  /// True when [key] is standard Base64 of exactly 32 bytes.
  static bool isValid(String? key) {
    if (key == null) return false;
    final trimmed = key.trim();
    if (trimmed.isEmpty) return false;
    try {
      final bytes = base64Decode(trimmed);
      return bytes.length == 32;
    } on FormatException {
      return false;
    }
  }

  /// WireGuard UAPI form: 64 lowercase hex chars, or null if [key] is invalid.
  static String? toHex(String? key) {
    if (!isValid(key)) {
      return null;
    }
    final bytes = base64Decode(key!.trim());
    final buffer = StringBuffer();
    for (final byte in bytes) {
      buffer.write(byte.toRadixString(16).padLeft(2, '0'));
    }
    return buffer.toString();
  }

  static Future<WgKeyPair> generateKeyPair() async {
    final random = Random.secure();
    final privateBytes = Uint8List.fromList(
      List<int>.generate(32, (_) => random.nextInt(256)),
    );
    privateBytes[0] &= 248;
    privateBytes[31] &= 127;
    privateBytes[31] |= 64;
    final publicBytes = X25519.publicFromPrivate(privateBytes);
    return WgKeyPair(
      privateKey: base64Encode(privateBytes),
      publicKey: base64Encode(publicBytes),
    );
  }

  static Future<String> publicKeyFromPrivate(String privateKey) async {
    if (!isValid(privateKey)) {
      throw ArgumentError('private key must be 32-byte Base64');
    }
    final publicBytes = X25519.publicFromPrivate(base64Decode(privateKey.trim()));
    return base64Encode(publicBytes);
  }
}
