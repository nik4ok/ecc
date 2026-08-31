import 'package:flutter_test/flutter_test.dart';
import 'package:vpn_app/features/account/domain/access_ticket.dart';
import 'package:vpn_app/features/account/domain/ticket_to_profile.dart';
import 'package:vpn_app/features/vpn_engine/domain/entities/vpn_profile.dart';

void main() {
  final ticket = AccessTicket.fromJson({
    'user_id': 'u-3',
    'display_name': 'Третий гость',
    'email': 'third@example.com',
    'client_address': '10.8.1.3/32',
    'client_public_key': 'lzMFxwiPIiewKz4KFxKQG6+f2BkUIZvu8woO3/+bT3w=',
    'endpoint_host': '89.19.217.190',
    'endpoint_port': 39783,
    'server_public_key': 's1bBvq1mlFNu+VeAJSP3lD4PGz/SJhAM9Jw3HPNuekw=',
    'preshared_key': 'zFJ/UgUJxzITCM1klFzBjP7JvkSbDiSGHYHvWF5tSA0=',
    'amnezia': {
      'jc': 5,
      'jmin': 10,
      'jmax': 50,
      's1': 45,
      's2': 81,
      's3': 60,
      's4': 12,
      'h1': 1,
      'h2': 2,
      'h3': 3,
      'h4': 4,
      'header_protection_key': '81A3uK4f+uME094NUUP6F+ryryeO5DrPcYB+zYWt6Xc=',
      'content_padding_addition': '10-100',
      'random_trailers': true,
      'disable_cookies': true,
    },
  });

  test('ticket becomes an AmneziaWG profile with the phone private key', () {
    const privateKey = 'MOwm/Mdk4iqT+sxvcdNznBcdA+PoNRG2BulKRCNhJ1Q=';
    final profile = profileFromTicket(ticket: ticket, clientPrivateKey: privateKey);
    expect(profile.protocolType, VpnProtocolType.amneziaWg);
    expect(profile.serverAddress, '89.19.217.190');
    expect(profile.serverPort, 39783);
    expect(profile.clientAddress, '10.8.1.3/32');
    expect(profile.clientPrivateKey, privateKey);
    expect(profile.amneziaParams!.randomTrailers, isTrue);
    expect(profile.amneziaParams!.headerProtectionKey, startsWith('81A3uK4f'));
  });
}
