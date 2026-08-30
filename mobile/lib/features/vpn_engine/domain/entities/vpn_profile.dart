import 'package:equatable/equatable.dart';
import 'amnezia_wg_params.dart';

enum VpnProtocolType { amneziaWg, vlessReality, hysteria2, auto }

enum VpnConnectionStatus { disconnected, connecting, handshaking, connected, disconnecting, error }

class VpnProfile extends Equatable {
  final String id;
  final String name;
  final String serverAddress;
  final int serverPort;
  final VpnProtocolType protocolType;
  
  // VLESS Reality fields
  final String? uuid;
  final String? publicKey;
  final String? shortId;
  final String? sni;
  
  // Hysteria 2 fields
  final String? hysteriaPassword;
  final String? obfsPassword;

  // AmneziaWG fields
  final String? clientPrivateKey;
  final String? clientAddress;
  final String? presharedKey;
  final AmneziaWgParams? amneziaParams;

  const VpnProfile({
    required this.id,
    required this.name,
    required this.serverAddress,
    required this.serverPort,
    required this.protocolType,
    this.uuid,
    this.publicKey,
    this.shortId,
    this.sni,
    this.hysteriaPassword,
    this.obfsPassword,
    this.clientPrivateKey,
    this.clientAddress,
    this.presharedKey,
    this.amneziaParams,
  });

  @override
  List<Object?> get props => [
        id,
        name,
        serverAddress,
        serverPort,
        protocolType,
        uuid,
        publicKey,
        shortId,
        sni,
        hysteriaPassword,
        obfsPassword,
        clientAddress,
        presharedKey,
        amneziaParams,
      ];
}
