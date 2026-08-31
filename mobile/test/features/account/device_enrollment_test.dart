import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:vpn_app/features/account/data/device_enrollment.dart';
import 'package:vpn_app/features/account/data/enrollment_vault.dart';
import 'package:vpn_app/features/account/data/registration_api.dart';
import 'package:vpn_app/features/vpn_engine/domain/constants/default_nodes.dart';
import 'package:vpn_app/features/vpn_engine/domain/generators/wg_keys.dart';

void main() {
  const pair = WgKeyPair(
    privateKey: 'yAnz5TF+lXXJte14tji3bwM6vEZTCqNSkA3W5AJFXPo=',
    publicKey: 'HIgo9xNzJMWLKASShiTqIyb2Hx7ePhVhwLE3KbPXeo0=',
  );

  Map<String, dynamic> ticketJson({String address = '10.8.1.3/32'}) => {
        'user_id': 'u-3',
        'display_name': 'Нидерланды (Амстердам)',
        'email': 'nova-guest@device.local',
        'client_address': address,
        'client_public_key': pair.publicKey,
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
      };

  test('new phone registers public key only and keeps the private key local', () async {
    String? postedBody;
    final client = MockClient((request) async {
      postedBody = request.body;
      return http.Response.bytes(
        utf8.encode(jsonEncode({'success': true, 'data': ticketJson(), 'error': null})),
        201,
        headers: {'content-type': 'application/json; charset=utf-8'},
      );
    });
    final vault = MemoryEnrollmentVault();
    final enrollment = DeviceEnrollment(
      api: RegistrationApi(baseUrl: 'http://127.0.0.1:8090', client: client),
      vault: vault,
      generateKeys: () async => pair,
    );

    final profile = await enrollment.ensureProfile();

    expect(profile.clientAddress, '10.8.1.3/32');
    expect(profile.clientPrivateKey, pair.privateKey);
    expect(postedBody, isNotNull);
    expect(postedBody, contains(pair.publicKey));
    expect(postedBody, isNot(contains(pair.privateKey)));
    expect(vault.privateKey, pair.privateKey);
    expect(vault.ticketJson, isNotNull);
  });

  test('second launch uses the saved ticket and does not call the cashier', () async {
    var calls = 0;
    final client = MockClient((request) async {
      calls += 1;
      return http.Response('{"success":false,"error":"should not be called"}', 500);
    });
    final vault = MemoryEnrollmentVault()
      ..privateKey = pair.privateKey
      ..ticketJson = jsonEncode(ticketJson(address: '10.8.1.4/32'));
    final enrollment = DeviceEnrollment(
      api: RegistrationApi(baseUrl: 'http://127.0.0.1:8090', client: client),
      vault: vault,
      generateKeys: () async => throw StateError('keys already exist'),
    );

    final profile = await enrollment.ensureProfile();

    expect(calls, 0);
    expect(profile.clientAddress, '10.8.1.4/32');
    expect(profile.clientPrivateKey, pair.privateKey);
  });

  test('cashier unreachable falls back to the test phone profile', () async {
    final client = MockClient((request) async {
      throw Exception('network down');
    });
    final enrollment = DeviceEnrollment(
      api: RegistrationApi(baseUrl: 'http://127.0.0.1:8090', client: client),
      vault: MemoryEnrollmentVault(),
      generateKeys: () async => pair,
    );

    final profile = await enrollment.ensureProfile();

    expect(profile, DefaultNodes.netherlandsAmneziaWg);
  });
}
