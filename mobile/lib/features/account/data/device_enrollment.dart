import 'dart:convert';

import '../domain/access_ticket.dart';
import '../domain/ticket_to_profile.dart';
import '../../vpn_engine/domain/constants/default_nodes.dart';
import '../../vpn_engine/domain/entities/vpn_profile.dart';
import '../../vpn_engine/domain/generators/wg_keys.dart';
import 'enrollment_vault.dart';
import 'registration_api.dart';

abstract class Enrollment {
  Future<VpnProfile> ensureProfile();
}

/// Creates a device keypair, asks the cashier for a room, keeps the private key on the phone.
class DeviceEnrollment implements Enrollment {
  DeviceEnrollment({
    required this.api,
    required this.vault,
    required this.generateKeys,
    this.fallback = DefaultNodes.netherlandsAmneziaWg,
    this.timeout = const Duration(seconds: 5),
    this.displayName = 'Нидерланды (Амстердам)',
  });

  final RegistrationApi api;
  final EnrollmentVault vault;
  final Future<WgKeyPair> Function() generateKeys;
  final VpnProfile fallback;
  final Duration timeout;
  final String displayName;

  @override
  Future<VpnProfile> ensureProfile() async {
    try {
      return await _ensure();
    } on Exception {
      return fallback;
    }
  }

  Future<VpnProfile> _ensure() async {
    var privateKey = await vault.readPrivateKey();
    final savedTicket = await vault.readTicketJson();
    if (privateKey != null &&
        WgKeys.isValid(privateKey) &&
        _ticketIsForThisCashier(savedTicket)) {
      return _profileFromSaved(savedTicket!, privateKey);
    }

    late final String publicKey;
    if (privateKey == null || !WgKeys.isValid(privateKey)) {
      final pair = await generateKeys();
      privateKey = pair.privateKey;
      publicKey = pair.publicKey;
      await vault.save(privateKey: privateKey);
    } else {
      publicKey = await WgKeys.publicKeyFromPrivate(privateKey);
    }

    try {
      final ticket = await api
          .register(
            email: _emailFor(publicKey),
            displayName: displayName,
            publicKey: publicKey,
          )
          .timeout(timeout);
      await vault.save(
        privateKey: privateKey,
        ticketJson: jsonEncode({
          ...ticket.toJson(),
          'cashier_base_url': api.cashierUrl,
        }),
      );
      return profileFromTicket(ticket: ticket, clientPrivateKey: privateKey);
    } on Exception {
      if (privateKey != null &&
          WgKeys.isValid(privateKey) &&
          savedTicket != null &&
          savedTicket.isNotEmpty) {
        return _profileFromSaved(savedTicket, privateKey);
      }
      rethrow;
    }
  }

  bool _ticketIsForThisCashier(String? savedTicket) {
    if (savedTicket == null || savedTicket.isEmpty) {
      return false;
    }
    final decoded = jsonDecode(savedTicket);
    if (decoded is! Map) {
      return false;
    }
    final savedUrl = decoded['cashier_base_url'];
    return savedUrl is String && savedUrl == api.cashierUrl;
  }

  VpnProfile _profileFromSaved(String savedTicket, String privateKey) {
    return profileFromTicket(
      ticket: AccessTicket.fromJson(jsonDecode(savedTicket) as Map<String, dynamic>),
      clientPrivateKey: privateKey,
    );
  }

  String _emailFor(String publicKey) {
    final tag = publicKey.replaceAll(RegExp(r'[^A-Za-z0-9]'), '');
    final short = tag.length >= 8 ? tag.substring(0, 8) : tag;
    return 'nova-$short@device.local';
  }
}
