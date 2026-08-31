// ignore_for_file: prefer_const_constructors
import 'package:flutter_test/flutter_test.dart';
import 'package:vpn_app/features/vpn_engine/domain/constants/default_nodes.dart';
import 'package:vpn_app/features/vpn_engine/domain/entities/amnezia_wg_params.dart';
import 'package:vpn_app/features/vpn_engine/domain/generators/amnezia_wg_config_generator.dart';

void main() {
  // ── shared fixtures ──────────────────────────────────────────────────────────

  const validParams = AmneziaWgParams(
    jc: 5, jmin: 50, jmax: 1000, s1: 12, s2: 34, h1: 1, h2: 2, h3: 3, h4: 4,
  );

  String generate({
    AmneziaWgParams params = validParams,
    String clientPrivateKey = 'cHJpdmF0ZWtleXRlc3Q=',
    String clientAddress = '10.8.0.2/32',
    String serverPublicKey = 'cHVibGlja2V5dGVzdA==',
    String serverAddress = '1.2.3.4',
    int serverPort = 51820,
    String? presharedKey,
    List<String> dnsServers = const ['1.1.1.1', '8.8.8.8'],
    List<String> allowedIps = const ['0.0.0.0/0', '::/0'],
    int mtu = 1280,
    int persistentKeepalive = 25,
  }) =>
      AmneziaWgConfigGenerator.generateClientConfig(
        clientPrivateKey: clientPrivateKey,
        clientAddress: clientAddress,
        serverPublicKey: serverPublicKey,
        serverAddress: serverAddress,
        serverPort: serverPort,
        params: params,
        presharedKey: presharedKey,
        dnsServers: dnsServers,
        allowedIps: allowedIps,
        mtu: mtu,
        persistentKeepalive: persistentKeepalive,
      );

  // ── [Interface] section ──────────────────────────────────────────────────────

  group('Interface section', () {
    late String config;
    setUpAll(() => config = generate());

    test('contains [Interface] header', () {
      expect(config, contains('[Interface]'));
    });

    test('contains PrivateKey line', () {
      expect(config, contains('PrivateKey = cHJpdmF0ZWtleXRlc3Q='));
    });

    test('contains Address line', () {
      expect(config, contains('Address = 10.8.0.2/32'));
    });

    test('contains DNS line with both servers', () {
      expect(config, contains('DNS = 1.1.1.1, 8.8.8.8'));
    });

    test('contains MTU line', () {
      expect(config, contains('MTU = 1280'));
    });
  });

  // ── AmneziaWG obfuscation params ────────────────────────────────────────────

  group('AmneziaWG obfuscation params', () {
    late String config;
    setUpAll(() => config = generate());

    test('Jc is present', () => expect(config, contains('Jc = 5')));
    test('Jmin is present', () => expect(config, contains('Jmin = 50')));
    test('Jmax is present', () => expect(config, contains('Jmax = 1000')));
    test('S1 is present', () => expect(config, contains('S1 = 12')));
    test('S2 is present', () => expect(config, contains('S2 = 34')));
    test('H1 is present', () => expect(config, contains('H1 = 1')));
    test('H2 is present', () => expect(config, contains('H2 = 2')));
    test('H3 is present', () => expect(config, contains('H3 = 3')));
    test('H4 is present', () => expect(config, contains('H4 = 4')));

    test('S3 is absent when null', () => expect(config, isNot(contains('S3'))));
    test('S4 is absent when null', () => expect(config, isNot(contains('S4'))));

    test('S3 is present when provided', () {
      final c = generate(
        params: const AmneziaWgParams(
          jc: 5, jmin: 50, jmax: 1000, s1: 0, s2: 0,
          h1: 1, h2: 2, h3: 3, h4: 4, s3: 77,
        ),
      );
      expect(c, contains('S3 = 77'));
    });

    test('S4 is present when provided', () {
      final c = generate(
        params: const AmneziaWgParams(
          jc: 5, jmin: 50, jmax: 1000, s1: 0, s2: 0,
          h1: 1, h2: 2, h3: 3, h4: 4, s4: 88,
        ),
      );
      expect(c, contains('S4 = 88'));
    });

    test('HeaderProtectionKey is absent when null', () {
      expect(config, isNot(contains('HeaderProtectionKey')));
    });

    test('HeaderProtectionKey is absent when empty string', () {
      final c = generate(
        params: const AmneziaWgParams(
          jc: 5, jmin: 50, jmax: 1000, s1: 0, s2: 0,
          h1: 1, h2: 2, h3: 3, h4: 4, headerProtectionKey: '',
        ),
      );
      expect(c, isNot(contains('HeaderProtectionKey')));
    });

    test('HeaderProtectionKey is present when provided', () {
      final c = generate(
        params: const AmneziaWgParams(
          jc: 5, jmin: 50, jmax: 1000, s1: 0, s2: 0,
          h1: 1, h2: 2, h3: 3, h4: 4, headerProtectionKey: 'mykey',
        ),
      );
      expect(c, contains('HeaderProtectionKey = mykey'));
    });
  });

  // ── [Peer] section ───────────────────────────────────────────────────────────

  group('Peer section', () {
    late String config;
    setUpAll(() => config = generate());

    test('contains [Peer] header', () {
      expect(config, contains('[Peer]'));
    });

    test('contains server PublicKey', () {
      expect(config, contains('PublicKey = cHVibGlja2V5dGVzdA=='));
    });

    test('contains AllowedIPs', () {
      expect(config, contains('AllowedIPs = 0.0.0.0/0, ::/0'));
    });

    test('contains Endpoint with host:port', () {
      expect(config, contains('Endpoint = 1.2.3.4:51820'));
    });

    test('contains PersistentKeepalive', () {
      expect(config, contains('PersistentKeepalive = 25'));
    });

    test('PresharedKey is absent when null', () {
      expect(config, isNot(contains('PresharedKey')));
    });

    test('PresharedKey is absent when empty string', () {
      expect(generate(presharedKey: ''), isNot(contains('PresharedKey')));
    });

    test('PresharedKey is present when provided', () {
      expect(
        generate(presharedKey: 'mypsk'),
        contains('PresharedKey = mypsk'),
      );
    });
  });

  // ── Config ordering: Interface before Peer ────────────────────────────────────

  test('[Interface] section appears before [Peer] section', () {
    final config = generate();
    final interfaceIdx = config.indexOf('[Interface]');
    final peerIdx = config.indexOf('[Peer]');
    expect(interfaceIdx, lessThan(peerIdx));
  });

  // ── Custom DNS / AllowedIPs overrides ────────────────────────────────────────

  test('custom DNS servers appear in config', () {
    final c = generate(dnsServers: ['9.9.9.9', '149.112.112.112']);
    expect(c, contains('DNS = 9.9.9.9, 149.112.112.112'));
  });

  test('split-tunnel AllowedIPs appear in config', () {
    const splitIps = ['10.0.0.0/8', '192.168.0.0/16'];
    final c = generate(allowedIps: splitIps);
    expect(c, contains('AllowedIPs = 10.0.0.0/8, 192.168.0.0/16'));
  });

  test('custom MTU appears in config', () {
    expect(generate(mtu: 1420), contains('MTU = 1420'));
  });

  test('custom persistentKeepalive appears in config', () {
    expect(generate(persistentKeepalive: 60), contains('PersistentKeepalive = 60'));
  });

  test('implicit MTU default is 1360', () {
    final config = AmneziaWgConfigGenerator.generateClientConfig(
      clientPrivateKey: 'cHJpdmF0ZWtleXRlc3Q=',
      clientAddress: '10.8.0.2/32',
      serverPublicKey: 'cHVibGlja2V5dGVzdA==',
      serverAddress: '1.2.3.4',
      serverPort: 51820,
      params: validParams,
    );
    expect(config, contains('MTU = 1360'));
  });

  test('netherlandsAmneziaWg produces a handshake-ready INI', () {
    const node = DefaultNodes.netherlandsAmneziaWg;
    expect(node.clientPrivateKey, isNotNull);
    expect(node.clientAddress, isNotNull);
    expect(node.publicKey, isNotNull);
    expect(node.amneziaParams, isNotNull);

    final config = AmneziaWgConfigGenerator.generateClientConfig(
      clientPrivateKey: node.clientPrivateKey!,
      clientAddress: node.clientAddress!,
      serverPublicKey: node.publicKey!,
      serverAddress: node.serverAddress,
      serverPort: node.serverPort,
      params: node.amneziaParams!,
      presharedKey: node.presharedKey,
    );

    expect(config, contains('Address = 10.8.1.2/32'));
    expect(config, contains('Endpoint = 89.19.217.190:39783'));
    expect(config, contains('HeaderProtectionKey'));
    expect(config, contains('RandomTrailers = on'));
    expect(config, contains('DisableCookies = on'));
    expect(config, contains('ContentPaddingAddition = 10-100'));
    expect(config, contains('PresharedKey'));
    expect(config, contains('S3'));
    expect(config, contains('S4'));
    expect(config, contains('MTU = 1360'));
  });

  // ── Invalid params throw ArgumentError ────────────────────────────────────────

  group('throws ArgumentError on invalid AmneziaWgParams', () {
    test('Jc = 0 throws', () {
      expect(
        () => generate(
          params: const AmneziaWgParams(
            jc: 0, jmin: 50, jmax: 1000, s1: 0, s2: 0,
            h1: 1, h2: 2, h3: 3, h4: 4,
          ),
        ),
        throwsA(isA<ArgumentError>()),
      );
    });

    test('Jmin >= Jmax throws', () {
      expect(
        () => generate(
          params: const AmneziaWgParams(
            jc: 5, jmin: 1000, jmax: 500, s1: 0, s2: 0,
            h1: 1, h2: 2, h3: 3, h4: 4,
          ),
        ),
        throwsA(isA<ArgumentError>()),
      );
    });

    test('Jmax > 1280 throws', () {
      expect(
        () => generate(
          params: const AmneziaWgParams(
            jc: 5, jmin: 50, jmax: 1281, s1: 0, s2: 0,
            h1: 1, h2: 2, h3: 3, h4: 4,
          ),
        ),
        throwsA(isA<ArgumentError>()),
      );
    });

    test('error message mentions "Invalid AmneziaWG parameters"', () {
      expect(
        () => generate(
          params: const AmneziaWgParams(
            jc: 0, jmin: 50, jmax: 1000, s1: 0, s2: 0,
            h1: 1, h2: 2, h3: 3, h4: 4,
          ),
        ),
        throwsA(
          isA<ArgumentError>().having(
            (e) => e.message,
            'message',
            contains('Invalid AmneziaWG parameters'),
          ),
        ),
      );
    });
  });
}
