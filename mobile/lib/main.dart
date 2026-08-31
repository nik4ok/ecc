import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'features/account/data/cashier_config.dart';
import 'features/account/data/device_enrollment.dart';
import 'features/account/data/registration_api.dart';
import 'features/account/data/secure_enrollment_vault.dart';
import 'features/vpn_engine/domain/entities/vpn_profile.dart';
import 'features/vpn_engine/data/datasources/native_vpn_data_source.dart';
import 'features/vpn_engine/data/datasources/web_mock_vpn_data_source.dart';
import 'features/vpn_engine/domain/generators/wg_keys.dart';
import 'features/vpn_engine/presentation/bloc/vpn_bloc.dart';
import 'features/vpn_engine/presentation/bloc/vpn_event.dart';
import 'features/vpn_engine/presentation/bloc/vpn_state.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  final NativeVpnDataSource vpnDataSource =
      kIsWeb ? WebMockVpnDataSource() : NativeVpnDataSourceImpl();
  runApp(NovaApp(vpnDataSource: vpnDataSource));
}

class NovaApp extends StatelessWidget {
  final NativeVpnDataSource vpnDataSource;

  const NovaApp({super.key, required this.vpnDataSource});

  @override
  Widget build(BuildContext context) {
    return BlocProvider(
      create: (_) => VpnBloc(
        dataSource: vpnDataSource,
        enrollment: DeviceEnrollment(
          api: RegistrationApi(baseUrl: CashierConfig.baseUrl),
          vault: SecureEnrollmentVault(),
          generateKeys: WgKeys.generateKeyPair,
        ),
      )..add(const InitializeVpnEvent()),
      child: MaterialApp(
        title: 'Nova',
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
      duration: const Duration(milliseconds: 1800),
    );
  }

  @override
  void dispose() {
    _pulseController.dispose();
    super.dispose();
  }

  void _syncAnimationWithState(VpnState state) {
    if (state.isConnected || state.isConnecting) {
      if (!_pulseController.isAnimating) {
        _pulseController.repeat(reverse: true);
      }
    } else {
      if (_pulseController.isAnimating) {
        _pulseController.stop();
        _pulseController.reset();
      }
    }
  }

  String _formatBytes(int bytes) {
    if (bytes <= 0) return '0 B';
    if (bytes < 1024) return '$bytes B';
    if (bytes < 1024 * 1024) return '${(bytes / 1024).toStringAsFixed(1)} KB';
    if (bytes < 1024 * 1024 * 1024) return '${(bytes / (1024 * 1024)).toStringAsFixed(1)} MB';
    return '${(bytes / (1024 * 1024 * 1024)).toStringAsFixed(2)} GB';
  }

  @override
  Widget build(BuildContext context) {
    return BlocConsumer<VpnBloc, VpnState>(
      listener: (context, state) {
        _syncAnimationWithState(state);
      },
      builder: (context, state) {
        final isConnected = state.isConnected;
        final isConnecting = state.isConnecting;
        final isError = state.status == VpnConnectionStatus.error;

        return Scaffold(
          body: SafeArea(
            child: Center(
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 520),
                child: SingleChildScrollView(
                  padding: const EdgeInsets.symmetric(horizontal: 24.0, vertical: 16.0),
                  child: ConstrainedBox(
                    constraints: BoxConstraints(
                      minHeight: (MediaQuery.of(context).size.height -
                              MediaQuery.of(context).padding.top -
                              MediaQuery.of(context).padding.bottom -
                              32)
                          .clamp(560.0, double.infinity),
                    ),
                    child: IntrinsicHeight(
                      child: Column(
                        children: [
                          // Top App Bar
                          Row(
                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                            children: [
                              Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  const Text(
                                    'NOVA',
                                    style: TextStyle(
                                      fontSize: 22,
                                      fontWeight: FontWeight.w900,
                                      letterSpacing: 1.5,
                                      color: Colors.white,
                                    ),
                                  ),
                                  const SizedBox(height: 6),
                                  Row(
                                    children: const [
                                      _ValueBadge('Анти-Блок', textColor: Color(0xFF10B981), bgColor: Color(0xFF10B981)),
                                      SizedBox(width: 5),
                                      _ValueBadge('1 Gbps', textColor: Color(0xFF38BDF8), bgColor: Color(0xFF38BDF8)),
                                      SizedBox(width: 5),
                                      _ValueBadge('4K Видео', textColor: Color(0xFFA78BFA), bgColor: Color(0xFFA78BFA)),
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
                                          : isError
                                              ? const Color(0xFFEF4444).withOpacity(0.15)
                                              : Colors.grey.withOpacity(0.1),
                                  borderRadius: BorderRadius.circular(20),
                                  border: Border.all(
                                    color: isConnected
                                        ? const Color(0xFF10B981)
                                        : isConnecting
                                            ? const Color(0xFFF59E0B)
                                            : isError
                                                ? const Color(0xFFEF4444)
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
                                              : isError
                                                  ? const Color(0xFFEF4444)
                                                  : Colors.grey.shade600,
                                    ),
                                    const SizedBox(width: 6),
                                    Text(
                                      isConnected
                                          ? 'Защита активна'
                                          : isConnecting
                                              ? 'Подключаемся...'
                                              : isError
                                                  ? 'Сбой'
                                                  : 'Не защищено',
                                      style: TextStyle(
                                        fontSize: 10,
                                        fontWeight: FontWeight.bold,
                                        color: isConnected
                                            ? const Color(0xFF10B981)
                                            : isConnecting
                                                ? const Color(0xFFF59E0B)
                                                : isError
                                                    ? const Color(0xFFEF4444)
                                                    : Colors.grey.shade400,
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                            ],
                          ),

                          if (state.obtainingPass) ...[
                            const SizedBox(height: 16),
                            const Text(
                              'Получаем пропуск у кассы…',
                              style: TextStyle(fontSize: 13, color: Color(0xFF38BDF8)),
                            ),
                          ],

                          if (state.errorMessage != null) ...[
                            const SizedBox(height: 16),
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                              decoration: BoxDecoration(
                                color: const Color(0xFFEF4444).withOpacity(0.12),
                                borderRadius: BorderRadius.circular(10),
                                border: Border.all(color: const Color(0xFFEF4444).withOpacity(0.3)),
                              ),
                              child: Row(
                                children: [
                                  const Icon(Icons.info_outline, size: 16, color: Color(0xFFEF4444)),
                                  const SizedBox(width: 8),
                                  Expanded(
                                    child: Text(
                                      state.errorMessage!,
                                      style: const TextStyle(fontSize: 12, color: Color(0xFFEF4444)),
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ],

                          const Spacer(),

                          // Central Glowing Power Button
                          Center(
                            child: GestureDetector(
                              onTap: () {
                                context.read<VpnBloc>().add(const ToggleVpnEvent());
                              },
                              child: AnimatedBuilder(
                                animation: _pulseController,
                                builder: (context, child) {
                                  final glowScale = isConnected || isConnecting ? _pulseController.value : 0.0;
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
                                              ? const Color(0xFF10B981).withOpacity(0.25 + glowScale * 0.25)
                                              : isConnecting
                                                  ? const Color(0xFFF59E0B).withOpacity(0.3)
                                                  : const Color(0xFF0284C7).withOpacity(0.08),
                                          blurRadius: 35,
                                          spreadRadius: isConnected ? (6 + glowScale * 6) : 2,
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
                                                ? 'Выключить'
                                                : isConnecting
                                                    ? 'Подключение...'
                                                    : 'Включить',
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

                          if (isConnected) ...[
                            const SizedBox(height: 16),
                            Row(
                              mainAxisAlignment: MainAxisAlignment.center,
                              children: [
                                const Icon(Icons.arrow_downward_rounded, size: 14, color: Color(0xFF10B981)),
                                const SizedBox(width: 4),
                                Text(
                                  '↓ Получено: ${_formatBytes(state.rxBytes)}',
                                  style: const TextStyle(fontSize: 12, color: Colors.white70),
                                ),
                                const SizedBox(width: 16),
                                const Icon(Icons.arrow_upward_rounded, size: 14, color: Color(0xFF38BDF8)),
                                const SizedBox(width: 4),
                                Text(
                                  '↑ Отправлено: ${_formatBytes(state.txBytes)}',
                                  style: const TextStyle(fontSize: 12, color: Colors.white70),
                                ),
                              ],
                            ),
                          ],

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
                                        'Российские сервисы работают',
                                        style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: Colors.white),
                                      ),
                                      Text(
                                        'Банки и Госуслуги — без сбоев',
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
                                        [
                                          if (state.currentProfile.clientAddress != null)
                                            state.currentProfile.clientAddress!,
                                          'Амстердам',
                                          'Европа',
                                        ].join(' • '),
                                        style: TextStyle(
                                          fontSize: 11,
                                          color: Colors.grey.shade400,
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
                          const SizedBox(height: 8),
                        ],
                      ),
                    ),
                  ),
                ),
              ),
            ),
          ),
        );
      },
    );
  }
}

class _ValueBadge extends StatelessWidget {
  final String label;
  final Color textColor;
  final Color bgColor;

  const _ValueBadge(this.label, {required this.textColor, required this.bgColor});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
      decoration: BoxDecoration(
        color: bgColor.withOpacity(0.15),
        borderRadius: BorderRadius.circular(5),
      ),
      child: Text(
        label,
        style: TextStyle(
          fontSize: 10,
          fontWeight: FontWeight.bold,
          color: textColor,
        ),
      ),
    );
  }
}
