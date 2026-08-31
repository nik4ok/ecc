import 'dart:typed_data';

/// RFC 7748 X25519. Used to derive a WireGuard public key from a 32-byte secret.
class X25519 {
  static final BigInt _p = (BigInt.one << 255) - BigInt.from(19);
  static final BigInt _a24 = BigInt.from(121665);

  static Uint8List publicFromPrivate(List<int> secret) {
    if (secret.length != 32) {
      throw ArgumentError('X25519 secret must be 32 bytes');
    }
    final base = Uint8List(32)..[0] = 9;
    return scalarmult(secret, base);
  }

  static Uint8List scalarmult(List<int> secret, List<int> point) {
    final clamped = Uint8List.fromList(secret);
    clamped[0] &= 248;
    clamped[31] &= 127;
    clamped[31] |= 64;

    var x1 = _decodeU(point);
    var x2 = BigInt.one;
    var z2 = BigInt.zero;
    var x3 = x1;
    var z3 = BigInt.one;
    var swap = 0;

    for (var t = 254; t >= 0; t--) {
      final kt = (clamped[t >> 3] >> (t & 7)) & 1;
      swap ^= kt;
      final swapped = _cswap(swap, x2, z2, x3, z3);
      x2 = swapped[0];
      z2 = swapped[1];
      x3 = swapped[2];
      z3 = swapped[3];
      swap = kt;

      final a = _mod(x2 + z2);
      final aa = _mod(a * a);
      final b = _mod(x2 - z2);
      final bb = _mod(b * b);
      final e = _mod(aa - bb);
      final c = _mod(x3 + z3);
      final d = _mod(x3 - z3);
      final da = _mod(d * a);
      final cb = _mod(c * b);
      x3 = _mod((da + cb) * (da + cb));
      z3 = _mod(x1 * ((da - cb) * (da - cb)));
      x2 = _mod(aa * bb);
      z2 = _mod(e * (aa + _mod(_a24 * e)));
    }

    final out = _cswap(swap, x2, z2, x3, z3);
    x2 = out[0];
    z2 = out[1];
    final x = _mod(x2 * z2.modPow(_p - BigInt.two, _p));
    return _encodeU(x);
  }

  static BigInt _mod(BigInt value) {
    var r = value % _p;
    if (r.isNegative) {
      r += _p;
    }
    return r;
  }

  static BigInt _decodeU(List<int> u) {
    final bytes = Uint8List.fromList(u);
    bytes[31] &= 127;
    return _decodeLittleEndian(bytes);
  }

  static BigInt _decodeLittleEndian(List<int> bytes) {
    var result = BigInt.zero;
    for (var i = bytes.length - 1; i >= 0; i--) {
      result = (result << 8) | BigInt.from(bytes[i]);
    }
    return result;
  }

  static Uint8List _encodeU(BigInt u) {
    var value = _mod(u);
    final out = Uint8List(32);
    for (var i = 0; i < 32; i++) {
      out[i] = (value & BigInt.from(255)).toInt();
      value = value >> 8;
    }
    return out;
  }

  static List<BigInt> _cswap(int swap, BigInt x2, BigInt z2, BigInt x3, BigInt z3) {
    if (swap == 0) {
      return [x2, z2, x3, z3];
    }
    return [x3, z3, x2, z2];
  }
}
