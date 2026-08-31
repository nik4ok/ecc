import 'dart:convert';

/// WireGuard/X25519 key helpers. Never log private keys.
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
}
