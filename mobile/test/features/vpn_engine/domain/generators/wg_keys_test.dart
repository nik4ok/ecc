import 'package:flutter_test/flutter_test.dart';
import 'package:vpn_app/features/vpn_engine/domain/generators/wg_keys.dart';

void main() {
  group('WgKeys.isValid', () {
    test('returns false for null', () {
      expect(WgKeys.isValid(null), isFalse);
    });

    test('returns false for empty or whitespace', () {
      expect(WgKeys.isValid(''), isFalse);
      expect(WgKeys.isValid('   '), isFalse);
    });

    test('returns false for the historic stub key (not 32 bytes)', () {
      expect(WgKeys.isValid('cHJpdmF0ZWtleXRlc3Q='), isFalse);
    });

    test('returns false for invalid base64', () {
      expect(WgKeys.isValid('not-valid-base64!!!'), isFalse);
    });

    test('returns true for a 32-byte dummy key used in unit tests', () {
      expect(
        WgKeys.isValid('dGVzdHByaXZhdGVrZXkxMjM0NTY3ODkwMTIzNDU2Nzg='),
        isTrue,
      );
    });
  });

  group('WgKeys.toHex', () {
    test('returns null for invalid keys', () {
      expect(WgKeys.toHex(null), isNull);
      expect(WgKeys.toHex(''), isNull);
      expect(WgKeys.toHex('cHJpdmF0ZWtleXRlc3Q='), isNull);
    });

    test('encodes a 32-byte key as 64 lowercase hex chars', () {
      const b64 = 'dGVzdHByaXZhdGVrZXkxMjM0NTY3ODkwMTIzNDU2Nzg=';
      final hex = WgKeys.toHex(b64);
      expect(hex, isNotNull);
      expect(hex!.length, 64);
      expect(hex, hex.toLowerCase());
      expect(RegExp(r'^[0-9a-f]+$').hasMatch(hex), isTrue);
    });
  });
}
