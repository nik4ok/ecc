import '../entities/vpn_profile.dart';
import '../entities/amnezia_wg_params.dart';

class DefaultNodes {
  static const VpnProfile netherlandsAmneziaWg = VpnProfile(
    id: "srv-nl-awg-02",
    name: "Нидерланды (Амстердам)",
    serverAddress: "89.19.217.190",
    serverPort: 39783,
    protocolType: VpnProtocolType.amneziaWg,
    publicKey: "s1bBvq1mlFNu+VeAJSP3lD4PGz/SJhAM9Jw3HPNuekw=",
    clientAddress: "10.8.1.2/32",
    clientPrivateKey: "MOwm/Mdk4iqT+sxvcdNznBcdA+PoNRG2BulKRCNhJ1Q=",
    presharedKey: "zFJ/UgUJxzITCM1klFzBjP7JvkSbDiSGHYHvWF5tSA0=",
    amneziaParams: AmneziaWgParams(
      jc: 5,
      jmin: 10,
      jmax: 50,
      s1: 45,
      s2: 81,
      s3: 60,
      s4: 12,
      h1: 1,
      h2: 2,
      h3: 3,
      h4: 4,
      headerProtectionKey: "81A3uK4f+uME094NUUP6F+ryryeO5DrPcYB+zYWt6Xc=",
    ),
  );
}
