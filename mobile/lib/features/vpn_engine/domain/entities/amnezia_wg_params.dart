import 'package:equatable/equatable.dart';

class AmneziaWgParams extends Equatable {
  final int jc;
  final int jmin;
  final int jmax;
  final int s1;
  final int s2;
  final int? s3;
  final int? s4;
  final int h1;
  final int h2;
  final int h3;
  final int h4;
  final String? headerProtectionKey;

  const AmneziaWgParams({
    required this.jc,
    required this.jmin,
    required this.jmax,
    required this.s1,
    required this.s2,
    this.s3,
    this.s4,
    required this.h1,
    required this.h2,
    required this.h3,
    required this.h4,
    this.headerProtectionKey,
  });

  List<String> validate() {
    final errors = <String>[];
    if (jc < 1 || jc > 128) errors.add('Jc must be between 1 and 128 (got $jc)');
    if (jmin >= jmax) errors.add('Jmin ($jmin) must be < Jmax ($jmax)');
    if (jmax > 1280) errors.add('Jmax must be <= 1280 (got $jmax)');
    return errors;
  }

  bool get isValid => validate().isEmpty;

  @override
  List<Object?> get props => [jc, jmin, jmax, s1, s2, s3, s4, h1, h2, h3, h4, headerProtectionKey];
}
