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

  group('WgKeys.generateKeyPair', () {
    test('private and public are valid 32-byte WireGuard keys', () async {
      final pair = await WgKeys.generateKeyPair();
      expect(WgKeys.isValid(pair.privateKey), isTrue);
      expect(WgKeys.isValid(pair.publicKey), isTrue);
      expect(pair.privateKey, isNot(pair.publicKey));
    });

    test('two generations are different', () async {
      final a = await WgKeys.generateKeyPair();
      final b = await WgKeys.generateKeyPair();
      expect(a.privateKey, isNot(b.privateKey));
      expect(a.publicKey, isNot(b.publicKey));
    });

    test('public key matches the RFC 7748 Alice vector', () async {
      const privateKey = 'dwdtCnMYpX08FsFyUbJmRd9ML4frwJkqsXf7pR25LCo=';
      const publicKey = 'hSDwCYkwp1R0i33ctD73Wg2/Og0mOBr066SpjqqbTmo=';
      expect(await WgKeys.publicKeyFromPrivate(privateKey), publicKey);
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
