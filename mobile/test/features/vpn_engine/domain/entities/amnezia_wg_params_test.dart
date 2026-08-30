// ignore_for_file: prefer_const_constructors
import 'package:flutter_test/flutter_test.dart';
import 'package:vpn_app/features/vpn_engine/domain/entities/amnezia_wg_params.dart';

void main() {
  group('AmneziaWgParams.validate()', () {
    // ── helpers ──────────────────────────────────────────────────────────────

    AmneziaWgParams make({
      int jc = 5,
      int jmin = 50,
      int jmax = 1000,
      int s1 = 0,
      int s2 = 0,
      int h1 = 1,
      int h2 = 2,
      int h3 = 3,
      int h4 = 4,
    }) =>
        AmneziaWgParams(
          jc: jc,
          jmin: jmin,
          jmax: jmax,
          s1: s1,
          s2: s2,
          h1: h1,
          h2: h2,
          h3: h3,
          h4: h4,
        );

    // ── happy path ───────────────────────────────────────────────────────────

    test('returns empty errors list for valid params', () {
      expect(make().validate(), isEmpty);
    });

    test('isValid is true when validate() returns no errors', () {
      expect(make().isValid, isTrue);
    });

    // ── Jc boundary tests ────────────────────────────────────────────────────

    test('Jc = 1 is accepted (lower boundary)', () {
      expect(make(jc: 1).validate(), isEmpty);
    });

    test('Jc = 128 is accepted (upper boundary)', () {
      expect(make(jc: 128).validate(), isEmpty);
    });

    test('Jc = 0 produces an error', () {
      final errors = make(jc: 0).validate();
      expect(errors, hasLength(1));
      expect(errors.first, contains('Jc'));
    });

    test('Jc = 129 produces an error', () {
      final errors = make(jc: 129).validate();
      expect(errors, hasLength(1));
      expect(errors.first, contains('Jc'));
    });

    test('Jc = -1 produces an error', () {
      final errors = make(jc: -1).validate();
      expect(errors, hasLength(1));
    });

    // ── Jmin / Jmax relationship ──────────────────────────────────────────────

    test('Jmin < Jmax is valid', () {
      expect(make(jmin: 50, jmax: 51).validate(), isEmpty);
    });

    test('Jmin == Jmax produces an error', () {
      final errors = make(jmin: 100, jmax: 100).validate();
      expect(errors, hasLength(1));
      expect(errors.first, contains('Jmin'));
    });

    test('Jmin > Jmax produces an error', () {
      final errors = make(jmin: 200, jmax: 100).validate();
      expect(errors, hasLength(1));
      expect(errors.first, contains('Jmin'));
    });

    // ── Jmax upper boundary ───────────────────────────────────────────────────

    test('Jmax = 1280 is accepted (upper boundary)', () {
      expect(make(jmin: 50, jmax: 1280).validate(), isEmpty);
    });

    test('Jmax = 1281 produces an error', () {
      final errors = make(jmin: 50, jmax: 1281).validate();
      expect(errors, hasLength(1));
      expect(errors.first, contains('Jmax'));
    });

    // ── Multiple errors ───────────────────────────────────────────────────────

    test('multiple invalid fields return multiple errors', () {
      final errors = make(jc: 0, jmin: 500, jmax: 100).validate();
      // Jc invalid + Jmin > Jmax
      expect(errors.length, greaterThanOrEqualTo(2));
    });

    // ── isValid convenience getter ────────────────────────────────────────────

    test('isValid is false when there are validation errors', () {
      expect(make(jc: 0).isValid, isFalse);
    });

    // ── Equatable ─────────────────────────────────────────────────────────────

    test('two params with same values are equal', () {
      final a = make();
      final b = make();
      expect(a, equals(b));
    });

    test('two params with different jc are not equal', () {
      expect(make(jc: 1), isNot(equals(make(jc: 2))));
    });

    test('optional s3/s4 null vs value affects equality', () {
      final withS3 = AmneziaWgParams(
        jc: 5, jmin: 50, jmax: 1000, s1: 0, s2: 0,
        h1: 1, h2: 2, h3: 3, h4: 4, s3: 42,
      );
      expect(withS3, isNot(equals(make())));
    });
  });
}
