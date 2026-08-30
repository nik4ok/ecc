import 'dart:async';
import 'package:flutter/services.dart';
import '../../domain/entities/vpn_profile.dart';

abstract class NativeVpnDataSource {
  Future<bool> startTunnel(String configJson);
  Future<bool> stopTunnel();
  Future<VpnConnectionStatus> getTunnelState();
  Stream<VpnConnectionStatus> get statusStream;
  Stream<Map<String, int>> get trafficStatsStream;
}

class NativeVpnDataSourceImpl implements NativeVpnDataSource {
  static const MethodChannel _channel = MethodChannel('com.vpn.app/engine');
  static const EventChannel _statusEventChannel = EventChannel('com.vpn.app/status');
  static const EventChannel _statsEventChannel = EventChannel('com.vpn.app/stats');

  @override
  Future<bool> startTunnel(String configJson) async {
    try {
      final bool? result = await _channel.invokeMethod<bool>('startVpn', {
        'config': configJson,
      });
      return result ?? false;
    } on PlatformException catch (e) {
      if (e.code == 'PERMISSION_DENIED') {
        return false;
      }
      return _isTunnelActive();
    } catch (_) {
      return _isTunnelActive();
    }
  }

  Future<bool> _isTunnelActive() async {
    final status = await getTunnelState();
    return status == VpnConnectionStatus.connecting ||
        status == VpnConnectionStatus.handshaking ||
        status == VpnConnectionStatus.connected;
  }

  @override
  Future<bool> stopTunnel() async {
    try {
      final bool? result = await _channel.invokeMethod<bool>('stopVpn');
      return result ?? false;
    } catch (_) {
      return false;
    }
  }

  @override
  Future<VpnConnectionStatus> getTunnelState() async {
    try {
      final String? status = await _channel.invokeMethod<String>('getTunnelState');
      return _mapStatus(status) ?? VpnConnectionStatus.disconnected;
    } catch (_) {
      return VpnConnectionStatus.disconnected;
    }
  }

  @override
  Stream<VpnConnectionStatus> get statusStream {
    try {
      return _statusEventChannel.receiveBroadcastStream().map((dynamic event) {
        final statusStr = (event is Map ? event['status'] : event)?.toString();
        return _mapStatus(statusStr);
      }).where((status) => status != null).cast<VpnConnectionStatus>();
    } catch (_) {
      return const Stream.empty();
    }
  }

  @override
  Stream<Map<String, int>> get trafficStatsStream {
    try {
      return _statsEventChannel.receiveBroadcastStream().map((dynamic event) {
        if (event is Map) {
          return {
            'rx': (event['rx'] as num?)?.toInt() ?? 0,
            'tx': (event['tx'] as num?)?.toInt() ?? 0,
          };
        }
        return {'rx': 0, 'tx': 0};
      }).handleError((_) => {'rx': 0, 'tx': 0});
    } catch (_) {
      return const Stream.empty();
    }
  }
}

VpnConnectionStatus? _mapStatus(String? rawStatus) {
  switch (rawStatus?.toUpperCase()) {
    case 'CONNECTING':
      return VpnConnectionStatus.connecting;
    case 'HANDSHAKING':
      return VpnConnectionStatus.handshaking;
    case 'CONNECTED':
      return VpnConnectionStatus.connected;
    case 'DISCONNECTING':
      return VpnConnectionStatus.disconnecting;
    case 'ERROR':
      return VpnConnectionStatus.error;
    case 'DISCONNECTED':
      return VpnConnectionStatus.disconnected;
    default:
      return null;
  }
}
