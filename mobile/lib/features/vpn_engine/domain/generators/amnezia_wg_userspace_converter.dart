import 'wg_keys.dart';

/// Converts a wg-quick / Amnezia INI into amneziawg-go UAPI (IpcSet) text.
///
/// HeaderProtectionKey is Base64 in the INI and hex in UAPI. The 2.3.7
/// Maven AAR dropped that key; v3 IpcSet applies it as header_protection_key.
class AmneziaWgUserspaceConverter {
  const AmneziaWgUserspaceConverter._();

  static const _interfaceKeys = <String, String>{
    'Jc': 'jc',
    'Jmin': 'jmin',
    'Jmax': 'jmax',
    'S1': 's1',
    'S2': 's2',
    'S3': 's3',
    'S4': 's4',
    'H1': 'h1',
    'H2': 'h2',
    'H3': 'h3',
    'H4': 'h4',
  };

  static const _keyFields = <String>{
    'PrivateKey',
    'PublicKey',
    'PresharedKey',
    'HeaderProtectionKey',
  };

  static String fromQuickConfig(String ini) {
    final lines = <String>[];
    var section = '';
    var seenPeer = false;

    void startPeer() {
      if (!seenPeer) {
        lines.add('replace_peers=true');
        seenPeer = true;
      }
    }

    for (final raw in ini.split('\n')) {
      final line = raw.trim();
      if (line.isEmpty || line.startsWith('#')) {
        continue;
      }
      if (line == '[Interface]') {
        section = 'interface';
        continue;
      }
      if (line == '[Peer]') {
        section = 'peer';
        startPeer();
        continue;
      }
      final eq = line.indexOf('=');
      if (eq <= 0) {
        continue;
      }
      final key = line.substring(0, eq).trim();
      final value = line.substring(eq + 1).trim();
      if (section == 'interface') {
        _appendInterface(lines, key, value);
      } else if (section == 'peer') {
        _appendPeer(lines, key, value);
      }
    }

    if (lines.isEmpty) {
      throw ArgumentError('AmneziaWG INI produced an empty UAPI config');
    }
    return '${lines.join('\n')}\n';
  }

  static void _appendInterface(List<String> lines, String key, String value) {
    if (key == 'PrivateKey') {
      final hex = WgKeys.toHex(value);
      if (hex == null) {
        throw ArgumentError('Invalid PrivateKey in AmneziaWG INI');
      }
      lines.add('private_key=$hex');
      return;
    }
    if (key == 'HeaderProtectionKey') {
      final hex = WgKeys.toHex(value);
      if (hex == null) {
        throw ArgumentError('Invalid HeaderProtectionKey in AmneziaWG INI');
      }
      lines.add('header_protection_key=$hex');
      return;
    }
    final mapped = _interfaceKeys[key];
    if (mapped != null) {
      lines.add('$mapped=$value');
    }
  }

  static void _appendPeer(List<String> lines, String key, String value) {
    if (key == 'PublicKey') {
      final hex = WgKeys.toHex(value);
      if (hex == null) {
        throw ArgumentError('Invalid PublicKey in AmneziaWG INI');
      }
      lines.add('public_key=$hex');
      return;
    }
    if (key == 'PresharedKey') {
      final hex = WgKeys.toHex(value);
      if (hex == null) {
        throw ArgumentError('Invalid PresharedKey in AmneziaWG INI');
      }
      lines.add('preshared_key=$hex');
      return;
    }
    if (key == 'AllowedIPs') {
      for (final part in value.split(',')) {
        final ip = part.trim();
        if (ip.isNotEmpty) {
          lines.add('allowed_ip=$ip');
        }
      }
      return;
    }
    if (key == 'Endpoint') {
      lines.add('endpoint=$value');
      return;
    }
    if (key == 'PersistentKeepalive') {
      lines.add('persistent_keepalive_interval=$value');
    }
  }
}
