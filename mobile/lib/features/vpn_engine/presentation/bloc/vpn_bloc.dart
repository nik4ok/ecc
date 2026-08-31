import 'dart:async';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'vpn_event.dart';
import 'vpn_state.dart';
import '../../data/datasources/native_vpn_data_source.dart';
import '../../domain/entities/vpn_profile.dart';
import '../../domain/generators/amnezia_wg_config_generator.dart';
import '../../domain/generators/singbox_config_generator.dart';
import '../../domain/generators/wg_keys.dart';

class _HandshakeTimeoutEvent extends VpnEvent {
  const _HandshakeTimeoutEvent();
}

class VpnBloc extends Bloc<VpnEvent, VpnState> {
  static const String handshakeTimeoutMessage = 'Сервер не ответил на рукопожатие';
  static const String invalidClientKeyMessage = 'Не задан корректный ключ клиента';

  final NativeVpnDataSource _dataSource;
  final Duration _handshakeTimeoutDuration;
  StreamSubscription<VpnConnectionStatus>? _statusSub;
  StreamSubscription<Map<String, int>>? _statsSub;
  Timer? _handshakeTimer;

  VpnBloc({
    required NativeVpnDataSource dataSource,
    Duration handshakeTimeout = const Duration(seconds: 20),
  })  : _dataSource = dataSource,
        _handshakeTimeoutDuration = handshakeTimeout,
        super(const VpnState()) {
    on<InitializeVpnEvent>(_onInitialize);
    on<ToggleVpnEvent>(_onToggleVpn);
    on<ChangeProfileEvent>(_onChangeProfile);
    on<ToggleSplitTunnelingEvent>(_onToggleSplitTunneling);
    on<VpnStatusUpdatedEvent>(_onStatusUpdated);
    on<VpnStatsUpdatedEvent>(_onStatsUpdated);
    on<_HandshakeTimeoutEvent>(_onHandshakeTimeout);

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

  void _cancelHandshakeTimeout() {
    _handshakeTimer?.cancel();
    _handshakeTimer = null;
  }

  void _armHandshakeTimeout() {
    _cancelHandshakeTimeout();
    _handshakeTimer = Timer(_handshakeTimeoutDuration, () {
      if (!isClosed) {
        add(const _HandshakeTimeoutEvent());
      }
    });
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
      _cancelHandshakeTimeout();
      emit(state.copyWith(status: VpnConnectionStatus.disconnecting));
      await _dataSource.stopTunnel();
      emit(state.copyWith(status: VpnConnectionStatus.disconnected));
    } else {
      final profile = state.currentProfile;

      if (profile.protocolType == VpnProtocolType.amneziaWg) {
        final clientPrivateKey = profile.clientPrivateKey;
        if (clientPrivateKey == null || !WgKeys.isValid(clientPrivateKey)) {
          emit(state.copyWith(
            status: VpnConnectionStatus.error,
            errorMessage: invalidClientKeyMessage,
          ));
          return;
        }
      }

      emit(state.copyWith(
        status: VpnConnectionStatus.connecting,
        errorMessage: null,
      ));
      _armHandshakeTimeout();

      try {
        final config = _generateConfig(profile);
        final success = await _dataSource.startTunnel(config);
        if (!success && state.isConnecting) {
          _cancelHandshakeTimeout();
          emit(state.copyWith(
            status: VpnConnectionStatus.error,
            errorMessage: "Не удалось установить соединение с сервером",
          ));
        }
      } catch (e) {
        _cancelHandshakeTimeout();
        emit(state.copyWith(
          status: VpnConnectionStatus.error,
          errorMessage: "Ошибка конфигурации: $e",
        ));
      }
    }
  }

  Future<void> _onHandshakeTimeout(
    _HandshakeTimeoutEvent event,
    Emitter<VpnState> emit,
  ) async {
    if (!state.isConnecting) return;
    _cancelHandshakeTimeout();
    await _dataSource.stopTunnel();
    emit(state.copyWith(
      status: VpnConnectionStatus.error,
      errorMessage: handshakeTimeoutMessage,
    ));
  }

  String _generateConfig(VpnProfile profile) {
    switch (profile.protocolType) {
      case VpnProtocolType.amneziaWg:
        if (profile.amneziaParams == null) {
          throw StateError('Параметры AmneziaWG не настроены для профиля: ${profile.name}');
        }
        final clientPrivateKey = profile.clientPrivateKey;
        if (clientPrivateKey == null || !WgKeys.isValid(clientPrivateKey)) {
          throw StateError(invalidClientKeyMessage);
        }
        return AmneziaWgConfigGenerator.generateClientConfig(
          clientPrivateKey: clientPrivateKey,
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
    if (event.status == VpnConnectionStatus.disconnected &&
        state.isConnecting &&
        !state.isDisconnecting) {
      return;
    }

    if (event.status == VpnConnectionStatus.disconnected &&
        state.isConnected &&
        !state.isDisconnecting) {
      _cancelHandshakeTimeout();
      emit(state.copyWith(
        status: VpnConnectionStatus.error,
        errorMessage:
            'Система закрыла VPN сразу после разрешения. Проверьте уведомления и повторите подключение.',
      ));
      return;
    }

    if (event.status == VpnConnectionStatus.error) {
      _cancelHandshakeTimeout();
      emit(state.copyWith(
        status: VpnConnectionStatus.error,
        errorMessage: state.errorMessage ?? handshakeTimeoutMessage,
      ));
      return;
    }

    if (event.status == VpnConnectionStatus.connected ||
        event.status == VpnConnectionStatus.disconnected) {
      _cancelHandshakeTimeout();
    }

    emit(state.copyWith(status: event.status));
  }

  void _onStatsUpdated(VpnStatsUpdatedEvent event, Emitter<VpnState> emit) {
    emit(state.copyWith(rxBytes: event.rxBytes, txBytes: event.txBytes));
  }

  @override
  Future<void> close() async {
    _cancelHandshakeTimeout();
    await _statusSub?.cancel();
    await _statsSub?.cancel();
    return super.close();
  }
}
