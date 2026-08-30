import 'dart:async';
import 'dart:math';
import '../../domain/entities/vpn_profile.dart';
import 'native_vpn_data_source.dart';

class WebMockVpnDataSource implements NativeVpnDataSource {
  final StreamController<VpnConnectionStatus> _statusController =
      StreamController<VpnConnectionStatus>.broadcast();
  final StreamController<Map<String, int>> _statsController =
      StreamController<Map<String, int>>.broadcast();

  VpnConnectionStatus _currentStatus = VpnConnectionStatus.disconnected;
  Timer? _statsTimer;
  int _rx = 0;
  int _tx = 0;

  @override
  Future<bool> startTunnel(String configJson) async {
    _currentStatus = VpnConnectionStatus.connecting;
    _statusController.add(VpnConnectionStatus.connecting);

    await Future<void>.delayed(const Duration(milliseconds: 600));
    _currentStatus = VpnConnectionStatus.connected;
    _statusController.add(VpnConnectionStatus.connected);

    _rx = 24 * 1024 * 1024; // 24 MB start
    _tx = 3 * 1024 * 1024;  // 3 MB start
    _statsController.add({'rx': _rx, 'tx': _tx});

    _statsTimer?.cancel();
    _statsTimer = Timer.periodic(const Duration(seconds: 1), (timer) {
      final random = Random();
      _rx += 1024 * 1024 + random.nextInt(1024 * 512);
      _tx += 1024 * 64 + random.nextInt(1024 * 64);
      _statsController.add({'rx': _rx, 'tx': _tx});
    });

    return true;
  }

  @override
  Future<bool> stopTunnel() async {
    _statsTimer?.cancel();
    _currentStatus = VpnConnectionStatus.disconnecting;
    _statusController.add(VpnConnectionStatus.disconnecting);

    await Future<void>.delayed(const Duration(milliseconds: 300));
    _currentStatus = VpnConnectionStatus.disconnected;
    _statusController.add(VpnConnectionStatus.disconnected);
    return true;
  }

  @override
  Future<VpnConnectionStatus> getTunnelState() async {
    return _currentStatus;
  }

  @override
  Stream<VpnConnectionStatus> get statusStream => _statusController.stream;

  @override
  Stream<Map<String, int>> get trafficStatsStream => _statsController.stream;
}
