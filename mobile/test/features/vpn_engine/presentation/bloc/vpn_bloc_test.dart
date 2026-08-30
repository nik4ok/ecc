import 'dart:async';
import 'package:bloc_test/bloc_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:vpn_app/features/vpn_engine/data/datasources/native_vpn_data_source.dart';
import 'package:vpn_app/features/vpn_engine/domain/entities/vpn_profile.dart';
import 'package:vpn_app/features/vpn_engine/presentation/bloc/vpn_bloc.dart';
import 'package:vpn_app/features/vpn_engine/presentation/bloc/vpn_event.dart';
import 'package:vpn_app/features/vpn_engine/presentation/bloc/vpn_state.dart';
import '../../../../helpers/vpn_test_helpers.dart';

void main() {
  late MockNativeVpnDataSource mockDataSource;
  late StreamController<VpnConnectionStatus> statusCtrl;
  late StreamController<Map<String, int>> statsCtrl;

  setUpAll(() {
    registerFallbackValue(VpnConnectionStatus.disconnected);
  });

  setUp(() {
    mockDataSource = MockNativeVpnDataSource();
    final controllers = stubDataSource(mockDataSource);
    statusCtrl = controllers.status;
    statsCtrl = controllers.stats;
  });

  tearDown(() async {
    await statusCtrl.close();
    await statsCtrl.close();
  });

  VpnBloc buildBloc() => VpnBloc(dataSource: mockDataSource);

  // ── Initial state ─────────────────────────────────────────────────────────────

  group('initial state', () {
    test('status is disconnected', () {
      expect(buildBloc().state.status, VpnConnectionStatus.disconnected);
    });

    test('rxBytes and txBytes are 0', () {
      final s = buildBloc().state;
      expect(s.rxBytes, 0);
      expect(s.txBytes, 0);
    });

    test('splitTunnelingEnabled is true', () {
      expect(buildBloc().state.splitTunnelingEnabled, isTrue);
    });

    test('errorMessage is null', () {
      expect(buildBloc().state.errorMessage, isNull);
    });
  });

  // ── ToggleVpnEvent: Connect (AmneziaWG) ─────────────────────────────────────

  group('ToggleVpnEvent — connect via AmneziaWG', () {
    blocTest<VpnBloc, VpnState>(
      'emits [connecting] on successful startTunnel and waits for native CONNECTED',
      build: () {
        stubDataSource(mockDataSource);
        return VpnBloc(dataSource: mockDataSource);
      },
      seed: () => VpnState(currentProfile: amneziaProfile()),
      act: (bloc) => bloc.add(const ToggleVpnEvent()),
      expect: () => [
        isA<VpnState>().having((s) => s.status, 'status', VpnConnectionStatus.connecting),
      ],
    );

    blocTest<VpnBloc, VpnState>(
      'promotes to connected only when native stream emits CONNECTED',
      build: () {
        final controllers = stubDataSource(mockDataSource);
        statusCtrl = controllers.status;
        statsCtrl = controllers.stats;
        return VpnBloc(dataSource: mockDataSource);
      },
      seed: () => VpnState(currentProfile: amneziaProfile()),
      act: (bloc) async {
        bloc.add(const ToggleVpnEvent());
        await Future<void>.delayed(Duration.zero);
        statusCtrl.add(VpnConnectionStatus.connected);
      },
      expect: () => [
        isA<VpnState>().having((s) => s.status, 'status', VpnConnectionStatus.connecting),
        isA<VpnState>().having((s) => s.status, 'status', VpnConnectionStatus.connected),
      ],
    );

    blocTest<VpnBloc, VpnState>(
      'ignores stale native DISCONNECTED while still connecting after permission dialog',
      build: () {
        final controllers = stubDataSource(mockDataSource);
        statusCtrl = controllers.status;
        statsCtrl = controllers.stats;
        return VpnBloc(dataSource: mockDataSource);
      },
      seed: () => VpnState(currentProfile: amneziaProfile()),
      act: (bloc) async {
        bloc.add(const ToggleVpnEvent());
        await Future<void>.delayed(Duration.zero);
        statusCtrl.add(VpnConnectionStatus.disconnected);
      },
      expect: () => [
        isA<VpnState>().having((s) => s.status, 'status', VpnConnectionStatus.connecting),
      ],
    );

    blocTest<VpnBloc, VpnState>(
      'calls startTunnel exactly once',
      build: () {
        stubDataSource(mockDataSource);
        return VpnBloc(dataSource: mockDataSource);
      },
      seed: () => VpnState(currentProfile: amneziaProfile()),
      act: (bloc) => bloc.add(const ToggleVpnEvent()),
      verify: (_) => verify(() => mockDataSource.startTunnel(any())).called(1),
    );
  });

  // ── ToggleVpnEvent: Connect (VLESS Reality) ─────────────────────────────────

  group('ToggleVpnEvent — connect via VLESS Reality', () {
    blocTest<VpnBloc, VpnState>(
      'emits [connecting] for VLESS profile until native confirms CONNECTED',
      build: () {
        stubDataSource(mockDataSource);
        return VpnBloc(dataSource: mockDataSource);
      },
      seed: () => VpnState(currentProfile: vlessProfile()),
      act: (bloc) => bloc.add(const ToggleVpnEvent()),
      expect: () => [
        isA<VpnState>().having((s) => s.status, 'status', VpnConnectionStatus.connecting),
      ],
    );
  });

  // ── ToggleVpnEvent: Failure scenario ────────────────────────────────────────

  group('ToggleVpnEvent — startTunnel returns false (VPN permission denied / OS refusal)', () {
    blocTest<VpnBloc, VpnState>(
      'emits [connecting, error] when startTunnel returns false',
      build: () {
        stubDataSource(mockDataSource, startTunnelResult: false);
        return VpnBloc(dataSource: mockDataSource);
      },
      seed: () => VpnState(currentProfile: amneziaProfile()),
      act: (bloc) => bloc.add(const ToggleVpnEvent()),
      expect: () => [
        isA<VpnState>().having((s) => s.status, 'status', VpnConnectionStatus.connecting),
        isA<VpnState>()
            .having((s) => s.status, 'status', VpnConnectionStatus.error)
            .having((s) => s.errorMessage, 'errorMessage', isNotNull),
      ],
    );

    blocTest<VpnBloc, VpnState>(
      'error state includes non-empty errorMessage',
      build: () {
        stubDataSource(mockDataSource, startTunnelResult: false);
        return VpnBloc(dataSource: mockDataSource);
      },
      seed: () => VpnState(currentProfile: amneziaProfile()),
      act: (bloc) => bloc.add(const ToggleVpnEvent()),
      verify: (bloc) {
        expect(bloc.state.errorMessage, isNotEmpty);
      },
    );
  });

  // ── ToggleVpnEvent: Disconnect ────────────────────────────────────────────────

  group('ToggleVpnEvent — disconnect', () {
    blocTest<VpnBloc, VpnState>(
      'emits [disconnecting, disconnected] when currently connected',
      build: () {
        stubDataSource(mockDataSource);
        return VpnBloc(dataSource: mockDataSource);
      },
      seed: () => VpnState(
        status: VpnConnectionStatus.connected,
        currentProfile: amneziaProfile(),
      ),
      act: (bloc) => bloc.add(const ToggleVpnEvent()),
      expect: () => [
        isA<VpnState>().having((s) => s.status, 'status', VpnConnectionStatus.disconnecting),
        isA<VpnState>().having((s) => s.status, 'status', VpnConnectionStatus.disconnected),
      ],
    );

    blocTest<VpnBloc, VpnState>(
      'calls stopTunnel exactly once when connected',
      build: () {
        stubDataSource(mockDataSource);
        return VpnBloc(dataSource: mockDataSource);
      },
      seed: () => const VpnState(status: VpnConnectionStatus.connected),
      act: (bloc) => bloc.add(const ToggleVpnEvent()),
      verify: (_) => verify(() => mockDataSource.stopTunnel()).called(1),
    );

    blocTest<VpnBloc, VpnState>(
      'emits [disconnecting, disconnected] when in connecting state',
      build: () {
        stubDataSource(mockDataSource);
        return VpnBloc(dataSource: mockDataSource);
      },
      seed: () => const VpnState(status: VpnConnectionStatus.connecting),
      act: (bloc) => bloc.add(const ToggleVpnEvent()),
      expect: () => [
        isA<VpnState>().having((s) => s.status, 'status', VpnConnectionStatus.disconnecting),
        isA<VpnState>().having((s) => s.status, 'status', VpnConnectionStatus.disconnected),
      ],
    );
  });

  // ── ChangeProfileEvent ────────────────────────────────────────────────────────

  group('ChangeProfileEvent', () {
    blocTest<VpnBloc, VpnState>(
      'updates currentProfile in state',
      build: buildBloc,
      act: (bloc) => bloc.add(ChangeProfileEvent(vlessProfile())),
      expect: () => [
        isA<VpnState>().having(
          (s) => s.currentProfile.id,
          'profileId',
          'test-vless-1',
        ),
      ],
    );

    blocTest<VpnBloc, VpnState>(
      'does not change connection status when profile changes',
      build: buildBloc,
      seed: () => const VpnState(status: VpnConnectionStatus.disconnected),
      act: (bloc) => bloc.add(ChangeProfileEvent(vlessProfile())),
      verify: (bloc) {
        expect(bloc.state.status, VpnConnectionStatus.disconnected);
      },
    );
  });

  // ── ToggleSplitTunnelingEvent ────────────────────────────────────────────────

  group('ToggleSplitTunnelingEvent', () {
    blocTest<VpnBloc, VpnState>(
      'disables split tunneling',
      build: buildBloc,
      act: (bloc) => bloc.add(const ToggleSplitTunnelingEvent(false)),
      expect: () => [
        isA<VpnState>().having((s) => s.splitTunnelingEnabled, 'splitTunnelingEnabled', isFalse),
      ],
    );

    blocTest<VpnBloc, VpnState>(
      'enables split tunneling',
      build: buildBloc,
      seed: () => const VpnState(splitTunnelingEnabled: false),
      act: (bloc) => bloc.add(const ToggleSplitTunnelingEvent(true)),
      expect: () => [
        isA<VpnState>().having((s) => s.splitTunnelingEnabled, 'splitTunnelingEnabled', isTrue),
      ],
    );
  });

  // ── VpnStatusUpdatedEvent (native stream ─────────────────────────────────────

  group('VpnStatusUpdatedEvent from native stream', () {
    blocTest<VpnBloc, VpnState>(
      'reflects handshaking status pushed by native layer',
      build: buildBloc,
      act: (bloc) {
        statusCtrl.add(VpnConnectionStatus.handshaking);
      },
      expect: () => [
        isA<VpnState>().having((s) => s.status, 'status', VpnConnectionStatus.handshaking),
      ],
    );

    blocTest<VpnBloc, VpnState>(
      'isConnecting is true when status is handshaking',
      build: buildBloc,
      act: (bloc) {
        statusCtrl.add(VpnConnectionStatus.handshaking);
      },
      verify: (bloc) => expect(bloc.state.isConnecting, isTrue),
    );

    blocTest<VpnBloc, VpnState>(
      'reflects error status pushed by native layer',
      build: buildBloc,
      act: (bloc) {
        statusCtrl.add(VpnConnectionStatus.error);
      },
      expect: () => [
        isA<VpnState>().having((s) => s.status, 'status', VpnConnectionStatus.error),
      ],
    );

    blocTest<VpnBloc, VpnState>(
      'unexpected native disconnect while connected becomes error, not silent snap-back',
      build: buildBloc,
      seed: () => const VpnState(status: VpnConnectionStatus.connected),
      act: (bloc) {
        statusCtrl.add(VpnConnectionStatus.disconnected);
      },
      expect: () => [
        isA<VpnState>()
            .having((s) => s.status, 'status', VpnConnectionStatus.error)
            .having((s) => s.errorMessage, 'errorMessage', isNotNull),
      ],
    );

    // Simulates: user denied VPN permission → native side emits error
    blocTest<VpnBloc, VpnState>(
      'recovers to disconnected when native emits disconnected after error',
      build: buildBloc,
      act: (bloc) {
        statusCtrl.add(VpnConnectionStatus.error);
        statusCtrl.add(VpnConnectionStatus.disconnected);
      },
      expect: () => [
        isA<VpnState>().having((s) => s.status, 'status', VpnConnectionStatus.error),
        isA<VpnState>().having((s) => s.status, 'status', VpnConnectionStatus.disconnected),
      ],
    );
  });

  // ── VpnStatsUpdatedEvent ─────────────────────────────────────────────────────

  group('VpnStatsUpdatedEvent from native stream', () {
    blocTest<VpnBloc, VpnState>(
      'updates rxBytes and txBytes',
      build: buildBloc,
      act: (bloc) {
        statsCtrl.add({'rx': 1024, 'tx': 2048});
      },
      expect: () => [
        isA<VpnState>()
            .having((s) => s.rxBytes, 'rxBytes', 1024)
            .having((s) => s.txBytes, 'txBytes', 2048),
      ],
    );

    blocTest<VpnBloc, VpnState>(
      'handles missing rx/tx keys gracefully (defaults to 0)',
      build: buildBloc,
      act: (bloc) {
        statsCtrl.add({});
      },
      expect: () => [
        isA<VpnState>()
            .having((s) => s.rxBytes, 'rxBytes', 0)
            .having((s) => s.txBytes, 'txBytes', 0),
      ],
    );

    blocTest<VpnBloc, VpnState>(
      'handles large byte counters (>2^32) without overflow',
      build: buildBloc,
      act: (bloc) {
        statsCtrl.add({'rx': 5000000000, 'tx': 8000000000});
      },
      expect: () => [
        isA<VpnState>()
            .having((s) => s.rxBytes, 'rxBytes', 5000000000)
            .having((s) => s.txBytes, 'txBytes', 8000000000),
      ],
    );
  });

  // ── State convenience getters ────────────────────────────────────────────────

  group('VpnState convenience getters', () {
    test('isConnected is true only when status == connected', () {
      const s = VpnState(status: VpnConnectionStatus.connected);
      expect(s.isConnected, isTrue);
      expect(const VpnState(status: VpnConnectionStatus.connecting).isConnected, isFalse);
    });

    test('isConnecting is true for connecting and handshaking', () {
      expect(
        const VpnState(status: VpnConnectionStatus.connecting).isConnecting,
        isTrue,
      );
      expect(
        const VpnState(status: VpnConnectionStatus.handshaking).isConnecting,
        isTrue,
      );
      expect(
        const VpnState(status: VpnConnectionStatus.connected).isConnecting,
        isFalse,
      );
    });

    test('isDisconnecting is true only for disconnecting status', () {
      expect(
        const VpnState(status: VpnConnectionStatus.disconnecting).isDisconnecting,
        isTrue,
      );
      expect(
        const VpnState(status: VpnConnectionStatus.connected).isDisconnecting,
        isFalse,
      );
    });
  });

  // ── copyWith preserves unchanged fields ──────────────────────────────────────

  group('VpnState.copyWith', () {
    test('only changes specified fields', () {
      const original = VpnState(
        status: VpnConnectionStatus.connected,
        rxBytes: 500,
        txBytes: 1000,
        splitTunnelingEnabled: false,
      );
      final updated = original.copyWith(status: VpnConnectionStatus.disconnected);

      expect(updated.status, VpnConnectionStatus.disconnected);
      expect(updated.rxBytes, 500);
      expect(updated.txBytes, 1000);
      expect(updated.splitTunnelingEnabled, isFalse);
    });

    test('copyWith clears errorMessage when not passed (null reset)', () {
      const original = VpnState(errorMessage: 'some error');
      final updated = original.copyWith(status: VpnConnectionStatus.disconnected);
      // errorMessage is not carried over (see copyWith implementation)
      expect(updated.errorMessage, isNull);
    });
  });

  // ── Bloc close() cancels subscriptions ──────────────────────────────────────

  test('close() cancels native stream subscriptions without error', () async {
    final bloc = buildBloc();
    await expectLater(bloc.close(), completes);
  });
}
