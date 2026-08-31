import 'package:flutter_test/flutter_test.dart';
import 'package:vpn_app/features/vpn_engine/domain/constants/default_nodes.dart';
import 'package:vpn_app/features/vpn_engine/domain/generators/amnezia_wg_config_generator.dart';
import 'package:vpn_app/features/vpn_engine/domain/generators/amnezia_wg_userspace_converter.dart';
import 'package:vpn_app/features/vpn_engine/domain/generators/wg_keys.dart';

void main() {
  const node = DefaultNodes.netherlandsAmneziaWg;

  String productionIni() {
    return AmneziaWgConfigGenerator.generateClientConfig(
      clientPrivateKey: node.clientPrivateKey!,
      clientAddress: node.clientAddress!,
      serverPublicKey: node.publicKey!,
      serverAddress: node.serverAddress,
      serverPort: node.serverPort,
      params: node.amneziaParams!,
      presharedKey: node.presharedKey,
    );
  }

  test('UAPI contains header_protection_key as 64 hex chars, not Base64', () {
    final uapi = AmneziaWgUserspaceConverter.fromQuickConfig(productionIni());
    final hpkHex = WgKeys.toHex(node.amneziaParams!.headerProtectionKey);
    expect(hpkHex, isNotNull);
    expect(hpkHex!.length, 64);
    expect(uapi, contains('header_protection_key=$hpkHex'));
    expect(uapi, isNot(contains('HeaderProtectionKey')));
    expect(uapi, isNot(contains(node.amneziaParams!.headerProtectionKey)));
  });

  test('UAPI uses hex private_key and public_key', () {
    final uapi = AmneziaWgUserspaceConverter.fromQuickConfig(productionIni());
    expect(uapi, contains('private_key=${WgKeys.toHex(node.clientPrivateKey)}'));
    expect(uapi, contains('public_key=${WgKeys.toHex(node.publicKey)}'));
    expect(uapi, contains('preshared_key=${WgKeys.toHex(node.presharedKey)}'));
  });

  test('UAPI keeps Amnezia junk and magic headers', () {
    final uapi = AmneziaWgUserspaceConverter.fromQuickConfig(productionIni());
    expect(uapi, contains('jc=5'));
    expect(uapi, contains('jmin=10'));
    expect(uapi, contains('jmax=50'));
    expect(uapi, contains('s1=45'));
    expect(uapi, contains('s2=81'));
    expect(uapi, contains('s3=60'));
    expect(uapi, contains('s4=12'));
    expect(uapi, contains('h1=1'));
    expect(uapi, contains('h2=2'));
    expect(uapi, contains('h3=3'));
    expect(uapi, contains('h4=4'));
  });

  test('UAPI includes replace_peers, endpoint and keepalive', () {
    final uapi = AmneziaWgUserspaceConverter.fromQuickConfig(productionIni());
    expect(uapi, contains('replace_peers=true'));
    expect(uapi, contains('endpoint=89.19.217.190:39783'));
    expect(uapi, contains('persistent_keepalive_interval=25'));
    expect(uapi, contains('allowed_ip=0.0.0.0/0'));
    expect(uapi, contains('allowed_ip=::/0'));
  });

  test('UAPI omits VpnService-only fields', () {
    final uapi = AmneziaWgUserspaceConverter.fromQuickConfig(productionIni());
    expect(uapi, isNot(contains('Address')));
    expect(uapi, isNot(contains('DNS')));
    expect(uapi, isNot(contains('MTU')));
  });

  test('UAPI omits header_protection_key when INI has none', () {
    final ini = productionIni().replaceAll(
      RegExp(r'HeaderProtectionKey = .+\n'),
      '',
    );
    final uapi = AmneziaWgUserspaceConverter.fromQuickConfig(ini);
    expect(uapi, isNot(contains('header_protection_key=')));
  });
}
