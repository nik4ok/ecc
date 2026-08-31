import 'dart:convert';

import 'package:http/http.dart' as http;

import '../domain/access_ticket.dart';

class RegistrationApi {
  final Uri baseUri;
  final http.Client _client;

  RegistrationApi({required String baseUrl, http.Client? client})
      : baseUri = Uri.parse(baseUrl),
        _client = client ?? http.Client();

  Future<AccessTicket> register({
    required String email,
    required String displayName,
    required String publicKey,
  }) async {
    final response = await _client.post(
      baseUri.resolve('/api/v1/register'),
      headers: const {'Content-Type': 'application/json'},
      body: jsonEncode({
        'email': email,
        'display_name': displayName,
        'public_key': publicKey,
      }),
    );
    final decoded = jsonDecode(response.body) as Map<String, dynamic>;
    if (decoded['success'] != true) {
      throw RegistrationException(decoded['error'] as String? ?? 'registration failed');
    }
    return AccessTicket.fromJson(decoded['data'] as Map<String, dynamic>);
  }
}

class RegistrationException implements Exception {
  final String message;
  const RegistrationException(this.message);

  @override
  String toString() => message;
}
