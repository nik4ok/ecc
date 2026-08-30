import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'features/vpn_engine/domain/entities/vpn_profile.dart';
import 'features/vpn_engine/domain/constants/default_nodes.dart';
import 'features/vpn_engine/data/datasources/native_vpn_data_source.dart';
import 'features/vpn_engine/presentation/bloc/vpn_bloc.dart';
import 'features/vpn_engine/presentation/bloc/vpn_event.dart';
import 'features/vpn_engine/presentation/bloc/vpn_state.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  final NativeVpnDataSource vpnDataSource = NativeVpnDataSourceImpl();
  runApp(StealthVpnApp(vpnDataSource: vpnDataSource));
}

class StealthVpnApp extends StatelessWidget {
  final NativeVpnDataSource vpnDataSource;

  const StealthVpnApp({super.key, required this.vpnDataSource});

  @override
  Widget build(BuildContext context) {
    return BlocProvider(
      create: (_) => VpnBloc(dataSource: vpnDataSource),
      child: MaterialApp(
        title: 'Stealth VPN',
        debugShowCheckedModeBanner: false,
        theme: ThemeData.dark().copyWith(
          scaffoldBackgroundColor: const Color(0xFF090D16),
          colorScheme: const ColorScheme.dark(
            primary: Color(0xFF0284C7),
            secondary: Color(0xFF10B981),
            surface: Color(0xFF0F172A),
          ),
        ),
        home: const VpnHomeScreen(),
      ),
    );
  }
}

class VpnHomeScreen extends StatefulWidget {
  const VpnHomeScreen({super.key});

  @override
  State<VpnHomeScreen> createState() => _VpnHomeScreenState();
}

class _VpnHomeScreenState extends State<VpnHomeScreen> with SingleTickerProviderStateMixin {
  late AnimationController _pulseController;

  @override
  void initState() {
    super.initState();
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 2),
    )..repeat(reverse: true);
  }

  @override
  void dispose() {
    _pulseController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return BlocBuilder<VpnBloc, VpnState>(
      builder: (context, state) {
        final isConnected = state.isConnected;
        final isConnecting = state.isConnecting;

        return Scaffold(
          body: SafeArea(
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 24.0, vertical: 20.0),
              child: Column(
                children: [
                  // Top Bar
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text(
                            'STEALTH VPN',
                            style: TextStyle(
                              fontSize: 22,
                              fontWeight: FontWeight.w900,
                              letterSpacing: 1.5,
                              color: Colors.white,
                            ),
                          ),
                          const SizedBox(height: 2),
                          Row(
                            children: [
                              Container(
                                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                decoration: BoxDecoration(
                                  color: const Color(0xFF0284C7).withOpacity(0.2),
                                  borderRadius: BorderRadius.circular(4),
                                ),
                                child: const Text(
                                  'AmneziaWG 2.0',
                                  style: TextStyle(
                                    fontSize: 10,
                                    fontWeight: FontWeight.bold,
                                    color: Color(0xFF38BDF8),
                                  ),
                                ),
                              ),
                              const SizedBox(width: 6),
                              Text(
                                '1 Gbps • Анти-DPI',
                                style: TextStyle(
                                  fontSize: 11,
                                  color: Colors.grey.shade400,
                                ),
                              ),
                            ],
                          ),
                        ],
                      ),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                        decoration: BoxDecoration(
                          color: isConnected
                              ? const Color(0xFF10B981).withOpacity(0.15)
                              : isConnecting
                                  ? const Color(0xFFF59E0B).withOpacity(0.15)
                                  : Colors.grey.withOpacity(0.1),
                          borderRadius: BorderRadius.circular(20),
                          border: Border.all(
                            color: isConnected
                                ? const Color(0xFF10B981)
                                : isConnecting
                                    ? const Color(0xFFF59E0B)
                                    : Colors.grey.shade800,
                          ),
                        ),
                        child: Row(
                          children: [
                            CircleAvatar(
                              radius: 4,
                              backgroundColor: isConnected
                                  ? const Color(0xFF10B981)
                                  : isConnecting
                                      ? const Color(0xFFF59E0B)
                                      : Colors.grey.shade600,
                            ),
                            const SizedBox(width: 6),
                            Text(
                              isConnected
                                  ? 'ЗАЩИЩЕНО'
                                  : isConnecting
                                      ? 'ПОДКЛЮЧЕНИЕ'
                                      : 'ОТКЛЮЧЕНО',
                              style: TextStyle(
                                fontSize: 10,
                                fontWeight: FontWeight.bold,
                                color: isConnected
                                    ? const Color(0xFF10B981)
                                    : isConnecting
                                        ? const Color(0xFFF59E0B)
                                        : Colors.grey.shade400,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),

                  const Spacer(),

                  // Power Button with Animated Glow
                  Center(
                    child: GestureDetector(
                      onTap: () {
                        context.read<VpnBloc>().add(const ToggleVpnEvent());
                      },
                      child: AnimatedBuilder(
                        animation: _pulseController,
                        builder: (context, child) {
                          return Container(
                            width: 195,
                            height: 195,
                            decoration: BoxDecoration(
                              shape: BoxShape.circle,
                              color: const Color(0xFF0F172A),
                              border: Border.all(
                                color: isConnected
                                    ? const Color(0xFF10B981)
                                    : isConnecting
                                        ? const Color(0xFFF59E0B)
                                        : const Color(0xFF0284C7).withOpacity(0.4),
                                width: 3,
                              ),
                              boxShadow: [
                                BoxShadow(
                                  color: isConnected
                                      ? const Color(0xFF10B981).withOpacity(0.25 + _pulseController.value * 0.2)
                                      : isConnecting
                                          ? const Color(0xFFF59E0B).withOpacity(0.3)
                                          : const Color(0xFF0284C7).withOpacity(0.1),
                                  blurRadius: 35,
                                  spreadRadius: isConnected ? 8 : 2,
                                ),
                              ],
                            ),
                            child: Center(
                              child: Column(
                                mainAxisAlignment: MainAxisAlignment.center,
                                children: [
                                  Icon(
                                    Icons.power_settings_new_rounded,
                                    size: 58,
                                    color: isConnected
                                        ? const Color(0xFF10B981)
                                        : isConnecting
                                            ? const Color(0xFFF59E0B)
                                            : Colors.white,
                                  ),
                                  const SizedBox(height: 8),
                                  Text(
                                    isConnected
                                        ? 'ОТКЛЮЧИТЬ'
                                        : isConnecting
                                            ? 'СОЕДИНЕНИЕ...'
                                            : 'ПОДКЛЮЧИТЬ',
                                    style: TextStyle(
                                      fontSize: 12,
                                      fontWeight: FontWeight.w800,
                                      letterSpacing: 0.8,
                                      color: isConnected
                                          ? const Color(0xFF10B981)
                                          : isConnecting
                                              ? const Color(0xFFF59E0B)
                                              : Colors.white,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          );
                        },
                      ),
                    ),
                  ),

                  const Spacer(),

                  // Smart Split-Tunneling Quick Tile
                  Container(
                    margin: const EdgeInsets.only(bottom: 12),
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                    decoration: BoxDecoration(
                      color: const Color(0xFF0F172A).withOpacity(0.7),
                      borderRadius: BorderRadius.circular(16),
                      border: Border.all(color: Colors.white.withOpacity(0.06)),
                    ),
                    child: Row(
                      children: [
                        const Icon(Icons.alt_route_rounded, color: Color(0xFF38BDF8), size: 20),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              const Text(
                                'Умный обход сервисов РФ',
                                style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: Colors.white),
                              ),
                              Text(
                                'Сбер, Т-Банк, Госуслуги напрямую',
                                style: TextStyle(fontSize: 11, color: Colors.grey.shade400),
                              ),
                            ],
                          ),
                        ),
                        Switch(
                          value: state.splitTunnelingEnabled,
                          activeColor: const Color(0xFF10B981),
                          onChanged: (val) {
                            context.read<VpnBloc>().add(ToggleSplitTunnelingEvent(val));
                          },
                        ),
                      ],
                    ),
                  ),

                  // Selected Node Card
                  Container(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: const Color(0xFF0F172A),
                      borderRadius: BorderRadius.circular(18),
                      border: Border.all(color: Colors.white.withOpacity(0.08)),
                    ),
                    child: Row(
                      children: [
                        const Text('🇳🇱', style: TextStyle(fontSize: 32)),
                        const SizedBox(width: 14),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                state.currentProfile.name,
                                style: const TextStyle(
                                  fontSize: 15,
                                  fontWeight: FontWeight.bold,
                                  color: Colors.white,
                                ),
                              ),
                              const SizedBox(height: 2),
                              Text(
                                'IP: ${state.currentProfile.serverAddress} • Порт ${state.currentProfile.serverPort} (1 Gbps)',
                                style: TextStyle(
                                  fontSize: 11,
                                  color: Colors.grey.shade400,
                                  fontFamily: 'monospace',
                                ),
                              ),
                            ],
                          ),
                        ),
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                          decoration: BoxDecoration(
                            color: const Color(0xFF10B981).withOpacity(0.1),
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: const Text(
                            '16 ms',
                            style: TextStyle(
                              fontSize: 11,
                              fontWeight: FontWeight.bold,
                              color: Color(0xFF10B981),
                              fontFamily: 'monospace',
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 12),
                ],
              ),
            ),
          ),
        );
      },
    );
  }
}
