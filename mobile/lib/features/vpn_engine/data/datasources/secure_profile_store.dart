import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class SecureProfileStore {
  static const FlutterSecureStorage _storage = FlutterSecureStorage(
    aOptions: AndroidOptions(encryptedSharedPreferences: true),
    iOptions: IOSOptions(accessibility: KeychainAccessibility.first_unlock),
  );

  static const String _keyPrefix = 'stealth_vpn_';

  static Future<void> saveClientPrivateKey(String profileId, String privateKey) async {
    await _storage.write(
      key: '${_keyPrefix}privkey_$profileId',
      value: privateKey,
    );
  }

  static Future<String?> getClientPrivateKey(String profileId) async {
    return await _storage.read(key: '${_keyPrefix}privkey_$profileId');
  }

  static Future<void> saveAuthToken(String token) async {
    await _storage.write(key: '${_keyPrefix}auth_token', value: token);
  }

  static Future<String?> getAuthToken() async {
    return await _storage.read(key: '${_keyPrefix}auth_token');
  }

  static Future<void> deleteProfileKeys(String profileId) async {
    await _storage.delete(key: '${_keyPrefix}privkey_$profileId');
  }

  static Future<void> clearAll() async {
    await _storage.deleteAll();
  }
}
