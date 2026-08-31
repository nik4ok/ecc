import '../entities/amnezia_wg_params.dart';

class AmneziaWgConfigGenerator {
  const AmneziaWgConfigGenerator._();

  static String generateClientConfig({
    required String clientPrivateKey,
    required String clientAddress,
    required String serverPublicKey,
    required String serverAddress,
    required int serverPort,
    required AmneziaWgParams params,
    String? presharedKey,
    List<String> dnsServers = const ['1.1.1.1', '8.8.8.8'],
    List<String> allowedIps = const ['0.0.0.0/0', '::/0'],
    int mtu = 1360,
    int persistentKeepalive = 25,
  }) {
    final errors = params.validate();
    if (errors.isNotEmpty) {
      throw ArgumentError('Invalid AmneziaWG parameters: ${errors.join('; ')}');
    }

    final isIpv6 = serverAddress.contains(':') && !serverAddress.startsWith('[');
    final endpoint = isIpv6 ? '[$serverAddress]:$serverPort' : '$serverAddress:$serverPort';

    final buffer = StringBuffer()
      ..writeln('[Interface]')
      ..writeln('PrivateKey = ${clientPrivateKey.trim()}')
      ..writeln('Address = ${clientAddress.trim()}')
      ..writeln('DNS = ${dnsServers.join(', ')}')
      ..writeln('MTU = $mtu')
      ..writeln('Jc = ${params.jc}')
      ..writeln('Jmin = ${params.jmin}')
      ..writeln('Jmax = ${params.jmax}')
      ..writeln('S1 = ${params.s1}')
      ..writeln('S2 = ${params.s2}');

    if (params.s3 != null) buffer.writeln('S3 = ${params.s3}');
    if (params.s4 != null) buffer.writeln('S4 = ${params.s4}');

    buffer
      ..writeln('H1 = ${params.h1}')
      ..writeln('H2 = ${params.h2}')
      ..writeln('H3 = ${params.h3}')
      ..writeln('H4 = ${params.h4}');

    if (params.headerProtectionKey != null && params.headerProtectionKey!.trim().isNotEmpty) {
      buffer.writeln('HeaderProtectionKey = ${params.headerProtectionKey!.trim()}');
    }
    if (params.contentPaddingAddition != null && params.contentPaddingAddition!.trim().isNotEmpty) {
      buffer.writeln('ContentPaddingAddition = ${params.contentPaddingAddition!.trim()}');
    }
    if (params.randomTrailers) {
      buffer.writeln('RandomTrailers = on');
    }
    if (params.disableCookies) {
      buffer.writeln('DisableCookies = on');
    }

    buffer
      ..writeln()
      ..writeln('[Peer]')
      ..writeln('PublicKey = ${serverPublicKey.trim()}');

    if (presharedKey != null && presharedKey.trim().isNotEmpty) {
      buffer.writeln('PresharedKey = ${presharedKey.trim()}');
    }

    buffer
      ..writeln('AllowedIPs = ${allowedIps.join(', ')}')
      ..writeln('Endpoint = $endpoint')
      ..writeln('PersistentKeepalive = $persistentKeepalive');

    return buffer.toString();
  }
}
