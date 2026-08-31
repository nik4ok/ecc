import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:vpn_app/features/account/data/registration_api.dart';

void main() {
  test('register parses cashier envelope into a ticket', () async {
    final client = MockClient((request) async {
      expect(request.url.path, '/api/v1/register');
      expect(request.method, 'POST');
      return http.Response(
        '''
        {
          "success": true,
          "data": {
            "user_id": "u-3",
            "display_name": "API guest",
            "email": "api-guest@example.com",
            "client_address": "10.8.1.3/32",
            "client_public_key": "qqqq",
            "endpoint_host": "89.19.217.190",
            "endpoint_port": 39783,
            "server_public_key": "s1bBvq1mlFNu+VeAJSP3lD4PGz/SJhAM9Jw3HPNuekw=",
            "preshared_key": "zFJ/UgUJxzITCM1klFzBjP7JvkSbDiSGHYHvWF5tSA0=",
            "amnezia": {"jc": 5, "jmin": 10, "jmax": 50, "s1": 45, "s2": 81, "s3": 60, "s4": 12, "h1": 1, "h2": 2, "h3": 3, "h4": 4, "random_trailers": true, "disable_cookies": true}
          },
          "error": null
        }
        ''',
        201,
      );
    });

    final api = RegistrationApi(baseUrl: 'http://127.0.0.1:8090', client: client);
    final ticket = await api.register(
      email: 'api-guest@example.com',
      displayName: 'API guest',
      publicKey: 'qqqq',
    );
    expect(ticket.clientAddress, '10.8.1.3/32');
    expect(ticket.endpointPort, 39783);
  });

  test('register throws cashier error text', () async {
    final client = MockClient((request) async {
      return http.Response(
        '{"success": false, "data": null, "error": "this device badge is already in the book"}',
        409,
      );
    });
    final api = RegistrationApi(baseUrl: 'http://127.0.0.1:8090', client: client);
    expect(
      () => api.register(email: 'a@b.c', displayName: 'A', publicKey: 'x'),
      throwsA(isA<RegistrationException>()),
    );
  });
}
