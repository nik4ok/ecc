import 'package:equatable/equatable.dart';

enum SplitTunnelMode { off, bypassSelected, tunnelSelectedOnly }

class SplitTunnelPolicy extends Equatable {
  final SplitTunnelMode mode;
  final Set<String> bypassPackages;
  final Set<String> bypassDomains;
  final Set<String> bypassCidrs;

  const SplitTunnelPolicy({
    this.mode = SplitTunnelMode.bypassSelected,
    this.bypassPackages = const {},
    this.bypassDomains = const {},
    this.bypassCidrs = const {},
  });

  @override
  List<Object?> get props => [mode, bypassPackages, bypassDomains, bypassCidrs];
}
