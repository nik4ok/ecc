import 'package:flutter_test/flutter_test.dart';
import 'package:vpn_app/features/account/domain/access_ticket.dart';

void main() {
  test('AccessTicket round-trips through JSON', () {
    final json = {
      'user_id': 'u-3',
      'display_name': 'Гость',
      'email': 'g@n.local',
      'client_address': '10.8.1.3/32',
      'client_public_key': 'HIgo9xNzJMWLKASShiTqIyb2Hx7ePhVhwLE3KbPXeo0=',
      'endpoint_host': '89.19.217.190',
      'endpoint_port': 39783,
      'server_public_key': 's1bBvq1mlFNu+VeAJSP3lD4PGz/SJhAM9Jw3HPNuekw=',
      'preshared_key': 'zFJ/UgUJxzITCM1klFzBjP7JvkSbDiSGHYHvWF5tSA0=',
      'amnezia': {'jc': 5, 'h1': 1},
    };
    final ticket = AccessTicket.fromJson(json);
    expect(AccessTicket.fromJson(ticket.toJson()).clientAddress, '10.8.1.3/32');
    expect(AccessTicket.fromJson(ticket.toJson()).endpointPort, 39783);
  });
}
