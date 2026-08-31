import '../../vpn_engine/domain/entities/amnezia_wg_params.dart';
import '../../vpn_engine/domain/entities/vpn_profile.dart';
import 'access_ticket.dart';

/// Combine a cashier ticket with the private key that never left the phone.
VpnProfile profileFromTicket({
  required AccessTicket ticket,
  required String clientPrivateKey,
}) {
  final amnezia = ticket.amnezia;
  return VpnProfile(
    id: ticket.userId,
    name: ticket.displayName,
    serverAddress: ticket.endpointHost,
    serverPort: ticket.endpointPort,
    protocolType: VpnProtocolType.amneziaWg,
    publicKey: ticket.serverPublicKey,
    clientPrivateKey: clientPrivateKey,
    clientAddress: ticket.clientAddress,
    presharedKey: ticket.presharedKey,
    amneziaParams: AmneziaWgParams(
      jc: amnezia['jc'] as int,
      jmin: amnezia['jmin'] as int,
      jmax: amnezia['jmax'] as int,
      s1: amnezia['s1'] as int,
      s2: amnezia['s2'] as int,
      s3: amnezia['s3'] as int?,
      s4: amnezia['s4'] as int?,
      h1: amnezia['h1'] as int,
      h2: amnezia['h2'] as int,
      h3: amnezia['h3'] as int,
      h4: amnezia['h4'] as int,
      headerProtectionKey: amnezia['header_protection_key'] as String?,
      contentPaddingAddition: amnezia['content_padding_addition'] as String?,
      randomTrailers: amnezia['random_trailers'] == true,
      disableCookies: amnezia['disable_cookies'] == true,
    ),
  );
}
