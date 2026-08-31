/// Stores the phone's private key and cashier ticket. Never log the private key.
abstract class EnrollmentVault {
  Future<String?> readPrivateKey();
  Future<String?> readTicketJson();
  Future<void> save({required String privateKey, String? ticketJson});
}

class MemoryEnrollmentVault implements EnrollmentVault {
  String? privateKey;
  String? ticketJson;

  @override
  Future<String?> readPrivateKey() async => privateKey;

  @override
  Future<String?> readTicketJson() async => ticketJson;

  @override
  Future<void> save({required String privateKey, String? ticketJson}) async {
    this.privateKey = privateKey;
    if (ticketJson != null) {
      this.ticketJson = ticketJson;
    }
  }
}
