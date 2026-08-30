import 'package:equatable/equatable.dart';
import '../../domain/entities/vpn_profile.dart';
import '../../domain/constants/default_nodes.dart';

class VpnState extends Equatable {
  final VpnConnectionStatus status;
  final VpnProfile currentProfile;
  final bool splitTunnelingEnabled;
  final int rxBytes;
  final int txBytes;
  final String? errorMessage;

  const VpnState({
    this.status = VpnConnectionStatus.disconnected,
    this.currentProfile = DefaultNodes.netherlandsAmneziaWg,
    this.splitTunnelingEnabled = true,
    this.rxBytes = 0,
    this.txBytes = 0,
    this.errorMessage,
  });

  bool get isConnected => status == VpnConnectionStatus.connected;
  bool get isConnecting => status == VpnConnectionStatus.connecting || status == VpnConnectionStatus.handshaking;
  bool get isDisconnecting => status == VpnConnectionStatus.disconnecting;

  VpnState copyWith({
    VpnConnectionStatus? status,
    VpnProfile? currentProfile,
    bool? splitTunnelingEnabled,
    int? rxBytes,
    int? txBytes,
    String? errorMessage,
  }) {
    return VpnState(
      status: status ?? this.status,
      currentProfile: currentProfile ?? this.currentProfile,
      splitTunnelingEnabled: splitTunnelingEnabled ?? this.splitTunnelingEnabled,
      rxBytes: rxBytes ?? this.rxBytes,
      txBytes: txBytes ?? this.txBytes,
      errorMessage: errorMessage,
    );
  }

  @override
  List<Object?> get props => [
        status,
        currentProfile,
        splitTunnelingEnabled,
        rxBytes,
        txBytes,
        errorMessage,
      ];
}
