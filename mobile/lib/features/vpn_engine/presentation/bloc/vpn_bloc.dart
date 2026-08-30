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
    on<ToggleVpnEvent>(_onToggleVpn);
    on<ChangeProfileEvent>(_onChangeProfile);
    on<ToggleSplitTunnelingEvent>(_onToggleSplitTunneling);
    on<VpnStatusUpdatedEvent>(_onStatusUpdated);
    on<VpnStatsUpdatedEvent>(_onStatsUpdated);

    _statusSub = _dataSource.statusStream.listen((status) {
      add(VpnStatusUpdatedEvent(status));
    });

    _statsSub = _dataSource.trafficStatsStream.listen((stats) {
      add(VpnStatsUpdatedEvent(
        rxBytes: stats['rx'] ?? 0,
        txBytes: stats['tx'] ?? 0,
      ));
    });
  }

  Future<void> _onToggleVpn(ToggleVpnEvent event, Emitter<VpnState> emit) async {
    if (state.isConnected || state.isConnecting) {
      emit(state.copyWith(status: VpnConnectionStatus.disconnecting));
      await _dataSource.stopTunnel();
      emit(state.copyWith(status: VpnConnectionStatus.disconnected));
    } else {
      emit(state.copyWith(status: VpnConnectionStatus.connecting));
      final profile = state.currentProfile;

      String config;
      if (profile.protocolType == VpnProtocolType.amneziaWg && profile.amneziaParams != null) {
        config = AmneziaWgConfigGenerator.generateClientConfig(
          clientPrivateKey: profile.clientPrivateKey ?? "aGVsbG93b3JsZHByaXZhdGVrZXkxMjM0NTY3ODkwMTI=",
          clientAddress: profile.clientAddress ?? "10.8.1.2/32",
          serverPublicKey: profile.publicKey ?? "dn+S2ksWUSFdjL69a8Q2rk+cBhV6Nt+YOAM2QVwmpAQ=",
          serverAddress: profile.serverAddress,
          serverPort: profile.serverPort,
          params: profile.amneziaParams!,
          presharedKey: profile.presharedKey,
        );
      } else {
        config = SingBoxConfigGenerator.generateVlessRealityConfig(
          serverAddress: profile.serverAddress,
          serverPort: profile.serverPort,
          uuid: profile.uuid ?? "",
          publicKey: profile.publicKey ?? "",
          shortId: profile.shortId ?? "",
          sni: profile.sni ?? "www.microsoft.com",
        );
      }

      final success = await _dataSource.startTunnel(config);
      if (success) {
        emit(state.copyWith(status: VpnConnectionStatus.connected));
      } else {
        emit(state.copyWith(
          status: VpnConnectionStatus.error,
          errorMessage: "Не удалось установить соединение",
        ));
      }
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
  Future<void> close() {
    _statusSub?.cancel();
    _statsSub?.cancel();
    return super.close();
  }
}
