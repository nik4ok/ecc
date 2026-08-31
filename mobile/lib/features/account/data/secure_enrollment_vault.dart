import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import 'enrollment_vault.dart';

class SecureEnrollmentVault implements EnrollmentVault {
  static const _privateKeyKey = 'nova_enroll_priv';
  static const _ticketKey = 'nova_enroll_ticket';

  final FlutterSecureStorage _storage;

  SecureEnrollmentVault({FlutterSecureStorage? storage})
      : _storage = storage ??
            const FlutterSecureStorage(
              aOptions: AndroidOptions(encryptedSharedPreferences: true),
              iOptions: IOSOptions(accessibility: KeychainAccessibility.first_unlock),
            );

  @override
  Future<String?> readPrivateKey() => _storage.read(key: _privateKeyKey);

  @override
  Future<String?> readTicketJson() => _storage.read(key: _ticketKey);

  @override
  Future<void> save({required String privateKey, String? ticketJson}) async {
    await _storage.write(key: _privateKeyKey, value: privateKey);
    if (ticketJson != null) {
      await _storage.write(key: _ticketKey, value: ticketJson);
    }
  }
}
