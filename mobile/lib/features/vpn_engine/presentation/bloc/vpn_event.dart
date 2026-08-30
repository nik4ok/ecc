import 'package:equatable/equatable.dart';
import '../../domain/entities/vpn_profile.dart';

abstract class VpnEvent extends Equatable {
  const VpnEvent();

  @override
  List<Object?> get props => [];
}

class InitializeVpnEvent extends VpnEvent {
  const InitializeVpnEvent();
}

class ToggleVpnEvent extends VpnEvent {
  const ToggleVpnEvent();
}

class ChangeProfileEvent extends VpnEvent {
  final VpnProfile profile;

  const ChangeProfileEvent(this.profile);

  @override
  List<Object?> get props => [profile];
}

class ToggleSplitTunnelingEvent extends VpnEvent {
  final bool enabled;

  const ToggleSplitTunnelingEvent(this.enabled);

  @override
  List<Object?> get props => [enabled];
}

class VpnStatusUpdatedEvent extends VpnEvent {
  final VpnConnectionStatus status;

  const VpnStatusUpdatedEvent(this.status);

  @override
  List<Object?> get props => [status];
}

class VpnStatsUpdatedEvent extends VpnEvent {
  final int rxBytes;
  final int txBytes;

  const VpnStatsUpdatedEvent({required this.rxBytes, required this.txBytes});

  @override
  List<Object?> get props => [rxBytes, txBytes];
}
