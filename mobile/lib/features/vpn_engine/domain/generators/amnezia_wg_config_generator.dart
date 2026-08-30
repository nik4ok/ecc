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
    int mtu = 1280,
    int persistentKeepalive = 25,
  }) {
    final errors = params.validate();
    if (errors.isNotEmpty) {
      throw ArgumentError('Invalid AmneziaWG parameters: ${errors.join('; ')}');
    }

    final buffer = StringBuffer()
      ..writeln('[Interface]')
      ..writeln('PrivateKey = $clientPrivateKey')
      ..writeln('Address = $clientAddress')
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

    if (params.headerProtectionKey != null && params.headerProtectionKey!.isNotEmpty) {
      buffer.writeln('HeaderProtectionKey = ${params.headerProtectionKey}');
    }

    buffer
      ..writeln()
      ..writeln('[Peer]')
      ..writeln('PublicKey = $serverPublicKey');

    if (presharedKey != null && presharedKey.isNotEmpty) {
      buffer.writeln('PresharedKey = $presharedKey');
    }

    buffer
      ..writeln('AllowedIPs = ${allowedIps.join(', ')}')
      ..writeln('Endpoint = $serverAddress:$serverPort')
      ..writeln('PersistentKeepalive = $persistentKeepalive');

    return buffer.toString();
  }
}
