import 'package:equatable/equatable.dart';

/// What the cashier returns. Never contains the phone's private key.
class AccessTicket extends Equatable {
  final String userId;
  final String displayName;
  final String email;
  final String clientAddress;
  final String clientPublicKey;
  final String endpointHost;
  final int endpointPort;
  final String serverPublicKey;
  final String presharedKey;
  final Map<String, dynamic> amnezia;

  const AccessTicket({
    required this.userId,
    required this.displayName,
    required this.email,
    required this.clientAddress,
    required this.clientPublicKey,
    required this.endpointHost,
    required this.endpointPort,
    required this.serverPublicKey,
    required this.presharedKey,
    required this.amnezia,
  });

  factory AccessTicket.fromJson(Map<String, dynamic> json) {
    return AccessTicket(
      userId: json['user_id'] as String,
      displayName: json['display_name'] as String,
      email: json['email'] as String,
      clientAddress: json['client_address'] as String,
      clientPublicKey: json['client_public_key'] as String,
      endpointHost: json['endpoint_host'] as String,
      endpointPort: json['endpoint_port'] as int,
      serverPublicKey: json['server_public_key'] as String,
      presharedKey: json['preshared_key'] as String,
      amnezia: Map<String, dynamic>.from(json['amnezia'] as Map),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'user_id': userId,
      'display_name': displayName,
      'email': email,
      'client_address': clientAddress,
      'client_public_key': clientPublicKey,
      'endpoint_host': endpointHost,
      'endpoint_port': endpointPort,
      'server_public_key': serverPublicKey,
      'preshared_key': presharedKey,
      'amnezia': amnezia,
    };
  }

  @override
  List<Object?> get props => [
        userId,
        displayName,
        email,
        clientAddress,
        clientPublicKey,
        endpointHost,
        endpointPort,
        serverPublicKey,
        presharedKey,
        amnezia,
      ];
}
