import 'dart:async';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'vpn_event.dart';
import 'vpn_state.dart';
import '../../data/datasources/native_vpn_data_source.dart';
import '../../domain/entities/vpn_profile.dart';
import '../../domain/generators/amnezia_wg_config_generator.dart';
import '../../domain/generators/singbox_config_generator.dart';

class VpnBloc extends Bloc<VpnEvent, VpnState> {
  final NativeVpnDataSource _dataSource;
  StreamSubscription<VpnConnectionStatus>? _statusSub;
  StreamSubscription<Map<String, int>>? _statsSub;

  VpnBloc({required NativeVpnDataSource dataSource})
      : _dataSource = dataSource,
        super(const VpnState()) {
    on<InitializeVpnEvent>(_onInitialize);
    on<ToggleVpnEvent>(_onToggleVpn);
    on<ChangeProfileEvent>(_onChangeProfile);
    on<ToggleSplitTunnelingEvent>(_onToggleSplitTunneling);
    on<VpnStatusUpdatedEvent>(_onStatusUpdated);
    on<VpnStatsUpdatedEvent>(_onStatsUpdated);

    _initSubscriptions();
  }

  void _initSubscriptions() {
    _statusSub = _dataSource.statusStream.listen(
      (status) {
        if (!isClosed) {
          add(VpnStatusUpdatedEvent(status));
        }
      },
      onError: (_) {
        if (!isClosed) {
          add(const VpnStatusUpdatedEvent(VpnConnectionStatus.error));
        }
      },
    );

    _statsSub = _dataSource.trafficStatsStream.listen(
      (stats) {
        if (!isClosed) {
          add(VpnStatsUpdatedEvent(
            rxBytes: stats['rx'] ?? 0,
            txBytes: stats['tx'] ?? 0,
          ));
        }
      },
      onError: (_) {},
    );
  }

  Future<void> _onInitialize(InitializeVpnEvent event, Emitter<VpnState> emit) async {
    final currentStatus = await _dataSource.getTunnelState();
    if (currentStatus != VpnConnectionStatus.disconnected) {
      emit(state.copyWith(status: currentStatus));
    }
  }

  Future<void> _onToggleVpn(ToggleVpnEvent event, Emitter<VpnState> emit) async {
    if (state.isDisconnecting) return;

    if (state.isConnected || state.isConnecting) {
      emit(state.copyWith(status: VpnConnectionStatus.disconnecting));
      await _dataSource.stopTunnel();
      emit(state.copyWith(status: VpnConnectionStatus.disconnected));
    } else {
      emit(state.copyWith(
        status: VpnConnectionStatus.connecting,
        errorMessage: null,
      ));

      final profile = state.currentProfile;

      try {
        final config = _generateConfig(profile);
        final success = await _dataSource.startTunnel(config);
        if (success) {
          emit(state.copyWith(status: VpnConnectionStatus.connected));
        } else {
          emit(state.copyWith(
            status: VpnConnectionStatus.error,
            errorMessage: "Не удалось установить соединение с сервером",
          ));
        }
      } catch (e) {
        emit(state.copyWith(
          status: VpnConnectionStatus.error,
          errorMessage: "Ошибка конфигурации: $e",
        ));
      }
    }
  }

  String _generateConfig(VpnProfile profile) {
    switch (profile.protocolType) {
      case VpnProtocolType.amneziaWg:
        if (profile.amneziaParams == null) {
          throw StateError('Параметры AmneziaWG не настроены для профиля: ${profile.name}');
        }
        return AmneziaWgConfigGenerator.generateClientConfig(
          clientPrivateKey: profile.clientPrivateKey ?? "cHJpdmF0ZWtleXRlc3Q=",
          clientAddress: profile.clientAddress ?? "10.8.1.2/32",
          serverPublicKey: profile.publicKey ?? "dn+S2ksWUSFdjL69a8Q2rk+cBhV6Nt+YOAM2QVwmpAQ=",
          serverAddress: profile.serverAddress,
          serverPort: profile.serverPort,
          params: profile.amneziaParams!,
          presharedKey: profile.presharedKey,
        );

      case VpnProtocolType.vlessReality:
        return SingBoxConfigGenerator.generateVlessRealityConfig(
          serverAddress: profile.serverAddress,
          serverPort: profile.serverPort,
          uuid: profile.uuid ?? "",
          publicKey: profile.publicKey ?? "",
          shortId: profile.shortId ?? "",
          sni: profile.sni ?? "www.microsoft.com",
        );

      case VpnProtocolType.hysteria2:
      case VpnProtocolType.auto:
        return SingBoxConfigGenerator.generateVlessRealityConfig(
          serverAddress: profile.serverAddress,
          serverPort: profile.serverPort,
          uuid: profile.uuid ?? "",
          publicKey: profile.publicKey ?? "",
          shortId: profile.shortId ?? "",
          sni: profile.sni ?? "www.microsoft.com",
        );
    }
  }

  void _onChangeProfile(ChangeProfileEvent event, Emitter<VpnState> emit) {
    emit(state.copyWith(currentProfile: event.profile));
  }

  void _onToggleSplitTunneling(ToggleSplitTunnelingEvent event, Emitter<VpnState> emit) {
    emit(state.copyWith(splitTunnelingEnabled: event.enabled));
  }

  void _onStatusUpdated(VpnStatusUpdatedEvent event, Emitter<VpnState> emit) {
    emit(state.copyWith(status: event.status));
  }

  void _onStatsUpdated(VpnStatsUpdatedEvent event, Emitter<VpnState> emit) {
    emit(state.copyWith(rxBytes: event.rxBytes, txBytes: event.txBytes));
  }

  @override
  Future<void> close() async {
    await _statusSub?.cancel();
    await _statsSub?.cancel();
    return super.close();
  }
}
