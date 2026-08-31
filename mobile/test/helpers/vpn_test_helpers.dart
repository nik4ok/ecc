import 'dart:async';
import 'package:mocktail/mocktail.dart';
import 'package:vpn_app/features/vpn_engine/data/datasources/native_vpn_data_source.dart';
import 'package:vpn_app/features/vpn_engine/domain/entities/amnezia_wg_params.dart';
import 'package:vpn_app/features/vpn_engine/domain/entities/vpn_profile.dart';

// ─── Mocks ────────────────────────────────────────────────────────────────────

class MockNativeVpnDataSource extends Mock implements NativeVpnDataSource {}

// ─── Shared Test Fixtures ─────────────────────────────────────────────────────

/// Minimal valid AmneziaWG params (jc=5, jmin=50, jmax=1000).
AmneziaWgParams validParams() => const AmneziaWgParams(
      jc: 5,
      jmin: 50,
      jmax: 1000,
      s1: 0,
      s2: 0,
      h1: 1,
      h2: 2,
      h3: 3,
      h4: 4,
    );

/// VpnProfile wired for AmneziaWG protocol with [validParams].
VpnProfile amneziaProfile() => VpnProfile(
      id: 'test-awg-1',
      name: 'Test AmneziaWG',
      serverAddress: '1.2.3.4',
      serverPort: 51820,
      protocolType: VpnProtocolType.amneziaWg,
      clientPrivateKey: 'dGVzdHByaXZhdGVrZXkxMjM0NTY3ODkwMTIzNDU2Nzg=',
      clientAddress: '10.8.0.2/32',
      publicKey: 'dGVzdHByaXZhdGVrZXkxMjM0NTY3ODkwMTIzNDU2Nzg=',
      amneziaParams: validParams(),
    );

/// VpnProfile for VLESS Reality protocol.
VpnProfile vlessProfile() => const VpnProfile(
      id: 'test-vless-1',
      name: 'Test VLESS',
      serverAddress: '5.6.7.8',
      serverPort: 443,
      protocolType: VpnProtocolType.vlessReality,
      uuid: '00000000-0000-0000-0000-000000000001',
      publicKey: 'dGVzdHB1YmxpY2tleXRlc3RwdWJsaWNrZXl0ZXN0cA==',
      shortId: 'abcdef01',
      sni: 'www.microsoft.com',
    );

// ─── Stream Controllers ────────────────────────────────────────────────────────

/// Creates a broadcast [StreamController] pair for [VpnConnectionStatus].
/// Remember to close it after each test.
StreamController<VpnConnectionStatus> makeStatusController() =>
    StreamController<VpnConnectionStatus>.broadcast();

StreamController<Map<String, int>> makeStatsController() =>
    StreamController<Map<String, int>>.broadcast();

/// Stubs [mock] with ready-to-use controllers; returns them for test control.
({
  StreamController<VpnConnectionStatus> status,
  StreamController<Map<String, int>> stats,
}) stubDataSource(
  MockNativeVpnDataSource mock, {
  bool startTunnelResult = true,
  bool stopTunnelResult = true,
}) {
  final status = makeStatusController();
  final stats = makeStatsController();

  when(() => mock.statusStream).thenAnswer((_) => status.stream);
  when(() => mock.trafficStatsStream).thenAnswer((_) => stats.stream);
  when(() => mock.startTunnel(any()))
      .thenAnswer((_) async => startTunnelResult);
  when(() => mock.stopTunnel()).thenAnswer((_) async => stopTunnelResult);

  return (status: status, stats: stats);
}
